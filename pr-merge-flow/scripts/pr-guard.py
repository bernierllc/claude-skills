#!/usr/bin/env python3
"""PreToolUse guard for PR discipline. Exit 2 blocks the tool call; the stderr
text is what the agent sees.

1. No base sync into a mergeable PR. `git merge|pull|rebase <base>` on a branch
   whose open PR GitHub already reports as mergeable restarts CI and review for
   nothing. Allowed when the PR is DIRTY (a real conflict) or BEHIND (the base
   requires up-to-date branches), and whenever there is no open PR or GitHub
   can't be asked. Override when a specific base commit is genuinely needed:
   put `sync-base: <reason>` in the command (e.g. a trailing `# sync-base: ...`).
2. PRs open ready for review, never as drafts (`gh pr create --draft`,
   `gh pr ready --undo`).
3. In a fork with no `gh repo set-default`, `gh pr create` without `-R/--repo`
   targets the UPSTREAM repo (a claude-skills PR landed on anthropics/skills
   this way, 2026-09-28). Blocked until the target is explicit.

Every tool call passes through here, so non-Bash input exits at once.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

SYNC_SUBCOMMANDS = {"merge", "pull", "rebase"}
# Anything else, including UNKNOWN, fails open.
MERGEABLE = {"CLEAN", "UNSTABLE", "BLOCKED", "HAS_HOOKS"}
CONTROL_FLAGS = {"--abort", "--continue", "--skip", "--quit", "--edit-todo"}
FLAGS_WITH_VALUE = {"-m", "-F", "-X", "-s", "--message", "--file", "--strategy",
                    "--strategy-option", "--exec", "-x", "--cleanup"}


KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "}"}
OPERATORS = set(";&|\n()")


def strip_comments_and_heredocs(cmd):
    """Drop `#` comments and heredoc bodies, keeping the newlines that end them.

    shlex gets both wrong: its comments swallow the newline (and start mid-word),
    and it parses heredoc bodies as shell, so one stray quote hides every later
    command. Bash rules: `#` starts a comment only at the start of an unquoted word.

    ponytail: `$(...)`/backtick nesting isn't tracked; a `#` or `<<` inside one is
    treated as top-level. Worst case is a missed or extra block, never a crash.
    """
    out, i, n, quote, pending = [], 0, len(cmd), None, []
    while i < n:
        c = cmd[i]
        if quote:
            out.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                out.append(cmd[i + 1])
                i += 1
            elif c == quote:
                quote = None
            i += 1
        elif c == "\\" and i + 1 < n:
            out.append(cmd[i:i + 2])
            i += 2
        elif c in "'\"":
            quote = c
            out.append(c)
            i += 1
        elif c == "#" and (not out or out[-1][-1] in " \t\r\n;&|()"):
            while i < n and cmd[i] != "\n":
                i += 1
        elif cmd.startswith("<<", i) and not cmd.startswith("<<<", i):
            m = re.match(r"""<<(-?)[ \t]*((?:\\.|'[^']*'|"[^"]*"|[^\s;&|()<>'"\\])+)""", cmd[i:])
            if m:
                try:  # the delimiter is the word after quote removal: <<'E'OF and <<E\OF end at EOF
                    delim = "".join(shlex.split(m.group(2)))
                except ValueError:
                    delim = m.group(2)
                pending.append((delim, bool(m.group(1))))
                out.append(m.group(0))
                i += m.end()
            else:
                out.append(c)
                i += 1
        elif c == "\n" and pending:
            out.append(c)
            lines, j = cmd[i + 1:].split("\n"), i + 1
            for delim, dash in pending:
                for k, line in enumerate(lines):
                    if (line.lstrip("\t") if dash else line) == delim:
                        j += sum(len(x) + 1 for x in lines[:k + 1])
                        lines = lines[k + 1:]
                        break
                else:  # no terminator: keep the rest, so nothing after it goes unchecked
                    break
            pending = []
            i = min(j, n)
        else:
            out.append(c)
            i += 1
    return "".join(out)


def segments(cmd):
    """Split a shell command into argv lists, one per simple command.

    Tokenizes first, so operators inside quotes stay in their argument and
    backslash-newline continues the command, as in Bash.
    """
    cmd = strip_comments_and_heredocs(cmd.replace("\\\n", " "))
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|\n()")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        tokens = list(lex)
    except ValueError:
        # Unbalanced quotes: fall back to words, but keep each line its own command.
        tokens = [t for line in cmd.split("\n") for t in line.split() + ["\n"]]
    argv = []
    for t in tokens + [";"]:
        if t and set(t) <= OPERATORS:
            while argv and argv[0] in KEYWORDS:
                argv.pop(0)
            if argv:
                yield argv
            argv = []
        else:
            argv.append(t)


def sync_calls(cmd, cwd):
    """Yield (dir, subcommand, refs) for each git merge/pull/rebase that names a ref.

    Tracks `cd DIR` and `git -C DIR`. A dir containing `$` or a backtick can't be
    resolved statically; it is yielded as-is so the caller can refuse it.
    """
    for argv in segments(cmd):
        if argv[0] == "cd" and len(argv) > 1:
            cwd = argv[1] if "$" in argv[1] else os.path.join(cwd, os.path.expanduser(argv[1]))
            continue
        if argv[0] != "git":
            continue
        d, i = cwd, 1
        while i < len(argv) and argv[i].startswith("-"):
            if argv[i] == "-C" and i + 1 < len(argv):
                d = argv[i + 1] if "$" in argv[i + 1] else os.path.join(d, os.path.expanduser(argv[i + 1]))
                i += 2
            elif argv[i] == "-c":
                i += 2
            else:
                i += 1
        if i >= len(argv) or argv[i] not in SYNC_SUBCOMMANDS:
            continue
        sub, rest, refs, skip = argv[i], argv[i + 1:], [], False
        if CONTROL_FLAGS & set(rest):
            continue
        for a in rest:
            if skip:
                skip = False
            elif a in FLAGS_WITH_VALUE:
                skip = True
            elif not a.startswith("-"):
                refs.append(a)
        if refs:
            yield d, sub, refs


