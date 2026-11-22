#!/usr/bin/env python3
"""Warn when a repo is missing review-gate wiring.

Prints WARN / OK / FAIL lines on stdout. It exits 1, with or without --strict, when the repo-tracked
.claude/skills/review-gate is older than this release, has an unreadable version, or its hooks.json and
SKILL.md disagree (3.2.19). With --strict (3.2.14) it also exits 1 when the workflow or a vendored script is
missing or differs from this skill's copy: the local checks, which need no token. Otherwise it exits 0. The
label and ruleset checks stay warnings, since CI's GITHUB_TOKEN usually cannot read rulesets.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    strict = "--strict" in (sys.argv[1:] if argv is None else argv)
    root = Path.cwd()
    problems = local_checks(root)
    parity = vendored_skill_parity(root)
    remote_checks()
    print(RERUN_HINT)
    if not parity:
        return 1  # a stale vendored skill fails with or without --strict
    if strict and problems:
        print(f"FAIL --strict: {problems} workflow/vendored-script problem(s) above")
        return 1
    return 0


def remote_checks() -> None:
    """Label and ruleset checks through gh; warnings only."""
    if shutil.which("gh") is None:  # the local checks above still ran; the rest needs the GitHub CLI
        print("WARN gh (GitHub CLI) not found; skip label and ruleset checks")
        return
    # gh doesn't expand {owner}/{repo} in all versions; resolve explicitly.
    repo = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        capture_output=True,
        text=True,
    )
    if repo.returncode != 0:
        print("WARN could not resolve repo via gh; skip ruleset check")
        return
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
    default_branch = (
        default_branch_proc.stdout.strip()
        if default_branch_proc.returncode == 0 and default_branch_proc.stdout.strip()
        else "main"
    )
    rulesets = gh_json(["api", f"repos/{full}/rulesets"])
    if rulesets is None:
        print("WARN could not list rulesets (need admin:repo_hook or similar)")
        return
    if not isinstance(rulesets, list):
        print("WARN unexpected rulesets payload")
        return

    branch_state = {
        b: {"resolution": False, "gate": False, "seen": False} for b in MERGE_BRANCHES
    }
    skipped_non_enforcing = 0
    skipped_wrong_branch = 0
    for rs in rulesets:
        rid = rs.get("id")
        name = rs.get("name")
        detail = gh_json(["api", f"repos/{full}/rulesets/{rid}"])
        if not isinstance(detail, dict):
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


if __name__ == "__main__":
    sys.exit(main())
