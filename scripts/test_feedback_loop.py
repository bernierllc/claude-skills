"""Tests for feedback-loop/scripts/feedback.py: the store every item logs friction into."""
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "feedback-loop" / "scripts" / "feedback.py"


class FeedbackStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "fb"
        self.env = {**os.environ, "AGENT_FEEDBACK_HOME": str(self.home)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_fb(self, *args, ok=True):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], env=self.env, capture_output=True, text=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def log(self, subject="skill:demo", severity="low", summary="something went wrong", *extra):
        return self.run_fb("log", subject, "--severity", severity, "--summary", summary, *extra).stdout.strip()

    def entries(self, kind="skill", name="demo"):
        path = self.home / "subjects" / kind / name / "entries.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def status(self, *args):
        return json.loads(self.run_fb("status", "--json", *args).stdout)["subjects"]

    def test_log_writes_one_entry_with_required_fields(self):
        eid = self.log("skill:demo", "medium", "  wrong   default ", "--suggestion", "fix it", "--phase", "plan")
        [e] = self.entries()
        self.assertEqual(e["id"], eid)
        self.assertEqual(len(eid), 12)
        self.assertEqual((e["kind"], e["name"], e["severity"], e["summary"]), ("skill", "demo", "medium", "wrong default"))
        self.assertEqual((e["suggestion"], e["phase"], e["reporter"]), ("fix it", "plan", "agent"))

    def test_parallel_writers_never_lose_an_entry(self):
        n = 40
        with ThreadPoolExecutor(max_workers=n) as pool:
            list(pool.map(lambda i: self.log("skill:demo", "low", f"entry {i}"), range(n)))
        got = self.entries()
        self.assertEqual(len(got), n)
        self.assertEqual({e["summary"] for e in got}, {f"entry {i}" for i in range(n)})

    def test_subjects_are_separate_and_nested_names_work(self):
        self.log("skill:a")
        self.log("hook:typecheck-on-edit/post-edit")
        self.log("process:my-project", "low", "ci was slow", "--area", "ci")
        subjects = {r["subject"]: r["total"] for r in self.status()}
        self.assertEqual(subjects, {"skill:a": 1, "hook:typecheck-on-edit/post-edit": 1, "process:my-project": 1})

    def test_unsafe_or_malformed_subjects_are_rejected(self):
        for bad in ("skill:../x", "skill:/abs", "skill:a//b", "nope:x", "skill:", "skill", "hook:a/../b",
                    "skill:CON", "skill:nul.txt", "hook:a/com1", "skill:x.", "skill:x/y."):
            with self.subTest(subject=bad):
                r = self.run_fb("log", bad, "--severity", "low", "--summary", "x", ok=False)
                self.assertEqual(r.returncode, 2)
        self.assertFalse((self.home / "subjects").exists())

    def test_area_only_for_process(self):
        r = self.run_fb("log", "skill:demo", "--severity", "low", "--summary", "x", "--area", "ci", ok=False)
        self.assertEqual(r.returncode, 2)

    def test_credentials_are_refused(self):
        for secret in ("token ghp_" + "a" * 36, "key AKIA" + "B" * 16, "sk-" + "c" * 30):
            with self.subTest(secret=secret[:8]):
                r = self.run_fb("log", "skill:demo", "--severity", "low", "--summary", secret, ok=False)
                self.assertEqual(r.returncode, 2)
                self.assertIn("credential", r.stderr)
        self.log("skill:demo", "low", "task-abcdefghijklmnopqrst stalled")  # 'sk-' inside a word is not a key

    def test_disabled_and_opted_out_are_quiet_noops(self):
        self.run_fb("config", "--opt-out", "skill:muted")
        self.log("skill:muted")
        self.assertFalse((self.home / "subjects" / "skill" / "muted").exists())
        self.run_fb("config", "--disable")
        r = self.run_fb("log", "skill:demo", "--severity", "high", "--summary", "x")
        self.assertEqual(r.stdout, "")
        self.assertFalse((self.home / "subjects" / "skill" / "demo").exists())
        self.run_fb("config", "--enable", "--opt-in", "skill:muted")
        self.log("skill:muted")
        self.assertEqual(len(self.entries("skill", "muted")), 1)

    def test_thresholds(self):
        cases = [(["high"], "1 high"), (["medium"] * 2, None), (["medium"] * 3, "3 medium"),
                 (["low"] * 4, None), (["low"] * 5, "5 total")]
        for i, (sevs, due) in enumerate(cases):
            subject = f"skill:t{i}"
            for s in sevs:
                self.log(subject, s, f"{s} {time.time_ns()}")
            with self.subTest(sevs=sevs):
                [row] = self.status(subject)
                self.assertEqual(row["due"], due)

    def test_review_resets_the_count_and_resolutions_close_entries(self):
        a = self.log("skill:demo", "high", "first")
        self.assertEqual(self.status("skill:demo")[0]["due"], "1 high")
        self.run_fb("mark-reviewed", "skill:demo", "--source-repo", "my-org/my-skills")
        [row] = self.status("skill:demo")
        self.assertEqual((row["due"], row["since_review"], row["open"]), (None, 0, 1))
        self.assertEqual(row["source_repo"], "my-org/my-skills")
        self.assertEqual(self.status("--due"), [])
        self.log("skill:demo", "high", "second")
        self.assertEqual(self.status("skill:demo")[0]["due"], "1 high")
        self.run_fb("resolve", "skill:demo", a, "--status", "folded", "--pr", "https://example.com/pr/1")
        self.assertEqual(self.status("skill:demo")[0]["open"], 1)
        review = json.loads(self.run_fb("review", "skill:demo", "--all", "--json").stdout)
        self.assertEqual([e["summary"] for e in review["entries"]], ["second"])
        r = self.run_fb("resolve", "skill:demo", "deadbeef0000", "--status", "merged", ok=False)
        self.assertEqual(r.returncode, 2)

    def test_identical_entries_in_the_same_second_get_distinct_ids(self):
        a = self.log("skill:demo", "high", "same thing")
        b = self.log("skill:demo", "high", "same thing")
        self.assertNotEqual(a, b)
        self.run_fb("resolve", "skill:demo", a, "--status", "folded")
        self.assertEqual(self.status("skill:demo")[0]["open"], 1)

    def test_entries_logged_during_a_review_stay_pending(self):
        self.log("skill:demo", "high", "seen in review")
        through = json.loads(self.run_fb("review", "skill:demo", "--json").stdout)["through"]
        self.log("skill:demo", "high", "logged while the review ran")
        self.run_fb("mark-reviewed", "skill:demo", "--through", str(through))
        [row] = self.status("skill:demo")
        self.assertEqual((row["since_review"], row["due"]), (1, "1 high"))
        r = self.run_fb("mark-reviewed", "skill:demo", "--through", "9", ok=False)
        self.assertEqual(r.returncode, 2)

    def test_parallel_resolutions_and_opt_outs_all_survive(self):
        n = 40
        ids = [self.log("skill:demo", "low", f"entry {i}") for i in range(n)]
        with ThreadPoolExecutor(max_workers=n) as pool:
            list(pool.map(lambda i: self.run_fb("resolve", "skill:demo", i, "--status", "folded"), ids))
            list(pool.map(lambda i: self.run_fb("config", "--opt-out", f"skill:s{i}"), range(n)))
        state = json.loads((self.home / "subjects/skill/demo/state.json").read_text())
        self.assertEqual(set(state["resolutions"]), set(ids))
        cfg = json.loads(self.run_fb("config", "--json").stdout)
        self.assertEqual(len(cfg["opt_out"]), n)

    def test_deferred_entries_stay_open(self):
        a = self.log("skill:demo", "high", "later")
        self.run_fb("resolve", "skill:demo", a, "--status", "deferred")
        self.assertEqual(self.status("skill:demo")[0]["due"], "1 high")

    def test_report_groups_process_feedback_by_area(self):
        self.log("process:my-project", "medium", "flaky e2e", "--area", "test")
        self.log("process:my-project", "low", "slow ci", "--area", "ci")
        self.log("process:my-project", "low", "slow ci again", "--area", "ci")
        [r] = json.loads(self.run_fb("report", "process:my-project", "--json").stdout)
        self.assertEqual(r["by_area"], {"test": 1, "ci": 2})
        self.assertEqual(r["by_status"], {"open": 3})

    def test_unreadable_line_is_skipped_not_fatal(self):
        self.log()
        with open(self.home / "subjects/skill/demo/entries.jsonl", "a") as f:
            f.write("{truncated\n")
        self.log()
        r = self.run_fb("status", "skill:demo", "--json")
        self.assertEqual(json.loads(r.stdout)["subjects"][0]["total"], 2)
        self.assertIn("unreadable line", r.stderr)

    def test_import_orchata_migrates_once(self):
        src = Path(self.tmp.name) / "friction.json"
        src.write_text(json.dumps({
            "opt_out": False, "last_review": "2026-08-01", "source_repo": "my-org/my-skills",
            "entries": [
                {"date": "2026-07-01", "severity": "high", "project": "p", "summary": "old", "suggestion": "s"},
                {"date": "2026-08-04", "level": "medium", "what_happened": "legacy fields"},
                {"date": "2026-08-05", "severity": "low", "summary": "folded", "pr": "https://example.com/pr/2"},
            ]}))
        self.run_fb("import-orchata", "--path", str(src))
        got = self.entries("skill", "orchata")
        self.assertEqual([e["summary"] for e in got], ["old", "legacy fields", "folded"])
        self.assertEqual(got[1]["severity"], "medium")
        [row] = self.status("skill:orchata")
        self.assertEqual((row["since_review"], row["open"], row["source_repo"]), (1, 2, "my-org/my-skills"))
        self.assertFalse(src.exists())
        os.replace(str(src) + ".migrated", src)
        self.run_fb("import-orchata", "--path", str(src))
        self.assertEqual(len(self.entries("skill", "orchata")), 3)

    def test_import_orchata_carries_opt_out(self):
        src = Path(self.tmp.name) / "friction.json"
        src.write_text(json.dumps({"opt_out": True, "entries": []}))
        self.run_fb("import-orchata", "--path", str(src))
        cfg = json.loads(self.run_fb("config", "--json").stdout)
        self.assertIn("skill:orchata", cfg["opt_out"])

    def test_import_holds_the_entries_lock_so_live_logs_cannot_interleave(self):
        src = Path(self.tmp.name) / "friction.json"
        src.write_text(json.dumps({"last_review": "2026-08-01", "entries": [
            {"date": "2026-07-01", "severity": "high", "summary": "old"}]}))
        path = self.home / "subjects/skill/orchata/entries.jsonl"
        path.parent.mkdir(parents=True)
        with open(path, "a") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            proc = subprocess.Popen([sys.executable, str(SCRIPT), "import-orchata", "--path", str(src)],
                                    env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            time.sleep(0.5)
            self.assertIsNone(proc.poll(), "import wrote while another writer held the entries lock")
        self.assertEqual(proc.wait(timeout=10), 0, proc.stderr.read())
        self.assertEqual([e["summary"] for e in self.entries("skill", "orchata")], ["old"])


class WindowsLockTest(unittest.TestCase):
    """Without fcntl, every read-modify-write and append still takes an exclusive (msvcrt) lock."""

    def test_msvcrt_lock_is_taken_and_released(self):
        spec = importlib.util.spec_from_file_location("feedback_win", SCRIPT)
        fb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fb)
        calls = []

        class FakeMsvcrt:
            LK_NBLCK, LK_UNLCK = "lock", "unlock"
            fails = 2  # contended twice, then granted

            @classmethod
            def locking(cls, fd, mode, nbytes):
                if mode == "lock" and cls.fails:
                    cls.fails -= 1
                    raise OSError("locked")
                calls.append((mode, os.lseek(fd, 0, os.SEEK_CUR), nbytes))

        fb.fcntl, fb.msvcrt = None, FakeMsvcrt
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fb.time, "sleep"), \
                mock.patch.dict(os.environ, {"AGENT_FEEDBACK_HOME": d}):
            fb.append_entry("skill", "demo", {"id": "x", "summary": "s"})
            with fb.locked(fb.config_lock()):
                pass
            lines = (Path(d) / "subjects/skill/demo/entries.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 1)
        off = fb.WIN_LOCK_OFFSET
        self.assertEqual(calls, [("lock", off, 1), ("unlock", off, 1)] * 2)


if __name__ == "__main__":
    unittest.main()
