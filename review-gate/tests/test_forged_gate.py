"""Behavior tests for the forged-`Review Gate` step (SEC-MVS-01 S5).

Runs the workflow template's real `run:` block under bash with a fake `gh` on PATH,
so a regression in the wiring (not only in the detector) fails here.
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
TEMPLATE = SKILL / "templates" / "review-gate.yml"
TRUSTED_RUN = ".github/workflows/review-gate.yml\tpull_request_target"

FAKE_GH = r'''#!/usr/bin/env python3
import base64, json, os, sys
state = os.environ["FAKE_STATE"]
args = sys.argv[1:]
with open(os.path.join(state, "calls.log"), "a") as log:
    log.write(" ".join(args) + "\n")
fixture = json.load(open(os.path.join(state, "fixture.json")))
__import__("time").sleep(fixture.get("sleep", 0))  # a slow GitHub, for merge-guard's time budget
path = next(a for a in args if a.startswith("repos/"))
fail = fixture.get("fail")  # {"pattern": regex over the joined args, "nth": which match 404s (1-based)}
if fail and __import__("re").search(fail["pattern"], " ".join(args)):
    seen_path = os.path.join(state, "fail.count")
    seen = int(open(seen_path).read()) + 1 if os.path.exists(seen_path) else 1
    open(seen_path, "w").write(str(seen))
    if seen == fail.get("nth", 1):
        print("gh: Not Found (HTTP 404)", file=sys.stderr); sys.exit(1)
HEAD = "a" * 40
created_path = os.path.join(state, "created.json")
created = json.load(open(created_path)) if os.path.exists(created_path) else []
if "-X" in args and "POST" in args:
    check_id = 900 + len(created)
    ext = next((a.split("=", 1)[1] for a in args if a.startswith("external_id=")), None)
    created.append({"id": check_id, "name": "Review Gate", "app": {"slug": "github-actions"},
                    "external_id": ext, "details_url": f"https://github.com/o/r/runs/{check_id}",
                    "check_suite": {"id": fixture.get("current_suite", 1)}})
    json.dump(created, open(created_path, "w")); print(check_id); sys.exit(0)
if "-X" in args and "PATCH" in args:
    concl = next(a.split("=", 1)[1] for a in args if a.startswith("conclusion="))
    with open(os.path.join(state, "patches.log"), "a") as patches:
        patches.write(f"{path.rsplit('/', 1)[1]} {concl}\n")
    open(os.path.join(state, "conclusion"), "w").write(concl); sys.exit(0)
if path.endswith("/contents/.github/workflows/review-gate.yml"):  # merge-guard's "is the gate configured"
    wf = fixture.get("workflow", True)
    if wf is True:
        sys.exit(0)
    print("gh: Not Found (HTTP 404)" if wf is False else "gh: Bad Gateway (HTTP 502)", file=sys.stderr); sys.exit(1)
if path.split("?")[0].endswith("/contents/scripts"):  # the gate's listing of the trusted scripts
    print(json.dumps([{"name": n, "type": "file"} for n in fixture["scripts"]])); sys.exit(0)
if "/contents/scripts/" in path:
    name = path.split("/contents/scripts/")[1].split("?")[0]
    src = fixture["scripts"].get(name)
    if src is None:
        sys.exit(1)
    print(json.dumps({"content": base64.b64encode(open(src, "rb").read()).decode()})); sys.exit(0)
if "/check-runs" in path and "/commits/" in path:
    if fixture.get("listing_fails"):
        sys.exit(1)
    if "raw_listing" in fixture:
        print(fixture["raw_listing"]); sys.exit(0)
    runs = fixture["check_runs"] + created + fixture.get("own_jobs", [])
    page2 = fixture.get("page2", [])  # served only to --paginate, as a second concatenated page
    pages = [{"total_count": len(runs) + len(page2), "check_runs": runs}]
    if page2 and "--paginate" in args:
        pages.append({"total_count": len(runs) + len(page2), "check_runs": page2})
    print(json.dumps(pages) if "--slurp" in args else "\n".join(json.dumps(p) for p in pages))
    sys.exit(0)
if path.split("/check-runs/")[-1].isdigit():  # the security lane's read of the newest scanner job's check run
    check_id = int(path.rsplit("/", 1)[1])
    found = [c for c in fixture["check_runs"] + fixture.get("own_jobs", []) if c.get("id") == check_id]
    if not found:
        sys.exit(1)
    print(json.dumps(found[0])); sys.exit(0)
if "/actions/workflows/" in path and "/runs?" in path:  # the security lane's scanner-run discovery, slurped
    wf = path.split("/actions/workflows/")[1].split("/")[0]
    found = [{"id": int(i), "path": pair.split("\t")[0], "event": pair.split("\t")[1]}
             for i, pair in fixture.get("runs", {}).items() if pair.split("\t")[0].endswith("/" + wf)]
    print(json.dumps([{"total_count": len(found), "workflow_runs": found}])); sys.exit(0)
if path.endswith("/annotations"):  # the security lane's read of one check run's annotations, slurped
    found = fixture.get("annotations", {}).get(path.split("/")[-2])
    if found is None:
        sys.exit(1)
    print(json.dumps([found])); sys.exit(0)
if "/contents/.github" in path:  # the security lane's directory listings, keyed by "<dir>?ref=<ref>"
    key = path.split("/contents/", 1)[1]
    default = [{"name": "review-gate.yml", "type": "file", "sha": "0" * 40}] if key.startswith(".github/workflows?") else None
    listing = fixture.get("contents", {}).get(key, default)
    if listing is None:
        sys.exit(1)
    print(json.dumps(listing)); sys.exit(0)
if "/pulls?" in path:  # the wrapper's head-repo/branch PR listing (3.2.16), one page
    if "branch_pulls_raw" in fixture:
        print(fixture["branch_pulls_raw"]); sys.exit(0)
    if fixture.get("branch_pulls") is None:  # null: that lookup fails
        sys.exit(1)
    print(json.dumps([fixture["branch_pulls"]])); sys.exit(0)
if "/pulls/" in path:
    if fixture.get("pull") is None:  # null: that lookup fails
        sys.exit(1)
    print(json.dumps(fixture["pull"])); sys.exit(0)
if "/actions/runs/" in path and "/jobs?" in path:  # the security lane's job listing for one run, slurped
    found = fixture.get("jobs", {}).get(path.split("/")[-2])
    if found is None:
        sys.exit(1)
    print(json.dumps([{"total_count": len(found), "jobs": found}])); sys.exit(0)
if "/actions/runs/" in path and "--jq" not in args:  # the wrapper's one run read: head fields and title (3.2.17)
    run_id = path.rsplit("/", 1)[1]
    heads, title = fixture.get("run_heads", {}).get(run_id), fixture.get("titles", {}).get(run_id)
    pair = fixture.get("runs", {}).get(run_id)
    if heads is None and title is None and pair is None:
        sys.exit(1)
    # a missing piece is absent from the run JSON, which must fail closed where the wrapper reads it
    print(json.dumps({**(dict(zip(("path", "event"), pair.split("\t"))) if pair else {}), **(heads or {}),
                      **({"display_title": title} if title else {})})); sys.exit(0)
if "/actions/runs/" in path:
    run_id = path.rsplit("/", 1)[1]
    if run_id not in fixture["runs"]:
        sys.exit(1)
    print(fixture["runs"][run_id]); sys.exit(0)
sys.exit(3)
'''


def run_block():
    lines = TEMPLATE.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "run: |") + 1
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = []
    for line in lines[start:]:
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        body.append(line)
    return textwrap.dedent("\n".join(body)) + "\n"


def job(name, run_id):
    return {"id": 9000 + run_id, "name": name, "app": {"slug": "github-actions"}, "details_url": f"https://github.com/o/r/actions/runs/{run_id}/job/9{run_id}",
            "html_url": f"https://github.com/o/r/actions/runs/{run_id}/job/9{run_id}"}


def api_check(name, check_id, pr=None, suite=1):
    return {"id": check_id, "name": name, "app": {"slug": "github-actions"}, "details_url": f"https://github.com/o/r/runs/{check_id}",
            "html_url": f"https://github.com/o/r/runs/{check_id}", "external_id": f"review-gate-pr-{pr}" if pr else None,
            "check_suite": {"id": suite}}


def run_title(pr):
    """The workflow run title GitHub shows for PR <pr>: the template's run-name as YAML parses it."""
    return str(yaml.safe_load(TEMPLATE.read_text())["run-name"]).replace(
        "${{ github.event.pull_request.number }}", str(pr))


