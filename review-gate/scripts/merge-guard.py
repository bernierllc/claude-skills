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
import shlex
import subprocess
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
PULL_URL = re.compile(r"github\.com/[^/]+/[^/]+/pull/(\d+)", re.I)


def extract_repo(cmd: str) -> str | None:
    m_repo = REPO_FLAG.search(cmd)
    if m_repo:
        return m_repo.group(1).strip("'\"")
    return None


def extract_merge_selector(cmd: str) -> str | None:
    """Positional selector after `pr merge`, or None when merging the current branch."""
    m = re.search(r"\bpr\s+merge\b(.*)$", cmd, re.S)
    if not m:
        return None
    try:
        tokens = shlex.split(m.group(1), posix=True)
    except ValueError:
        tokens = m.group(1).split()
    for tok in tokens:
        if tok.startswith("-"):
            continue
        return tok.strip("'\"")
    return None


def extract_pr_and_repo(cmd: str) -> tuple[int | None, str | None]:
    """Legacy helper: numeric selector only. Prefer resolve_pr_number for merges."""
    repo = extract_repo(cmd)
    m = re.search(r"\bpr\s+merge\s+(\d+)\b", cmd)
    if m:
        return int(m.group(1)), repo
    return None, repo


def resolve_pr_number(cmd: str, cwd: str | None = None) -> tuple[int | None, str | None, str | None]:
    """Resolve gh pr merge selector → (number, repo, error).

    Supports number, pull URL, branch name, and omitted selector (current branch)
    via `gh pr view`, matching https://cli.github.com/manual/gh_pr_merge.
    """
    repo = extract_repo(cmd)
    selector = extract_merge_selector(cmd)
    if selector and selector.isdigit():
        return int(selector), repo, None
    if selector:
        m_url = PULL_URL.search(selector)
        if m_url:
            return int(m_url.group(1)), repo, None
    args = ["gh", "pr", "view", "--json", "number", "-q", ".number"]
    if selector:
        args.insert(2, selector)
    if repo:
        args.extend(["-R", repo])
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=cwd or None,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return None, repo, f"review-gate: could not resolve PR via gh: {e}"
    if proc.returncode != 0 or not proc.stdout.strip().isdigit():
        detail = (proc.stderr or proc.stdout or "gh pr view failed").strip()
        return None, repo, f"review-gate: could not resolve PR from merge selector: {detail}"
    return int(proc.stdout.strip()), repo, None


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

    Splits on `&&`, `;`, and newlines so multiline Bash tool calls like
    `cd /other\\ngh pr merge 42` resolve the post-cd directory.
    """
    cwd = start_cwd
    out: list[tuple[str, str]] = []
    for part in re.split(r"\s*(?:&&|;|\n)\s*", cmd):
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
    number, repo, err = resolve_pr_number(segment, cwd=cwd)
    if err:
        return err
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