def names_base(refs, base):
    """True when a ref spells the PR base: bare, refs/heads/, <remote>/ or refs/remotes/<remote>/.

    ponytail: string match, not commit resolution; a local branch named `x/<base>`
    also matches (the block is overridable). Resolve with rev-parse if that bites.
    """
    for r in refs:
        r = r.removeprefix("refs/heads/")
        if r.startswith("refs/remotes/"):
            r = r.removeprefix("refs/remotes/")
        if r == base or (r.endswith("/" + base) and "/" not in r[:-len(base) - 1]):
            return True
    return False


def pr_state(d):
    """Return (baseRefName, mergeStateStatus) for the open PR of d's branch, or None."""
    try:
        branch = subprocess.run(["git", "-C", d, "rev-parse", "--abbrev-ref", "HEAD"],
                                capture_output=True, text=True, timeout=5).stdout.strip()
        if not branch or branch == "HEAD":
            return None
        for attempt in range(2):
            out = subprocess.run(
                ["gh", "pr", "view", branch, "--json", "state,baseRefName,mergeStateStatus"],
                cwd=d, capture_output=True, text=True, timeout=8)
            if out.returncode != 0:
                return None
            pr = json.loads(out.stdout)
            if pr.get("state") != "OPEN":
                return None
            # GitHub computes mergeability lazily; the first read is often UNKNOWN.
            if pr.get("mergeStateStatus") != "UNKNOWN" or attempt:
                return pr["baseRefName"], pr["mergeStateStatus"]
            time.sleep(2)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return None


GH_ALIASES = {"new": "create"}


def gh_pr(argv):
    """Return (subcommand, has_repo_flag) for a `gh pr <sub>` call, else None.

    `-R/--repo` is inherited, so it may come before `pr`; `new` is an alias of `create`.
    """
    if argv[0] != "gh":
        return None
    pos, has_repo, skip = [], False, False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a in ("-R", "--repo"):
            has_repo = skip = True
        elif a.startswith("--repo=") or (a.startswith("-R") and len(a) > 2):
            has_repo = True
        elif not a.startswith("-"):
            pos.append(a)
    if len(pos) < 2 or pos[0] != "pr":
        return None
    return GH_ALIASES.get(pos[1], pos[1]), has_repo


def draft_violation(cmd):
    for argv in segments(cmd):
        pr = gh_pr(argv)
        if not pr:
            continue
        if pr[0] == "create" and any(a in ("--draft", "-d") or a.startswith("--draft=") for a in argv):
            return True
        if pr[0] == "ready" and "--undo" in argv:
            return True
    return False


def creates_pr_without_repo(cmd):
    return any((pr := gh_pr(argv)) and pr == ("create", False) for argv in segments(cmd))


def unpinned_fork(cwd):
    """Return 'owner/repo (fork of parent)' when cwd is a fork with no gh default repo."""
    try:
        if subprocess.run(["gh", "repo", "set-default", "--view"], cwd=cwd,
                          capture_output=True, text=True, timeout=8).stdout.strip():
            return None
        out = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner,isFork,parent"],
                             cwd=cwd, capture_output=True, text=True, timeout=8)
        r = json.loads(out.stdout) if out.returncode == 0 else {}
        if r.get("isFork") and r.get("parent"):
            p = r["parent"]
            return f"{r['nameWithOwner']} (fork of {p['owner']['login']}/{p['name']})"
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None
    return None


def check(cmd, cwd):
    """Return a block message, or None to allow."""
    if draft_violation(cmd):
        return ("Blocked: PRs open ready for review, never as drafts. Drop --draft / --undo. "
                "If the user explicitly asked for a draft, ask them to run it with `! gh pr create --draft ...`.")
    if creates_pr_without_repo(cmd):
        fork = unpinned_fork(cwd)
        if fork:
            return (f"Blocked: {fork} has no `gh repo set-default`, so `gh pr create` would open the "
                    "PR on the upstream repo. Pass `-R <owner>/<repo>` or run "
                    "`gh repo set-default <owner>/<repo>` first.")
    if "sync-base:" in cmd:
        return None
    for d, sub, refs in sync_calls(cmd, cwd):
        if "$" in d or "`" in d:
            return (f"Blocked: `git {sub}` runs in a directory the guard can't resolve ({d}). "
                    "Don't sync the base into every worktree in a loop: most of those PRs are already "
                    "mergeable, and each sync restarts their CI and review. Run it per worktree with a "
                    "literal path so each PR is checked, or add `# sync-base: <reason>` if you need a "
                    "specific base commit.")
        state = pr_state(d)
        if not state:
            continue
        base, status = state
        if names_base(refs, base) and status in MERGEABLE:
            return (f"Blocked: this branch's PR into `{base}` is {status}, so GitHub can already merge it. "
                    f"Pulling `{base}` in restarts CI and review for nothing. Sync only when "
                    "`gh pr view --json mergeStateStatus` says DIRTY (a conflict). To land the PR: "
                    "`gh pr merge <n> --auto --squash` (or `--merge` for promotions). If you truly need "
                    f"a commit from `{base}` (a fix your tests depend on), add `# sync-base: <reason>`.")
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    msg = check(data.get("tool_input", {}).get("command", ""), data.get("cwd") or os.getcwd())
    if msg:
        print(msg, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