RG_PATH = ".github/workflows/review-gate.yml"
HEAD_SHA = "a" * 40


def pull(head_ref="chore/revendor-review-gate", head_repo="o/r", head_sha=HEAD_SHA):
    return {"number": 7, "created_at": "2026-11-20T10:00:00Z", "base": {"ref": "main", "repo": {"full_name": "o/r", "default_branch": "main"}},
            "head": {"ref": head_ref, "sha": head_sha, "repo": {"full_name": head_repo}}}


# The gate's own run, as the provenance check reads it: PR #7's head, and #7 alone on its head branch.
PROVENANCE = {"pull": pull(), "branch_pulls": [{"number": 7, "head": {"sha": HEAD_SHA, "ref": "chore/revendor-review-gate"},
                                                "created_at": "2026-11-20T10:00:00Z", "closed_at": None}]}


def other_pr(number, sha="c" * 40, created_at="2026-11-18T10:00:00Z", closed_at="2026-11-19T10:00:00Z"):
    return {"number": number, "head": {"sha": sha}, "created_at": created_at, "closed_at": closed_at}


def run_heads(head_branch="chore/revendor-review-gate", head_repo="o/r", head_sha=HEAD_SHA,
              created_at="2026-11-20T10:00:05Z"):
    return {"head_sha": head_sha, "head_branch": head_branch, "head_repository": {"full_name": head_repo},
            "created_at": created_at}


