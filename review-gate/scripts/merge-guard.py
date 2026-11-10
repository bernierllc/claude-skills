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
# Loose detector; `is_gh_pr_merge` confirms token order (allows `gh pr -R … merge`).
MERGE_RE = re.compile(r"\bgh\b.*\bpr\b.*\bmerge\b", re.S)
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=(.*)$")
PULL_URL = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+)/pull/(\d+)",
    re.I,
)
# Subshell `(cd` / `( cd` — require `-R` (env wrappers handled via tokens).
SUBSHELL_CD_RE = re.compile(r"\(\s*cd\b", re.I)
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
# Separators that do not guarantee a preceding `cd` applied to the parent shell.
CONDITIONAL_SEPS = frozenset({"||", "|", "&"})


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
        # Outside quotes: backslash escapes the next char / continues a line.
        if c == "\\" and i + 1 < n:
            nxt = cmd[i + 1]
            if nxt == "\n":
                # Line continuation — do not treat the newline as a chain boundary.
                if buf and not buf[-1].isspace():
                    buf.append(" ")
                i += 2
                continue
            buf.append(c)
            buf.append(nxt)
            i += 2
            continue
        # Shell comment — ignore through end of line (do not split on `&&` inside it).
        if c == "#" and (i == 0 or cmd[i - 1].isspace()):
            while i < n and cmd[i] != "\n":
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


