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
PULL_URL = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", re.I)
# Value-taking flags from https://cli.github.com/manual/gh_pr_merge — skip their args
# so they are not mistaken for a branch/URL selector.
MERGE_VALUE_FLAGS = frozenset(
    {
        "--match-head-commit",
        "--body",
        "--body-file",
        "--subject",
        "--author-email",
        "-R",
        "--repo",
    }
)


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
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            if "=" in tok:
                i += 1
                continue
            if tok in MERGE_VALUE_FLAGS:
                i += 2
                continue
            i += 1
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

    Supports number, pull URL (including owner/repo from the URL), branch name,
    and omitted selector (current branch) via `gh pr view`.
    """
    repo = extract_repo(cmd)
    selector = extract_merge_selector(cmd)
    if selector and selector.isdigit():
        return int(selector), repo, None
    if selector:
        m_url = PULL_URL.search(selector)
        if m_url:
            url_repo = f"{m_url.group(1)}/{m_url.group(2)}"
            return int(m_url.group(3)), repo or url_repo, None
    args = ["gh", "pr", "view", "--json", "number,url"]
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
    if proc.returncode != 0 or not proc.stdout.strip():
        detail = (proc.stderr or proc.stdout or "gh pr view failed").strip()
        return None, repo, f"review-gate: could not resolve PR from merge selector: {detail}"
    try:
        data = json.loads(proc.stdout)
        number = int(data["number"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        return None, repo, f"review-gate: could not parse gh pr view output: {e}"
    if not repo:
        m_url = PULL_URL.search(data.get("url") or "")
        if m_url:
            repo = f"{m_url.group(1)}/{m_url.group(2)}"
    return number, repo, None


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


def _cd_target_unresolvable(target: str) -> bool:
    """True when the guard cannot know the post-cd directory statically."""
    if not target or target == "-":
        return True
    if "$" in target or "`" in target:
        return True
    return False


def iter_merge_segments(
    cmd: str, start_cwd: str
) -> tuple[list[tuple[str, str]], str | None]:
    """Return ((segment, cwd)…, error).

    Splits on `&&`, `;`, and newlines. Unresolvable `cd` before a merge without
    an explicit `-R`/`--repo` fails closed so we never evaluate the wrong repo.
    """
    cwd = start_cwd
    unresolved_cd = False
    out: list[tuple[str, str]] = []
    for part in re.split(r"\s*(?:&&|;|\n)\s*", cmd):
        part = part.strip()
        if not part:
            continue
        m_cd = CD_RE.match(part)
        if m_cd and not MERGE_RE.search(part):
            target = m_cd.group(1).strip("'\"")
            if _cd_target_unresolvable(target):
                unresolved_cd = True
                continue
            expanded = os.path.expanduser(target)
            cwd = expanded if os.path.isabs(expanded) else os.path.join(cwd, expanded)
            unresolved_cd = False
            continue
        if MERGE_RE.search(part):
            if unresolved_cd and not extract_repo(part):
                return [], (
                    "review-gate: cannot resolve `cd` target before `gh pr merge`; "
                    "use a literal path or pass `-R owner/repo`"
                )
            out.append((part, cwd))
    return out, None


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
    segments, seg_err = iter_merge_segments(cmd, start)
    if seg_err:
        return seg_err
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