class ForgedGateWorkflow(unittest.TestCase):
    def gate(self, check_runs, runs=None, listing_fails=False, missing=(), evaluations=1, prs=None, fixture=None, empty=()):
        """prs: [(pr_number, checker_rc)] evaluations on the same head sha (default PR 7 passing).

        Each evaluation's own job (`Review Gate`, run 600 + n) is on the head, as GitHub lists it.
        """
        prs = prs or [("7", 0)] * evaluations
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bindir = tmp / "bin"; bindir.mkdir()
            (bindir / "gh").write_text(FAKE_GH); (bindir / "gh").chmod(0o755)
            passing_checker = tmp / "check-review-gate.py"
            passing_checker.write_text("import os, sys\nprint('review-gate ok')\nsys.exit(int(os.environ['FAKE_CHECKER_RC']))\n")
            scripts = {"check-review-gate.py": str(passing_checker),
                       "check-forged-gate-names.py": str(SCRIPTS / "check-forged-gate-names.py"),
                       "check-forged-review-gate.py": str(SCRIPTS / "check-forged-review-gate.py"),
                       "check-security-scan.py": str(SCRIPTS / "check-security-scan.py")}
            for name in missing:
                scripts.pop(name)
            for name in empty:
                (tmp / f"empty-{name}").write_text("")
                scripts[name] = str(tmp / f"empty-{name}")
            own_ids = [str(600 + n) for n, _ in enumerate(prs)]
            (tmp / "fixture.json").write_text(json.dumps(
                {"scripts": scripts, "check_runs": check_runs, "listing_fails": listing_fails,
                 "runs": {**{i: TRUSTED_RUN for i in own_ids}, **(runs or {})},
                 "titles": {i: run_title(n) for i, (n, _) in zip(own_ids, prs)},
                 **PROVENANCE, "run_heads": {i: run_heads() for i in own_ids},
                 "own_jobs": [job("Review Gate", int(i)) for i in own_ids], **(fixture or {})}))
            workdir = tmp / "job"; workdir.mkdir()
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=str(tmp), GH_TOKEN="x",
                       PR_NUMBER="7", REPO="o/r", SHA="a" * 40, DEFAULT_BRANCH="main")
            # The block writes the trusted scripts to /tmp/<name>; point that at this test's own dir.
            script = run_block().replace("/tmp/", f"{workdir}/")
            self.rcs = []
            for pr_number, checker_rc in prs:
                proc = subprocess.run(["bash", "-e", "-c", script], capture_output=True, text=True,
                                      env=dict(env, PR_NUMBER=pr_number, FAKE_CHECKER_RC=str(checker_rc)))
                self.rcs.append(proc.returncode)
            self.calls = (tmp / "calls.log").read_text().splitlines()
            self.patches = (tmp / "patches.log").read_text().splitlines() if (tmp / "patches.log").exists() else []
            self.created = json.loads((tmp / "created.json").read_text()) if (tmp / "created.json").exists() else []
            return proc.returncode, proc.stdout + proc.stderr

    def final(self):
        out = {}
        for line in self.patches:
            check_id, conclusion = line.split()
            out[check_id] = conclusion
        return out

    def test_forged_same_repo_review_gate_job_fails_the_gate(self):
        rc, out = self.gate([job("Review Gate", 500)], runs={"500": ".github/workflows/forge.yml\tpull_request"})
        self.assertEqual(rc, 1, out)
        self.assertIn("forged check 'Review Gate'", out)

    def test_own_job_and_other_jobs_pass(self):
        rc, out = self.gate([job("CI", 502)], runs={"502": ".github/workflows/ci.yml\tpull_request"})
        self.assertEqual(rc, 0, out)

    def test_failing_checker_fails_the_job(self):
        rc, out = self.gate([])
        self.assertEqual(rc, 0, out)
        rc, out = self.gate([], prs=[("7", 1)])
        self.assertEqual(rc, 1, out)

    # 3.2.8: the job IS the required check. Its check run is on the PR head in its own run's suite
    # (email_demo #1068), the suite the required-status rule reads; a Checks API POST lands in the head's
    # oldest suite and the rule read "expected" (#104). So the job carries the name and nothing is POSTed.
    def test_gate_job_is_named_like_the_required_check(self):
        self.assertEqual(yaml.safe_load(TEMPLATE.read_text())["jobs"]["gate"]["name"], "Review Gate")

    def test_no_check_run_is_posted(self):
        self.assertNotIn("-X POST", run_block())
        self.gate([api_check("Review Gate", 41, pr=7)])
        self.assertEqual(self.created, [])
        self.assertFalse([c for c in self.calls if "POST" in c], self.calls)

    def test_main_via_staging_pull_request_job_is_not_flagged(self):
        # Several repos publish this name from a plain pull_request job; Review Gate must not block them.
        rc, out = self.gate([job("PRs into main must come from staging", 503)],
                            runs={"503": ".github/workflows/main-via-staging.yml\tpull_request"})
        self.assertEqual(rc, 0, out)

    # 3.2.1 still holds for runs 3.2.0-3.2.7 POSTed: every evaluation completes all of this PR's legacy
    # API runs with its result, so no earlier red (or green) API run stays standing beside the job.
    def test_every_legacy_api_run_of_this_pr_gets_the_latest_result(self):
        legacy = [api_check("Review Gate", 41, pr=7), api_check("Review Gate", 42, pr=7)]
        rc, out = self.gate(legacy, prs=[("7", 0), ("7", 1)])
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.final(), {"41": "failure", "42": "failure"})
        self.gate(legacy, prs=[("7", 1), ("7", 0)])
        self.assertEqual(self.final(), {"41": "success", "42": "success"})

    # nevar-content Codex P1: two PRs on one head sha must not complete each other's legacy runs. Each
    # also sees the other's gate job on the head, so both fail closed (3.2.8): only 41 ever gets PR 11's.
    def test_shared_head_pr_b_never_flips_pr_a_legacy_run(self):
        self.gate([api_check("Review Gate", 41, pr=11), api_check("Review Gate", 42, pr=12)],
                  prs=[("11", 1), ("12", 0)])
        self.assertEqual(self.rcs, [1, 1])
        self.assertEqual(self.final(), {"41": "failure", "42": "failure"})

    def test_unmarked_or_other_pr_runs_and_jobs_are_never_patched(self):
        # Pre-3.2.2 runs carry no PR marker: they could belong to any PR on this head, so never adopt them.
        rc, out = self.gate([api_check("Review Gate", 41), api_check("Review Gate", 42, pr=8),
                             job("Review Gate", 500)], runs={"500": ".github/workflows/forge.yml\tpull_request"})
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.patches, [])

    # #105 Codex P1: another PR on this head (open, merged, or closed-unmerged, which commits/{sha}/pulls
    # omits) leaves a trusted-pair job here. Its run title names that PR, so it is not this PR's result.
    def test_another_prs_gate_job_on_this_head_fails_the_gate(self):
        rc, out = self.gate([job("Review Gate", 517)], runs={"517": TRUSTED_RUN},
                            fixture={"titles": {"600": run_title(7), "517": run_title(8)}})
        self.assertEqual(rc, 1, out)
        self.assertIn("'Review Gate - PR #8', not 'Review Gate - PR #7'", out)
        # 517 is rejected on its title alone, read with its head fields in the run's one fetch (3.2.17, #134)
        self.assertEqual(self.calls.count("api repos/o/r/actions/runs/517"), 1, self.calls)

    def test_failed_listing_fails_closed(self):
        rc, out = self.gate([], listing_fails=True)
        self.assertEqual(rc, 1, out)

    def test_unreadable_run_lookup_fails_closed(self):
        rc, out = self.gate([job("Review Gate", 504)])
        self.assertEqual(rc, 1, out)
        self.assertIn("forged-check step failed (exit 2)", out)

    def test_empty_trusted_script_fails_closed(self):
        for name in ("check-review-gate.py", "check-forged-review-gate.py"):
            with self.subTest(name=name):
                rc, out = self.gate([], empty=(name,))
                self.assertEqual(rc, 1, out)
                self.assertIn(f"Could not load trusted scripts/{name}", out)

    def test_missing_detector_on_default_branch_fails_closed(self):
        rc, out = self.gate([], missing=("check-forged-gate-names.py",))
        self.assertEqual(rc, 1, out)
        self.assertIn("Could not load trusted scripts/check-forged-gate-names.py", out)
        self.assertIn("::error::review-gate: gh api GET repos/o/r/contents/scripts/check-forged-gate-names.py?ref=main failed", out)

    # nevar-auth #26 (3.2.7): a PATCH got "gh: Not Found (HTTP 404)", the step died without naming the call,
    # and its POSTed run stayed queued. 3.2.8 POSTs nothing; any API error fails the job, which IS the
    # check (a terminal failure even with the Checks API down), and the log names method and endpoint.
    # Legacy cleanup stays best effort: the failed job, not the legacy run, is what blocks the merge.
    def api_error(self, pattern, nth=1, prs=None):
        rc, out = self.gate([api_check("Review Gate", 41, pr=7)], prs=prs,
                            fixture={"fail": {"pattern": pattern, "nth": nth}})
        self.assertEqual(rc, 1, out)
        return out

    def test_initial_legacy_patch_error_fails_before_evaluating(self):
        out = self.api_error(r"PATCH repos/o/r/check-runs/41 ")
        self.assertIn("::error::review-gate: gh api PATCH repos/o/r/check-runs/41 failed (exit 1)", out)
        self.assertFalse([c for c in self.calls if "/contents/" in c], self.calls)

    def test_final_legacy_patch_error_turns_a_pass_into_a_failure(self):
        out = self.api_error(r"PATCH repos/o/r/check-runs/41 ", nth=2)
        self.assertIn("::error::review-gate: gh api PATCH repos/o/r/check-runs/41 failed (exit 1)", out)
        self.assertIn("were not all completed; failing closed", out)
        self.assertEqual(self.patches, ["41 failure"])

    def test_legacy_listing_error_fails_closed_and_names_the_call(self):
        out = self.api_error(r"check_name=Review%20Gate")
        self.assertIn("::error::review-gate: gh api GET repos/o/r/commits/" + "a" * 40
                      + "/check-runs?check_name=Review%20Gate&filter=all&per_page=100 failed", out)
        self.assertIn("could not list legacy Review Gate check runs", out)
        self.assertEqual(self.patches, [])

    def test_final_legacy_listing_error_fails_a_passing_gate(self):
        out = self.api_error(r"check_name=Review%20Gate", nth=2)
        self.assertIn("could not list legacy Review Gate check runs", out)
        self.assertEqual(self.patches, ["41 failure"])

    def test_forged_listing_error_names_the_call(self):
        out = self.api_error(r"check-runs\?per_page=100&filter=all")
        self.assertIn("::error::review-gate: gh api GET repos/o/r/commits/" + "a" * 40
                      + "/check-runs?per_page=100&filter=all failed", out)
        self.assertEqual(self.final(), {"41": "failure"})

    # Sonnet b on ea4fb8b, P1 1: both listings must read every page, not only the first 100 runs.
    def test_forged_job_on_a_later_page_fails_the_gate(self):
        rc, out = self.gate([], runs={"500": ".github/workflows/forge.yml\tpull_request"},
                            fixture={"page2": [job("Review Gate", 500)]})
        self.assertEqual(rc, 1, out)
        self.assertIn("forged check 'Review Gate'", out)

    def test_legacy_run_on_a_later_page_is_completed(self):
        rc, out = self.gate([], fixture={"page2": [api_check("Review Gate", 41, pr=7)]})
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.final(), {"41": "success"})

    # Sonnet b on ea4fb8b, P1 2-3: the trigger, token scope and step inputs are the security boundary.
    def test_trigger_permissions_and_inputs_are_pinned(self):
        wf = yaml.safe_load(TEMPLATE.read_text())
        self.assertEqual(wf[True], {"pull_request_target": {"types": [
            "opened", "reopened", "ready_for_review", "synchronize", "edited", "labeled", "unlabeled"]}})
        self.assertEqual(wf["permissions"], {"contents": "read", "pull-requests": "read", "checks": "write",
                                             "actions": "read"})
        # no concurrency group: a cancelled newest run blocks the merge (review-gate-sandbox PR #30)
        self.assertNotIn("concurrency", wf)
        self.assertNotIn("concurrency", wf["jobs"]["gate"])
        self.assertEqual(list(wf["jobs"]), ["gate"])
        (step,) = wf["jobs"]["gate"]["steps"]
        self.assertEqual(step["env"], {
            "GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
            "PR_NUMBER": "${{ github.event.pull_request.number }}",
            "REPO": "${{ github.repository }}",
            "SHA": "${{ github.event.pull_request.head.sha }}",
            "DEFAULT_BRANCH": "${{ github.event.repository.default_branch }}"})
        self.assertNotIn("uses", step)  # no checkout: PR-head code never runs

    # 3.2.7 P1: an unquoted run-name lost " #<n>" to a YAML comment. Parse the real template, as GitHub does.
    def test_run_name_keeps_the_pr_number(self):
        self.assertEqual(run_title(7), "Review Gate - PR #7")
        wrapper = (SCRIPTS / "check-forged-review-gate.py").read_text()
        self.assertIn(f'RUN_TITLE = "{run_title("{pr}")}"', wrapper)  # the wrapper matches this exact title
        for line in TEMPLATE.read_text().split("\njobs:\n", 1)[0].splitlines():  # top-level plain scalars
            if line and not line[0].isspace() and not line.startswith("#") and ": " in line:
                value = line.split(": ", 1)[1].strip()
                self.assertFalse(" #" in value and value[0] not in "\"'", line)


