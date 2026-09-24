"""Tests for generate-manifest.py.

Run: python3 -m unittest discover -s scripts -p 'test_*.py'
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "generate_manifest", Path(__file__).resolve().parent / "generate-manifest.py"
)
generate_manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_manifest)


def write_skill(root: Path, rel: str, name: str) -> None:
    path = root / rel / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"---\nname: {name}\nversion: 1.0.0\n---\n")


class BuildSkills(unittest.TestCase):
    def test_duplicate_names_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "gdocs", "gdocs")
            write_skill(root, "document-skills/gdocs", "gdocs")
            with self.assertRaises(generate_manifest.DuplicateSkillName) as ctx:
                generate_manifest.build_skills(root)
            self.assertIn("document-skills/gdocs/SKILL.md", str(ctx.exception))

    def test_unique_names_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "a", "a")
            write_skill(root, "b", "b")
            self.assertEqual(set(generate_manifest.build_skills(root)), {"a", "b"})


if __name__ == "__main__":
    unittest.main()
