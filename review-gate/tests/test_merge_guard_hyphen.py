"""merge-guard must not treat a hyphenated word like `pr-merge-flow` as `pr ... merge`.

Runs the real hook in a subprocess (test_check_review_gate.py monkeypatches the module globally).
Row: https://app.notion.com/p/41a4efecc95a81fba79fd4d79b23bf92
"""
import json
import os
import resource
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



# Runs the real guard's main() in a child with a profile hook counting every Python and C call it makes: a
# deterministic measure of the guard's work. Only stdout carries the count; the guard writes to stderr.
_COUNTER = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("merge_guard", sys.argv[1])
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
calls = 0
def count(frame, event, arg):
    global calls
    calls += 1
sys.setprofile(count)
rc = guard.main()
sys.setprofile(None)
sys.stdout.write(json.dumps({"rc": rc, "calls": calls}))
"""

# Profiled calls per command character. Today's guard spends at most ~196 on these commands on CPython 3.11-3.15;
# the 3.2.17 guard that took 5-40 s spent 264-452. A change that needs more raises this on purpose, in review.
CALLS_PER_CHAR = 250
# The guard denies on its own deadline (CHECK_DEADLINE_S) when its checks run too long; that deny is not this one.
DEADLINE_DENY = "did not finish within"


def counted(cmd):
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": tempfile.gettempdir()}
    proc = subprocess.run([sys.executable, "-c", _COUNTER, str(GUARD)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=120, env=ENV)
    out = json.loads(proc.stdout)
    if DEADLINE_DENY in proc.stderr:
        raise AssertionError(f"counted run hit the guard's own deadline:\n{proc.stderr}")
    return out["rc"], out["calls"], proc.stderr


# Counted calls cannot see work done inside one C call or in bytecode (slicing, `str.count` on a growing prefix,
# regex backtracking), so the child's CPU time is compared too. It self-normalizes to the runner's speed: a 10x
# longer command (about 16 KB to 160 KB) must cost under SIZE_RATIO * CPU_SLACK times the CPU. Today's guard
# measures 3.9-12.9x (mildly superlinear past 80 KB); a quadratic `cmd[:i].count(...)` in shell_comments 35-55x.
SIZE_RATIO, CPU_SLACK = 10, 2


def cpu_growth(build, small=2, reps=3):
    def spent(cmd):
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        hook(cmd)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        return (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime)
    # Small and big runs alternate so contention hits both; best of reps, since contention only ever adds time.
    runs = [(spent(build(small)), spent(build(small * SIZE_RATIO))) for _ in range(reps)]
    return min(b for _, b in runs) / min(s for s, _ in runs)


class BoundedWork(unittest.TestCase):
    """3.2.18 (Codex P1): the hook is killed at timeout_ms and Claude Code then drops the denial. No command may
    keep the guard busy: an 80 KB command used to take 6-47 s (the commit-hint regex, array_assembled_merge).

    3.3.3: measured by counted calls, not wall clock, which flaked at 1.004 s on a shared runner. Each command
    runs at two sizes: calls per character stay under CALLS_PER_CHAR and do not grow with size (linear work).
    Counted calls miss C-level and bytecode work, so child CPU time at 10x the size is bounded too. The full
    80 KB command must still get the real denial, not the guard's own deadline denial."""

    # name -> (build(n) giving a command of about n * 8 KB, expected exit code)
    CASES = {
        "git spam after a merge": (lambda n: "gh pr merge 7 # " + "git " * (2000 * n), 2),
        "git spam before a merge": (lambda n: "git " * (2000 * n) + "; gh pr merge 7", 2),
        "long commit message naming a merge": (lambda n: 'git commit -m "gh pr merge 5 ' + "x" * (8000 * n) + '"', 2),
        "long merge argument": (lambda n: "gh pr merge 7 --body '" + "y" * (8000 * n) + "'", 2),
        "long echo": (lambda n: "echo '" + "z" * (8000 * n) + "'", 0),
        # No size shortcut: every command is normalized and checked in full, so a long PR body is still allowed.
        "long pr body": (lambda n: "gh pr create --title t --body '" + "word " * (1600 * n) + "'", 0),
        # Codex P1 on f9f4dce: the size check read raw text, so a quote- or backslash-split `gh … merge` past
        # the limit was allowed although the normal checks deny it. It must read the same dequoted form.
        "merge split by quotes": (lambda n: ": '" + "z" * (8000 * n) + "'; g''h pr mer''ge 7 --squash", 2),
        "merge split by backslashes": (lambda n: ": '" + "z" * (8000 * n) + "'; g\\h pr mer\\ge 7 --squash", 2),
    }

    def test_huge_commands_do_linear_bounded_work(self):
        for label, (build, want) in self.CASES.items():
            with self.subTest(case=label):
                per_char = []
                for n in (1, 2):
                    cmd = build(n)
                    rc, calls, err = counted(cmd)
                    self.assertEqual(rc, want, err)
                    per_char.append(calls / len(cmd))
                self.assertLess(per_char[0], CALLS_PER_CHAR, f"{label}: {per_char[0]:.1f} calls per character")
                self.assertLessEqual(per_char[1], per_char[0] * 1.05, f"{label}: work grows faster than size")

    def test_huge_commands_get_the_real_decision(self):
        for label, (build, want) in self.CASES.items():
            with self.subTest(case=label):
                rc, err = hook(build(10))
                self.assertEqual(rc, want, err)
                self.assertNotIn(DEADLINE_DENY, err)

    def test_the_counter_sees_the_work(self):
        # The measure would pass a guard that does nothing: a command 10x longer must cost about 10x the calls.
        small, large = (counted(self.CASES["long merge argument"][0](n))[1] for n in (1, 10))
        self.assertGreater(large, small * 9)

    def test_huge_commands_cpu_grows_linearly(self):
        for label, (build, _) in self.CASES.items():
            with self.subTest(case=label):
                growth = cpu_growth(build)
                self.assertLess(growth, SIZE_RATIO * CPU_SLACK, f"{label}: CPU grew {growth:.1f}x for {SIZE_RATIO}x the size")

    def test_normal_size_denials_are_unchanged(self):
        rc, err = hook("gh pr merge 5 --squash")
        self.assertEqual(rc, 2, err)
        self.assertNotIn("git commit -F <file>", err)
        self.assertNotIn("too long", err)
        rc, err = hook('git commit -m "docs: explain gh pr merge --squash"')
        self.assertEqual(rc, 2, err)
        self.assertIn("git commit -F <file>", err)