class WrapperReason(unittest.TestCase):
    def test_wrapper_reason_still_holds(self):
        # The wrapper exists because downstream repos still publish the main-via-staging name from other
        # Actions jobs, so it scopes the detector to `Review Gate`. 3.2.20 re-vendored aec's map, which now
        # pins that name to the guard's own pull_request_target job (the guard sees its own in-progress run).
        import importlib.util
        spec = importlib.util.spec_from_file_location("cfgn", SCRIPTS / "check-forged-gate-names.py")
        detector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(detector)
        self.assertEqual(detector.PROTECTED["PRs into main must come from staging"],
                         {(".github/workflows/main-via-staging.yml", "pull_request_target")})
        self.assertEqual(detector.PROTECTED["Review Gate"],
                         {(".github/workflows/review-gate.yml", "pull_request_target")})
        header = (SCRIPTS / "check-forged-review-gate.py").read_text()
        self.assertIn("THE GATE'S OWN JOB IS THE RESULT", header)
        self.assertIn("WHY THIS WRAPPER EXISTS", header)
        self.assertIn("DELETE THIS WRAPPER when Option A or B", header)


class WrapperDetector(unittest.TestCase):
    def wrapper(self, check_runs, runs, stdin=None, fixture=None, **env_over):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp); (bindir / "gh").write_text(FAKE_GH); (bindir / "gh").chmod(0o755)
            (bindir / "fixture.json").write_text(json.dumps({
                "scripts": {}, "check_runs": check_runs, "runs": runs,
                "titles": {i: run_title(7) for i in runs}, **PROVENANCE,
                "run_heads": {i: run_heads() for i in runs}, **(fixture or {})}))
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=tmp, REPO="o/r", PR_NUMBER="7")
            for key, value in env_over.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value
            if stdin is None:
                stdin = json.dumps({"total_count": len(check_runs), "check_runs": check_runs})
            proc = subprocess.run([sys.executable, str(SCRIPTS / "check-forged-review-gate.py")], input=stdin,
                                  env=env, capture_output=True, text=True)
            self.calls = (bindir / "calls.log").read_text().splitlines() if (bindir / "calls.log").exists() else []
            return proc.returncode, proc.stderr

    def test_gate_job_from_the_trusted_pair_exits_0(self):
        # Includes a pre-3.2.0 workflow's `Review Gate` job: same pair, also the real gate result.
        rc, err = self.wrapper([job("Review Gate", 506), api_check("Review Gate", 41, pr=7)], {"506": TRUSTED_RUN})
        self.assertEqual(rc, 0, err)

    def test_legacy_api_run_alone_exits_0(self):
        rc, err = self.wrapper([api_check("Review Gate", 41)], {})
        self.assertEqual(rc, 0, err)

    def test_trusted_pair_job_of_another_pr_exits_1(self):
        # A closed-unmerged child's run on this head: no PR listing shows it, its run title does.
        for title in ("Review Gate - PR #8", "Review Gate - PR #77", " Review Gate - PR #8 "):  # stripped, as before
            with self.subTest(title=title):
                rc, err = self.wrapper([job("Review Gate", 517)], {"517": TRUSTED_RUN},
                                       fixture={"titles": {"517": title}})
                self.assertEqual(rc, 1, err)
                self.assertIn("not 'Review Gate - PR #7'", err)
                # 3.2.13: another PR's real run title names that PR and the fix
                self.assertIn("shared head sha, not this PR's run: ", err)
                self.assertIn(f"this head sha is also PR #{title.strip().rsplit('#', 1)[1]}'s head, and that PR's Review Gate "
                              "run is listed on it. Push a new commit to this PR (an empty commit works) so it "
                              "has a head of its own", err)

    # 3.2.16: the run title is not trust. A default branch whose review-gate.yml predates run-name (defect 4)
    # titles the gate's run with the PR title, which the PR author writes. Every run takes one provenance path.
    def gate_run(self, title=None, pair=TRUSTED_RUN, **fixture):
        return self.wrapper([job("Review Gate", 530)], {"530": pair},
                            fixture={"titles": {"530": title or run_title(7)}, **fixture})

    def test_own_run_passes_on_provenance_whatever_its_title(self):
        for title in (run_title(7), "chore: re-vendor review-gate 3.2.16", "Review Gate - PR", "Review Gate"):
            with self.subTest(title=title):
                rc, err = self.gate_run(title)
                self.assertEqual(rc, 0, err)

    def test_fork_pr_run_from_its_fork_exits_0(self):
        rc, err = self.gate_run(pull=pull(head_repo="fork/r"), run_heads={"530": run_heads(head_repo="fork/r")})
        self.assertEqual(rc, 0, err)

    def test_older_closed_pr_from_the_same_branch_is_ignored(self):
        rc, err = self.gate_run(branch_pulls=[*PROVENANCE["branch_pulls"], other_pr(3)])
        self.assertEqual(rc, 0, err)

    def test_run_of_another_pr_exits_1_even_titled_as_this_prs(self):
        # Codex P1 r4649920913: a PR sharing #7's sha, titled `Review Gate - PR #7`, was accepted on its title.
        cases = {
            "other path": dict(pair=".github/workflows/forge.yml\tpull_request_target"),
            "other event": dict(pair=f"{RG_PATH}\tpull_request"),
            "run from a fork, PR in this repo": dict(run_heads={"530": run_heads(head_repo="fork/r")}),
            "run from this repo, PR from a fork": dict(pull=pull(head_repo="fork/r")),
            "other head branch": dict(run_heads={"530": run_heads(head_branch="other")}),
            "other head sha": dict(run_heads={"530": run_heads(head_sha="b" * 40)}),
            "run older than the PR": dict(run_heads={"530": run_heads(created_at="2026-11-19T10:00:00Z")}),
            "another open PR on this head sha": dict(branch_pulls=[*PROVENANCE["branch_pulls"],
                                                                   other_pr(9, HEAD_SHA, closed_at=None)]),
            # commits/{sha}/pulls omits closed-unmerged PRs; a later one closed on this sha still counts.
            "later PR closed unmerged on this sha": dict(branch_pulls=[
                *PROVENANCE["branch_pulls"], other_pr(9, HEAD_SHA, "2026-11-20T10:00:01Z", "2026-11-20T10:00:03Z")]),
            "PR on this branch open at the run, since moved on": dict(branch_pulls=[
                *PROVENANCE["branch_pulls"], other_pr(9, "d" * 40, "2026-11-20T09:00:00Z", None)]),
        }
        for title in (run_title(7), "chore: re-vendor review-gate 3.2.16"):
            for label, kwargs in cases.items():
                with self.subTest(title=title, case=label):
                    rc, err = self.gate_run(title, **kwargs)
                    self.assertEqual(rc, 1, err)
                    self.assertIn("forged check 'Review Gate'", err)
                    if label.startswith("later"):  # closed: its head is frozen, so a new commit does help
                        self.assertIn("this head sha is also PR #9's head. Push a new commit", err)
                    if label.startswith(("another", "PR on")):  # open: a new commit is its head too
                        self.assertIn("PR #9 is also open from head branch", err)

    # 3.2.18 (Codex P1): an empty listing proved nothing, yet read as "no competing PR". The listing must
    # positively contain this PR, on this head ref and sha, or the run cannot be attributed to it.
    def test_listing_without_this_pr_exits_2(self):
        me = PROVENANCE["branch_pulls"][0]
        cases = {
            "no pages": dict(branch_pulls_raw="[]"),
            "one empty page": dict(branch_pulls=[]),
            "only another PR": dict(branch_pulls=[other_pr(3)]),
            "malformed JSON": dict(branch_pulls_raw="[[{"),
            "this PR on another sha": dict(branch_pulls=[{**me, "head": {**me["head"], "sha": "e" * 40}}]),
            "this PR on another ref": dict(branch_pulls=[{**me, "head": {**me["head"], "ref": "other"}}]),
            "this PR without a ref": dict(branch_pulls=[{**me, "head": {"sha": HEAD_SHA}}]),
        }
        for label, kwargs in cases.items():
            with self.subTest(case=label):
                rc, err = self.gate_run(**kwargs)
                self.assertEqual(rc, 2, err)
        rc, err = self.gate_run(branch_pulls=[me])  # a valid listing holding only this PR still passes
        self.assertEqual(rc, 0, err)

    # 3.2.18 (Codex P2): with two OPEN PRs on one head branch, a new commit becomes both PRs' head, so the
    # push-a-commit advice never helps. It holds only when the other PR is closed (its head is frozen).
    def test_open_pr_on_the_same_branch_names_close_or_split(self):
        for sha in (HEAD_SHA, "d" * 40):
            with self.subTest(sha=sha):
                rc, err = self.gate_run(branch_pulls=[*PROVENANCE["branch_pulls"],
                                                      other_pr(9, sha, "2026-11-20T09:00:00Z", None)])
                self.assertEqual(rc, 1, err)
                self.assertIn("shared head sha, not this PR's run: ", err)
                self.assertIn("PR #9 is also open from head branch 'chore/revendor-review-gate', so a new commit "
                              "becomes its head too. Close PR #9 or open each PR from its own head branch", err)
                self.assertNotIn("Push a new commit", err)

    # Codex P2 on f9f4dce: a run titled for another PR took an early return with push-a-new-commit advice, even
    # when that PR is open on this head branch, where a new commit becomes its head too.
    def test_run_titled_for_another_open_pr_names_close_or_split(self):
        rc, err = self.gate_run(run_title(9), branch_pulls=[*PROVENANCE["branch_pulls"],
                                                            other_pr(9, HEAD_SHA, "2026-11-20T09:00:00Z", None)])
        self.assertEqual(rc, 1, err)
        self.assertIn("not 'Review Gate - PR #7'", err)
        self.assertIn("Close PR #9 or open each PR from its own head branch", err)
        self.assertNotIn("Push a new commit", err)

    def test_missing_or_mistyped_provenance_exits_2(self):
        # Codex P2 r4649920164: null == null matched, and a null pull.head raised AttributeError (exit 1).
        no_head = {**pull(), "head": None}
        cases = {
            "pull lookup fails": dict(pull=None),
            "run lookup fails": dict(run_heads={}),
            "listing fails": dict(branch_pulls=None),
            "listing not pages": dict(branch_pulls_raw="{}"),
            "listing entry not a PR": dict(branch_pulls_raw="[[{}]]"),
            "null head sha on both": dict(pull=pull(head_sha=None), run_heads={"530": run_heads(head_sha=None)}),
            "null head ref and branch": dict(pull=pull(head_ref=None), run_heads={"530": run_heads(head_branch=None)}),
            "empty head ref and branch": dict(pull=pull(head_ref=""), run_heads={"530": run_heads(head_branch="")}),
            "pull.head null": dict(pull=no_head),
            "fork deleted (head.repo null)": dict(pull={**pull(), "head": {**pull()["head"], "repo": None}}),
            "PR created_at missing": dict(pull={k: v for k, v in pull().items() if k != "created_at"}),
            "listed PR head sha null": dict(branch_pulls=[*PROVENANCE["branch_pulls"],
                                                          {**other_pr(9, closed_at=None), "head": {"sha": None}}]),
            "listed PR number a string": dict(branch_pulls=[*PROVENANCE["branch_pulls"], {**other_pr(9), "number": "9"}]),
            "listed PR closed_at a number": dict(branch_pulls=[*PROVENANCE["branch_pulls"], {**other_pr(9), "closed_at": 0}]),
        }
        for title in (run_title(7), "chore: re-vendor review-gate 3.2.16"):
            for label, kwargs in cases.items():
                with self.subTest(title=title, case=label):
                    rc, err = self.gate_run(title, **kwargs)
                    self.assertEqual(rc, 2, err)

    # #134: every gate run on a head used to refetch the PR, the branch PR listing and its run (~4 calls each),
    # inside merge-guard's 20 s budget. One PR read, one listing read, and each distinct run read once.
    def test_many_gate_runs_fetch_the_pr_and_listing_once(self):
        ids = [str(540 + n) for n in range(12)]
        jobs = [job("Review Gate", int(i)) for i in ids] + [job("Review Gate", int(ids[0]))]  # a rerun's 2nd job
        rc, err = self.wrapper(jobs, {i: TRUSTED_RUN for i in ids})
        self.assertEqual(rc, 0, err)
        count = lambda pattern: sum(1 for c in self.calls if re.search(pattern, c))
        self.assertEqual(count(r"repos/o/r/pulls/7\b"), 1, self.calls)
        self.assertEqual(count(r"repos/o/r/pulls\?"), 1, self.calls)
        for i in ids:
            with self.subTest(run=i):
                # 3.2.18 (Codex P2): one read per run gives path, event, head fields and title together
                self.assertEqual(count(rf"actions/runs/{i}\b"), 1, self.calls)
        self.assertEqual(len(self.calls), len(ids) + 2, self.calls)

    def test_untrusted_jobs_exit_1(self):
        for pair in (".github/workflows/forge.yml\tpull_request",
                     ".github/workflows/forge.yml\tpull_request_target",
                     f"{RG_PATH}\tpull_request"):  # a PR-edited review-gate.yml runs under pull_request
            with self.subTest(pair=pair):
                rc, err = self.wrapper([job("Review Gate", 508)], {"508": pair})
                self.assertEqual(rc, 1, err)
                self.assertIn("untrusted workflow", err)

    def test_untrusted_job_is_forged_even_beside_a_trusted_one(self):
        rc, err = self.wrapper([job("Review Gate", 506), job("Review Gate", 508)],
                               {"506": TRUSTED_RUN, "508": ".github/workflows/forge.yml\tpull_request"})
        self.assertEqual(rc, 1, err)
        self.assertIn("runs/508", err)
        self.assertNotIn("runs/506", err)

    def test_ambiguous_input_exits_2(self):
        for kwargs in ({"PR_NUMBER": None}, {"PR_NUMBER": "7abc"}, {"fixture": {"titles": {}}}):
            with self.subTest(kwargs=str(kwargs)):
                rc, err = self.wrapper([job("Review Gate", 514)], {"514": TRUSTED_RUN}, **kwargs)
                self.assertEqual(rc, 2, err)

    # aec #154 (dba592db): empty or runless input cannot be evaluated, so it fails closed.
    def test_empty_listing_exits_2(self):
        for stdin in ("", json.dumps({"total_count": 0, "check_runs": []})):
            with self.subTest(stdin=stdin):
                rc, err = self.wrapper([], {}, stdin=stdin)
                self.assertEqual(rc, 2, err)


