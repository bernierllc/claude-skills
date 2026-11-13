"""Hook scripts log their own crashes to feedback-loop, best-effort, and still fail loudly."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = {
    "pr-merge-flow/scripts/pr-guard.py": "hook:pr-merge-flow/pmf-pr-guard",
    "review-gate/scripts/merge-guard.py": "hook:review-gate/rg-merge-guard",
    "verification-writer/scripts/scan-versions.py": "hook:verification-writer/vw-scan-on-edit",
    "verification-writer/scripts/route-scanner.py": "hook:verification-writer/vw-route-scan-on-edit",
    "api-verification-writer/scripts/scan-api-surfaces.py": "hook:api-verification-writer/avw-scan-on-edit",
}
# Subjects must name hook ids that exist in the owning skill's hooks.json.
FAKE_BIN = "import json, sys; open(sys.argv[0] + '.calls', 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"


class HookFeedbackTest(unittest.TestCase):
    def test_subjects_name_real_hook_ids(self):
        for script, subject in HOOKS.items():
            owner, hook_id = subject.removeprefix("hook:").split("/")
            ids = [h["id"] for h in json.loads((ROOT / owner / "hooks.json").read_text())["hooks"]]
            self.assertIn(hook_id, ids, script)

    def test_crash_is_logged_and_still_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "feedback.py"
            fake.write_text(FAKE_BIN)
            for script, subject in HOOKS.items():
                with self.subTest(script=script):
                    # Run the script's own __main__ guard with main() replaced by one that crashes.
                    code = (f"import runpy, sys; sys.argv=[{str(ROOT / script)!r}]; sys.path.insert(0, {str((ROOT / script).parent)!r})\n"
                            f"g = runpy.run_path({str(ROOT / script)!r}, run_name='hook')\n"
                            "def boom(*a, **k): raise RuntimeError('boom')\n"
                            "g['main'] = boom\n"
                            f"src = open({str(ROOT / script)!r}).read()\n"
                            "exec(compile(src[src.rindex('if __name__'):], 'guard', 'exec'), {**g, '__name__': '__main__'})\n")
                    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                       env={**os.environ, "AGENT_FEEDBACK_BIN": str(fake)})
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn("RuntimeError", r.stderr)
                    last = json.loads((Path(str(fake) + ".calls")).read_text().splitlines()[-1])
                    self.assertEqual(last[:2], ["log", subject])
                    self.assertTrue(last[last.index("--summary") + 1].endswith("crashed: RuntimeError"), last)

    def test_missing_store_is_silent(self):
        script = ROOT / "verification-writer/scripts/route-scanner.py"
        code = (f"import runpy; g = runpy.run_path({str(script)!r}, run_name='hook'); "
                "g['fb_log']('hook:a/b', 'low', 'x'); print('ok')")
        env = {**os.environ, "AGENT_FEEDBACK_BIN": "", "CLAUDE_PROJECT_DIR": "/nonexistent", "HOME": "/nonexistent"}
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "ok"), r.stderr)


if __name__ == "__main__":
    unittest.main()