class OneNormalizationPath(unittest.TestCase):
    """3.2.18 (Codex high on 921eff6): the guard decided on text it had not normalized. Bash joins
    backslash-newline and decodes ANSI-C `$'...'` before it runs a word, so the guard must too, first, and its
    loose `gh … pr … merge` scan must stay linear so no input outlives the hook timeout."""

    SPELLINGS = {"ansi-c": "$'\\x67\\x68' pr $'mer\\x67e' 7", "continuation": "g\\\nh pr mer\\\nge 7"}

    def test_executable_spellings_deny_with_and_without_padding(self):
        for label, tail in self.SPELLINGS.items():
            for pad in ("", ": '" + "z" * 16001 + "'; "):
                with self.subTest(case=label, padded=bool(pad)):
                    rc, err = hook(pad + tail)
                    self.assertEqual(rc, 2, err)

    def test_repeated_gh_pr_words_deny_with_linear_work(self):
        # The old `.*`-joined regex backtracked in C, where counted calls cannot see it; at ~80 KB it ran past
        # the guard's own deadline, so the real denial (not the deadline one) is what proves the scan stays linear.
        per_char = []
        for n in (1333, 2666):  # ~8 KB, ~16 KB
            cmd = "gh pr " * n + "; g''h pr mer''ge 7"
            rc, calls, err = counted(cmd)
            self.assertEqual(rc, 2, err)
            per_char.append(calls / len(cmd))
        self.assertLess(per_char[0], CALLS_PER_CHAR)
        self.assertLessEqual(per_char[1], per_char[0] * 1.05, "work grows faster than size")
        growth = cpu_growth(lambda n: "gh pr " * (1333 * n) + "; g''h pr mer''ge 7")
        self.assertLess(growth, SIZE_RATIO * CPU_SLACK, f"CPU grew {growth:.1f}x for {SIZE_RATIO}x the size")
        rc, err = hook("gh pr " * 13333 + "; g''h pr mer''ge 7")  # ~80 KB
        self.assertEqual(rc, 2, err)
        self.assertNotIn(DEADLINE_DENY, err)

    def test_benign_commands_still_pass(self):
        # Quoted `gh pr merge` text stays blocked by design (QuotedMentions, #130); these are the benign shapes.
        for cmd in ("gh pr view 7", "gh pr checks 7 \\\n  --watch=false", "echo 'see pr-merge-flow'",
                    "echo $'tab\\there'", "ls \\\n  -la", "echo $'it\\'s'"):
            with self.subTest(cmd=cmd):
                rc, err = hook(cmd)
                self.assertEqual(rc, 0, err)

    def test_deadline_denies_instead_of_timing_out(self):
        import importlib.util, io
        spec = importlib.util.spec_from_file_location("mg_deadline", GUARD)
        mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)
        mg.CHECK_DEADLINE_S = 0.01
        mg.check_command = lambda cmd, cwd=None: __import__("time").sleep(5)
        stdin, stderr = sys.stdin, sys.stderr
        sys.stdin, sys.stderr = io.StringIO(json.dumps({"tool_input": {"command": "gh pr view 7"}})), io.StringIO()
        try:
            rc = mg.main()
            msg = sys.stderr.getvalue()
        finally:
            sys.stdin, sys.stderr = stdin, stderr
        self.assertEqual(rc, 2)
        self.assertIn("did not finish", msg)


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
