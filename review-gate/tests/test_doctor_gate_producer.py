"""doctor-review-gate.py: can the default branch publish a required `Review Gate`? (3.8.0)

Plan: agents-environment-config plans/2026-11-24-doctor-required-check-workflow-exists.md, step 9.
The doctor runs as a real subprocess. `gh` is the only stand-in: a fake executable on PATH that serves
fixture GitHub API responses (third-party, so no network), in the `gh api --include` output shape.
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
DOCTOR = SKILL / "scripts" / "doctor-review-gate.py"
INSTALLER = SKILL / "scripts" / "install-workflow.py"
GATE_YML = (SKILL / "templates" / "review-gate.yml").read_text()
DOCTOR_YML = (SKILL / "templates" / "review-gate-doctor.yml").read_text()  # the real companion workflow
FLAG = "--expect-default-branch-gate"
REPO = "my-org/my-app"

FAKE_GH = f"""#!{sys.executable}
import json, os, sys
fx = json.load(open(os.environ["FAKE_GH"]))
a = sys.argv[1:]
if a[:2] == ["repo", "view"]:
    if "nameWithOwner" in a:
        print(fx["repo"]); sys.exit(0)
    if fx.get("default") is None:
        print("gh: could not read repo", file=sys.stderr); sys.exit(1)
    print(fx["default"]); sys.exit(0)
if a[:2] == ["label", "list"]:
    print(json.dumps([{{"name": "review:high"}}])); sys.exit(0)
if a[:2] == ["api", "--include"] and len(a) == 3:
    with open(os.environ["FAKE_GH"] + ".calls", "a") as log:
        log.write(a[2] + "\\n")
    r = fx["api"].get(a[2], {{"status": 404, "body": {{"message": "Not Found"}}}})
    if r.get("transient"):
        print("error connecting to api.github.com", file=sys.stderr); sys.exit(1)
    st = r["status"]
    hdr = "".join(f"{{k}}: {{v}}\\n" for k, v in r.get("headers", {{}}).items())
    sys.stdout.write(f"HTTP/2.0 {{st}} X\\nContent-Type: application/json\\n{{hdr}}\\n" + json.dumps(r.get("body")))
    if st >= 400:
        print(f"gh: error (HTTP {{st}})", file=sys.stderr); sys.exit(1)
    sys.exit(0)
