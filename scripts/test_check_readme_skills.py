"""Tests for check-readme-skills.py.

Run: python3 -m unittest discover -s scripts -p 'test_*.py'
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
_spec = importlib.util.spec_from_file_location(
    "check_readme_skills", Path(__file__).resolve().parent / "check-readme-skills.py"
)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def repo(tmp: str, readme: str, skills: dict[str, str]) -> Path:
    root = Path(tmp)
    for name, rel in skills.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(f"---\nname: {name}\nversion: 1.0.0\n---\n")
    (root / "README.md").write_text(readme)
    return root


class CheckReadmeSkills(unittest.TestCase):
    def test_all_linked_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, "- [**a**](a/SKILL.md) - x\n- [**b**](docs/b/SKILL.md) - y\n",
                        {"a": "a/SKILL.md", "b": "docs/b/SKILL.md"})
            self.assertEqual(check.problems(root), [])

    def test_missing_skill_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, "- [**a**](a/SKILL.md) - x\n", {"a": "a/SKILL.md", "b": "b/SKILL.md"})
            self.assertEqual(len(check.problems(root)), 1)
            self.assertIn("b: not in README.md", check.problems(root)[0])

    def test_unlinked_bold_name_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, "- **a** - x\n", {"a": "a/SKILL.md"})
            self.assertIn("a: not in README.md", check.problems(root)[0])

    def test_wrong_and_dead_links_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, "- [**a**](old/SKILL.md) - x\n", {"a": "a/SKILL.md"})
            errs = check.problems(root)
            self.assertTrue(any("but the skill is at a/SKILL.md" in e for e in errs))
            self.assertTrue(any("old/SKILL.md, which does not exist" in e for e in errs))

    def test_non_skill_bold_links_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, "- [**a**](a/SKILL.md) - x\nSee [**Notion**](https://notion.so)\n",
                        {"a": "a/SKILL.md"})
            self.assertEqual(check.problems(root), [])

    def test_duplicate_entry_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, "- [**a**](old/SKILL.md) - x\n- [**a**](a/SKILL.md) - x\n",
                        {"a": "a/SKILL.md"})
            errs = check.problems(root)
            self.assertIn("a: listed more than once in README.md", errs)
            self.assertTrue(any("old/SKILL.md, which does not exist" in e for e in errs))

    def test_node_modules_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, "- [**a**](a/SKILL.md) - x\n",
                        {"a": "a/SKILL.md", "dep": "a/node_modules/dep/SKILL.md"})
            self.assertEqual(check.problems(root), [])


if __name__ == "__main__":
    unittest.main()
