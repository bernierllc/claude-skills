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
# Pull *URL* selectors must include a scheme (gh treats scheme-less paths as branch names).
# Groups: host, owner, repo, number. Optional query/fragment/trailing path (gh accepts them).
PULL_URL = re.compile(
    r"https?://(?:www\.)?([^/\s]+)/([^/]+)/([^/]+)/pull/(\d+)(?:[/?#][^\s]*)?",
    re.I,
)
DOTCOM_PULL_HOSTS = frozenset({"github.com", "www.github.com"})
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
# Single-letter value-taking flags (cobra/pflag bundles: `-dR owner/repo`).
MERGE_VALUE_SHORT = frozenset({"R", "b", "F", "t", "A"})
# Separators that do not guarantee a preceding `cd` applied to the parent shell.
CONDITIONAL_SEPS = frozenset({"||", "|", "&"})


def _consume_merge_argv_flag(
    tokens: list[str], i: int
) -> tuple[int, str | None, bool]:
    """Advance past a merge argv flag at ``tokens[i]``.

    Returns ``(next_index, repo_from_-R_or_None, missing_value)``.
    Understands cobra-style short clusters (``-dR owner/target``, ``-dRowner/target``)
    so a bundled ``R`` is not skipped as an unknown boolean flag.
    """
    tok = tokens[i]
    if tok in ("-R", "--repo"):
        if i + 1 >= len(tokens):
            return i + 1, None, True
        return i + 2, tokens[i + 1], False
    if tok.startswith("--repo="):
        return i + 1, tok.split("=", 1)[1], False
    if tok.startswith("--"):
        if "=" in tok:
            return i + 1, None, False
        if tok in MERGE_VALUE_FLAGS:
            if i + 1 >= len(tokens):
                return i + 1, None, True
            return i + 2, None, False
        return i + 1, None, False
    if not tok.startswith("-") or tok == "-":
        return i + 1, None, False
    # Short option or cluster: -Rowner, -bTEXT, -dR owner, -dRowner, -b, …
    if "=" in tok:
        # ``-R=owner/repo`` / ``-b=text`` (unlikely for gh, but consume as one token).
        key, _, val = tok[1:].partition("=")
        if key == "R":
            return i + 1, val, False
        return i + 1, None, False
    body = tok[1:]
    j = 0
    while j < len(body):
        ch = body[j]
        if ch in MERGE_VALUE_SHORT:
            attached = body[j + 1 :]
            if attached:
                value = attached
                next_i = i + 1
            else:
                if i + 1 >= len(tokens):
                    return i + 1, None, True
                value = tokens[i + 1]
                next_i = i + 2
            if ch == "R":
                return next_i, value, False
            return next_i, None, False
        j += 1
    return i + 1, None, False


def _shell_tokens(cmd: str) -> list[str]:
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return cmd.split()


