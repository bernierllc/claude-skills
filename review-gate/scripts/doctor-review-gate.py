#!/usr/bin/env python3
"""Warn when a repo is missing review-gate wiring.

Prints WARN / OK / FAIL lines on stdout. It exits 1, with or without --strict, when the repo-tracked
.claude/skills/review-gate is older than this release, has an unreadable version, or its hooks.json and
SKILL.md disagree (3.2.19). With --strict (3.2.14) it also exits 1 when the workflow or a vendored script is
missing or differs from this skill's copy: the local checks, which need no token. With
--expect-default-branch-gate (3.8.0) it also exits 1 when an enforcing main/staging ruleset requires `Review Gate`
and the default branch, read completely, has no .github/workflows/review-gate.yml (or .yaml) with a
pull_request_target trigger. Otherwise it exits 0: the label and ruleset checks, and that producer check without
the option or with incomplete evidence, stay warnings, since CI's GITHUB_TOKEN usually cannot read rulesets.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
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


def gh_json(args: list[str]) -> object | None:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def ruleset_is_enforcing(detail: dict) -> bool:
    """True when the ruleset actively blocks merges (not disabled/evaluate)."""
    return detail.get("enforcement") == "active"


def _github_path_fnmatch(name: str, pat: str) -> bool:
    """Match ``name`` against ``pat`` with GitHub ruleset pathname semantics.

    ``*`` and ``?`` do not cross ``/``. Recursive traversal requires ``**/``
    (GitHub/Ruby ``FNM_PATHNAME``); a bare ``**`` is pathname-local like ``*``.
    See GitHub ruleset fnmatch docs (not Python ``fnmatch``, which treats ``/``
    as an ordinary character).
    """
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
    return re.fullmatch("".join(out), name) is not None


def _fnmatch_ref(
    pat: str, ref: str, branch: str, *, default_branch: str = "main"
) -> bool:
    """True when a GitHub ruleset fnmatch pattern matches ``ref`` / ``branch``."""
    if pat == "~ALL":
        return True
    if pat == "~DEFAULT_BRANCH":
        return branch == default_branch
    if _github_path_fnmatch(ref, pat) or _github_path_fnmatch(branch, pat):
        return True
    return False


def _branch_covered_by_ref_name(
    branch: str,
    include: list[str],
    exclude: list[str],
    *,
    default_branch: str = "main",
) -> bool:
    ref = f"refs/heads/{branch}"
    # Exclusions use the same fnmatch semantics as GitHub rulesets.
    for pat in exclude:
        if _fnmatch_ref(pat, ref, branch, default_branch=default_branch):
            return False
    if not include:
        return False
    return any(
        _fnmatch_ref(pat, ref, branch, default_branch=default_branch) for pat in include
    )


def ruleset_covered_branches(
    detail: dict, *, default_branch: str = "main"
) -> list[str]:
    """Return ``main``/``staging`` branches this ruleset's ref conditions cover."""
    conditions = detail.get("conditions") or {}
    ref_name = conditions.get("ref_name") or {}
    include = [str(x) for x in (ref_name.get("include") or [])]
    exclude = [str(x) for x in (ref_name.get("exclude") or [])]
    if not include:
        return []
    return [
        b
        for b in MERGE_BRANCHES
        if _branch_covered_by_ref_name(
            b, include, exclude, default_branch=default_branch
        )
    ]


def ruleset_targets_merge_branches(
    detail: dict, *, default_branch: str = "main"
) -> bool:
    """True when ruleset ``conditions.ref_name`` covers ``main`` and/or ``staging``."""
    return bool(ruleset_covered_branches(detail, default_branch=default_branch))


def ruleset_requires_review_gate(detail: dict) -> bool:
    """True when a ruleset detail requires the ``Review Gate`` status check."""
    for rule in detail.get("rules") or []:
        if rule.get("type") != "required_status_checks":
            continue
        params = rule.get("parameters") or {}
        for check in params.get("required_status_checks") or []:
            if not isinstance(check, dict):
                continue
            if check.get("context") == REVIEW_GATE_CONTEXT:
                return True
    return False


def ruleset_requires_conversation_resolution(detail: dict) -> bool:
    """True when a ruleset requires review-thread resolution on pull requests."""
    for rule in detail.get("rules") or []:
        if rule.get("type") != "pull_request":
            continue
        params = rule.get("parameters") or {}
        if params.get("required_review_thread_resolution") is True:
            return True
    return False


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
CONTENTS_CAP = 1000  # the Contents API lists at most this many directory entries
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
    proc = subprocess.run(["gh", "api", "--include", path], capture_output=True, text=True)
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
    except json.JSONDecodeError:
        return status, None, reason + ", unparsable body"
    if status == 404 and isinstance(data, dict) and "No commit found" in str(data.get("message", "")):
        reason += ", missing ref"
    return status, data, reason


