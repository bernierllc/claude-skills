#!/usr/bin/env python3
"""Warn when a repo is missing review-gate wiring.

Prints WARN / OK / FAIL lines on stdout. It exits 1, with or without --strict, when the repo-tracked
.claude/skills/review-gate is older than this release, has an unreadable version, or its hooks.json and
SKILL.md disagree (3.2.19). With --strict (3.2.14) it also exits 1 when the workflow or a vendored script is
missing or differs from this skill's copy: the local checks, which need no token. With
--expect-default-branch-gate (3.8.0) it also exits 1 when an enforcing main/staging ruleset requires `Review Gate`
and both .github/workflows/review-gate.yml and .yaml probe as 404 on the readable default branch; a gate file
that exists never fails, and neither its content nor its trigger is read. Otherwise it exits 0: the label and ruleset checks, and that producer check without
the option or with incomplete evidence, stay warnings, since CI's GITHUB_TOKEN usually cannot read rulesets.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

REVIEW_GATE_CONTEXT = "Review Gate"
# Branches the install instructions say must carry Review Gate + conversation rules.
MERGE_BRANCHES = ("main", "staging")


MAIN_REVIEW_LABEL = "review:high"  # must stay in check-review-gate.py MAIN_REVIEW_LABELS (pinned by a test)


SKILL_SCRIPTS = Path(__file__).resolve().parent


def _load_installer():
    """install-workflow.py owns the list of vendored scripts; load it rather than keep a second list."""
    spec = importlib.util.spec_from_file_location("install_workflow", SKILL_SCRIPTS / "install-workflow.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gh(*args: str) -> subprocess.CompletedProcess:
    """Run gh. An undecodable byte becomes U+FFFD, so bad output reaches the unverified paths, not a traceback."""
    return subprocess.run(["gh", *args], capture_output=True, text=True, errors="replace")


def gh_json(args: list[str]) -> object | None:
    proc = gh(*args)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except (ValueError, RecursionError):  # bad JSON, a huge int, deep nesting
        return None


def _ref_pattern(pat: str) -> str | re.Pattern:
    """A GitHub ruleset ref pattern compiled to a regex, or the ``~ALL`` / ``~DEFAULT_BRANCH`` token.

    ``*`` and ``?`` do not cross ``/``. Recursive traversal requires ``**/``
    (GitHub/Ruby ``FNM_PATHNAME``); a bare ``**`` is pathname-local like ``*``.
    See GitHub ruleset fnmatch docs (not Python ``fnmatch``, which treats ``/``
    as an ordinary character). Raises re.error or ValueError for a pattern it cannot read.
    """
    if pat in ("~ALL", "~DEFAULT_BRANCH"):
        return pat
    if pat.startswith("~"):
        raise ValueError(f"unknown token {pat!r}")
    i = 0
    out: list[str] = []
    while i < len(pat):
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pat.startswith("**", i):
            # Bare ``**`` does not cross ``/`` (``File.fnmatch("refs/**",
            # "refs/heads/main", FNM_PATHNAME)`` is false).
            out.append("[^/]*")
            i += 2
            continue
        ch = pat[i]
        if ch == "*":
            out.append("[^/]*")
            i += 1
            continue
        if ch == "?":
            out.append("[^/]")
            i += 1
            continue
        if ch == "[":
            j = i + 1
            if j < len(pat) and pat[j] in ("!", "^"):
                j += 1
            if j < len(pat) and pat[j] == "]":
                j += 1
            while j < len(pat) and pat[j] != "]":
                j += 1
            if j >= len(pat):
                out.append(re.escape(ch))
                i += 1
            else:
                klass = pat[i : j + 1]
                # fnmatch ``[!abc]`` → regex ``[^abc]`` (GitHub/Ruby FNMATCH).
                if len(klass) > 2 and klass[1] == "!":
                    klass = "[^" + klass[2:]
                out.append(klass)
                i = j + 1
            continue
        out.append(re.escape(ch))
        i += 1
    return re.compile("".join(out))


RULESET_TARGETS = ("branch", "tag", "push", "repository")


class Ruleset(NamedTuple):
    """The ruleset fields the doctor uses, each already type-checked by parse_ruleset."""
    target: str
    enforcement: str = ""
    include: tuple = ()  # compiled ref patterns or ~ALL / ~DEFAULT_BRANCH
    exclude: tuple = ()
    checks: tuple = ()  # (context, integration_id or None) of every required status check
    rule_types: frozenset = frozenset()
    resolution: bool = False  # a pull_request rule requires review-thread resolution


def _strs(v: object) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def parse_ruleset(d: object) -> tuple[Ruleset | None, str]:
    """Read every ruleset field the doctor uses, with an explicit type check each: (parsed, "") or (None, the
    first problem). A missing key is a problem like a wrong type. Nothing downstream reads the raw API object."""
    if not isinstance(d, dict):
        return None, f"a {type(d).__name__}, not a ruleset object"
    if d.get("target") not in RULESET_TARGETS:
        return None, f"target {d.get('target')!r} is not one of {', '.join(RULESET_TARGETS)}"
    if d["target"] != "branch":
        return Ruleset(d["target"]), ""  # rules for tags, pushes or repositories never gate a branch merge
    if not isinstance(d.get("enforcement"), str):
        return None, "enforcement is missing or not a string"
    ref = d["conditions"].get("ref_name") if isinstance(d.get("conditions"), dict) else None
    if not (isinstance(ref, dict) and _strs(ref.get("include")) and _strs(ref.get("exclude"))):
        return None, "conditions.ref_name is not an object with include and exclude lists of strings"
    try:
        include, exclude = (tuple(_ref_pattern(p) for p in ref[k]) for k in ("include", "exclude"))
    except (re.error, ValueError) as e:
        return None, f"conditions.ref_name holds a pattern this doctor cannot read ({e})"
    rules = d.get("rules")
    if not (isinstance(rules, list) and all(isinstance(r, dict) and isinstance(r.get("type"), str) for r in rules)):
        return None, "rules is not a list of objects with a string type"
    checks, resolution = [], False
    for r in rules:
        params = r.get("parameters")
        if r["type"] == "required_status_checks":
            cs = params.get("required_status_checks") if isinstance(params, dict) else None
            if not (isinstance(cs, list) and all(
                    isinstance(c, dict) and isinstance(c.get("context"), str)
                    and ("integration_id" not in c or type(c["integration_id"]) is int) for c in cs)):
                return None, ("rule 'required_status_checks' parameters are not an object with a list of checks, "
                              "each a string context and an integer or absent integration_id")
            checks += [(c["context"], c.get("integration_id")) for c in cs]
        elif r["type"] == "pull_request":
            if not (isinstance(params, dict) and type(params.get("required_review_thread_resolution")) is bool):
                return None, "rule 'pull_request' parameters have no boolean required_review_thread_resolution"
            resolution = resolution or params["required_review_thread_resolution"]
    return Ruleset("branch", d["enforcement"], include, exclude, tuple(checks),
                   frozenset(r["type"] for r in rules), resolution), ""


def ruleset_covered_branches(rs: Ruleset, *, default_branch: str = "main") -> list[str]:
    """Return the ``main``/``staging`` branches this ruleset's ref conditions cover."""
    def hit(pat: str | re.Pattern, b: str) -> bool:
        if isinstance(pat, str):
            return pat == "~ALL" or b == default_branch
        return bool(pat.fullmatch(f"refs/heads/{b}") or pat.fullmatch(b))
    return [b for b in MERGE_BRANCHES
            if not any(hit(p, b) for p in rs.exclude) and any(hit(p, b) for p in rs.include)]