class MergeGuardForgedStep(unittest.TestCase):
    """3.2.13 (SEC-MVS-01 rung 1): merge-guard runs the forged-check wrapper before a merge, fail closed."""

    def guard(self, fixture, budget=None):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mg_forged", SCRIPTS / "merge-guard.py")
        mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)
        if budget is not None:
            mg.HOOK_BUDGET_S = budget
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp); (bindir / "gh").write_text(FAKE_GH); (bindir / "gh").chmod(0o755)
            (bindir / "fixture.json").write_text(json.dumps({"scripts": {}, "runs": {}, "titles": {}, **PROVENANCE,
                                                             "run_heads": {"506": run_heads()}, **fixture}))
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=tmp)
            return mg.forged_gate_check("o", "r", 7, "a" * 40, None, env)

    def test_own_trusted_run_allows(self):
        self.assertIsNone(self.guard({"check_runs": [job("Review Gate", 506)], "runs": {"506": TRUSTED_RUN},
                                      "titles": {"506": run_title(7)}}))

    def test_forged_job_blocks_exit_1(self):
        msg = self.guard({"check_runs": [job("Review Gate", 508)],
                          "runs": {"508": ".github/workflows/forge.yml\tpull_request"}, "titles": {"508": run_title(7)}})
        self.assertIn("forged-check step exited 1", msg)
        self.assertIn("untrusted workflow", msg)
        self.assertNotIn("::error::", msg)

    def test_another_prs_run_blocks_and_names_the_fix(self):
        msg = self.guard({"check_runs": [job("Review Gate", 517)], "runs": {"517": TRUSTED_RUN},
                          "titles": {"517": run_title(8)}})
        self.assertIn("forged-check step exited 1", msg)
        self.assertIn("is also PR #8", msg)

    def test_unevaluable_blocks_exit_2(self):
        msg = self.guard({"check_runs": [job("Review Gate", 514)], "runs": {"514": TRUSTED_RUN}})
        self.assertIn("forged-check step exited 2", msg)

    # cop P2 on #121: an empty listing is "nothing to forge" unless the repo is configured for Review Gate
    def test_empty_listing_in_configured_repo_blocks_exit_2(self):
        msg = self.guard({"check_runs": [], "workflow": True})
        self.assertIn("forged-check step exited 2", msg)

    def test_empty_listing_in_unconfigured_repo_allows(self):
        self.assertIsNone(self.guard({"check_runs": [], "workflow": False}))

    def test_empty_listing_with_failed_config_lookup_blocks(self):
        msg = self.guard({"check_runs": [], "workflow": "error"})
        self.assertIn("could not tell whether o/r has .github/workflows/review-gate.yml", msg)

    def test_malformed_listing_blocks_even_in_unconfigured_repo(self):
        # cop P2 on f99ca1ac: null, {}, "", 0 and false are not an empty list and must not read as one
        for raw in ("not json", '{"total_count": 0}', "", '{"check_runs": null}', "{}", '""', "0", "false",
                    '{"check_runs": []} {"check_runs": null}', '{"check_runs": [1]}'):
            with self.subTest(raw=raw):
                msg = self.guard({"check_runs": [], "workflow": False, "raw_listing": raw})
                self.assertIn("forged-check step exited 2", msg)

    # cop P2 on f99ca1ac: the hook is killed (and does not block) at timeout_ms; the step must block first
    def test_slow_github_blocks_within_the_budget(self):
        import time
        started = time.monotonic()
        msg = self.guard({"check_runs": [], "workflow": False, "sleep": 5}, budget=1)
        self.assertLess(time.monotonic() - started, 4)
        self.assertIn("did not finish within 1 s", msg)

    def test_spent_budget_blocks_before_calling_gh(self):
        msg = self.guard({"check_runs": [], "workflow": False}, budget=0)
        self.assertIn("did not finish within 0 s", msg)

    def test_budget_fits_under_the_hook_timeout(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mg_budget", SCRIPTS / "merge-guard.py")
        mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)
        hook = json.loads((SKILL / "hooks.json").read_text())["hooks"][0]
        self.assertLessEqual(mg.HOOK_BUDGET_S * 1000 + 5000, hook["timeout_ms"])

    # 3.2.14: the gate's own GraphQL reads (pr_payload) share the budget; a slow one used to outlive the hook
    def test_slow_gate_read_blocks_within_the_budget(self):
        import importlib.util
        import time
        from unittest import mock
        spec = importlib.util.spec_from_file_location("mg_slow", SCRIPTS / "merge-guard.py")
        mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)
        mg.HOOK_BUDGET_S = 1
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp); (bindir / "gh").write_text(FAKE_GH); (bindir / "gh").chmod(0o755)
            (bindir / "fixture.json").write_text(json.dumps({"sleep": 5}))
            with mock.patch.dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=tmp):
                started = time.monotonic()
                msg = mg.check_one("gh -R o/r pr merge 7 --squash", cwd=tmp)
            self.assertLess(time.monotonic() - started, 4)
            self.assertTrue(msg.startswith("review-gate: gate check failed: gh api POST graphql did not finish "
                                           "within the time budget"), msg)
            self.assertTrue((bindir / "calls.log").read_text().startswith("api "))  # it reached gh, then timed out

    def _stalled_gh_merge(self, command):
        """Run check_one under a 1 s budget against a gh that stalls 5 s; returns (message, elapsed, calls)."""
        import importlib.util
        import time
        from unittest import mock
        spec = importlib.util.spec_from_file_location("mg_stall", SCRIPTS / "merge-guard.py")
        mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)
        mg.HOOK_BUDGET_S = 1
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp); (bindir / "gh").write_text(FAKE_GH); (bindir / "gh").chmod(0o755)
            (bindir / "fixture.json").write_text(json.dumps({"sleep": 5}))
            env = {k: v for k, v in os.environ.items() if k not in ("GH_REPO", "GH_HOST")}
            env.update(PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=tmp)
            with mock.patch.dict(os.environ, env, clear=True):
                started = time.monotonic()
                msg = mg.check_one(command, cwd=tmp)
                elapsed = time.monotonic() - started
            return msg, elapsed, (bindir / "calls.log").read_text()

    def test_stalled_repo_view_blocks_within_the_budget(self):
        # Codex P1 on #122: no -R means `gh repo view`, which had no timeout at all.
        msg, elapsed, calls = self._stalled_gh_merge("gh pr merge 7 --squash")
        self.assertLess(elapsed, 4)
        self.assertTrue(calls.startswith("repo view"), calls)
        self.assertEqual(msg, "review-gate: gate check failed: gh repo view did not finish within the time "
                              "budget (GitHub slow or unreachable); retry")

    def test_stalled_selector_resolution_blocks_within_the_budget(self):
        # Codex P1 on #122: `gh pr view <branch>` kept its own fixed 20 s, outside the shared budget.
        msg, elapsed, calls = self._stalled_gh_merge("gh -R o/r pr merge feature-x --squash")
        self.assertLess(elapsed, 4)
        self.assertTrue(calls.startswith("pr view feature-x"), calls)
        self.assertTrue(msg.startswith("review-gate blocked merge: resolving the PR from the merge selector "
                                       "did not finish within 1 s"), msg)

    def test_spent_deadline_fails_closed_before_calling_gh(self):
        import importlib.util
        import time
        spec = importlib.util.spec_from_file_location("gate_deadline", SCRIPTS / "check-review-gate.py")
        gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
        with gate.gh_deadline(time.monotonic() - 1), self.assertRaisesRegex(RuntimeError, "time budget"):
            gate.run_gh(["repos/o/r"], hostname="github.com")
        with gate.gh_deadline(None):  # the workflow sets no deadline
            self.assertIsNone(gate._GH_DEADLINE.get())

    def test_failed_listing_blocks(self):
        msg = self.guard({"check_runs": [], "listing_fails": True})
        self.assertIn("could not list check runs on aaaaaaaaaaaa", msg)