def declares_pull_request_target(text: str) -> bool | None:
    """Does a workflow's top-level ``on:`` name ``pull_request_target``? None when ``on:`` has a form this
    parser does not read, so an unread form is never taken as proof of absence (or presence)."""
    # shortcut: a line parser, not YAML: scalar, one-line [list], block list and block mapping forms only.
    lines = text.lstrip("﻿").splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"""^(?:on|'on'|"on")\s*:(.*)$""", line)
        if not m:
            continue
        rest = re.sub(r"\s+#.*$", "", m.group(1)).strip()
        if re.fullmatch(r"[\w-]+", rest):
            return rest == "pull_request_target"
        if re.fullmatch(r"\[[^\[\]{}]*\]", rest):
            return "pull_request_target" in [x.strip().strip("'\"") for x in rest[1:-1].split(",")]
        if rest:
            return None  # flow mapping, multi-line flow list, anchor, ...
        events, indent = [], None
        for child in lines[i + 1:]:
            if not child.strip() or child.lstrip().startswith("#"):
                continue
            width = len(child) - len(child.lstrip())
            if width == 0 and not child.startswith("- "):
                break  # the next top-level key (a column-0 "- " item is a block list under on:)
            indent = width if indent is None else indent
            if width > indent:
                continue  # an event's own settings
            if width < indent:
                return None
            item = re.fullmatch(r"""(-\s+)?['"]?([\w-]+)['"]?\s*(:.*)?(\s+#.*)?""", child.strip())
            if not item or (item.group(1) and item.group(3)):
                return None
            events.append(item.group(2))
        return "pull_request_target" in events if events else None
    return False


def gate_producer(full: str, default_branch: str) -> tuple[str, str]:
    """Look for the skill's gate workflow on the default branch.

    Returns (verdict, detail): "present"; "absent" (the inventory is complete and readable, and no exact-path
    review-gate.yml/.yaml with a pull_request_target trigger exists); or "unknown" (the evidence is incomplete).
    """
    status, _, reason = gh_api(f"repos/{full}/branches/{quote(default_branch)}")
    if status != 200:
        return "unknown", f"default branch {default_branch!r} is not readable ({reason or 'no response'})"
    status, listing, reason = gh_api(f"repos/{full}/contents/.github/workflows?ref={quote(default_branch, safe='')}")
    if status == 404 and "missing ref" not in reason:
        listing = []  # the repo and branch are readable, so 404 means no .github/workflows directory
    elif status != 200:
        return "unknown", f"could not list .github/workflows on {default_branch!r} ({reason})"
    if not isinstance(listing, list):
        return "unknown", f"unexpected .github/workflows listing on {default_branch!r}"
    types = {e.get("path"): e.get("type") for e in listing if isinstance(e, dict)}
    paths = {path for path, kind in types.items() if kind == "file"}
    for path in GATE_PATHS:
        if path in types and types[path] != "file":  # a symlink or submodule there may still be the gate
            return "unknown", f"{path} on {default_branch!r} is a {types[path]}, not a file; not read"
    found_without_trigger = []
    for path in GATE_PATHS:
        if path not in paths:
            continue
        status, blob, reason = gh_api(f"repos/{full}/contents/{path}?ref={quote(default_branch, safe='')}")
        if status != 200 or not isinstance(blob, dict) or blob.get("encoding") != "base64":
            return "unknown", f"could not read {path} on {default_branch!r} ({reason})"
        try:
            text = base64.b64decode(blob.get("content") or "").decode("utf-8")
            found = declares_pull_request_target(text)
        except (ValueError, UnicodeDecodeError):
            return "unknown", f"could not decode {path} on {default_branch!r}"
        if found is None:
            return "unknown", f"could not read the on: triggers of {path} on {default_branch!r}"
        if found:
            return "present", f"{path} on {default_branch!r} declares pull_request_target"
        found_without_trigger.append(path)
    if len(listing) >= CONTENTS_CAP:
        return "unknown", (f".github/workflows on {default_branch!r} lists {len(listing)} entries, the Contents API "
                           "cap, so the listing may be incomplete")
    if found_without_trigger:
        return "absent", f"{found_without_trigger[0]} on {default_branch!r} has no pull_request_target trigger"
    return "absent", f"no .github/workflows/review-gate.yml (or .yaml) on {default_branch!r}"