def local_checks(root: Path) -> int:
    """Workflow and vendored-script checks; returns how many WARNs they printed."""
    problems = 0
    wf = root / ".github" / "workflows" / "review-gate.yml"
    template = Path(__file__).resolve().parents[1] / "templates" / "review-gate.yml"
    if wf.is_file() and template.is_file() and wf.read_bytes() != template.read_bytes():
        # 3.2.6: an older copy reuses one check run per head, so an edit-triggered suite can leave
        # the required check "expected" (BLOCKED with every check green).
        problems += 1
        print(
            f"WARN {wf.relative_to(root)} differs from this skill's template; re-run "
            "install-workflow.py --force and merge it to the default branch"
        )
    elif wf.is_file():
        print(f"OK workflow {wf.relative_to(root)}")
    else:
        problems += 1
        print(
            "WARN missing .github/workflows/review-gate.yml — copy from "
            "skill review-gate/templates/review-gate.yml"
        )
    workflows = root / ".github" / "workflows"
    refresh = workflows / "review-gate-security-refresh.yml"
    refresh_template = template.with_name(refresh.name)
    if (workflows / "review-gate-security-scan.yml").is_file():
        # without it a default-branch change to the scan config or policy leaves every open PR's gate red (stale)
        if not refresh.is_file() or refresh.read_bytes() != refresh_template.read_bytes():
            problems += 1
            print(f"WARN {refresh.relative_to(root)} is missing or differs from this skill's template; re-run "
                  "install-workflow.py --force and merge it to the default branch")
        else:
            print(f"OK workflow {refresh.relative_to(root)}")
    installer = _load_installer()
    for name in installer.VENDORED_SCRIPTS:
        script = root / "scripts" / name
        if not script.is_file():
            problems += 1
            print(f"WARN missing scripts/{name}; re-run install-workflow.py and merge it to the default branch")
        elif script.read_bytes() != (SKILL_SCRIPTS / name).read_bytes():
            # the installer keeps a newer or custom aec detector, so that WARN is expected and --strict passes it
            problems += not (name == installer.VENDORED and installer.keeps_detector(script))
            hint = (" (if yours is a newer agents-environment-config copy, the installer keeps it)"
                    if name == installer.VENDORED else "")
            print(f"WARN scripts/{name} differs from the skill; re-run install-workflow.py --force "
                  f"and merge it to the default branch{hint}")
        else:
            print(f"OK vendored script {script.relative_to(root)}")
    return problems


