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
MERGE_RE = re.compile(
    r"\bgh(?:\s+-R(?:=\S+|\s+\S+|\S+)|\s+--repo(?:=\S+|\s+\S+))*\s+pr\s+merge\b"
)
PULL_URL = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+)/pull/(\d+)",
    re.I,
)
# Subshell `( cd …` — require `-R` (env wrappers handled via tokens).
SUBSHELL_CD_RE = re.compile(r"(?:^|[\s;|&])\(\s*cd\s", re.I)
# Value-taking flags from `gh pr merge --help` (and shared -R/--repo).
# Walk argv and consume their values so body text cannot fake a -R match.
MERGE_VALUE_FLAGS = frozenset(
    {
        "--match-head-commit",
        "--body",
        "-b",
        "--body-file",
        "-F",
        "--subject",
        "-t",
        "--author-email",
        "-A",
        "-R",
        "--repo",
    }
)
# Separators that do not guarantee a preceding `cd` ran (fail closed).
CONDITIONAL_SEPS = frozenset({"||", "|"})


def _shell_tokens(cmd: str) -> list[str]:
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return cmd.split()


def shell_comments(cmd: str) -> list[str]:
    """Return `#…` shell comments, ignoring `#` inside single/double quotes."""
    comments: list[str] = []
    i = 0
    in_single = False
    in_double = False
    while i < len(cmd):
        c = cmd[i]
        if in_single:
            if c == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if c == "\\" and i + 1 < len(cmd):
                i += 2
                continue
            if c == '"':
                in_double = False
            i += 1
            continue
        if c == "'":
            in_single = True
            i += 1
            continue
        if c == '"':
            in_double = True
            i += 1
            continue
        if c == "#" and (i == 0 or cmd[i - 1].isspace()):
            end = cmd.find("\n", i)
            if end < 0:
                end = len(cmd)
            comments.append(cmd[i:end])
            i = end
            continue
        i += 1
    return comments


def has_override(cmd: str) -> bool:
    """True only when `# review-gate-ok:` appears in a real shell comment."""
    return any(OVERRIDE.search(c) for c in shell_comments(cmd))


def split_shell_chains(cmd: str) -> list[tuple[str, str]]:
    """Split on chain operators outside quotes.

    Returns [(segment, sep_after), ...] where sep_after is one of
    '', '&&', '||', '|', ';', '&', '\\n'.
    """
    parts: list[tuple[str, str]] = []
    buf: list[str] = []
    i = 0
    in_single = False
    in_double = False
    n = len(cmd)

    def flush(sep: str) -> None:
        text = "".join(buf).strip()
        buf.clear()
        if text:
            parts.append((text, sep))

    while i < n:
        c = cmd[i]
        if in_single:
            buf.append(c)
            if c == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            buf.append(c)
            if c == "\\" and i + 1 < n:
                buf.append(cmd[i + 1])
                i += 2
                continue
            if c == '"':
                in_double = False
            i += 1
            continue
        if c == "'":
            in_single = True
            buf.append(c)
            i += 1
            continue
        if c == '"':
            in_double = True
            buf.append(c)
            i += 1
            continue
        if c == "&" and i + 1 < n and cmd[i + 1] == "&":
            flush("&&")
            i += 2
            continue
        if c == "|" and i + 1 < n and cmd[i + 1] == "|":
            flush("||")
            i += 2
            continue
        if c == "|":
            flush("|")
            i += 1
            continue
        if c == ";":
            flush(";")
            i += 1
            continue
        if c == "&":
            flush("&")
            i += 1
            continue
        if c == "\n":
            flush("\n")
            i += 1
            continue
        buf.append(c)
        i += 1
    flush("")
    return parts


def env_wraps_merge(part: str) -> bool:
    """True when `env` appears before `gh` in the segment (any -C/--chdir spelling)."""
    tokens = _shell_tokens(part)
    try:
        gh_i = next(i for i, t in enumerate(tokens) if t == "gh")
    except StopIteration:
        return False
    return any(t == "env" for t in tokens[:gh_i])


def scoped_dir_requires_repo(part: str) -> bool:
    """True when the segment uses env/subshell chdir we refuse to model without -R."""
    return env_wraps_merge(part) or bool(SUBSHELL_CD_RE.search(part))


def extract_repo(cmd: str) -> str | None:
    """Return -R/--repo from the argv, never from quoted flag values (e.g. --body)."""
    tokens = _shell_tokens(cmd)
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-R", "--repo"):
            if i + 1 < len(tokens):
                return tokens[i + 1]
            return None
        if tok.startswith("--repo="):
            return tok.split("=", 1)[1]
        if tok.startswith("-R") and tok != "-R":
            return tok[2:]
        if tok.startswith("-"):
            if "=" in tok:
                i += 1
                continue
            # Consume value-taking flags (including -R handled above).
            base = tok
            if base in MERGE_VALUE_FLAGS:
                i += 2
                continue
            i += 1
            continue
        i += 1
    return None


