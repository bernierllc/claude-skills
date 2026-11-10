#!/usr/bin/env python3
"""PreToolUse guard: block gh pr merge when review-gate checks fail.

Exit 0 = allow. Exit 2 = block (stderr message for the agent).
Override: include `# review-gate-ok: <reason>` in the Bash command.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_review_gate", Path(__file__).resolve().with_name("check-review-gate.py")
)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

OVERRIDE = re.compile(r"#\s*review-gate-ok:\s*\S")
MERGE_RE = re.compile(r"\bgh(?:\s+-R\s+\S+|\s+--repo(?:=|\s+)\S+)*\s+pr\s+merge\b")
# `-R` requires a separator (space); bare `-Rowner/repo` is not a gh form we support.
REPO_FLAG = re.compile(r"(?:(?:^|\s)-R|--repo)(?:=|\s+)(\S+)")
CD_RE = re.compile(r"^cd\s+(?:--\s+)?(\S+)")


def extract_pr_and_repo(cmd: str) -> tuple[int | None, str | None]:
    repo = None
    m_repo = REPO_FLAG.search(cmd)
    if m_repo:
        repo = m_repo.group(1).strip("'\"")
    m = re.search(r"\bpr\s+merge\s+(\d+)\b", cmd)
    if m:
        return int(m.group(1)), repo
    return None, repo


def payload_cwd(payload: dict, inp: dict) -> str:
    """AEC puts cwd at the top level; some harnesses nest it under tool_input."""
    for candidate in (
        payload.get("cwd"),
        payload.get("working_directory"),
        inp.get("working_directory"),
        inp.get("cwd"),
    ):
        if candidate:
            return str(candidate)
    return os.getcwd()


def iter_merge_segments(cmd: str, start_cwd: str) -> list[tuple[str, str]]:
    """Return (segment, cwd) for each `gh pr merge`, applying prior `cd` in the chain.

    Covers agent patterns like `cd /other && gh pr merge 42`. Unresolvable cds
    (`cd -`, `$VAR`) leave cwd unchanged so -R still wins when present.
    """
    cwd = start_cwd
    out: list[tuple[str, str]] = []
    for part in re.split(r"\s*(?:&&|;)\s*", cmd):
        part = part.strip()
        if not part:
            continue
        m_cd = CD_RE.match(part)
        if m_cd and not MERGE_RE.search(part):
            target = m_cd.group(1).strip("'\"")
            if target.startswith("$") or target == "-":
                continue
            expanded = os.path.expanduser(target)
            cwd = expanded if os.path.isabs(expanded) else os.path.join(cwd, expanded)
            continue
        if MERGE_RE.search(part):
            out.append((part, cwd))
    return out


def check_one(segment: str, cwd: str | None) -> str | None:
    number, repo = extract_pr_and_repo(segment)
    if number is None:
        return "review-gate: could not parse PR number from `gh pr merge` command"
    try:
        owner, name = gate.parse_repo(repo, cwd=cwd)
        pr = gate.pr_payload(owner, name, number)
        reasons = gate.evaluate(pr)
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if "not found" in msg:
            return f"review-gate: {e}"
        print(f"review-gate: skip (infra): {e}", file=sys.stderr)
        return None
    if reasons:
        return "review-gate blocked merge:\n" + "\n".join(f"- {r}" for r in reasons)
    return None


def check_command(cmd: str, cwd: str | None = None) -> str | None:
    if not MERGE_RE.search(cmd):
        return None
    if OVERRIDE.search(cmd):
        return None
    start = cwd or os.getcwd()
    segments = iter_merge_segments(cmd, start)
    if not segments:
        return check_one(cmd, start)
    for segment, seg_cwd in segments:
        err = check_one(segment, seg_cwd)
        if err:
            return err
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if (payload.get("tool_name") or payload.get("toolName") or "") not in (
        "Bash",
        "bash",
        "Shell",
        "shell",
    ):
        return 0
    inp = payload.get("tool_input") or payload.get("input") or {}
    cmd = inp.get("command") or inp.get("cmd") or ""
    if not cmd:
        return 0
    cwd = payload_cwd(payload, inp)
    err = check_command(cmd, cwd)
    if err:
        print(err, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
