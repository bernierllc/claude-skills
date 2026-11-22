"""Behavior tests for Review Gate's security lane (check-security-scan.py, 3.3.0; marker name 3.3.1).

Each trust check a-f in the script's docstring has a test here that fails when that check is removed.
The lane runs against a fake `gh` (test_forged_gate.FAKE_GH), so no network and no real repo.
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_forged_gate  # noqa: E402  (its TestCases stay out of this module's namespace: not run twice)
from test_forged_gate import FAKE_GH, HEAD_SHA, PROVENANCE, SCRIPTS, run_heads  # noqa: E402

LANE = SCRIPTS / "check-security-scan.py"
_spec = importlib.util.spec_from_file_location("check_security_scan", LANE)
lane_module = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(lane_module)
NOW = "2099-01-01T12:00:00+00:00"  # SECURITY_LANE_NOW: the lane's clock, moved forward past every fixture date
DONE = "2099-01-01T11:00:00Z"  # a scan that completed an hour before NOW
SCAN_RUN = ".github/workflows/review-gate-security-scan.yml\tpull_request_target"
TREE = "b" * 40  # the default branch's .github/security-scan tree
PR_TREE = "d" * 40  # the same directory as the PR head has it
ENABLED = [{"name": "review-gate.yml", "type": "file", "sha": "0" * 40},
           {"name": "review-gate-security-scan.yml", "type": "file", "sha": "1" * 40}]
# 3.3.1: a repo's OWN workflow that happens to be named security-scan.yml (mbernier.com has one) is not the marker
OWN_SCAN = [ENABLED[0], {"name": "security-scan.yml", "type": "file", "sha": "2" * 40}]
# main's policy revision as the fake serves it: review-gate.yml listed, scripts/ empty, .claude/ absent
POLICY = lane_module._revision({".github/workflows/review-gate.yml": "0" * 40})


def scan(run_id=700, job_id=None, conclusion="success", status="completed", head=HEAD_SHA,
         started="2026-11-20T10:01:00Z", slug="github-actions", annotations=1, completed=DONE):
    job_id = job_id or 8000 + run_id
    return {"id": 8000 + run_id, "name": "Security Scan", "app": {"slug": slug}, "head_sha": head, "status": status,
            "conclusion": conclusion, "started_at": started, "completed_at": completed, "output": {"annotations_count": annotations},
            "details_url": f"https://github.com/o/r/actions/runs/{run_id}/job/{job_id}"}


def note(outcome="passed", tree=TREE, **over):
    """The scan's one notice; `over` replaces a freshness field (pr, head, base-ref, workflow, policy, exceptions-until)."""
    fields = {"pr": "7", "head": HEAD_SHA, "base-ref": "main", "workflow": "1" * 40, "policy": POLICY,
              "exceptions-until": "none", **{k.replace("_", "-"): v for k, v in over.items()}}
    return {"title": "security-scan", "annotation_level": "notice", "path": ".github",
            "message": f"outcome={outcome} config-tree={tree} " + " ".join(f"{k}={v}" for k, v in fields.items())}


MAIN_SHA = "c" * 40  # the default branch commit a dispatched re-scan ran


def dispatch_run(run_id=710, pr=7, head=HEAD_SHA, branch="main", path=SCAN_RUN.split("\t")[0],
                 event="workflow_dispatch", sha=MAIN_SHA):
    """A Security Refresh re-scan: the default branch's scan workflow, titled for PR `pr` @ `head`."""
    return {"id": run_id, "path": path, "event": event, "head_branch": branch, "head_sha": sha,
            "display_title": lane_module.RUN_TITLE.format(pr=pr, head=head)}


def job_of(check, **over):
    """The Actions job GitHub lists for a scanner check run: same id, its run, bound by check_run_url."""
    return {"id": check["id"], "run_id": int(check["details_url"].split("/runs/")[1].split("/")[0]),
            "check_run_url": f"https://api.github.com/repos/o/r/check-runs/{check['id']}",
            **{k: check.get(k) for k in ("status", "conclusion", "started_at", "completed_at", "head_sha")}, **over}


