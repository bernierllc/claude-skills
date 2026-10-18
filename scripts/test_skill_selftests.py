"""Runs skill selftests that need no installed hook (CI's repo script tests pick this up)."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# git-conventions' selftest checks the hook installed in a repo, so it is not listed here.
SELFTESTS = ["typecheck-on-edit/scripts/selftest.sh"]


class SkillSelftests(unittest.TestCase):
    def test_selftests_pass(self):
        for rel in SELFTESTS:
            with self.subTest(selftest=rel):
                r = subprocess.run(["bash", str(ROOT / rel)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
