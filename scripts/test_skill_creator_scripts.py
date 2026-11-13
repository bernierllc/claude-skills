"""Regression tests for the skill-creator fixes layered on the upstream sync."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SC = Path(__file__).resolve().parent.parent / "skill-creator"
sys.path.insert(0, str(SC))
sys.path.insert(0, str(SC / "eval-viewer"))

from scripts.quick_validate import validate_skill  # noqa: E402
from scripts.aggregate_benchmark import load_run_results  # noqa: E402
from generate_review import generate_html  # noqa: E402


class SkillCreatorTests(unittest.TestCase):
    def test_validator_allows_repo_metadata_keys(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "SKILL.md").write_text(
                "---\nname: demo\ndescription: A demo\nversion: 1.0.0\nauthor: x\n"
                "source: s\nsource_path: p\ndependencies: []\n---\nbody\n"
            )
            ok, msg = validate_skill(d)
            self.assertTrue(ok, msg)

    def test_viewer_escapes_script_close(self):
        runs = [{"id": "r", "prompt": "p", "outputs": [{"name": "a", "type": "text", "content": "</script><b>"}]}]
        html = generate_html(runs, "demo")
        self.assertNotIn("</script><b>", html)

    def test_aggregate_flat_layout_reads_tokens_with_grading_timing(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "eval-0" / "with_skill"
            (run / "outputs").mkdir(parents=True)
            (run / "grading.json").write_text(json.dumps(
                {"summary": {"pass_rate": 1.0, "passed": 1, "failed": 0, "total": 1},
                 "timing": {"total_duration_seconds": 5.0}}))
            (run / "timing.json").write_text(json.dumps({"total_duration_seconds": 5.0, "total_tokens": 1234}))
            res = load_run_results(Path(d))
            self.assertEqual(res["with_skill"][0]["tokens"], 1234)
            self.assertEqual(res["with_skill"][0]["time_seconds"], 5.0)


if __name__ == "__main__":
    unittest.main()