def extract_merge_selector(cmd: str) -> str | None:
    """Positional selector after `pr merge`, or None when merging the current branch."""
    m = re.search(r"\bpr\s+merge\b(.*)$", cmd, re.S)
    if not m:
        return None
    tokens = _shell_tokens(m.group(1))
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            if tok in ("-R", "--repo"):
                i += 2
                continue
            if tok.startswith("-R") and tok != "-R":
                i += 1
                continue
            if tok.startswith("--repo="):
                i += 1
                continue
            if "=" in tok:
                i += 1
                continue
            if tok in MERGE_VALUE_FLAGS:
                i += 2
                continue
            i += 1
            continue
        return tok
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


def _cd_target_unresolvable(target: str | None) -> bool:
    """True when the guard cannot know the post-cd directory statically."""
    if not target or target == "-":
        return True
    if "$" in target or "`" in target:
        return True
    return False


DIR_BUILTINS = frozenset({"cd", "pushd"})


def parse_dir_builtin(part: str, builtin: str) -> str | None:
    """Return the directory operand of cd/pushd, skipping -L/-P/-- options.

    None means bare builtin, `cd -`, or no directory token (treat as unresolvable).
    """
    try:
        tokens = shlex.split(part, posix=True)
    except ValueError:
        tokens = part.split()
    if not tokens or tokens[0] != builtin:
        return None
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            i += 1
            break
        if tok.startswith("-") and tok != "-":
            i += 1
            continue
        break
    if i >= len(tokens):
        return None
    return tokens[i].strip("'\"")


def iter_merge_segments(
    cmd: str, start_cwd: str
) -> tuple[list[tuple[str, str]], str | None]:
    """Return ((segment, cwd)…, error).

    Quote-aware split on `&&`, `||`, `|`, `;`, `&`, and newlines.
    Unresolvable / conditional cd/pushd/popd before a merge without `-R` fails closed.
    """
    cwd = start_cwd
    unresolved_cd = False
    out: list[tuple[str, str]] = []
    for part, sep_after in split_shell_chains(cmd):
        if not MERGE_RE.search(part):
            tokens = _shell_tokens(part)
            first = tokens[:1]
            if first and first[0] == "popd":
                unresolved_cd = True
                continue
            if first and first[0] in DIR_BUILTINS:
                # `cd … || merge` does not apply the new cwd in Bash when cd fails.
                if sep_after in CONDITIONAL_SEPS:
                    unresolved_cd = True
                    continue
                target = parse_dir_builtin(part, first[0])
                if _cd_target_unresolvable(target):
                    unresolved_cd = True
                    continue
                assert target is not None
                expanded = os.path.expanduser(target)
                cwd = expanded if os.path.isabs(expanded) else os.path.join(cwd, expanded)
                unresolved_cd = False
                continue
            # `if cd …`, `then pushd …`, etc. — use tokens so quoted text is ignored.
            if any(t in DIR_BUILTINS or t == "popd" for t in tokens):
                unresolved_cd = True
                continue
        if MERGE_RE.search(part):
            # Multiple merges in one segment (should be rare after |/|| splits).
            if len(re.findall(r"\bpr\s+merge\b", part)) > 1:
                return [], (
                    "review-gate: multiple `gh pr merge` invocations in one shell "
                    "segment; run them as separate commands"
                )
            if scoped_dir_requires_repo(part) and not extract_repo(part):
                return [], (
                    "review-gate: command-scoped directory change detected "
                    "(e.g. `env -C`/`--chdir` / subshell `cd`); pass `-R owner/repo` explicitly"
                )
            if unresolved_cd and not extract_repo(part):
                return [], (
                    "review-gate: cannot resolve directory change before `gh pr merge`; "
                    "use a literal `cd`/`pushd` path or pass `-R owner/repo`"
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
        # Repo resolution failures are gate failures, not infra to skip.
        if "not found" in msg or "could not resolve owner/repo" in msg:
            return f"review-gate: {e}"
        print(f"review-gate: skip (infra): {e}", file=sys.stderr)
        return None
    if reasons:
        return "review-gate blocked merge:\n" + "\n".join(f"- {r}" for r in reasons)
    return None


def check_command(cmd: str, cwd: str | None = None) -> str | None:
    if not MERGE_RE.search(cmd):
        return None
    if has_override(cmd):
        return None
    start = cwd or os.getcwd()
    segments, seg_err = iter_merge_segments(cmd, start)
    if seg_err:
        return seg_err
    if not segments:
        if scoped_dir_requires_repo(cmd) and not extract_repo(cmd):
            return (
                "review-gate: command-scoped directory change detected "
                "(e.g. `env -C`/`--chdir` / subshell `cd`); pass `-R owner/repo` explicitly"
            )
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