# First pr-merge-flow release whose every copy documents the installed-skill command (1.4.2 shipped both).
COP_DOC_FIXED_IN = (1, 4, 3)


def cop_doc_skip_reason(doc_path: Path) -> str | None:
    """Why the cop-command check cannot apply to this sibling pr-merge-flow, or None to check it.

    Vendored repos carry whatever pr-merge-flow they installed; an older copy predates the
    documented command and is that repo's upgrade to make, not a review-gate failure.
    """
    if not doc_path.exists():
        return "pr-merge-flow is not installed beside review-gate (vendored layout)"
    m = re.search(r"^version:\s*(\d+)\.(\d+)\.(\d+)", doc_path.read_text(), re.M)
    if not m:
        return "pr-merge-flow SKILL.md carries no version"
    if tuple(map(int, m.groups())) < COP_DOC_FIXED_IN:
        return f"vendored pr-merge-flow {'.'.join(m.groups())} predates the documented cop command"
    return None


def assert_cop_doc_uses_installed_skill(tc: unittest.TestCase, doc: str) -> None:
    runs = [l for l in doc.splitlines() if "python3" in l and "check-forged-review-gate.py" in l]
    tc.assertTrue(runs)
    for line in runs:
        tc.assertIn("python3 ~/.claude/skills/review-gate/scripts/check-forged-review-gate.py", line)
        tc.assertNotRegex(line, r"python3 (\./)?scripts/")