print("unexpected gh call: " + " ".join(a), file=sys.stderr); sys.exit(2)
"""


def ruleset(rid, contexts=(("Review Gate", None),), include=("~DEFAULT_BRANCH",), enforcement="active"):
    checks = [{"context": c, **({"integration_id": i} if i is not None else {})} for c, i in contexts]
    return {"id": rid, "name": f"rs{rid}", "enforcement": enforcement,
            "conditions": {"ref_name": {"include": list(include), "exclude": []}},
            "rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": checks}}]}


def fixture(rulesets, workflows=None, default="main", extra=None, pages=None):
    """workflows: {path: text} on the default branch; None means no .github/workflows directory."""
    api = {f"repos/{REPO}/branches/{default}": {"status": 200, "body": {"name": default}}}
    for page, items in enumerate(pages or [rulesets], start=1):
        api[f"repos/{REPO}/rulesets?per_page=100&page={page}"] = {
            "status": 200, "body": [{"id": r["id"], "name": r["name"]} for r in items]}
    for r in [r for items in (pages or [rulesets]) for r in items]:
        api[f"repos/{REPO}/rulesets/{r['id']}"] = {"status": 200, "body": r}
    if workflows is not None:
        api[f"repos/{REPO}/contents/.github/workflows?ref={default}"] = {
            "status": 200, "body": [{"path": p, "name": p.rsplit("/", 1)[1], "type": "file"} for p in workflows]}
        for p, text in workflows.items():
            api[f"repos/{REPO}/contents/{p}?ref={default}"] = {
                "status": 200, "body": {"encoding": "base64", "content": base64.b64encode(text.encode()).decode()}}
    api.update(extra or {})
    return {"repo": REPO, "default": default, "api": api}


def run_doctor(fx, *args):
    with tempfile.TemporaryDirectory() as tmp:
        bin_dir, cwd = Path(tmp, "bin"), Path(tmp, "repo")
        bin_dir.mkdir()
        cwd.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        fx_path = Path(tmp, "fx.json")
        fx_path.write_text(json.dumps(fx))
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_GH": str(fx_path)}
        proc = subprocess.run([sys.executable, str(DOCTOR), *args], cwd=cwd, env=env, capture_output=True, text=True)
        calls_path = Path(str(fx_path) + ".calls")
        calls = calls_path.read_text().splitlines() if calls_path.exists() else []
    assert "Traceback" not in proc.stderr, proc.stderr
    return proc, calls


def lines(proc, prefix):
    return [ln for ln in proc.stdout.splitlines() if ln.startswith(prefix)]


GATE = {".github/workflows/review-gate.yml": GATE_YML}
NO_GATE = {".github/workflows/ci.yml": "name: CI\non: pull_request\n"}
NO_TRIGGER = {".github/workflows/review-gate.yml": "name: Review Gate\non: pull_request\njobs: {}\n"}
WORKFLOWS = f"repos/{REPO}/contents/.github/workflows?ref=main"
DEEP = "on: pull_request_target\nx: " + "[" * 5000 + "]" * 5000 + "\n"  # any content, however nested, is only searched
MALFORMED = "on: [pull_request_target\n\tjobs: {{{\n\0"

class WithTheOption(unittest.TestCase):
    def assertFails(self, fx, *needles):
        proc, _ = run_doctor(fx, FLAG)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        fails = [ln for ln in lines(proc, "FAIL ") if "Review Gate" in ln]
        self.assertEqual(len(fails), 1, proc.stdout)
        for n in ("merge review-gate.yml to main before requiring the check", *needles):
            self.assertIn(n, fails[0])
        self.assertIn("FAIL 1 required-check problem(s) above", proc.stdout)
        return fails[0]

    def test_gate_on_the_default_branch_passes(self):
        proc, _ = run_doctor(fixture([ruleset(1)], GATE), FLAG)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(lines(proc, "FAIL"), [])
        self.assertIn("OK 'Review Gate' (required on main) has its producer: .github/workflows/review-gate.yml "
                      "on 'main' names pull_request_target (the trigger and its branch filters are not analyzed)", proc.stdout)

    def test_yaml_extension_counts(self):
        proc, _ = run_doctor(fixture([ruleset(1)], {".github/workflows/review-gate.yaml": GATE_YML}), FLAG)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_gate_absent_fails(self):
        self.assertFails(fixture([ruleset(1)], NO_GATE), "no .github/workflows/review-gate.yml (or .yaml) on 'main'")

    def test_actions_integration_id_is_analyzed(self):
        self.assertFails(fixture([ruleset(1, (("Review Gate", 15368),))], NO_GATE))

    def test_gate_only_on_a_covered_branch_fails_naming_the_default_branch(self):
        rs = ruleset(1, include=("refs/heads/main", "refs/heads/staging"))
        fx = fixture([rs], NO_GATE, extra={  # staging carries the gate; it must not count
            "repos/my-org/my-app/contents/.github/workflows?ref=staging": {
                "status": 200, "body": [{"path": ".github/workflows/review-gate.yml", "type": "file"}]}})
        line = self.assertFails(fx, "on 'main'", "copy on staging or another branch does not count",
                                "required on main/staging")
        self.assertIn("default branch only", line)

    def test_real_companion_doctor_workflow_does_not_mask_a_deleted_gate(self):
        self.assertIn("Review Gate", DOCTOR_YML)  # the reason a substring match would be wrong
        self.assertFails(fixture([ruleset(1)], {".github/workflows/review-gate-doctor.yml": DOCTOR_YML}))

    def test_absent_workflows_directory_on_a_readable_repo_fails(self):
        self.assertFails(fixture([ruleset(1)], None))

    def test_more_than_one_page_of_rulesets_is_read(self):
        page1 = [ruleset(i, enforcement="evaluate") for i in range(1, 101)]
        proc, calls = run_doctor(fixture(None, NO_GATE, pages=[page1, [ruleset(200)]]), FLAG)
        self.assertIn(f"repos/{REPO}/rulesets?per_page=100&page=2", calls)
        self.assertEqual(proc.returncode, 1, proc.stdout)  # only page 2 requires the gate

    def test_unknown_default_branch_warns(self):
        fx = fixture([ruleset(1)], NO_GATE)
        fx["default"] = None
        proc, _ = run_doctor(fx, FLAG)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("WARN could not read the default branch name", proc.stdout)


class WithoutTheOption(unittest.TestCase):
    def test_missing_gate_states_warn_and_name_the_option(self):
        for workflows in (NO_GATE, None, {".github/workflows/review-gate-doctor.yml": DOCTOR_YML}):
            with self.subTest(workflows=workflows and list(workflows)):
                proc, _ = run_doctor(fixture([ruleset(1)], workflows))
                self.assertEqual(proc.returncode, 0, proc.stdout)
                self.assertEqual(lines(proc, "FAIL"), [])
                warns = [ln for ln in lines(proc, "WARN 'Review Gate'") if FLAG in ln]
                self.assertEqual(len(warns), 1, proc.stdout)
                self.assertIn("merge review-gate.yml to main before requiring the check", warns[0])

    def test_pr_supplied_pull_request_workflow_named_review_gate_warns_never_fails(self):
        wf = {".github/workflows/gate.yml": "name: Review Gate\non:\n  pull_request:\njobs: {}\n"}
        proc, _ = run_doctor(fixture([ruleset(1)], wf))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("A PR-supplied pull_request workflow or an external app can also publish it", proc.stdout)

    def test_source_less_context_warns(self):
        proc, _ = run_doctor(fixture([ruleset(1)], None))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(len(lines(proc, "WARN 'Review Gate' (required on main) may not report")), 1, proc.stdout)


class EitherWay(unittest.TestCase):
    def both(self, fx):
        return [run_doctor(fx, *args) for args in ((), (FLAG,))]

    def test_present_gate_without_the_trigger_name_warns_and_never_fails(self):
        for text in (NO_TRIGGER[".github/workflows/review-gate.yml"], MALFORMED.replace("pull_request_target", "x")):
            for proc, _ in self.both(fixture([ruleset(1)], {".github/workflows/review-gate.yml": text})):
                with self.subTest(text=text):
                    self.assertEqual(proc.returncode, 0, proc.stdout)
                    self.assertEqual(lines(proc, "FAIL"), [])
                    warn = lines(proc, "WARN producer of 'Review Gate'")
                    self.assertEqual(len(warn), 1, proc.stdout)
                    self.assertIn("review-gate.yml on 'main' exists, trigger not verified", warn[0])

    def test_present_gate_naming_the_trigger_is_ok_however_it_is_written(self):
        filtered = GATE_YML.replace("    types: [", "    branches: [staging]\n    types: [", 1)  # not analyzed
        for text in (DEEP, MALFORMED, filtered):  # run_doctor asserts no traceback
            for proc, _ in self.both(fixture([ruleset(1)], {".github/workflows/review-gate.yml": text})):
                with self.subTest(text=text[:40]):
                    self.assertEqual(proc.returncode, 0, proc.stdout)
                    self.assertIn("has its producer", proc.stdout)

    def test_non_actions_integration_id_is_skipped(self):
        for proc, calls in self.both(fixture([ruleset(1, (("Review Gate", 99999),))], None)):
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("pins 'Review Gate' to integration 99999 (not GitHub Actions); producer check skipped",
                          proc.stdout)
            self.assertNotIn(WORKFLOWS, calls)

    def test_other_required_context_warns_not_verified(self):
        fx = fixture([ruleset(1, (("Review Gate", None), ("CI / test", None)))], GATE)
        for proc, _ in self.both(fx):
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("WARN required check 'CI / test': producer not verified (generic producer analysis is out "
                          "of scope)", proc.stdout)
            self.assertIn("other branches are out of scope", proc.stdout)

    def test_contents_api_cap_warns(self):
        listing = [{"path": f".github/workflows/w{i}.yml", "type": "file"} for i in range(1000)]
        fx = fixture([ruleset(1)], NO_GATE, extra={WORKFLOWS: {"status": 200, "body": listing}})
        for proc, _ in self.both(fx):
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("lists 1000 entries, the Contents API cap", proc.stdout)

    def test_denied_missing_ref_transient_and_rate_limit_warn_naming_the_status(self):
        cases = {
            "HTTP 403": {WORKFLOWS: {"status": 403, "body": {"message": "Resource not accessible"}}},
            "HTTP 403, rate limited": {WORKFLOWS: {"status": 403, "headers": {"X-Ratelimit-Remaining": "0"},
                                                   "body": {"message": "API rate limit exceeded"}}},
            "HTTP 404": {f"repos/{REPO}/branches/main": {"status": 404, "body": {"message": "Branch not found"}}},
            "HTTP 404, missing ref": {WORKFLOWS: {"status": 404,
                                                  "body": {"message": "No commit found for the ref main"}}},
            "error connecting": {WORKFLOWS: {"transient": True}},
        }
        for needle, extra in cases.items():
            for proc, _ in self.both(fixture([ruleset(1)], NO_GATE, extra=extra)):
                with self.subTest(case=needle):
                    self.assertEqual(proc.returncode, 0, proc.stdout)
                    warn = lines(proc, "WARN producer of 'Review Gate'")
                    self.assertEqual(len(warn), 1, proc.stdout)
                    self.assertIn(needle, warn[0])

    def test_gate_file_reads_that_fail_warn(self):
        gate = f"repos/{REPO}/contents/.github/workflows/review-gate.yml?ref=main"
        cases = {
            "HTTP 403": {gate: {"status": 403, "body": {"message": "denied"}}},
            "HTTP 429, rate limited": {gate: {"status": 429, "body": {"message": "slow down"}}},
            "could not read .github/workflows/review-gate.yml": {gate: {"status": 200, "body": {"encoding": "none"}}},
            "could not decode": {gate: {"status": 200, "body": {"encoding": "base64", "content": "//79"}}},
            "could not decode .github": {gate: {"status": 200, "body": {"encoding": "base64", "content": 123}}},
            "is a symlink, not a file": {WORKFLOWS: {"status": 200, "body": [
                {"path": ".github/workflows/review-gate.yml", "type": "symlink"}]}},
        }
        for needle, extra in cases.items():
            for proc, _ in self.both(fixture([ruleset(1)], GATE, extra=extra)):
                with self.subTest(case=needle):
                    self.assertEqual(proc.returncode, 0, proc.stdout)
                    warn = lines(proc, "WARN producer of 'Review Gate'")
                    self.assertEqual(len(warn), 1, proc.stdout)
                    self.assertIn(needle, warn[0])

    def test_line_wrapped_base64_from_the_contents_api_is_read(self):
        b64 = base64.b64encode(GATE_YML.encode()).decode()
        wrapped = "\n".join(b64[i:i + 60] for i in range(0, len(b64), 60))
        gate = f"repos/{REPO}/contents/.github/workflows/review-gate.yml?ref=main"
        fx = fixture([ruleset(1)], GATE, extra={gate: {"status": 200, "body": {"encoding": "base64", "content": wrapped}}})
        proc, _ = run_doctor(fx, FLAG)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("has its producer", proc.stdout)

    def test_unreadable_rulesets_warn_and_say_the_producer_check_is_skipped(self):
        fx = fixture([ruleset(1)], NO_GATE, extra={
            f"repos/{REPO}/rulesets?per_page=100&page=1": {"status": 403, "body": {"message": "denied"}}})
        for proc, _ in self.both(fx):
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("WARN could not list rulesets (HTTP 403;", proc.stdout)
            self.assertIn("Review Gate producer checks are skipped", proc.stdout)


class InstallerHint(unittest.TestCase):
    def test_merge_to_the_default_branch_comes_before_requiring_the_check(self):
        with tempfile.TemporaryDirectory() as repo:
            out = subprocess.run([sys.executable, str(INSTALLER)], cwd=repo, capture_output=True, text=True).stdout
        merge = out.index("1. merge these files to the default branch")
        self.assertLess(merge, out.index("2. Only then add 'Review Gate' as a required status check"))
        self.assertIn(f"doctor-review-gate.py {FLAG}", out)


if __name__ == "__main__":
    unittest.main()