def fixture(checks=None, notes=None, runs=None, body="", contents=None, heads=None, jobs=None, dispatch=()):
    checks = [scan()] if checks is None else checks
    listed = {rid: [] for rid in {"700": 0, **(runs or {})}}
    for c in checks:
        if "/job/" in c["details_url"]:
            listed.setdefault(str(job_of(c)["run_id"]), []).append(job_of(c))
    base = copy.deepcopy(PROVENANCE)
    base["pull"]["body"] = body
    return {**base, "scripts": {}, "check_runs": checks, "dispatch_runs": list(dispatch),
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


def lane(fix, sha=HEAD_SHA, args=(), **env_over):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bindir = tmp / "bin"; bindir.mkdir()
        (bindir / "gh").write_text(FAKE_GH); (bindir / "gh").chmod(0o755)
        (tmp / "fixture.json").write_text(json.dumps(fix))
        env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=str(tmp), GH_TOKEN="x",
                   PR_NUMBER="7", REPO="o/r", SHA=sha, DEFAULT_BRANCH="main", **{"SECURITY_LANE_NOW": NOW, **env_over})
        proc = subprocess.run([sys.executable, "-I", str(LANE), *args], capture_output=True, text=True, env=env)
        posts = tmp / "posts.log"
        lane.posts = posts.read_text().splitlines() if posts.exists() else []
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
        rc, out = lane(fixture(runs={"700": ".github/workflows/review-gate-security-scan.yml\tpull_request"}))
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
        self.assertIn("not its run's head", out)

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

    def test_d_a_cancelled_unstarted_job_does_not_outrank_a_later_success(self):
        cancelled, rerun = scan(700, conclusion="cancelled", started=None), scan(701)
        rc, out = lane(fixture(checks=[cancelled, rerun], runs={"701": SCAN_RUN}, heads={"701": run_heads()}))
        self.assertEqual(rc, 0, out)

    def test_d_no_scan_yet_is_incomplete(self):
        rc, out = lane(fixture(checks=[]))
        self.assertEqual(rc, 1, out)
        self.assertIn("Review Gate re-runs", out)

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
        rc, out = lane(fixture(checks=[]))  # the head lists no review-gate-security-scan.yml; main does
        self.assertEqual(rc, 1, out)

    def test_f_lane_off_when_default_branch_lacks_the_workflow(self):
        rc, out = lane(fixture(checks=[], contents={".github/workflows?ref=main": ENABLED[:1]}))
        self.assertEqual(rc, 0, out)
        self.assertIn("not enabled", out)

    def test_f_own_unrelated_security_scan_yml_keeps_the_lane_off(self):
        # its own failing "Security Scan" job is not ours to judge: no marker, no lane
        own = scan(conclusion="failure")
        rc, out = lane(fixture(checks=[own], runs={"700": ".github/workflows/security-scan.yml\tpull_request"},
                               contents={".github/workflows?ref=main": OWN_SCAN}))
        self.assertEqual(rc, 0, out)
        self.assertIn("not enabled", out)

    def test_f_pr_adding_the_marker_does_not_enable_the_lane(self):
        rc, out = lane(fixture(checks=[], contents={".github/workflows?ref=main": ENABLED[:1],
                                                    f".github/workflows?ref={HEAD_SHA}": ENABLED,
                                                    ".github/workflows?ref=chore/revendor-review-gate": ENABLED}))
        self.assertEqual(rc, 0, out)
        self.assertIn("not enabled", out)

    def test_unreadable_listing_exits_2(self):
        fix = fixture(); fix["listing_fails"] = True
        self.assertEqual(lane(fix)[0], 2)
        self.assertEqual(lane(fixture(contents={".github/workflows?ref=main": {"message": "not a list"}}))[0], 2)
        for entry in (None, "garbage", {"type": "file"}):  # a malformed entry never reads as "lane not enabled"
            self.assertEqual(lane(fixture(checks=[], contents={".github/workflows?ref=main": [entry]}))[0], 2, entry)
        capped = [{"name": f"w{i}.yml", "type": "file"} for i in range(1000)]  # review-gate-security-scan.yml may lie past the cap
        self.assertEqual(lane(fixture(checks=[], contents={".github/workflows?ref=main": capped}))[0], 2)


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

    # SKILLS-SEC-CLAIM-2: negation is not parsed (each parser was evaded in review), so a failure report
    # that uses a pass word fails closed and the error says how to reword it
    def test_a_pass_word_counts_even_when_negated(self):
        for line in ("Security scan: semgrep did not pass", "Security scan: gitleaks isn’t clean",
                     "Security scan: gitleaks did not pass but semgrep passed",
                     "Security scan: semgrep not only passed but found zero issues",
                     "Security scan: semgrep did not fail to pass",
                     "Security scan: semgrep found no pass-blocking issues"):
            body = f"## Review\n\n{line}\n"
            rc, out = lane(fixture(checks=[], body=body, contents={".github/workflows?ref=main": ENABLED[:1]}))
            self.assertEqual(rc, 1, (line, out))
            self.assertIn("claims a scanner pass", out)
            self.assertIn("reword it without a pass word", out)

    def test_a_failure_report_without_a_pass_word_is_not_a_claim(self):
        for line in ("Security scan: zizmor failed", "Security scan: semgrep reported 2 findings"):
            body = f"## Review\n\n{line}\n"
            rc, out = lane(fixture(checks=[], body=body, contents={".github/workflows?ref=main": ENABLED[:1]}))
            self.assertEqual(rc, 0, (line, out))

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
        # the gate lists its four trusted scripts (sha 5...), so main's policy revision includes them
        scripts = ("check-review-gate.py", "check-forged-gate-names.py", "check-forged-review-gate.py", "check-security-scan.py")
        policy = lane_module._revision({".github/workflows/review-gate.yml": "0" * 40,
                                        **{f"scripts/{n}": "5" * 40 for n in scripts}})
        fix = fixture(notes={8700: [note(policy=policy)]})
        with mock.patch.dict(os.environ, SECURITY_LANE_NOW=NOW):
            rc, out = self.gate([scan()], runs={"700": SCAN_RUN}, fixture={
                "contents": fix["contents"], "annotations": fix["annotations"], "jobs": fix["jobs"],
                "run_heads": {"600": run_heads(), "700": run_heads()}})
        self.assertEqual(rc, 0, out)
        self.assertIn("security lane ok", out)

    def test_missing_lane_script_with_the_lane_off_leaves_the_result_unchanged(self):
        # #145 Codex P1: a manual install that predates check-security-scan.py must not turn every gate red
        rc_present, _ = self.gate([])
        rc, out = self.gate([], missing=("check-security-scan.py",))
        self.assertEqual((rc_present, rc), (0, 0), out)
        self.assertIn("security lane not enabled", out)
        self.assertFalse(any("contents/scripts/check-security-scan.py" in c for c in self.calls), self.calls)

    def test_missing_lane_script_with_the_lane_on_fails_closed(self):
        rc, out = self.gate([], missing=("check-security-scan.py",), fixture={"contents": {".github/workflows?ref=main": ENABLED}})
        self.assertEqual(rc, 1, out)
        self.assertIn("Could not load trusted scripts/check-security-scan.py", out)

    def test_own_security_scan_yml_without_the_marker_skips_a_missing_lane_script(self):
        # 3.3.1: the mbernier.com shape, a re-vendor without the lane script must stay green
        rc, out = self.gate([], missing=("check-security-scan.py",), fixture={"contents": {".github/workflows?ref=main": OWN_SCAN}})
        self.assertEqual(rc, 0, out)
        self.assertIn("security lane not enabled", out)

    def test_a_pr_adding_the_marker_does_not_load_the_lane(self):
        rc, out = self.gate([], missing=("check-security-scan.py",), fixture={"contents": {
            ".github/workflows?ref=main": ENABLED[:1], f".github/workflows?ref={HEAD_SHA}": ENABLED}})
        self.assertEqual(rc, 0, out)
        self.assertFalse(any("contents/scripts/check-security-scan.py" in c for c in self.calls), self.calls)

    def test_a_failed_listing_fails_closed(self):
        for pattern in (r"contents/\.github/workflows\?", r"contents/scripts\?"):
            with self.subTest(pattern=pattern):
                rc, out = self.gate([], missing=("check-security-scan.py",), fixture={"fail": {"pattern": pattern}})
                self.assertEqual(rc, 1, out)
                self.assertIn("to decide the security lane", out)

    def test_an_empty_or_capped_listing_fails_closed(self):
        capped = [{"name": f"w{i}.yml", "type": "file"} for i in range(1000)]
        for body in ({"raw": ""}, {"raw": " \n"}, {"raw": "[] []"}, capped):
            with self.subTest(body=str(body)[:30]):
                rc, out = self.gate([], missing=("check-security-scan.py",), fixture={"contents": {".github/workflows?ref=main": body}})
                self.assertEqual(rc, 1, out)
                self.assertIn("to decide the security lane", out)


