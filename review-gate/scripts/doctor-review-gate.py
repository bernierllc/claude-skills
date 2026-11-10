#!/usr/bin/env python3
"""Warn when a repo is missing review-gate wiring.

Exit 0 always for v1 (warnings only) so AEC/CI can adopt gradually.
Prints WARN / OK lines on stdout.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REVIEW_GATE_CONTEXT = "Review Gate"


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


def main() -> int:
    root = Path.cwd()
    wf = root / ".github" / "workflows" / "review-gate.yml"
    if wf.is_file():
        print(f"OK workflow {wf.relative_to(root)}")
    else:
        print(
            "WARN missing .github/workflows/review-gate.yml — copy from "
            "skill review-gate/templates/review-gate.yml"
        )
    checker = root / "scripts" / "check-review-gate.py"
    if checker.is_file():
        print(f"OK trusted checker {checker.relative_to(root)}")
    else:
        print(
            "WARN missing scripts/check-review-gate.py — the workflow loads this "
            "from the PR base SHA; re-run install-workflow.py"
        )

    rulesets = gh_json(["api", "repos/{owner}/{repo}/rulesets", "--jq", "."])
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
    rulesets = gh_json(["api", f"repos/{full}/rulesets"])
    if rulesets is None:
        print("WARN could not list rulesets (need admin:repo_hook or similar)")
        return 0
    if not isinstance(rulesets, list):
        print("WARN unexpected rulesets payload")
        return 0

    checked = 0
    missing_flag = []
    gate_required_on: list[str] = []
    status_check_rulesets = 0
    enforcing_seen = 0
    skipped_non_enforcing = 0
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
        enforcing_seen += 1
        if any(
            rule.get("type") == "required_status_checks"
            for rule in (detail.get("rules") or [])
        ):
            status_check_rulesets += 1
            if ruleset_requires_review_gate(detail):
                gate_required_on.append(str(name))
                print(f"OK ruleset {name!r} requires status check {REVIEW_GATE_CONTEXT!r}")
            else:
                print(
                    f"WARN ruleset {name!r} has required_status_checks but "
                    f"missing context {REVIEW_GATE_CONTEXT!r}"
                )
        for rule in detail.get("rules") or []:
            if rule.get("type") != "pull_request":
                continue
            checked += 1
            params = rule.get("parameters") or {}
            if params.get("required_review_thread_resolution") is True:
                print(f"OK ruleset {name!r} requires conversation resolution")
            else:
                missing_flag.append(name)
                print(
                    f"WARN ruleset {name!r} has pull_request rule but "
                    f"required_review_thread_resolution is not true"
                )
    if enforcing_seen == 0:
        print(
            "WARN no actively enforcing rulesets found "
            f"(saw {skipped_non_enforcing} disabled/evaluate)"
            if skipped_non_enforcing
            else "WARN no actively enforcing rulesets found"
        )
    if checked == 0:
        print("WARN no pull_request rules found on any enforcing ruleset")
    elif missing_flag:
        print(
            "HINT flip with gh api -X PUT repos/.../rulesets/<id> "
            "(see email_demo plan 2026-10-16 §6a)"
        )
    if status_check_rulesets == 0:
        print(
            f"WARN no required_status_checks rules found on enforcing rulesets — "
            f"add {REVIEW_GATE_CONTEXT!r} as a required check on staging/main"
        )
    elif not gate_required_on:
        print(
            f"HINT add required check context {REVIEW_GATE_CONTEXT!r} on staging/main "
            "rulesets (Checks API name from the review-gate workflow job)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