class CopMergeCommand(unittest.TestCase):
    def test_documented_command_never_runs_the_pr_checkout(self):
        # A PR controls its checkout's scripts/, so the cop's merge-time run must use the installed skill.
        doc_path = SKILL.parent / "pr-merge-flow" / "SKILL.md"
        reason = cop_doc_skip_reason(doc_path)
        if reason:
            self.skipTest(reason)
        assert_cop_doc_uses_installed_skill(self, doc_path.read_text())

    def test_absent_or_older_vendored_copy_skips_and_current_passes(self):
        installed = "python3 ~/.claude/skills/review-gate/scripts/check-forged-review-gate.py --pr 5"
        docs = {
            "1.4.1": "---\nversion: 1.4.1\n---\nno cop command yet\n",
            "1.4.2": "---\nversion: 1.4.2\n---\npython3 scripts/check-forged-review-gate.py --pr 5\n",
            "1.4.3": f"---\nversion: 1.4.3\n---\n{installed}\n",
            "1.5.2": f"---\nversion: 1.5.2\n---\n{installed}\n",
        }
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("not installed", cop_doc_skip_reason(Path(d) / "SKILL.md"))
            for version, text in docs.items():
                path = Path(d) / f"{version}.md"
                path.write_text(text)
                with self.subTest(version=version):
                    if version in ("1.4.1", "1.4.2"):
                        self.assertIn("predates", cop_doc_skip_reason(path))
                    else:
                        self.assertIsNone(cop_doc_skip_reason(path))
                        assert_cop_doc_uses_installed_skill(self, text)
        # A current copy that regresses to the PR checkout's scripts/ still fails.
        with self.assertRaises(AssertionError):
            assert_cop_doc_uses_installed_skill(self, "python3 scripts/check-forged-review-gate.py --pr 5")


class InstalledCopies(unittest.TestCase):
    def test_repo_copies_match_skill_copies(self):
        # This repo's own gate loads scripts/ and .github/workflows/ from main; keep them the skill's copies.
        # The repo that installed the gate: SKILL.parent here; the repo root when vendored under .claude/skills.
        root = next((d for d in SKILL.parents if (d / ".github/workflows/review-gate.yml").is_file()), None)
        if root is None:
            self.skipTest("review-gate is not installed into a repo above this skill")
        for name in ("check-forged-gate-names.py", "check-forged-review-gate.py", "check-review-gate.py",
                     "check-security-scan.py"):
            self.assertEqual((root / "scripts" / name).read_bytes(), (SCRIPTS / name).read_bytes(), name)
        self.assertEqual((root / ".github/workflows/review-gate.yml").read_bytes(), TEMPLATE.read_bytes())


if __name__ == "__main__":
    unittest.main()