def vendored_skill_parity(root: Path) -> bool:
    """False (with a FAIL line and the one fix) when the repo-tracked copy of this skill is older than this
    release, or its hooks.json and SKILL.md versions disagree. `aec run-script skill:review-gate` runs the repo
    copy first, so a stale one keeps an old merge guard running however new the installed skill is. Run from the
    vendored copy itself (the --doctor-job workflow does), it skips only the newer-release comparison."""
    installer = _load_installer()
    dest = root / installer.VENDORED_SKILL
    skill_root = SKILL_SCRIPTS.parent
    if not dest.is_dir():
        return True  # nothing vendored
    is_self = dest.resolve() == skill_root
    # this copy's own installer cannot replace itself, so the self case names the re-vendor the doctor job names
    fix = ("aec install skill review-gate, then commit .claude/skills/review-gate" if is_self
           else f"python3 {SKILL_SCRIPTS / 'install-workflow.py'} --force")
    try:
        have, want = installer.skill_version(dest), installer.skill_version(skill_root)
    except ValueError as e:
        print(f"FAIL {e}; fix that version line or replace the copy by hand (the installer refuses it)")
        return False
    if have is None:
        print(f"FAIL {installer.VENDORED_SKILL}/SKILL.md has no readable version; replace the copy by hand")
        return False
    if not is_self and want is not None and have < want:  # the copy cannot see a release newer than itself
        print(f"FAIL {installer.VENDORED_SKILL} is {installer.dotted(have)}, this release is "
              f"{installer.dotted(want)}; replace the whole copy and commit it: {fix}")
        return False
    hooks = installer.hooks_version(dest)
    if hooks != installer.dotted(have):
        print(f"FAIL {installer.VENDORED_SKILL}/hooks.json is {hooks}, its SKILL.md is {installer.dotted(have)}; "
              f"replace the whole copy and commit it: {fix}")
        return False
    print(f"OK vendored skill {installer.VENDORED_SKILL} {installer.dotted(have)}")
    return True


RERUN_HINT = ("NOTE Review Gate does not re-run when a thread is resolved or a review lands; re-fire it with "
              "gh pr edit <n> --remove-label review:high && gh pr edit <n> --add-label review:high "
              "(a PR into main; other bases add the label, then remove it)")