def list_rulesets(full: str) -> tuple[list | None, str]:
    rulesets: list = []
    page = 1
    while True:
        status, data, reason = gh_api(f"repos/{full}/rulesets?per_page={PAGE}&page={page}")
        if status != 200:
            return None, reason
        if not isinstance(data, list):
            return None, "unexpected rulesets payload"
        rulesets.extend(data)
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
    repo = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        capture_output=True,
        text=True,
    )
    if repo.returncode != 0:
        print("WARN could not resolve repo via gh; skip ruleset check")
        return 0
    full = repo.stdout.strip()
    labels = gh_json(["label", "list", "-R", full, "--search", MAIN_REVIEW_LABEL, "--json", "name"])
    if isinstance(labels, list) and any(lb.get("name") == MAIN_REVIEW_LABEL for lb in labels):
        print(f"OK label {MAIN_REVIEW_LABEL!r} exists")
    else:
        print(
            f"WARN label {MAIN_REVIEW_LABEL!r} missing (or unreadable): every PR into main fails the gate; "
            f"gh label create {MAIN_REVIEW_LABEL} -R {full}"
        )
    default_branch_proc = subprocess.run(
        [
            "gh",
            "repo",
            "view",
            full,
            "--json",
            "defaultBranchRef",
            "-q",
            ".defaultBranchRef.name",
        ],
        capture_output=True,
        text=True,
    )
    default_known = default_branch_proc.returncode == 0 and bool(default_branch_proc.stdout.strip())
    default_branch = default_branch_proc.stdout.strip() if default_known else "main"
    rulesets, reason = list_rulesets(full)
    if rulesets is None:
        print(f"WARN could not list rulesets ({reason}; needs Metadata read, which CI's GITHUB_TOKEN usually "
              "lacks); the ruleset and Review Gate producer checks are skipped")
        return 0

    branch_state = {
        b: {"resolution": False, "gate": False, "seen": False} for b in MERGE_BRANCHES
    }
    skipped_non_enforcing = 0
    skipped_wrong_branch = 0
    gate_branches: list[str] = []  # covered branches whose Review Gate requirement this doctor analyzes
    other_contexts: dict[str, None] = {}
    for rs in rulesets:
        rid = rs.get("id")
        name = rs.get("name")
        status, detail, reason = gh_api(f"repos/{full}/rulesets/{rid}")
        if status != 200 or not isinstance(detail, dict):
            print(f"WARN could not read ruleset {name!r} ({reason}); ignored")
            continue
        if not ruleset_is_enforcing(detail):
            skipped_non_enforcing += 1
            enf = detail.get("enforcement") or "unknown"
            print(
                f"WARN ruleset {name!r} enforcement={enf!r} "
                "(disabled/evaluate does not block merges); ignored"
            )
            continue
        covered = ruleset_covered_branches(detail, default_branch=default_branch)
        if not covered:
            skipped_wrong_branch += 1
            print(
                f"WARN ruleset {name!r} does not target main/staging "
                "(conditions.ref_name); ignored for Review Gate coverage"
            )
            continue
        for rule in detail.get("rules") or []:
            if rule.get("type") != "required_status_checks":
                continue
            for check in (rule.get("parameters") or {}).get("required_status_checks") or []:
                if not isinstance(check, dict):
                    continue
                context = check.get("context")
                if context != REVIEW_GATE_CONTEXT:
                    other_contexts.setdefault(str(context))
                elif check.get("integration_id") not in (None, ACTIONS_INTEGRATION_ID):
                    print(f"OK ruleset {name!r} pins {REVIEW_GATE_CONTEXT!r} to integration "
                          f"{check.get('integration_id')} (not GitHub Actions); producer check skipped")
                else:
                    gate_branches.extend(b for b in covered if b not in gate_branches)
        has_resolution = ruleset_requires_conversation_resolution(detail)
        has_gate = ruleset_requires_review_gate(detail)
        has_status_rule = any(
            rule.get("type") == "required_status_checks"
            for rule in (detail.get("rules") or [])
        )
        for branch in covered:
            branch_state[branch]["seen"] = True
            if has_resolution:
                branch_state[branch]["resolution"] = True
                print(
                    f"OK ruleset {name!r} requires conversation resolution "
                    f"on {branch}"
                )
            if has_gate:
                branch_state[branch]["gate"] = True
                print(
                    f"OK ruleset {name!r} requires status check "
                    f"{REVIEW_GATE_CONTEXT!r} on {branch}"
                )
            elif has_status_rule:
                print(
                    f"WARN ruleset {name!r} has required_status_checks on {branch} "
                    f"but missing context {REVIEW_GATE_CONTEXT!r}"
                )
            if not has_resolution:
                # pull_request rule present without the flag
                if any(
                    rule.get("type") == "pull_request"
                    for rule in (detail.get("rules") or [])
                ):
                    print(
                        f"WARN ruleset {name!r} has pull_request rule on {branch} but "
                        f"required_review_thread_resolution is not true"
                    )

    if not any(st["seen"] for st in branch_state.values()):
        bits: list[str] = []
        if skipped_non_enforcing:
            bits.append(f"{skipped_non_enforcing} disabled/evaluate")
        if skipped_wrong_branch:
            bits.append(f"{skipped_wrong_branch} not targeting main/staging")
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
