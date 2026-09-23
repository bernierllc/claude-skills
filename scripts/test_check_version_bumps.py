"""Tests for check-version-bumps.py against real throwaway git repos.

Run: python3 -m unittest discover -s scripts -p 'test_*.py'
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-version-bumps.py"


def skill_md(name: str, version: str) -> str:
    return f"---\nname: {name}\nversion: {version}\n---\n\n# {name}\n"


class CheckVersionBumps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write("alpha/SKILL.md", skill_md("alpha", "1.0.0"))
        self.write("alpha/references/notes.md", "one\n")
        self.write("suite/SKILL.md", skill_md("suite", "2.0.0"))
        self.write("suite/inner/SKILL.md", skill_md("inner", "0.1.0"))
        self.write("README.md", "root\n")
        self.commit("base")
        self.git("branch", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def run_check(self):
        return subprocess.run(
            ["python3", str(SCRIPT), "base"], cwd=self.repo, capture_output=True, text=True
        )

    def test_unbumped_skill_md_change_fails(self):
        self.write("alpha/SKILL.md", skill_md("alpha", "1.0.0") + "new rule\n")
        self.commit("change")
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("alpha", r.stdout)

    def test_unbumped_reference_file_change_fails(self):
        self.write("alpha/references/notes.md", "two\n")
        self.commit("change")
        self.assertEqual(self.run_check().returncode, 1)

    def test_bumped_change_passes(self):
        self.write("alpha/SKILL.md", skill_md("alpha", "1.1.0") + "new rule\n")
        self.commit("change")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_version_compared_numerically(self):
        self.write("alpha/SKILL.md", skill_md("alpha", "1.0.10"))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "to 1.0.10")
        self.git("branch", "-f", "base")
        self.write("alpha/SKILL.md", skill_md("alpha", "1.0.9"))
        self.commit("downgrade")
        self.assertEqual(self.run_check().returncode, 1)

    def test_nested_skill_owns_its_files(self):
        self.write("suite/inner/SKILL.md", skill_md("inner", "0.2.0") + "x\n")
        self.commit("bump inner only")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout)  # suite itself untouched

    def test_new_skill_and_non_skill_files_pass(self):
        self.write("fresh/SKILL.md", skill_md("fresh", "0.1.0"))
        self.write("README.md", "changed\n")
        self.commit("add")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