EXPECT_GATE_FLAG = "--expect-default-branch-gate"
ACTIONS_INTEGRATION_ID = 15368  # GitHub Actions' app id: a check pinned to it is a workflow job
GATE_PATHS = (".github/workflows/review-gate.yml", ".github/workflows/review-gate.yaml")
PAGE = 100


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    strict = "--strict" in args
    root = Path.cwd()
    problems = local_checks(root)
    parity = vendored_skill_parity(root)
    remote_failures = remote_checks(expect_gate=EXPECT_GATE_FLAG in args)
    print(RERUN_HINT)
    if not parity:
        return 1  # a stale vendored skill fails with or without --strict
    if strict and problems:
        print(f"FAIL --strict: {problems} workflow/vendored-script problem(s) above")
        return 1
    if remote_failures:
        print(f"FAIL {remote_failures} required-check problem(s) above")
        return 1
    return 0


def gh_api(path: str) -> tuple[int | None, object | None, str]:
    """GET through ``gh api --include``: (HTTP status or None when no response arrived, parsed body, reason)."""
    proc = gh("api", "--include", path)
    m = re.match(r"HTTP/\S+ (\d{3})", proc.stdout)
    if not m:
        return None, None, (proc.stderr.strip() or "no HTTP response")[:200]
    status = int(m.group(1))
    head, _, body = proc.stdout.replace("\r\n", "\n").partition("\n\n")
    if status == 429 or (status == 403 and re.search(r"(?im)^x-ratelimit-remaining:\s*0\s*$", head)):
        reason = f"HTTP {status}, rate limited"
    else:
        reason = f"HTTP {status}"
    try:
        data = json.loads(body) if body.strip() else None
    except (ValueError, RecursionError):  # bad JSON, a huge int, deep nesting
        return status, None, reason + ", unparsable body"
    if status == 404 and isinstance(data, dict) and "No commit found" in str(data.get("message", "")):
        reason += ", missing ref"
    return status, data, reason


def gate_producer(full: str, default_branch: str) -> tuple[str, str]:
    """Probe each exact gate path on the default branch through the Contents API; nothing is listed or decoded.

    Returns (verdict, detail): "present" (a 200 file object at the requested path); "absent" (the branch is
    readable and every path is a JSON-object 404 that is not a missing ref); or "unknown" (any other status or
    shape). The file's content, trigger and branch filters are never read.
    """
    status, data, reason = gh_api(f"repos/{full}/branches/{quote(default_branch)}")
    if status == 200 and not isinstance(data, dict):
        status, reason = None, f"{reason}, a {type(data).__name__}, not a branch object"
    if status != 200:
        return "unknown", f"default branch {default_branch!r} is not readable ({reason or 'no response'})"
    problems = []
    for path in GATE_PATHS:
        status, data, reason = gh_api(f"repos/{full}/contents/{path}?ref={quote(default_branch, safe='')}")
        if status == 200 and isinstance(data, dict) and data.get("type") == "file" and data.get("path") == path:
            return "present", (f"the review-gate workflow {path} is present on {default_branch!r} (its trigger and "
                               "branch filters are not analyzed)")
        if status == 404 and reason == "HTTP 404" and isinstance(data, dict):  # GitHub's JSON 404, not a missing ref
            continue
        if status == 200:
            shape = (f"type {data.get('type')!r} at path {data.get('path')!r}" if isinstance(data, dict)
                     else f"a {type(data).__name__}")
            reason = f"{reason}, {shape}, not a file at {path}"
        elif status == 404 and reason == "HTTP 404":
            reason = f"{reason}, a {type(data).__name__}, not an error object"
        problems.append(f"{path} ({reason or 'no response'})")
    if problems:
        return "unknown", f"could not probe {'; '.join(problems)} on {default_branch!r}"
    return "absent", f"no .github/workflows/review-gate.yml (or .yaml) on {default_branch!r}"


