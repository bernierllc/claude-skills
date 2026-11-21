"""merge-guard must not treat a hyphenated word like `pr-merge-flow` as `pr ... merge`.

Runs the real hook in a subprocess (test_check_review_gate.py monkeypatches the module globally).
Row: https://app.notion.com/p/41a4efecc95a81fba79fd4d79b23bf92
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "merge-guard.py"


# Keep the hook's best-effort feedback logging away from the real feedback store.
_HOME = tempfile.mkdtemp(prefix="rg-hook-home-")
ENV = {k: v for k, v in os.environ.items() if k not in ("AGENT_FEEDBACK_BIN", "CLAUDE_PROJECT_DIR")}
ENV.update(HOME=_HOME, CLAUDE_PROJECT_DIR=_HOME)


def hook(cmd, tool="Bash", raw=None, argv=None):
    payload = {"tool_name": tool, "tool_input": {"command": cmd}, "cwd": tempfile.gettempdir()}
    proc = subprocess.run(argv or [sys.executable, str(GUARD)], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, timeout=60, env=ENV)
    return proc.returncode, proc.stderr


class AnyShellToolName(unittest.TestCase):
    def test_merge_blocks_under_any_tool_name(self):
        for tool in ("Bash", "mcp__skin_target__garment_Bash", "run_shell_command", "BashTool", ""):
            with self.subTest(tool=tool):
                self.assertEqual(hook("gh pr merge 5 --squash", tool=tool)[0], 2)

    def test_no_command_passes_and_unreadable_input_blocks(self):
        self.assertEqual(hook("", tool="Edit")[0], 0)
        self.assertEqual(hook("", raw="not json")[0], 2)
        self.assertEqual(hook("", raw="[1]")[0], 2)

    def test_crash_fails_closed(self):
        # ~1000-deep `$( … )` nest: RecursionError used to exit 1, a non-blocking hook error, so the merge ran.
        n = 1000
        cmd = "echo " + "$( echo " * (n - 1) + "$( gh pr merge 5 -R o/r )" + " )" * (n - 1)
        rc, err = hook(cmd)
        self.assertEqual(rc, 2, err[-300:])
        self.assertIn("crashed (RecursionError); blocked", err)

    def test_crash_with_failing_feedback_log_still_blocks(self):
        # fb_log raising inside the crash handler (Path.home() → RuntimeError) must not turn the block into exit 1.
        n = 1000
        cmd = "echo " + "$( echo " * (n - 1) + "$( gh pr merge 5 -R o/r )" + " )" * (n - 1)
        code = ("import pathlib, runpy, sys\n"
                "def _boom(*a, **k): raise RuntimeError('no home')\n"
                "pathlib.Path.home = classmethod(_boom)\n"
                f"runpy.run_path({str(GUARD)!r}, run_name='__main__')\n")
        rc, err = hook(cmd, argv=[sys.executable, "-c", code])
        self.assertEqual(rc, 2, err[-300:])
        self.assertIn("crashed (RecursionError); blocked", err)

    def test_missing_gate_module_blocks(self):
        # merge-guard copied without check-review-gate.py (half-applied upgrade): import failure must exit 2.
        d = tempfile.mkdtemp(prefix="rg-lonely-")
        try:
            shutil.copy(GUARD, d)
            rc, err = hook("gh pr merge 5 --squash", argv=[sys.executable, str(Path(d) / GUARD.name)])
        finally:
            shutil.rmtree(d)
        self.assertEqual(rc, 2, err[-300:])
        self.assertIn("cannot load check-review-gate.py", err)

    def test_input_and_cmd_aliases_are_checked(self):
        for payload in ({"input": {"command": "gh pr merge 5 --squash"}},
                        {"tool_input": {"cmd": "gh pr merge 5 --squash"}}):
            with self.subTest(payload=payload):
                self.assertEqual(hook("", raw=json.dumps({**payload, "cwd": tempfile.gettempdir()}))[0], 2)


class HyphenatedMentions(unittest.TestCase):
    def test_mention_only_commands_pass(self):
        for cmd in ['grep -rn pr-merge-flow . "$@"',
                    'ls ~/.claude/skills/pr-merge-flow "$@"',
                    'set -- pr-merge-flow; echo "$@"',
                    'args=(pr-merge-flow docs); ls "${args[@]}"',
                    "aec install skill pr-merge-flow </dev/null"]:
            with self.subTest(cmd=cmd):
                rc, err = hook(cmd)
                self.assertEqual(rc, 0, err)

    def test_real_merges_still_block(self):
        for cmd in ['set -- pr merge 5; gh "$@"',
                    'args=(pr merge 5); gh "${args[@]}"',
                    "g''h pr merge 5 --squash",
                    'g"h" pr merge 5',
                    "gh pr merge 5 --squash"]:
            with self.subTest(cmd=cmd):
                rc, err = hook(cmd)
                self.assertEqual(rc, 2, f"not blocked: {cmd}\n{err}")


class QuotedMentions(unittest.TestCase):
    """`gh pr merge` quoted as data still blocks; no inert-mention allowlist (#130 round 1, CS-REVIEW-GATE-FIXES)."""

    def test_hyphenated_names_pass(self):
        for cmd in ['git commit -m "vendor pr-merge-flow"', "grep pr merge"]:
            with self.subTest(cmd=cmd):
                rc, err = hook(cmd)
                self.assertEqual(rc, 0, err)

    def test_quoted_data_mentions_block(self):
        # Kept from 3.2.14: an allowlist for these lost blocks (#130 Codex P1-a/P1-b), so it was dropped.
        for cmd in ['grep -rn "gh pr merge" review-gate/SKILL.md',
                    "cd review-gate && grep -c 'gh pr merge' SKILL.md",
                    'grep -e "gh pr merge 5 --admin" -e "gh pr merge 5 --auto" file',
                    'git add "notes on gh pr merge.md"']:
            with self.subTest(cmd=cmd):
                rc, err = hook(cmd)
                self.assertEqual(rc, 2, f"not blocked: {cmd}\n{err}")

    def test_runnable_forms_still_block(self):
        for cmd in ['gh pr merge "$@"',
                    "gh pr merge 12 -R o/r --squash",
                    'f() { gh pr merge "$@"; }; f 5',
                    'grep x; gh pr merge 5',
                    'grep x & gh pr merge 5',
                    'grep "gh pr merge 5" notes | sh',
                    'grep -h "gh pr merge 5" notes > run.sh',
                    'grep x <(gh pr merge 5)',
                    'git commit -m "$(gh pr merge 5)"',
                    'git commit -m "`gh pr merge 5`"',
                    'git -c core.editor=x commit -m "gh pr merge 5"',
                    'GIT_EDITOR=x git commit -m "gh pr merge 5"',
                    "alias grep='bash -c'\ngrep 'gh pr merge 5'",
                    "hash -p /bin/bash grep; grep -c 'gh pr merge 5'",
                    "grep () { bash -c 'gh pr merge 5'; }; grep x",
                    "bash -c 'grep x; gh pr merge 5'",
                    "rg --pre sh 'gh pr merge 5' notes",
                    "echo 'gh pr merge 5' && grep x",
                    # #130 Codex P1-a: an escaped quote switches quoting, hiding $( ) and backticks from the scan.
                    'git commit -m "\\"\'$(gh pr merge 5 --admin)"\\\'',
                    'git commit -m "\\"\'`gh pr merge 5 --auto`"\\\'',
                    'grep -e "\\"\'`gh pr merge 5 --auto`"\\\' file',
                    'grep "\\"\'$(gh pr merge 5 --admin)"\\\' file']:
            with self.subTest(cmd=cmd):
                rc, err = hook(cmd)
                self.assertEqual(rc, 2, f"not blocked: {cmd}\n{err}")

    def test_commit_message_mentions_block_and_name_the_file_escape(self):
        # #130 Codex P1-b: commit hooks (commit-msg, post-commit) can run the message text.
        for cmd in ['git commit --amend -m "gh pr merge 5 --admin"',
                    'git commit --amend -m "gh pr merge 5 --auto"',
                    'cd /tmp && git commit --amend -m "gh pr merge 5 --admin"',
                    'git commit -m "docs: explain gh pr merge --squash"',
                    'git add -A && git commit -m "x" -m "never run gh pr merge 5 by hand"',
                    "git commit -m '$(gh pr merge 5)'"]:
            with self.subTest(cmd=cmd):
                rc, err = hook(cmd)
                self.assertEqual(rc, 2, f"not blocked: {cmd}\n{err}")
                self.assertIn("git commit -F <file>", err)



class BoundedWork(unittest.TestCase):
    """3.2.18 (Codex P1): the hook is killed at timeout_ms and Claude Code then drops the denial. No command may
    keep the guard busy: an 80 KB command used to take 6-47 s (the commit-hint regex, array_assembled_merge)."""

    def test_huge_commands_deny_well_under_a_second(self):
        import time
        for label, cmd in {
            "git spam after a merge": "gh pr merge 7 # " + "git " * 20000,
            "git spam before a merge": "git " * 20000 + "; gh pr merge 7",
            "long commit message naming a merge": 'git commit -m "gh pr merge 5 ' + "x" * 80000 + '"',
            "long merge argument": "gh pr merge 7 --body '" + "y" * 80000 + "'",
        }.items():
            with self.subTest(case=label):
                started = time.monotonic()
                rc, err = hook(cmd)
                self.assertLess(time.monotonic() - started, 1.0, label)
                self.assertEqual(rc, 2, err)

    def test_normal_size_denials_are_unchanged(self):
        rc, err = hook("gh pr merge 5 --squash")
        self.assertEqual(rc, 2, err)
        self.assertNotIn("git commit -F <file>", err)
        self.assertNotIn("too long", err)
        rc, err = hook('git commit -m "docs: explain gh pr merge --squash"')
        self.assertEqual(rc, 2, err)
        self.assertIn("git commit -F <file>", err)

    def test_huge_commands_without_merge_pass(self):
        self.assertEqual(hook("echo '" + "z" * 80000 + "'")[0], 0)


class DirPathSymlink(unittest.TestCase):
    """3.2.18 (Codex P2): `<link>/..` must mean the parent of the link's target, as the shell resolves it, not the
    lexical parent of the link; otherwise the guard checks a different checkout than the command runs in."""

    def test_dir_path_resolves_symlinks_before_dotdot(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mg_symlink", GUARD)
        mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)
        with tempfile.TemporaryDirectory() as tmp:
            repo_a = Path(tmp) / "repoA"; (repo_a / "sub").mkdir(parents=True)
            (Path(tmp) / "elsewhere").mkdir()
            link = Path(tmp) / "elsewhere" / "link"; link.symlink_to(repo_a / "sub")
            got = mg.payload_cwd({"cwd": "/tmp/session"}, {"dir_path": f"{link}/../"})
            self.assertEqual(os.path.realpath(got), os.path.realpath(repo_a))
            self.assertEqual(got, os.path.realpath(repo_a))  # already resolved: later joins cannot collapse `..`


if __name__ == "__main__":
    unittest.main()
