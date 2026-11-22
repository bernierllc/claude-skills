"""Behavior tests for Review Gate's security lane (check-security-scan.py, 3.3.0).

Each trust check a-f in the script's docstring has a test here that fails when that check is removed.
The lane runs against a fake `gh` (test_forged_gate.FAKE_GH), so no network and no real repo.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_forged_gate  # noqa: E402  (its TestCases stay out of this module's namespace: not run twice)
from test_forged_gate import FAKE_GH, HEAD_SHA, PROVENANCE, SCRIPTS, run_heads  # noqa: E402

LANE = SCRIPTS / "check-security-scan.py"
SCAN_RUN = ".github/workflows/security-scan.yml\tpull_request_target"
TREE = "b" * 40  # the default branch's .github/security-scan tree
PR_TREE = "d" * 40  # the same directory as the PR head has it
ENABLED = [{"name": "review-gate.yml", "type": "file", "sha": "0" * 40},
           {"name": "security-scan.yml", "type": "file", "sha": "1" * 40}]


def scan(run_id=700, job_id=None, conclusion="success", status="completed", head=HEAD_SHA,
         started="2026-11-20T10:01:00Z", slug="github-actions", annotations=1):
    job_id = job_id or 8000 + run_id
    return {"id": 8000 + run_id, "name": "Security Scan", "app": {"slug": slug}, "head_sha": head, "status": status,
            "conclusion": conclusion, "started_at": started, "output": {"annotations_count": annotations},
            "details_url": f"https://github.com/o/r/actions/runs/{run_id}/job/{job_id}"}


def note(outcome="passed", tree=TREE):
    return {"title": "security-scan", "annotation_level": "notice", "path": ".github",
            "message": f"outcome={outcome} config-tree={tree}"}


def job_of(check, **over):
    """The Actions job GitHub lists for a scanner check run: same id, its run, bound by check_run_url."""
    return {"id": check["id"], "run_id": int(check["details_url"].split("/runs/")[1].split("/")[0]),
            "check_run_url": f"https://api.github.com/repos/o/r/check-runs/{check['id']}",
            **{k: check.get(k) for k in ("status", "conclusion", "started_at", "head_sha")}, **over}


def fixture(checks=None, notes=None, runs=None, body="", contents=None, heads=None, jobs=None):
    checks = [scan()] if checks is None else checks
    listed = {rid: [] for rid in {"700": 0, **(runs or {})}}
    for c in checks:
        if "/job/" in c["details_url"]:
            listed.setdefault(str(job_of(c)["run_id"]), []).append(job_of(c))
    base = copy.deepcopy(PROVENANCE)
    base["pull"]["body"] = body
    return {**base, "scripts": {}, "check_runs": checks,
            "runs": {"700": SCAN_RUN, **(runs or {})},
            "run_heads": {"700": run_heads(), **(heads or {})},
            "jobs": {**listed, **(jobs or {})},
            "annotations": {str(c["id"]): (notes or {}).get(c["id"], [note()]) for c in checks},
            "contents": {".github/workflows?ref=main": ENABLED,
                         ".github?ref=main": [{"name": "security-scan", "type": "dir", "sha": TREE}],
                         # what the PR head has: the lane must never read these (trust check f)
                         f".github/workflows?ref={HEAD_SHA}": ENABLED[:1],
                         ".github/workflows?ref=chore/revendor-review-gate": ENABLED[:1],
                         f".github?ref={HEAD_SHA}": [{"name": "security-scan", "type": "dir", "sha": PR_TREE}],
                         ".github?ref=chore/revendor-review-gate": [{"name": "security-scan", "type": "dir", "sha": PR_TREE}],
                         **(contents or {})}}


def lane(fix, sha=HEAD_SHA):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bindir = tmp / "bin"; bindir.mkdir()
        (bindir / "gh").write_text(FAKE_GH); (bindir / "gh").chmod(0o755)
        (tmp / "fixture.json").write_text(json.dumps(fix))
        env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=str(tmp), GH_TOKEN="x",
                   PR_NUMBER="7", REPO="o/r", SHA=sha, DEFAULT_BRANCH="main")
        proc = subprocess.run([sys.executable, "-I", str(LANE)], capture_output=True, text=True, env=env)
        return proc.returncode, proc.stdout + proc.stderr


class TrustChecks(unittest.TestCase):
    def test_trusted_passing_scan_passes(self):
        rc, out = lane(fixture())
        self.assertEqual(rc, 0, out)
        self.assertIn("security lane ok", out)

    def test_not_applicable_passes(self):
        rc, out = lane(fixture(notes={8700: [note("not-applicable")]}))
        self.assertEqual(rc, 0, out)

    # (a) workflow ref: a PR's own workflow publishing the name is forged
    def test_a_untrusted_workflow_job_is_forged(self):
        rc, out = lane(fixture(runs={"700": ".github/workflows/pr-scan.yml\tpull_request"}))
        self.assertEqual(rc, 1, out)
        self.assertIn("forged 'Security Scan'", out)

    def test_a_trusted_path_on_another_event_is_forged(self):
        rc, out = lane(fixture(runs={"700": ".github/workflows/security-scan.yml\tpull_request"}))
        self.assertEqual(rc, 1, out)

    # (a) a Checks API POST that copies the real job's URL: its id is not that job's id
    def test_a_check_id_must_equal_the_job_id(self):
        rc, out = lane(fixture(checks=[scan(job_id=1234)]))
        self.assertEqual(rc, 1, out)
        self.assertIn("forged", out)

    # (a) SEC-01: a POSTed check PATCHed to point details_url at its own id, under the trusted run
    def test_a_posted_then_patched_check_is_forged(self):
        other = job_of(scan(), id=9999, check_run_url="https://api.github.com/repos/o/r/check-runs/9999")
        rc, out = lane(fixture(jobs={"700": [other]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("forged", out)

    def test_a_job_must_name_this_check_run(self):
        rc, out = lane(fixture(jobs={"700": [job_of(scan(), check_run_url="https://api.github.com/repos/o/r/check-runs/1")]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("forged", out)

    def test_a_job_must_belong_to_the_run(self):
        rc, out = lane(fixture(jobs={"700": [job_of(scan(), run_id=701)]}))
        self.assertEqual(rc, 1, out)

    # (a) SEC-02: renaming the newest (failed) check must not let an older success decide
    def test_a_renamed_newest_check_fails(self):
        old = scan(700)
        new = {**scan(701, conclusion="failure", started="2026-11-20T11:00:00Z"), "name": "Renamed"}
        rc, out = lane(fixture(checks=[old, new], runs={"701": SCAN_RUN}, heads={"701": run_heads()},
                               notes={8701: [note("findings")]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("named 'Renamed'", out)

    def test_a_unreadable_job_listing_exits_2(self):
        fix = fixture(); del fix["jobs"]["700"]
        self.assertEqual(lane(fix)[0], 2)

    def test_a_api_posted_check_is_never_evidence(self):
        posted = {**scan(), "details_url": "https://github.com/o/r/runs/8700"}
        rc, out = lane(fixture(checks=[posted]))
        self.assertEqual(rc, 1, out)
        self.assertIn("no trusted 'Security Scan' run", out)

    # (a) provenance: the trusted workflow, but another PR's run (another head branch)
    def test_a_another_prs_run_is_not_accepted(self):
        rc, out = lane(fixture(heads={"700": run_heads(head_branch="feat/other")}))
        self.assertEqual(rc, 1, out)
        self.assertIn("not this PR's scan", out)

    # (b) publisher app
    def test_b_other_app_is_rejected(self):
        rc, out = lane(fixture(checks=[scan(slug="some-app")]))
        self.assertEqual(rc, 1, out)
        self.assertIn("not github-actions", out)

    # (c) head sha
    def test_c_scan_on_another_sha_is_rejected(self):
        rc, out = lane(fixture(checks=[scan(head="e" * 40)]))
        self.assertEqual(rc, 1, out)
        self.assertIn("not the PR head", out)

    def test_c_moved_pr_head_exits_2(self):
        rc, out = lane(fixture(), sha="f" * 40)
        self.assertEqual(rc, 2, out)

    # (d) freshness: the newest trusted run decides
    def test_d_older_success_does_not_mask_newer_failure(self):
        old, new = scan(700, started="2026-11-20T10:01:00Z"), scan(701, conclusion="failure", started="2026-11-20T11:00:00Z")
        rc, out = lane(fixture(checks=[old, new], runs={"701": SCAN_RUN}, heads={"701": run_heads()},
                               notes={8701: [note("findings")]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("reported findings", out)

    def test_d_newest_in_progress_is_incomplete(self):
        old, new = scan(700), scan(701, status="in_progress", conclusion=None, started="2026-11-20T11:00:00Z")
        rc, out = lane(fixture(checks=[old, new], runs={"701": SCAN_RUN}, heads={"701": run_heads()}))
        self.assertEqual(rc, 1, out)
        self.assertIn("in_progress", out)

    def test_d_status_and_conclusion_come_from_the_job(self):
        rc, out = lane(fixture(jobs={"700": [job_of(scan(), status="in_progress", conclusion=None)]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("in_progress", out)
        rc, out = lane(fixture(jobs={"700": [job_of(scan(), conclusion="failure")]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("scanner error", out)

    def test_d_job_started_at_orders_runs(self):
        old, new = scan(700, started="2026-11-20T11:00:00Z"), scan(701, conclusion="failure")
        rc, out = lane(fixture(checks=[old, new], runs={"701": SCAN_RUN}, heads={"701": run_heads()},
                               notes={8701: [note("findings")]},
                               jobs={"700": [job_of(old, started_at="2026-11-20T09:00:00Z")],
                                     "701": [job_of(new, started_at="2026-11-20T10:00:00Z")]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("reported findings", out)

    def test_d_a_higher_job_id_does_not_outrank_a_later_start(self):
        late, early = scan(700, conclusion="failure"), scan(701)
        rc, out = lane(fixture(checks=[late, early], runs={"701": SCAN_RUN}, heads={"701": run_heads()},
                               notes={8700: [note("findings")]},
                               jobs={"700": [job_of(late, started_at="2026-11-20T10:00:00Z")],
                                     "701": [job_of(early, started_at="2026-11-20T09:00:00Z")]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("reported findings", out)

    def test_d_a_newer_queued_job_is_incomplete(self):
        done, queued = scan(700), scan(701, status="queued", conclusion=None, started=None)
        rc, out = lane(fixture(checks=[done, queued], runs={"701": SCAN_RUN}, heads={"701": run_heads()}))
        self.assertEqual(rc, 1, out)
        self.assertIn("is queued", out)

    def test_d_no_scan_yet_is_incomplete(self):
        rc, out = lane(fixture(checks=[]))
        self.assertEqual(rc, 1, out)
        self.assertIn("re-fire Review Gate", out)

    # (e) digest: the scan must have used the default branch's current config tree
    def test_e_stale_config_tree_is_rejected(self):
        rc, out = lane(fixture(notes={8700: [note(tree="9" * 40)]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("config tree", out)

    def test_e_exactly_one_outcome_annotation(self):
        rc, out = lane(fixture(checks=[scan(annotations=2)], notes={8700: [note(), note()]}))
        self.assertEqual(rc, 1, out)
        rc, out = lane(fixture(checks=[scan(annotations=0)], notes={8700: []}))
        self.assertEqual(rc, 1, out)

    def test_e_outcome_must_agree_with_conclusion(self):
        rc, out = lane(fixture(notes={8700: [note("findings")]}))
        self.assertEqual(rc, 1, out)
        rc, out = lane(fixture(checks=[scan(conclusion="cancelled")]))
        self.assertEqual(rc, 1, out)
        self.assertIn("scanner error", out)

    def test_e_annotation_count_mismatch_exits_2(self):
        rc, out = lane(fixture(checks=[scan(annotations=3)]))
        self.assertEqual(rc, 2, out)

    def test_e_missing_config_dir_fails(self):
        rc, out = lane(fixture(contents={".github?ref=main": []}))
        self.assertEqual(rc, 1, out)

    # (f) base-side: config, activation and validator come from the default branch, never the PR head
    def test_f_pr_side_config_tree_is_not_trusted(self):
        rc, out = lane(fixture(notes={8700: [note(tree=PR_TREE)]}))
        self.assertEqual(rc, 1, out)

    def test_f_pr_deleting_the_workflow_does_not_disable_the_lane(self):
        rc, out = lane(fixture(checks=[]))  # the head lists no security-scan.yml; main does
        self.assertEqual(rc, 1, out)

    def test_f_lane_off_when_default_branch_lacks_the_workflow(self):
        rc, out = lane(fixture(checks=[], contents={".github/workflows?ref=main": ENABLED[:1]}))
        self.assertEqual(rc, 0, out)
        self.assertIn("not enabled", out)

    def test_unreadable_listing_exits_2(self):
        fix = fixture(); fix["listing_fails"] = True
        self.assertEqual(lane(fix)[0], 2)
        self.assertEqual(lane(fixture(contents={".github/workflows?ref=main": {"message": "not a list"}}))[0], 2)
        for entry in (None, "garbage", {"type": "file"}):  # a malformed entry never reads as "lane not enabled"
            self.assertEqual(lane(fixture(checks=[], contents={".github/workflows?ref=main": [entry]}))[0], 2, entry)


class BodyClaims(unittest.TestCase):
    CLAIM = "## Summary\n\nx\n\n## Review\n\nSecurity scan passed with gitleaks and semgrep clean\n"

    def test_claim_without_the_lane_fails(self):
        rc, out = lane(fixture(checks=[], body=self.CLAIM, contents={".github/workflows?ref=main": ENABLED[:1]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("claims a scanner pass", out)

    def test_claim_with_a_failing_scan_names_the_claim(self):
        rc, out = lane(fixture(checks=[scan(conclusion="failure")], notes={8700: [note("findings")]}, body=self.CLAIM))
        self.assertEqual(rc, 1, out)
        self.assertIn("claims a scanner pass", out)

    def test_claim_with_a_verified_pass_is_fine(self):
        self.assertEqual(lane(fixture(body=self.CLAIM))[0], 0)

    def test_security_review_line_is_advisory_only(self):
        body = "## Review\n\nSecurity review: nevar-security-review on abc found no P0 or P1\n"
        rc, out = lane(fixture(checks=[], body=body, contents={".github/workflows?ref=main": ENABLED[:1]}))
        self.assertEqual(rc, 0, out)
        self.assertIn("ADVISORY/UNVERIFIED", out)

    def test_labelled_claim_outside_review_counts(self):
        body = "Security scan: osv-scanner ok\n\n## Review\n\nFallback review: codex on x — verdict: clean\n"
        rc, out = lane(fixture(checks=[], body=body, contents={".github/workflows?ref=main": ENABLED[:1]}))
        self.assertEqual(rc, 1, out)

    # SEC-03: a CR-only body splits into lines as the incumbent gate splits it
    def test_cr_only_newlines_still_find_the_claim(self):
        body = "## Review\r\rSecurity scan: semgrep passed\r"
        rc, out = lane(fixture(checks=[], body=body, contents={".github/workflows?ref=main": ENABLED[:1]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("claims a scanner pass", out)

    def test_fallback_attestation_is_not_a_claim(self):
        body = "## Review\n\nFallback review: codex on " + "a" * 40 + " — verdict: clean\n"
        rc, out = lane(fixture(checks=[], body=body, contents={".github/workflows?ref=main": ENABLED[:1]}))
        self.assertEqual(rc, 0, out)


class GateWiring(unittest.TestCase):
    """The real review-gate.yml block: the lane loads from the default branch and its failure fails the gate."""
    gate = test_forged_gate.ForgedGateWorkflow.gate

    def test_lane_failure_fails_the_gate(self):
        rc, out = self.gate([], fixture={"contents": {".github/workflows?ref=main": ENABLED}})
        self.assertEqual(rc, 1, out)
        self.assertIn("security lane failed (exit 1)", out)
        self.assertTrue(any("contents/scripts/check-security-scan.py?ref=main" in c for c in self.calls), self.calls)

    def test_lane_pass_keeps_the_gate_green(self):
        fix = fixture()
        rc, out = self.gate([scan()], runs={"700": SCAN_RUN}, fixture={
            "contents": fix["contents"], "annotations": fix["annotations"], "jobs": fix["jobs"],
            "run_heads": {"600": run_heads(), "700": run_heads()}})
        self.assertEqual(rc, 0, out)
        self.assertIn("security lane ok", out)

    def test_missing_lane_script_fails_closed(self):
        rc, out = self.gate([], missing=("check-security-scan.py",))
        self.assertEqual(rc, 1, out)


if __name__ == "__main__":
    unittest.main()