def list_rulesets(full: str) -> tuple[list | None, str]:
    """Every ruleset summary as {"id": int, "name": str}, or (None, why not)."""
    rulesets: list = []
    page = 1
    while True:
        status, data, reason = gh_api(f"repos/{full}/rulesets?per_page={PAGE}&page={page}")
        if status != 200:
            return None, f"{reason}; needs Metadata read, which CI's GITHUB_TOKEN usually lacks"
        if not (isinstance(data, list) and all(
                isinstance(r, dict) and type(r.get("id")) is int and isinstance(r.get("name"), str) for r in data)):
            return None, f"{reason}, a {type(data).__name__}, not a list of objects with an integer id and a string name"
        rulesets += [{"id": r["id"], "name": r["name"]} for r in data]
        if len(data) < PAGE:
            return rulesets, ""
        page += 1


def remote_checks(*, expect_gate: bool = False) -> int:
    """Label, ruleset and Review Gate producer checks through gh. Returns the number of FAIL lines printed:
    only the producer check can fail, and only with --expect-default-branch-gate; everything else warns."""
    if shutil.which("gh") is None:  # the local checks above still ran; the rest needs the GitHub CLI
        print("WARN gh (GitHub CLI) not found; skip label and ruleset checks")
        return 0
    # gh doesn't expand {owner}/{repo} in all versions; resolve explicitly.
    repo = gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")
    if repo.returncode != 0:
        print("WARN could not resolve repo via gh; skip ruleset check")
        return 0
    full = repo.stdout.strip()
    labels = gh_json(["label", "list", "-R", full, "--search", MAIN_REVIEW_LABEL, "--json", "name"])
    if not (isinstance(labels, list) and all(isinstance(lb, dict) and isinstance(lb.get("name"), str)
                                             for lb in labels)):
        print(f"WARN label {MAIN_REVIEW_LABEL!r} unverified: the label list is unreadable or not a list of objects "
              f"with a string name (a {type(labels).__name__})")
    elif any(lb["name"] == MAIN_REVIEW_LABEL for lb in labels):
        print(f"OK label {MAIN_REVIEW_LABEL!r} exists")
    else:
        print(
            f"WARN label {MAIN_REVIEW_LABEL!r} missing: every PR into main fails the gate; "
            f"gh label create {MAIN_REVIEW_LABEL} -R {full}"
        )
    default_branch_proc = gh("repo", "view", full, "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name")
    default_known = default_branch_proc.returncode == 0 and bool(default_branch_proc.stdout.strip())
    default_branch = default_branch_proc.stdout.strip() if default_known else "main"
    rulesets, reason = list_rulesets(full)
    if rulesets is None:
        print(f"WARN could not list rulesets ({reason}); the ruleset and Review Gate producer checks are skipped")
        return 0

    branch_state = {
        b: {"resolution": False, "gate": False, "seen": False} for b in MERGE_BRANCHES
    }
    skipped_non_enforcing = 0
    skipped_wrong_branch = 0
    unverified = 0
    gate_branches: list[str] = []  # covered branches whose Review Gate requirement this doctor analyzes
    other_contexts: dict[str, None] = {}
    for entry in rulesets:
        name = entry["name"]
        status, detail, reason = gh_api(f"repos/{full}/rulesets/{entry['id']}")
        rs, problem = parse_ruleset(detail) if status == 200 else (None, f"not readable ({reason})")
        if rs is None:
            unverified += 1
            print(f"WARN ruleset {name!r} unverified: {problem}; its branch coverage, {REVIEW_GATE_CONTEXT!r} and "
                  "conversation-resolution requirements are not counted")
            continue
        if rs.target != "branch":
            skipped_wrong_branch += 1
            print(f"WARN ruleset {name!r} targets {rs.target}, not branches; ignored for Review Gate coverage")
            continue
        if rs.enforcement != "active":
            skipped_non_enforcing += 1
            print(
                f"WARN ruleset {name!r} enforcement={rs.enforcement!r} "
                "(disabled/evaluate does not block merges); ignored"
            )
            continue
        covered = ruleset_covered_branches(rs, default_branch=default_branch)
        if not covered:
            skipped_wrong_branch += 1
            print(
                f"WARN ruleset {name!r} does not target main/staging "
                "(conditions.ref_name); ignored for Review Gate coverage"
            )
            continue
        for context, integration in rs.checks:
            if context != REVIEW_GATE_CONTEXT:
                other_contexts.setdefault(context)
            elif integration not in (None, ACTIONS_INTEGRATION_ID):
                print(f"OK ruleset {name!r} pins {REVIEW_GATE_CONTEXT!r} to integration "
                      f"{integration} (not GitHub Actions); producer check skipped")
            else:
                gate_branches.extend(b for b in covered if b not in gate_branches)
        has_gate = any(context == REVIEW_GATE_CONTEXT for context, _ in rs.checks)
        for branch in covered:
            branch_state[branch]["seen"] = True
            if rs.resolution:
                branch_state[branch]["resolution"] = True
                print(
                    f"OK ruleset {name!r} requires conversation resolution "
                    f"on {branch}"
                )
            elif "pull_request" in rs.rule_types:
                print(
                    f"WARN ruleset {name!r} has pull_request rule on {branch} but "
                    f"required_review_thread_resolution is not true"
                )
            if has_gate:
                branch_state[branch]["gate"] = True
                print(
                    f"OK ruleset {name!r} requires status check "
                    f"{REVIEW_GATE_CONTEXT!r} on {branch}"
                )
            elif "required_status_checks" in rs.rule_types:
                print(
                    f"WARN ruleset {name!r} has required_status_checks on {branch} "
                    f"but missing context {REVIEW_GATE_CONTEXT!r}"
                )

    if not any(st["seen"] for st in branch_state.values()):
        bits: list[str] = []
        if skipped_non_enforcing:
            bits.append(f"{skipped_non_enforcing} disabled/evaluate")
        if skipped_wrong_branch:
            bits.append(f"{skipped_wrong_branch} not targeting main/staging")
        if unverified:
            bits.append(f"{unverified} unverified")
        suffix = f" (saw {', '.join(bits)})" if bits else ""
        print(f"WARN no actively enforcing main/staging rulesets found{suffix}")

    for branch in MERGE_BRANCHES:
        st = branch_state[branch]
        if not st["seen"]:
            print(
                f"WARN branch {branch!r} has no enforcing ruleset with Review Gate "
                "wiring"
            )
            continue
        if not st["resolution"]:
            print(
                f"WARN branch {branch!r} missing required_review_thread_resolution "
                "on an enforcing ruleset"
            )
        if not st["gate"]:
            print(
                f"WARN branch {branch!r} missing required status check "
                f"{REVIEW_GATE_CONTEXT!r}"
            )

    for context in other_contexts:
        print(f"WARN required check {context!r}: producer not verified (generic producer analysis is out of scope)")
    if other_contexts or gate_branches:
        print("NOTE required checks are read only from rulesets covering main/staging; other branches are out of "
              "scope")
    return gate_producer_check(full, default_branch, default_known, gate_branches, expect_gate)


def gate_producer_check(full: str, default_branch: str, default_known: bool, gate_branches: list[str],
                        expect_gate: bool) -> int:
    """Can the default branch publish the required Review Gate? 1 for a confirmed failure, else 0."""
    if not gate_branches:
        return 0
    required = f"{REVIEW_GATE_CONTEXT!r} (required on {'/'.join(gate_branches)})"
    if not default_known:
        print(f"WARN could not read the default branch name; producer of {required} not verified")
        return 0
    verdict, detail = gate_producer(full, default_branch)
    if verdict == "present":
        print(f"OK {required} has its producer: {detail}")
        return 0
    if verdict == "unknown":
        print(f"WARN producer of {required} not verified: {detail}")
        return 0
    fix = (f"{detail}; merge review-gate.yml to {default_branch} before requiring the check (GitHub loads a "
           "pull_request_target workflow from the default branch only, so a copy on staging or another branch "
           "does not count)")
    if expect_gate:
        print(f"FAIL {required} cannot report: {fix}")
        return 1
    print(f"WARN {required} may not report: {fix}. A PR-supplied pull_request workflow or an external app can "
          f"also publish it; pass {EXPECT_GATE_FLAG} to make this a failure when this repo uses the skill's "
          "review-gate.yml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
