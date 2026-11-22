import re
import subprocess
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
from finding_id import CATEGORIES, finding_id  # noqa: E402


class FindingIdTest(unittest.TestCase):
    def test_stable_and_formatted(self):
        a = finding_id("authz", "src/app/api/admin/route.ts", "PUT /api/admin/settings")
        self.assertRegex(a, r"^NSR-AUTHZ-[0-9a-f]{8}$")
        self.assertEqual(a, finding_id("AUTHZ", "./src/app/api/admin/route.ts", " PUT /api/admin/settings "))

    def test_equivalent_paths_share_an_id(self):
        base = finding_id("AUTHZ", "src/app.py", "f")
        for spelling in ["src//app.py", "src/./app.py", "./src/app.py", "src\\app.py", "src/x/../app.py"]:
            with self.subTest(spelling=spelling):
                self.assertEqual(base, finding_id("AUTHZ", spelling, "f"))

    def test_inputs_change_id(self):
        base = finding_id("AUTHZ", "a.py", "f")
        self.assertNotEqual(base, finding_id("TENANT", "a.py", "f"))
        self.assertNotEqual(base, finding_id("AUTHZ", "b.py", "f"))
        self.assertNotEqual(base, finding_id("AUTHZ", "a.py", "g"))

    def test_rejects_bad_input(self):
        for args in [("a", "x.py", "f"), ("AUTHZ", "/abs/x.py", "f"), ("AUTHZ", "../x.py", "f"),
                     ("AUTHZ", "C:/x.py", "f"), ("AUTHZ", "c:x.py", "f"), ("AUTHZ", "\\\\host\\x.py", "f"),
                     ("AUTHZ", "a/../../x.py", "f"), ("AUTHZ", ".", "f"),
                     ("AUTHZ", "x.py", " "), ("AU-THZ", "x.py", "f"), ("AUTH", "x.py", "f")]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                finding_id(*args)

    def test_categories_match_skill_table(self):
        table = re.findall(r"^\| `([A-Z][A-Z0-9]+)` \|", (SKILL / "SKILL.md").read_text(), re.M)
        self.assertEqual(len(table), len(set(table)))
        self.assertEqual(set(table), CATEGORIES)

    def test_cli(self):
        script = SKILL / "scripts" / "finding_id.py"
        ok = subprocess.run([sys.executable, "-I", str(script), "DEP", "package-lock.json", "minimist"],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout.strip(), finding_id("DEP", "package-lock.json", "minimist"))
        bad = subprocess.run([sys.executable, "-I", str(script), "DEP"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