def shell_comments(cmd: str) -> list[str]:
    """Return `#…` shell comments at depth 0 (not quotes / `<(…)` / `$(…)` / backticks)."""
    comments: list[str] = []
    i = 0
    in_single = False
    in_double = False
    depth = 0
    n = len(cmd)
    while i < n:
        c = cmd[i]
        if in_single:
            if c == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if c == "\\" and i + 1 < n:
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
        # Legacy backtick command substitution — skip until closing unescaped `.
        if c == "`":
            i += 1
            while i < n:
                if cmd[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if cmd[i] == "`":
                    i += 1
                    break
                i += 1
            continue
        # Nested process / command substitutions and subshells.
        if c in "<>" and i + 1 < n and cmd[i + 1] == "(":
            depth += 1
            i += 2
            continue
        if c == "$" and i + 1 < n and cmd[i + 1] == "(":
            depth += 1
            i += 2
            continue
        if c == "(":
            depth += 1
            i += 1
            continue
        if c == ")" and depth > 0:
            depth -= 1
            i += 1
            continue
        if depth == 0 and _is_unescaped_shell_comment_hash(cmd, i):
            end = cmd.find("\n", i)
            if end < 0:
                end = n
            comments.append(cmd[i:end])
            i = end
            continue
        i += 1
    return comments


def _is_unescaped_shell_comment_hash(cmd: str, i: int) -> bool:
    """True when ``cmd[i]`` is ``#`` starting a real shell comment (not ``\\ #``)."""
    if i < 0 or i >= len(cmd) or cmd[i] != "#":
        return False
    if i == 0:
        return True
    if not cmd[i - 1].isspace():
        return False
    # Odd number of backslashes immediately before that whitespace → escaped space.
    bs = 0
    k = i - 2
    while k >= 0 and cmd[k] == "\\":
        bs += 1
        k -= 1
    return bs % 2 == 0


def segment_has_override(part: str) -> bool:
    """True when `# review-gate-ok:` is a shell comment on this merge segment."""
    if not is_gh_pr_merge(part):
        return False
    return any(OVERRIDE.search(c) for c in shell_comments(part))


def has_override(cmd: str) -> bool:
    """True when any merge segment carries `# review-gate-ok:`.

    Overrides must be attached to the ``gh pr merge`` invocation itself — not
    buried in heredoc data or a prior unrelated line. Each merge segment is
    evaluated independently (an override on one does not waive others).
    """
    chains = split_shell_chains(cmd)
    parts = [p for p, _ in chains] if chains else [cmd]
    return any(segment_has_override(p) for p in parts)


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
        # Shell comment — keep text on the segment (for `# review-gate-ok:`) but do
        # not treat `&&` / `|` inside the comment as chain operators.
        if c == "#" and (i == 0 or cmd[i - 1].isspace()):
            while i < n and cmd[i] != "\n":
                buf.append(cmd[i])
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


# Value-taking options from `env --help` that can appear before NAME=VALUE / COMMAND.
ENV_VALUE_FLAGS = frozenset(
    {
        "-C",
        "--chdir",
        "-u",
        "--unset",
        "-S",
        "--split-string",
        "--block-signal",
        "--default-signal",
        "--ignore-signal",
    }
)


# gh config location: GH_CONFIG_DIR, else $XDG_CONFIG_HOME/gh, else $HOME/.config/gh.
GH_CONFIG_LOCATION_VARS = frozenset({"GH_CONFIG_DIR", "XDG_CONFIG_HOME", "HOME"})
# Vars whose cleared (-u / -i) state the gate must mirror for host/config fidelity.
GH_TRACKED_ENV_VARS = frozenset({"GH_HOST", "GH_REPO"}) | GH_CONFIG_LOCATION_VARS


def _env_wrapper_state(
    tokens: list[str],
) -> tuple[dict[str, str], set[str]]:
    """Collect env NAME=VALUE / -u / -i effects before `gh`.

    Returns ``(assignments, cleared_names)``. Cleared names are unset for the
    child (``-u/--unset``, ``-i``, or bare ``-``) unless a later assignment
    re-sets them.
    """
    try:
        env_i = next(i for i, t in enumerate(tokens) if t == "env")
        gh_i = next(i for i, t in enumerate(tokens) if t == "gh")
    except StopIteration:
        return {}, set()
    if env_i >= gh_i:
        return {}, set()
    out: dict[str, str] = {}
    cleared: set[str] = set()
    i = env_i + 1
    while i < gh_i:
        tok = tokens[i]
        if ASSIGNMENT_RE.match(tok):
            key, _, val = tok.partition("=")
            out[key] = val
            cleared.discard(key)
            i += 1
            continue
        if tok.startswith("-"):
            # Bare ``-`` implies ``-i`` (GNU env).
            if tok in ("-", "-i", "--ignore-environment"):
                out.clear()
                cleared |= set(GH_TRACKED_ENV_VARS)
                i += 1
                continue
            if tok.startswith("--") and "=" in tok:
                # ``--unset=GH_HOST``
                flag, _, val = tok.partition("=")
                if flag in ("--unset", "-u"):
                    out.pop(val, None)
                    cleared.add(val)
                i += 1
                continue
            # Sticky ``-uGH_HOST`` / ``-C/path`` (no separate operand).
            if tok.startswith("-u") and tok != "-u":
                name = tok[2:]
                out.pop(name, None)
                cleared.add(name)
                i += 1
                continue
            if tok.startswith("-C") and tok != "-C":
                i += 1
                continue
            base = tok.split("=", 1)[0]
            if base in ENV_VALUE_FLAGS:
                if i + 1 >= gh_i:
                    break
                operand = tokens[i + 1]
                if base in ("-u", "--unset"):
                    out.pop(operand, None)
                    cleared.add(operand)
                i += 2
                continue
            i += 1
            continue
        break
    return out, cleared


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


def _command_name_dynamic(tok: str) -> bool:
    """True when a command token may expand to a different executable at runtime."""
    if not tok:
        return False
    # `$…`, backticks, tilde, ANSI-C residue (`$\x67\x68` after shlex).
    if "$" in tok or "`" in tok or tok.startswith("~") or "\\" in tok:
        return True
    return False


def dynamic_gh_pr_merge(part: str) -> bool:
    """True when ``pr``…``merge`` follows a dynamic executable (not literal ``gh``).

    Example: ``$'\\x67\\x68' -R owner/target pr merge 42`` runs ``gh`` after Bash
    expands the ANSI-C quote, but tokenizers only see a non-``gh`` command name.
    Fail closed — do not treat it as unrelated shell input.
    """
    if is_gh_pr_merge(part):
        return False
    tokens, _ = _skip_leading_assignments(_shell_tokens(part))
    try:
        pr_i = next(i for i, t in enumerate(tokens) if t == "pr")
        next(i for i in range(pr_i + 1, len(tokens)) if tokens[i] == "merge")
    except StopIteration:
        return False
    i = _index_after_env_wrapper(tokens)
    while i < len(tokens) and tokens[i] in SHELL_PREFIX_KEYWORDS:
        i += 1
    if i >= len(tokens) or i >= pr_i:
        return False
    cmd = tokens[i]
    if cmd == "gh":
        return False
    return _command_name_dynamic(cmd)


def env_wraps_merge(part: str) -> bool:
    """True when `env` appears before `gh` in the segment (any -C/--chdir spelling)."""
    tokens, _ = _skip_leading_assignments(_shell_tokens(part))
    try:
        gh_i = next(i for i, t in enumerate(tokens) if t == "gh")
    except StopIteration:
        return False
    return any(t == "env" for t in tokens[:gh_i])


def _index_after_env_wrapper(tokens: list[str]) -> int:
    """Return index of the command after an optional leading ``env`` wrapper."""
    if not tokens or tokens[0] != "env":
        return 0
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if ASSIGNMENT_RE.match(tok):
            i += 1
            continue
        if tok.startswith("-"):
            if tok in ("-", "-i", "--ignore-environment"):
                i += 1
                continue
            if tok.startswith("--") and "=" in tok:
                i += 1
                continue
            if tok.startswith("-u") and tok != "-u":
                i += 1
                continue
            if tok.startswith("-C") and tok != "-C":
                i += 1
                continue
            base = tok.split("=", 1)[0]
            if base in ENV_VALUE_FLAGS:
                i += 2
                continue
            i += 1
            continue
        break
    return i


# Shell words that may precede a local ``gh`` (control flow / trivial builtins).
SHELL_PREFIX_KEYWORDS = frozenset(
    {"then", "do", "else", "elif", "time", "command", "builtin", "exec", "!"}
)


def gh_is_direct_command(part: str) -> bool:
    """True when ``gh`` is the executed binary (optional ``env`` / shell keywords).

    Rejects ``ssh``/``xargs``/``docker``/… wrappers that run merge in another
    environment or append unseen argv — fail closed; require a direct ``gh``.
    """
    tokens, _ = _skip_leading_assignments(_shell_tokens(part))
    i = _index_after_env_wrapper(tokens)
    while i < len(tokens) and tokens[i] in SHELL_PREFIX_KEYWORDS:
        i += 1
    return i < len(tokens) and tokens[i] == "gh"


def scoped_dir_requires_repo(part: str) -> bool:
    """True when the segment uses env/subshell chdir we refuse to model without -R."""
    return env_wraps_merge(part) or bool(SUBSHELL_CD_RE.search(part))


# Git location / config overrides change which repo `gh` sees without `-R`.
GIT_LOCATION_VARS = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"})
GIT_CONFIG_VARS = frozenset(
    {
        "GIT_CONFIG",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_COUNT",
    }
)


def is_git_env_override_key(key: str) -> bool:
    """True for GIT_DIR / GIT_CONFIG_COUNT / GIT_CONFIG_KEY_n / … overrides."""
    if key in GIT_LOCATION_VARS or key in GIT_CONFIG_VARS:
        return True
    return key.startswith("GIT_CONFIG_KEY_") or key.startswith("GIT_CONFIG_VALUE_")


def sets_git_location(part: str) -> bool:
    """True when the command sets GIT_DIR / GIT_WORK_TREE / GIT_CONFIG_* overrides."""
    tokens = _shell_tokens(part)
    rest, leading = _skip_leading_assignments(tokens)
    if any(is_git_env_override_key(k) for k in leading):
        return True
    env_assigns, _cleared = _env_wrapper_state(rest)
    return any(is_git_env_override_key(k) for k in env_assigns)


def _repo_operand_unresolvable(repo: str | None) -> bool:
    """True when -R/--repo/GH_REPO still contains shell expansion."""
    if not repo:
        return False
    return "$" in repo or "`" in repo


def _env_overlay_unresolvable(val: str | None) -> bool:
    """True when a command-scoped env overlay still needs shell expansion.

    Covers ``$`` / backticks and leading ``~`` (Bash tilde-expands unquoted
    ``~/…`` / ``~user/…``; after ``shlex`` we cannot tell quoting, so fail closed).
    """
    if not val:
        return False
    if _repo_operand_unresolvable(val):
        return True
    return val.startswith("~")


def _normalize_repo_operand(val: str) -> str:
    return "$UNRESOLVED" if _repo_operand_unresolvable(val) else val


def repo_from_pull_url_match(m: re.Match[str]) -> str:
    """Build `HOST/OWNER/REPO` from a PULL_URL match (dotcom kept explicit)."""
    host, owner, name = m.group(1), m.group(2), m.group(3)
    if host.lower() in DOTCOM_PULL_HOSTS:
        return f"github.com/{owner}/{name}"
    return f"{host}/{owner}/{name}"


def _apply_gh_host(repo: str | None, assignments: dict[str, str]) -> str | None:
    """Prefix a hostless OWNER/REPO with a GH_HOST assignment.

    Matches ``gh help environment``: GH_HOST (leading or via ``env``) selects
    the API host when the repository slug does not already embed one. Dotcom is
    kept as an explicit ``github.com/…`` slug so API calls can pass
    ``--hostname`` and override a process-level Enterprise GH_HOST. Dynamic
    hosts fail closed.
    """
    if not repo or repo == "$UNRESOLVED":
        return repo
    parts = [p for p in repo.strip().strip("/").split("/") if p]
    if len(parts) >= 3:
        return repo
    if "GH_HOST" not in assignments:
        return repo
    gh_host = assignments.get("GH_HOST")
    # Empty ``GH_HOST=`` clears the host → gh defaults to github.com.
    if gh_host is None or gh_host == "":
        return f"github.com/{repo}"
    if _repo_operand_unresolvable(gh_host):
        return "$UNRESOLVED"
    if gh_host.lower() in DOTCOM_PULL_HOSTS:
        return f"github.com/{repo}"
    return f"{gh_host}/{repo}"


def extract_repo_resolution(cmd: str) -> tuple[str | None, bool]:
    """Return ``(repo_slug|None|$UNRESOLVED, scrub_process_gh_repo)``.

    ``scrub_process_gh_repo`` is True when the command clears GH_REPO for the
    child (empty ``GH_REPO=``, ``env -u GH_REPO``, ``env -i``) so gate ``gh``
    calls must drop the hook process GH_REPO and resolve the tool cwd instead.
    """
    tokens = _shell_tokens(cmd)
    rest, assignments = _skip_leading_assignments(tokens)
    # ``env NAME=VALUE … gh`` overlays leading assignments (matches the child env).
    env_assigns, cleared = _env_wrapper_state(rest)
    assignments = {**assignments, **env_assigns}
    if "GH_HOST" in cleared and "GH_HOST" not in env_assigns:
        # Child has no GH_HOST → gh defaults to github.com; say so explicitly.
        assignments["GH_HOST"] = "github.com"
    # Empty ``GH_REPO=`` or ``-u GH_REPO`` clears the selector for the child.
    cleared_gh_repo = "GH_REPO" in cleared
    if "GH_REPO" in assignments and assignments.get("GH_REPO") == "":
        cleared_gh_repo = True
    elif cleared_gh_repo and "GH_REPO" not in env_assigns:
        assignments.pop("GH_REPO", None)
    found: str | None = None
    # Only scan gh argv (not `env -uGH_REPO` / similar wrappers — those contain
    # the letter R and must not be parsed as bundled merge short flags).
    try:
        i = rest.index("gh")
    except ValueError:
        i = 0
    while i < len(rest):
        tok = rest[i]
        if tok.startswith("-"):
            next_i, repo_val, missing = _consume_merge_argv_flag(rest, i)
            if missing and repo_val is None and tok in ("-R", "--repo"):
                return None, cleared_gh_repo
            if repo_val is not None:
                found = _normalize_repo_operand(repo_val)
            i = next_i
            continue
        i += 1
    if found is not None:
        # Explicit -R wins; process GH_REPO is irrelevant for repo identity.
        return _apply_gh_host(found, assignments), False
    if "GH_REPO" in assignments:
        gh_repo = assignments.get("GH_REPO")
        if gh_repo == "":
            return None, True
        return _apply_gh_host(_normalize_repo_operand(gh_repo), assignments), False
    if cleared_gh_repo:
        return None, True
    return None, False


def extract_repo(cmd: str) -> str | None:
    """Return the last -R/--repo from argv, or a leading/env GH_REPO= assignment."""
    repo, _scrub = extract_repo_resolution(cmd)
    return repo


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
        if tok == "--":
            # Option terminator — next token is the selector even if it starts with -.
            if i + 1 >= len(tokens):
                return None
            nxt = tokens[i + 1]
            if nxt in {")", "fi", "done", "esac"}:
                return None
            return nxt
        if tok.startswith("-"):
            next_i, _repo_val, _missing = _consume_merge_argv_flag(tokens, i)
            i = next_i
            continue
        # Trailing subshell closer etc.
        if tok in {")", "fi", "done", "esac"}:
            i += 1
            continue
        return tok
    return None


def is_pull_url_selector(selector: str) -> re.Match[str] | None:
    """Match only when the *entire* merge selector is a pull URL (not a substring)."""
    return PULL_URL.fullmatch(selector.strip())


def has_literal_repo(part: str) -> bool:
    """True when the merge names a concrete owner/repo (-R, GH_REPO=, or pull URL)."""
    repo = extract_repo(part)
    if repo and repo != "$UNRESOLVED" and "/" in repo:
        return True
    selector = extract_merge_selector(part)
    if selector and is_pull_url_selector(selector):
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


def _apply_overlay_env_var(
    env: dict[str, str], overlays: dict[str, str], key: str
) -> None:
    """Set or clear ``key`` on ``env`` from a command-scoped overlay.

    Callers must reject unresolvable values via ``gh_config_overlay_unresolved``
    before relying on the resulting env (we never silently keep the hook value).
    """
    if key not in overlays:
        return
    val = overlays[key]
    if val == "":
        env.pop(key, None)
    elif not _env_overlay_unresolvable(val):
        env[key] = val


def gh_config_overlay_unresolved(cmd: str) -> bool:
    """True when a command-scoped gh config/host path still needs shell expansion.

    Bash expands ``GH_CONFIG_DIR="$HOME/enterprise"`` and unquoted
    ``GH_CONFIG_DIR=~/enterprise`` for the merge child, but our parser only
    sees the raw ``$HOME/…`` / ``~/…`` — fail closed rather than checking
    against the hook's inherited config dir/host.
    """
    tokens = _shell_tokens(cmd)
    rest, leading = _skip_leading_assignments(tokens)
    env_assigns, _cleared = _env_wrapper_state(rest)
    overlays = {**leading, **env_assigns}
    for key in GH_TRACKED_ENV_VARS:
        if key not in overlays:
            continue
        val = overlays[key]
        if val and _env_overlay_unresolvable(val):
            return True
    return False


def _child_gh_env(cmd: str, scrub_gh_repo: bool) -> dict[str, str] | None:
    """Build a subprocess env mirroring command-scoped gh config for gate ``gh``.

    Propagates ``GH_HOST`` / ``GH_REPO`` / ``GH_CONFIG_DIR`` / ``XDG_CONFIG_HOME`` /
    ``HOME`` so host selection and config dirs match the merge child.
    """
    tokens = _shell_tokens(cmd)
    rest, leading = _skip_leading_assignments(tokens)
    env_assigns, cleared = _env_wrapper_state(rest)
    overlays = {**leading, **env_assigns}
    touches = (
        "GH_HOST" in overlays
        or "GH_REPO" in overlays
        or any(k in overlays for k in GH_CONFIG_LOCATION_VARS)
        or bool(cleared & GH_TRACKED_ENV_VARS)
        or scrub_gh_repo
    )
    if not touches:
        return None
    env = os.environ.copy()
    if "GH_HOST" in cleared and "GH_HOST" not in env_assigns:
        env.pop("GH_HOST", None)
    elif "GH_HOST" in overlays:
        _apply_overlay_env_var(env, overlays, "GH_HOST")
    if (
        scrub_gh_repo
        or ("GH_REPO" in cleared and "GH_REPO" not in env_assigns)
        or overlays.get("GH_REPO") == ""
    ):
        env.pop("GH_REPO", None)
    elif "GH_REPO" in overlays and overlays["GH_REPO"]:
        val = overlays["GH_REPO"]
        if not _repo_operand_unresolvable(val):
            env["GH_REPO"] = val
    for key in GH_CONFIG_LOCATION_VARS:
        if key in cleared and key not in env_assigns:
            env.pop(key, None)
        else:
            _apply_overlay_env_var(env, overlays, key)
    return env


def resolve_pr_number(
    cmd: str, cwd: str | None = None
) -> tuple[int | None, str | None, str | None, bool]:
    """Resolve gh pr merge selector → (number, repo, error, scrub_gh_repo).

    Supports number, pull URL (including owner/repo from the URL), branch name,
    and omitted selector (current branch) via `gh pr view`.
    """
    repo, scrub_gh_repo = extract_repo_resolution(cmd)
    if repo == "$UNRESOLVED":
        return None, None, (
            "review-gate: dynamic `-R`/`--repo`/GH_REPO operand (e.g. \"$VAR\"); "
            "pass a literal `owner/repo`"
        ), False
    if gh_config_overlay_unresolved(cmd):
        return None, None, (
            "review-gate: dynamic GH_CONFIG_DIR/XDG_CONFIG_HOME/HOME/GH_HOST "
            "(e.g. \"$HOME/…\" or \"~/…\"); pass a literal path or unset the var"
        ), scrub_gh_repo
    selector = extract_merge_selector(cmd)
    if selector and selector.isdigit():
        return int(selector), repo, None, scrub_gh_repo
    if selector:
        m_url = is_pull_url_selector(selector)
        if m_url:
            # gh resolves the repository from the URL selector even when -R
            # disagrees (e.g. `gh pr merge https://…/target/pull/7 -R owner/safe`).
            url_repo = repo_from_pull_url_match(m_url)
            return int(m_url.group(4)), url_repo, None, False
    child_env = _child_gh_env(cmd, scrub_gh_repo)
    args = ["gh", "pr", "view", "--json", "number,url"]
    if selector:
        # Branches that start with `-` need `--` (same as `gh pr merge -- -release`).
        if selector.startswith("-"):
            args.extend(["--", selector])
        else:
            args.insert(2, selector)
    if repo:
        args.extend(["-R", repo])
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=cwd or None,
            env=child_env,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return None, repo, f"review-gate: could not resolve PR via gh: {e}", scrub_gh_repo
    if proc.returncode != 0 or not proc.stdout.strip():
        detail = (proc.stderr or proc.stdout or "gh pr view failed").strip()
        return (
            None,
            repo,
            f"review-gate: could not resolve PR from merge selector: {detail}",
            scrub_gh_repo,
        )
    try:
        data = json.loads(proc.stdout)
        number = int(data["number"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        return (
            None,
            repo,
            f"review-gate: could not parse gh pr view output: {e}",
            scrub_gh_repo,
        )
    if not repo:
        m_url = PULL_URL.search(data.get("url") or "")
        if m_url:
            repo = repo_from_pull_url_match(m_url)
    return number, repo, None, scrub_gh_repo


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
        if not gh_is_direct_command(part):
            return [], (
                "review-gate: `gh pr merge` must be the directly executed command "
                "(no ssh/xargs/docker/… wrappers); run `gh -R owner/repo pr merge <n>`"
            )
        if scoped_dir_requires_repo(part) and not has_literal_repo(part):
            return [], (
                "review-gate: command-scoped directory change detected "
                "(e.g. `env -C`/`--chdir` / subshell `cd`); pass `-R owner/repo` explicitly"
            )
        if sets_git_location(part) and not has_literal_repo(part):
            return [], (
                "review-gate: GIT_DIR/GIT_CONFIG_* without literal `-R owner/repo`; "
                "pass `-R` (git location/config env is not modeled)"
            )
        if compound and not has_literal_repo(part):
            return [], COMPOUND_MERGE_MSG
        # Always evaluate against the tool cwd; literal -R selects the repo.
        out.append((part, start_cwd))
    return out, None


def check_one(segment: str, cwd: str | None) -> str | None:
    number, repo, err, scrub_gh_repo = resolve_pr_number(segment, cwd=cwd)
    if err:
        return err
    if number is None:
        return "review-gate: could not parse PR number from `gh pr merge` command"
    child_env = _child_gh_env(segment, scrub_gh_repo)
    try:
        with gate.gh_subprocess_env(child_env):
            hostname, owner, name = gate.parse_repo_with_host(
                repo, cwd=cwd, env=child_env
            )
            pr = gate.pr_payload(owner, name, number, hostname=hostname)
            reasons = gate.evaluate(pr)
    except Exception as e:  # noqa: BLE001
        # Fail closed: infra / GraphQL errors must not silently allow merges.
        return f"review-gate: gate check failed: {e}"
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
        # `$'\x67\x68' … pr merge` / `$(printf gh) … pr merge` — dynamic executable.
        if any(dynamic_gh_pr_merge(p) for p in parts):
            return (
                "review-gate: dynamic `gh` executable name "
                "(e.g. $'\\x67\\x68' / $(…) / `…`); "
                "run literal `gh -R owner/repo pr merge <n>`"
            )
        return None
    start = cwd or os.getcwd()
    segments, seg_err = iter_merge_segments(cmd, start)
    if seg_err:
        return seg_err
    if not segments:
        if segment_has_override(cmd):
            return None
        if not gh_is_direct_command(cmd):
            return (
                "review-gate: `gh pr merge` must be the directly executed command "
                "(no ssh/xargs/docker/… wrappers); run `gh -R owner/repo pr merge <n>`"
            )
        if scoped_dir_requires_repo(cmd) and not has_literal_repo(cmd):
            return (
                "review-gate: command-scoped directory change detected "
                "(e.g. `env -C`/`--chdir` / subshell `cd`); pass `-R owner/repo` explicitly"
            )
        if sets_git_location(cmd) and not has_literal_repo(cmd):
            return (
                "review-gate: GIT_DIR/GIT_CONFIG_* without literal `-R owner/repo`; "
                "pass `-R` (git location/config env is not modeled)"
            )
        return check_one(cmd, start)
    for segment, seg_cwd in segments:
        if segment_has_override(segment):
            continue
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