class Freshness(unittest.TestCase):
    """(g) a scan stands only for this PR's current head and base and main's current workflow and policy."""

    def stale(self, fix, why):
        rc, out = lane(fix)
        self.assertEqual(rc, 1, out)
        self.assertIn("is stale", out)
        self.assertIn(why, out)
        self.assertIn("Security Refresh", out)

    def test_each_notice_field_must_match(self):
        for over, why in (({"pr": "8"}, "scanned PR #8"), ({"head": "e" * 40}, "@ eeeeeeeeeeee"),
                          ({"base_ref": "staging"}, "now targets 'main'"), ({"workflow": "3" * 40}, "scan workflow blob"),
                          ({"policy": "0" * 64}, "policy revision")):
            with self.subTest(over=over):
                self.stale(fixture(notes={8700: [note(**over)]}), why)

    def test_a_policy_change_on_main_makes_the_scan_stale(self):
        fix = fixture(); fix["scripts"] = {"check-security-scan.py": str(LANE)}  # main now lists the lane script
        self.stale(fix, "policy revision")
        guard = {".claude/skills/review-gate/scripts?ref=main": [{"name": "merge-guard.py", "type": "file", "sha": "6" * 40}]}
        self.stale(fixture(contents=guard), "policy revision")

    def test_a_scan_workflow_change_on_main_makes_the_scan_stale(self):
        moved = [ENABLED[0], {**ENABLED[1], "sha": "4" * 40}]
        self.stale(fixture(contents={".github/workflows?ref=main": moved}), "scan workflow blob")

    def test_an_expired_exception_makes_the_scan_stale(self):
        self.stale(fixture(notes={8700: [note(exceptions_until="2098-12-31")]}), "expired after 2098-12-31")
        self.assertEqual(lane(fixture(notes={8700: [note(exceptions_until="2099-01-01")]}))[0], 0)

    def test_the_clock_only_moves_forward(self):
        # a past SECURITY_LANE_NOW cannot revive an exception that expired before today
        rc, out = lane(fixture(notes={8700: [note(exceptions_until="2026-01-01")]}),
                       SECURITY_LANE_NOW="2000-01-01T00:00:00+00:00")
        self.assertEqual(rc, 1, out)
        self.assertIn("expired after 2026-01-01", out)

    def test_a_naive_clock_override_exits_2(self):
        self.assertEqual(lane(fixture(), SECURITY_LANE_NOW="2099-01-01T12:00:00")[0], 2)

    def test_a_scan_older_than_max_age_is_stale(self):
        self.stale(fixture(checks=[scan(completed="2098-12-30T23:59:59Z")]), "more than 36 h ago")
        self.assertEqual(lane(fixture(checks=[scan(completed="2098-12-31T00:00:01Z")]))[0], 0)

    def test_a_completed_at_without_timezone_is_stale(self):
        self.stale(fixture(checks=[scan(completed="2099-01-01T11:00:00")]), "more than 36 h ago")

    def test_a_pre_3_4_notice_says_re_vendor(self):
        old = {**note(), "message": f"outcome=passed config-tree={TREE}"}
        rc, out = lane(fixture(notes={8700: [old]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("re-vendor nevar-security-review's scan template", out)

    def test_extra_notice_text_is_malformed(self):
        bad = {**note(), "message": note()["message"] + " outcome=passed"}
        rc, out = lane(fixture(notes={8700: [bad]}))
        self.assertEqual(rc, 1, out)
        self.assertIn("malformed", out)


class DispatchRescan(unittest.TestCase):
    """The Security Refresh re-scan: a workflow_dispatch run of main's scan workflow, titled for this PR and head."""

    def rescan(self, run=None, **scan_over):
        check = scan(710, head=MAIN_SHA, started="2026-11-21T10:00:00Z", **scan_over)
        return check, fixture(checks=[scan(), check], dispatch=[run or dispatch_run()],
                              notes={8700: [note(policy="0" * 64)], 8710: [note()]})

    def test_a_fresh_rescan_supersedes_a_stale_scan(self):
        rc, out = lane(fixture(notes={8700: [note(policy="0" * 64)]}))
        self.assertEqual(rc, 1, out)  # the pull_request_target scan alone is stale
        rc, out = lane(self.rescan()[1])
        self.assertEqual(rc, 0, out)
        self.assertIn("security lane ok", out)

    def test_a_rescan_not_titled_for_this_pr_and_head_is_never_evidence(self):
        for run in (dispatch_run(pr=8), dispatch_run(head="e" * 40), dispatch_run(branch="feat/x"),
                    dispatch_run(path=".github/workflows/other.yml"), dispatch_run(event="pull_request")):
            with self.subTest(run=run):
                rc, out = lane(self.rescan(run)[1])
                self.assertEqual(rc, 1, out)
                self.assertIn("forged 'Security Scan' check 8710", out)

    def test_a_rescan_check_must_be_on_its_runs_commit(self):
        _, fix = self.rescan()
        fix["check_runs"][1]["head_sha"] = HEAD_SHA  # the job says main's commit, the check run the PR head
        rc, out = lane(fix)
        self.assertEqual(rc, 1, out)
        self.assertIn("not its run's head cccccccccccc", out)

    def test_a_rescan_notice_must_name_this_pr_and_head(self):
        check, fix = self.rescan()
        fix["annotations"][str(check["id"])] = [note(head="e" * 40)]
        rc, out = lane(fix)
        self.assertEqual(rc, 1, out)
        self.assertIn("is stale", out)

    def test_a_failing_rescan_fails(self):
        check, fix = self.rescan(conclusion="failure")
        fix["annotations"][str(check["id"])] = [note("findings")]
        rc, out = lane(fix)
        self.assertEqual(rc, 1, out)
        self.assertIn("reported findings", out)


class PolicyRevision(unittest.TestCase):
    """--policy-revision (the scan workflow's step) and the lane's remote revision agree on the same blobs."""

    def git(self, repo, *args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    def test_local_revision_matches_the_remote_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.git(repo, "init", "-q")
            blobs = {}
            for path in (".github/workflows/review-gate.yml", "scripts/check-security-scan.py"):
                (repo / path).parent.mkdir(parents=True, exist_ok=True)
                (repo / path).write_text(f"{path}\n")
            (repo / "scripts/check-review-gate.py").symlink_to("check-security-scan.py")  # not a regular file: "-"
            (repo / "scripts/unrelated.py").write_text("x\n")
            self.git(repo, "add", "-A")
            self.git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "c")
            for path in (".github/workflows/review-gate.yml", "scripts/check-security-scan.py"):
                blobs[path] = self.git(repo, "rev-parse", f"HEAD:{path}")
            rc, out = lane({}, args=("--policy-revision", str(repo)))
            self.assertEqual((rc, out.strip()), (0, lane_module._revision(blobs)))
            # the same blobs served through the Contents API give the same revision the lane checks
            fix = fixture(notes={8700: [note(policy=out.strip())]},
                          contents={".github/workflows?ref=main": [{**ENABLED[0], "sha": blobs[".github/workflows/review-gate.yml"]}, ENABLED[1]]})
            fix["scripts"] = {"check-security-scan.py": str(LANE)}
            fix["script_shas"] = {"check-security-scan.py": blobs["scripts/check-security-scan.py"]}
            self.assertEqual(lane(fix)[0], 0)

    def test_not_a_checkout_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = lane({}, args=("--policy-revision", tmp))
            self.assertEqual(rc, 2, out)
            self.assertIn("could not compute the policy revision", out)

    def test_unknown_arguments_exit_2(self):
        self.assertEqual(lane(fixture(), args=("--bogus",))[0], 2)


GATE_RUN = ".github/workflows/review-gate.yml\tpull_request_target"
REFRESH = Path(__file__).resolve().parents[1] / "templates" / "review-gate-security-refresh.yml"


def refresh_fixture(gate_runs=None, open_pulls=None, **extra):
    fix = fixture()
    fix["pull"]["state"] = "open"
    gate_runs = {"650": {"display_title": "Review Gate - PR #7", "status": "completed",
                         "created_at": "2026-11-21T10:00:00Z"}} if gate_runs is None else gate_runs
    fix["runs"].update({i: GATE_RUN for i in gate_runs})
    fix["run_meta"] = gate_runs
    fix["open_pulls"] = [{"number": 7, "head": {"sha": HEAD_SHA}}] if open_pulls is None else open_pulls
    return {**fix, **extra}


class Refresh(unittest.TestCase):
    """--refresh, the Security Refresh workflow's body, against the fake gh; posts.log holds its POSTs."""

    def refresh(self, fix, event="push", title=""):
        rc, out = lane(fix, args=("--refresh",), EVENT=event, TITLE=title)
        return rc, out, lane.posts

    def test_push_dispatches_a_rescan_and_reruns_the_gate(self):
        rc, out, posts = self.refresh(refresh_fixture())
        self.assertEqual(rc, 0, out)
        dispatch = next(p for p in posts if "/dispatches" in p)
        self.assertIn("actions/workflows/review-gate-security-scan.yml/dispatches", dispatch)
        for field in ("ref=main", "inputs[pr]=7", f"inputs[head]={HEAD_SHA}"):
            self.assertIn(field, dispatch.split())
        self.assertIn("api repos/o/r/actions/runs/650/rerun -X POST", posts)

    def test_the_newest_gate_run_of_this_pr_is_rerun(self):
        runs = {"650": {"display_title": "Review Gate - PR #7", "status": "completed", "created_at": "2026-11-21T10:00:00Z"},
                "651": {"display_title": "Review Gate - PR #7", "status": "completed", "created_at": "2026-11-21T11:00:00Z"},
                "652": {"display_title": "Review Gate - PR #8", "status": "completed", "created_at": "2026-11-21T12:00:00Z"}}
        rc, out, posts = self.refresh(refresh_fixture(runs))
        self.assertEqual(rc, 0, out)
        self.assertEqual([p for p in posts if "/rerun" in p], ["api repos/o/r/actions/runs/651/rerun -X POST"])

    def test_a_running_gate_run_is_left_to_the_scan_on_push(self):
        runs = {"650": {"display_title": "Review Gate - PR #7", "status": "in_progress", "created_at": "2026-11-21T10:00:00Z"}}
        rc, out, posts = self.refresh(refresh_fixture(runs))
        self.assertEqual(rc, 0, out)
        self.assertFalse([p for p in posts if "/rerun" in p], posts)
        self.assertIn("still running", out)

    def test_a_refused_rerun_fails_and_names_the_pr(self):
        rc, out, _ = self.refresh(refresh_fixture(post_fails=[r"/rerun"]))
        self.assertEqual(rc, 1, out)
        self.assertIn("PR #7: its Review Gate run 650 could not be re-run", out)
        self.assertIn("close and reopen that PR", out)

    def test_a_refused_dispatch_fails_and_skips_that_prs_rerun(self):
        two = [{"number": 7, "head": {"sha": HEAD_SHA}}, {"number": 8, "head": {"sha": "e" * 40}}]
        runs = {"650": {"display_title": "Review Gate - PR #7", "status": "completed", "created_at": "2026-11-21T10:00:00Z"},
                "660": {"display_title": "Review Gate - PR #8", "status": "completed", "created_at": "2026-11-21T10:00:00Z"}}
        rc, out, posts = self.refresh(refresh_fixture(runs, two, post_fails=[r"inputs\[pr\]=7 "]))
        self.assertEqual(rc, 1, out)
        self.assertIn("PR #7: Security Scan could not be dispatched", out)
        self.assertNotIn("api repos/o/r/actions/runs/650/rerun -X POST", posts)
        self.assertIn("api repos/o/r/actions/runs/660/rerun -X POST", posts)  # the other PR still refreshed

    def test_no_gate_run_fails(self):
        rc, out, _ = self.refresh(refresh_fixture({}))
        self.assertEqual(rc, 1, out)
        self.assertIn("no Review Gate run to re-run", out)

    def test_workflow_run_reruns_the_scanned_prs_gate_after_it_finishes(self):
        runs = {"650": {"display_title": "Review Gate - PR #7", "status": ["in_progress", "completed"],
                        "created_at": "2026-11-21T10:00:00Z"}}
        rc, out, posts = self.refresh(refresh_fixture(runs), "workflow_run", lane_module.RUN_TITLE.format(pr=7, head=HEAD_SHA))
        self.assertEqual(rc, 0, out)
        self.assertEqual(posts, ["api repos/o/r/actions/runs/650/rerun -X POST"])

    def test_workflow_run_of_something_else_does_nothing(self):
        for title in ("Security Scan - PR #7 @ main; rm -rf /", "anything", ""):
            with self.subTest(title=title):
                rc, out, posts = self.refresh(refresh_fixture(), "workflow_run", title)
                self.assertEqual((rc, posts), (0, []), out)
                self.assertNotIn("rm -rf", out)  # never echoed

    def test_workflow_run_for_a_moved_or_closed_pr_does_nothing(self):
        moved = lane_module.RUN_TITLE.format(pr=7, head="e" * 40)
        rc, out, posts = self.refresh(refresh_fixture(), "workflow_run", moved)
        self.assertEqual((rc, posts), (0, []), out)
        fix = refresh_fixture(); fix["pull"]["state"] = "closed"
        rc, out, posts = self.refresh(fix, "workflow_run", lane_module.RUN_TITLE.format(pr=7, head=HEAD_SHA))
        self.assertEqual((rc, posts), (0, []), out)

    def test_missing_env_exits_2(self):
        self.assertEqual(lane(refresh_fixture(), args=("--refresh",))[0], 2)  # no EVENT


class RefreshWorkflow(unittest.TestCase):
    """The real review-gate-security-refresh.yml: its triggers and its run block against the fake gh."""

    def test_push_paths_are_the_policy_files_plus_the_scan_config(self):
        on = yaml.safe_load(REFRESH.read_text())[True]  # YAML 1.1 reads the `on` key as True
        self.assertEqual(sorted(on["push"]["paths"]), sorted([*lane_module.POLICY_FILES, ".github/security-scan/**",
                                                              ".github/workflows/review-gate-security-scan.yml"]))
        self.assertEqual(on["workflow_run"], {"workflows": ["Security Scan"], "types": ["completed"]})
        self.assertIn("schedule", on)

    def test_least_privilege_and_no_expressions_in_run(self):
        doc = yaml.safe_load(REFRESH.read_text())
        self.assertEqual(doc["permissions"], {})
        job = doc["jobs"]["refresh"]
        self.assertEqual(job["permissions"], {"actions": "write", "contents": "read", "pull-requests": "read"})
        self.assertNotIn("concurrency", doc)
        self.assertNotIn("${{", job["steps"][0]["run"])

    def run_block(self, fix, event="push", title="", missing=()):
        run = yaml.safe_load(REFRESH.read_text())["jobs"]["refresh"]["steps"][0]["run"]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bindir = tmp / "bin"; bindir.mkdir()
            (bindir / "gh").write_text(FAKE_GH); (bindir / "gh").chmod(0o755)
            fix = {**fix, "scripts": {n: str(SCRIPTS / n) for n in
                                      ("check-security-scan.py", "check-forged-review-gate.py", "check-forged-gate-names.py")
                                      if n not in missing}}
            (tmp / "fixture.json").write_text(json.dumps(fix))
            work = tmp / "job"; work.mkdir()
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=str(tmp), GH_TOKEN="x",
                       REPO="o/r", EVENT=event, TITLE=title, SECURITY_LANE_NOW=NOW)
            proc = subprocess.run(["bash", "-c", run.replace("/tmp/", f"{work}/")], capture_output=True, text=True, env=env)
            posts = tmp / "posts.log"
            return proc.returncode, proc.stdout + proc.stderr, posts.read_text().splitlines() if posts.exists() else []

    def test_the_run_block_loads_main_scripts_and_refreshes(self):
        rc, out, posts = self.run_block(refresh_fixture())
        self.assertEqual(rc, 0, out)
        self.assertEqual(len([p for p in posts if "/dispatches" in p and "ref=main" in p]), 1, posts)
        self.assertIn("api repos/o/r/actions/runs/650/rerun -X POST", posts)

    def test_a_missing_script_fails_closed(self):
        rc, out, posts = self.run_block(refresh_fixture(), missing=("check-forged-gate-names.py",))
        self.assertNotEqual(rc, 0, out)
        self.assertEqual(posts, [])


class MergeGuardSecurityLane(unittest.TestCase):
    """merge-guard runs the lane itself before a merge (not only CI's gate run), failing closed."""

    def guard(self, fix, head=HEAD_SHA, budget=None):
        spec = importlib.util.spec_from_file_location("mg_lane", SCRIPTS / "merge-guard.py")
        mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)
        if budget is not None:
            mg.HOOK_BUDGET_S = budget
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp); (bindir / "gh").write_text(FAKE_GH); (bindir / "gh").chmod(0o755)
            (bindir / "fixture.json").write_text(json.dumps(fix))
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=tmp, SECURITY_LANE_NOW=NOW)
            return mg.security_lane_check("o", "r", 7, head, None, env)

    def test_a_fresh_passing_scan_allows(self):
        self.assertIsNone(self.guard(fixture()))

    def test_a_repo_without_the_lane_allows(self):
        self.assertIsNone(self.guard(fixture(contents={".github/workflows?ref=main": ENABLED[:1]})))

    def test_a_scan_gone_stale_since_ci_blocks(self):
        msg = self.guard(fixture(notes={8700: [note(policy="0" * 64)]}))
        self.assertIn("security lane exited 1", msg)
        self.assertIn("policy revision", msg)
        self.assertNotIn("::error::", msg)

    def test_a_moved_head_blocks(self):
        self.assertIn("security lane exited 2", self.guard(fixture(), head="e" * 40))

    def test_the_default_branch_comes_from_the_api(self):
        fix = fixture(); fix["default_branch"] = "trunk"  # main's listings no longer apply: "not enabled"
        self.assertIsNone(self.guard(fix))

    def test_an_unreadable_default_branch_blocks(self):
        msg = self.guard({**fixture(), "fail": {"pattern": r"^api repos/o/r$"}})
        self.assertIn("could not read the default branch of o/r", msg)

    def test_running_out_of_budget_blocks(self):
        msg = self.guard({**fixture(), "sleep": 0.3}, budget=0.2)
        self.assertIn("security lane did not finish within", msg)


if __name__ == "__main__":
    unittest.main()