def _skip_leading_assignments(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    """Strip leading VAR=value tokens; return (rest, assignments)."""
    env: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        m = ASSIGNMENT_RE.match(tokens[i])
        if not m:
            break
        key, _, val = tokens[i].partition("=")
        env[key] = val
        i += 1
    return tokens[i:], env


def is_gh_pr_merge(part: str) -> bool:
    """True when tokens contain `gh` … `pr` … `merge` (flags allowed between)."""
    tokens, _ = _skip_leading_assignments(_shell_tokens(part))
    try:
        gh_i = tokens.index("gh")
        pr_i = next(i for i in range(gh_i + 1, len(tokens)) if tokens[i] == "pr")
        next(i for i in range(pr_i + 1, len(tokens)) if tokens[i] == "merge")
        return True
    except (ValueError, StopIteration):
        return False


def env_wraps_merge(part: str) -> bool:
    """True when `env` appears before `gh` in the segment (any -C/--chdir spelling)."""
    tokens, _ = _skip_leading_assignments(_shell_tokens(part))
    try:
        gh_i = next(i for i, t in enumerate(tokens) if t == "gh")
    except StopIteration:
        return False
    return any(t == "env" for t in tokens[:gh_i])


def scoped_dir_requires_repo(part: str) -> bool:
    """True when the segment uses env/subshell chdir we refuse to model without -R."""
    return env_wraps_merge(part) or bool(SUBSHELL_CD_RE.search(part))


def _repo_operand_unresolvable(repo: str | None) -> bool:
    """True when -R/--repo/GH_REPO still contains shell expansion."""
    if not repo:
        return False
    return "$" in repo or "`" in repo


def extract_repo(cmd: str) -> str | None:
    """Return -R/--repo from argv, or a leading GH_REPO= assignment.

    Returns the sentinel ``$UNRESOLVED`` when the operand is dynamic so callers
    can fail closed (empty string would be ambiguous with “no repo”).
    """
    tokens = _shell_tokens(cmd)
    rest, assignments = _skip_leading_assignments(tokens)
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok in ("-R", "--repo"):
            if i + 1 < len(rest):
                val = rest[i + 1]
                return "$UNRESOLVED" if _repo_operand_unresolvable(val) else val
            return None
        if tok.startswith("--repo="):
            val = tok.split("=", 1)[1]
            return "$UNRESOLVED" if _repo_operand_unresolvable(val) else val
        if tok.startswith("-R") and tok != "-R":
            val = tok[2:]
            return "$UNRESOLVED" if _repo_operand_unresolvable(val) else val
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
    gh_repo = assignments.get("GH_REPO")
    if gh_repo is None or gh_repo == "":
        return None
    return "$UNRESOLVED" if _repo_operand_unresolvable(gh_repo) else gh_repo


def extract_merge_selector(cmd: str) -> str | None:
    """Positional selector after `merge`, or None when merging the current branch."""
    tokens, _ = _skip_leading_assignments(_shell_tokens(cmd))
    try:
        gh_i = tokens.index("gh")
        pr_i = next(i for i in range(gh_i + 1, len(tokens)) if tokens[i] == "pr")
        merge_i = next(i for i in range(pr_i + 1, len(tokens)) if tokens[i] == "merge")
    except (ValueError, StopIteration):
        return None
    i = merge_i + 1
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
        # Trailing subshell closer etc.
        if tok in {")", "fi", "done", "esac"}:
            i += 1
            continue
        return tok
    return None


def has_literal_repo(part: str) -> bool:
    """True when the merge names a concrete owner/repo (-R, GH_REPO=, or pull URL)."""
    repo = extract_repo(part)
    if repo and repo != "$UNRESOLVED" and "/" in repo:
        return True
    selector = extract_merge_selector(part)
    if selector and PULL_URL.search(selector):
        return True
    return False


COMPOUND_MERGE_MSG = (
    "review-gate: compound shell command with `gh pr merge`; "
    "pass literal `-R owner/repo` on each merge "
    "(cd/export/subshell/cwd chains are not modeled)"
)


def extract_pr_and_repo(cmd: str) -> tuple[int | None, str | None]:
    """Legacy helper: numeric selector only. Prefer resolve_pr_number for merges."""
    repo = extract_repo(cmd)
    selector = extract_merge_selector(cmd)
    if selector and selector.isdigit():
        return int(selector), repo
    return None, repo


def resolve_pr_number(cmd: str, cwd: str | None = None) -> tuple[int | None, str | None, str | None]:
    """Resolve gh pr merge selector → (number, repo, error).

    Supports number, pull URL (including owner/repo from the URL), branch name,
    and omitted selector (current branch) via `gh pr view`.
    """
    repo = extract_repo(cmd)
    if repo == "$UNRESOLVED":
        return None, None, (
            "review-gate: dynamic `-R`/`--repo`/GH_REPO operand (e.g. \"$VAR\"); "
            "pass a literal `owner/repo`"
        )
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
# Sourced scripts run in the current shell and may change cwd.
SOURCE_BUILTINS = frozenset({"source", "."})
# Control-flow prefixes where a later `cd` is a real builtin (`if cd …`).
SHELL_KEYWORDS = frozenset(
    {
        "if",
        "then",
        "else",
        "elif",
        "while",
        "until",
        "for",
        "do",
        "case",
        "select",
        "time",
        "!",
    }
)


def parse_dir_builtin(part: str, builtin: str) -> str | None:
    """Return the directory operand of cd/pushd, skipping -L/-P/-- options.

    None means bare builtin, `cd -`, or no directory token (treat as unresolvable).
    """
    try:
        tokens = shlex.split(part, posix=True)
    except ValueError:
        tokens = part.split()
    if not tokens:
        return None
    head = tokens[0].lstrip("(")
    if head != builtin:
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
    return tokens[i].rstrip(")").strip("'\"")


def _leading_dir_builtin(tokens: list[str]) -> str | None:
    """Return cd/pushd/popd if it is the first actionable token (incl. `(cd`)."""
    if not tokens:
        return None
    head = tokens[0].lstrip("(")
    if head in DIR_BUILTINS or head == "popd":
        return head
    return None


def iter_merge_segments(
    cmd: str, start_cwd: str
) -> tuple[list[tuple[str, str]], str | None]:
    """Return ((segment, cwd)…, error).

    Quote-aware split on `&&`, `||`, `|`, `;`, `&`, and newlines.

    Policy (fail closed): any *compound* command (more than one shell segment)
    requires a literal `-R`/`--repo`/GH_REPO=/pull-URL on each merge. We do not
    model cd/export/subshell/cwd interactions across segments — that rat-hole
    kept producing review findings. Prefer `gh -R owner/repo pr merge <n>`.
    """
    chains = split_shell_chains(cmd)
    compound = len(chains) > 1
    out: list[tuple[str, str]] = []
    for part, _sep_after in chains:
        if not is_gh_pr_merge(part):
            continue
        toks = _shell_tokens(part)
        merge_verbs = sum(
            1
            for i, t in enumerate(toks)
            if t == "merge" and "pr" in toks[:i] and "gh" in toks[:i]
        )
        if merge_verbs > 1:
            return [], (
                "review-gate: multiple `gh pr merge` invocations in one shell "
                "segment; run them as separate commands"
            )
        if scoped_dir_requires_repo(part) and not has_literal_repo(part):
            return [], (
                "review-gate: command-scoped directory change detected "
                "(e.g. `env -C`/`--chdir` / subshell `cd`); pass `-R owner/repo` explicitly"
            )
        if compound and not has_literal_repo(part):
            return [], COMPOUND_MERGE_MSG
        # Always evaluate against the tool cwd; literal -R selects the repo.
        out.append((part, start_cwd))
    return out, None


def check_one(segment: str, cwd: str | None) -> str | None:
    number, repo, err = resolve_pr_number(segment, cwd=cwd)
    if err:
        return err
    if number is None:
        return "review-gate: could not parse PR number from `gh pr merge` command"
    try:
        hostname, owner, name = gate.parse_repo_with_host(repo, cwd=cwd)
        pr = gate.pr_payload(owner, name, number, hostname=hostname)
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
    parts = [p for p, _ in split_shell_chains(cmd)] or [cmd]
    if not any(is_gh_pr_merge(p) for p in parts):
        # `bash -c 'gh pr merge …'` / `eval '…'` leave the merge inside one token.
        if MERGE_RE.search(cmd):
            return (
                "review-gate: shell-wrapped `gh pr merge` detected "
                "(e.g. `bash -c` / `eval`); run `gh -R owner/repo pr merge <n>` directly"
            )
        return None
    if has_override(cmd):
        return None
    start = cwd or os.getcwd()
    segments, seg_err = iter_merge_segments(cmd, start)
    if seg_err:
        return seg_err
    if not segments:
        if scoped_dir_requires_repo(cmd) and not has_literal_repo(cmd):
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
