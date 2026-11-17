"""merge-guard must not treat a hyphenated word like `pr-merge-flow` as `pr ... merge`.

Runs the real hook in a subprocess (test_check_review_gate.py monkeypatches the module globally).
Row: https://app.notion.com/p/41a4efecc95a81fba79fd4d79b23bf92
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "merge-guard.py"


def hook(cmd, tool="Bash", raw=None):
    payload = {"tool_name": tool, "tool_input": {"command": cmd}, "cwd": tempfile.gettempdir()}
    proc = subprocess.run([sys.executable, str(GUARD)], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, timeout=60)
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


if __name__ == "__main__":
    unittest.main()
