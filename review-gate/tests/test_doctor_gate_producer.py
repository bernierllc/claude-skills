"""doctor-review-gate.py: can the default branch publish a required `Review Gate`? (3.8.0)

Plan: agents-environment-config plans/2026-11-24-doctor-required-check-workflow-exists.md, step 9.
The doctor runs as a real subprocess. `gh` is the only stand-in: a fake executable on PATH that serves
fixture GitHub API responses (third-party, so no network), in the `gh api --include` output shape.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
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
def emit(text, site):
    sys.stdout.write(text); sys.stdout.flush()
    if fx.get("ff") == site:  # an undecodable byte at this call site
        sys.stdout.buffer.write(b"\\xff"); sys.stdout.flush()
    sys.stdout.write("\\n")
if a[:2] == ["repo", "view"]:
    if "nameWithOwner" in a:
        emit(fx["repo"], "nameWithOwner"); sys.exit(0)
    if fx.get("default") is None:
        print("gh: could not read repo", file=sys.stderr); sys.exit(1)
    emit(fx["default"], "defaultBranchRef"); sys.exit(0)
if a[:2] == ["label", "list"]:
    emit(fx.get("labels_raw") or json.dumps(fx.get("labels", [{{"name": "review:high"}}])), "label"); sys.exit(0)
if a[:2] == ["api", "--include"] and len(a) == 3:
    with open(os.environ["FAKE_GH"] + ".calls", "a") as log:
        log.write(a[2] + "\\n")
    r = fx["api"].get(a[2], {{"status": 404, "body": {{"message": "Not Found"}}}})
    if r.get("transient"):
        print("error connecting to api.github.com", file=sys.stderr); sys.exit(1)
    st = r["status"]
    hdr = "".join(f"{{k}}: {{v}}\\n" for k, v in r.get("headers", {{}}).items())
    emit(f"HTTP/2.0 {{st}} X\\nContent-Type: application/json\\n{{hdr}}\\n" + r.get("raw", json.dumps(r.get("body"))), a[2])
    if st >= 400:
        print(f"gh: error (HTTP {{st}})", file=sys.stderr); sys.exit(1)
    sys.exit(0)
print("unexpected gh call: " + " ".join(a), file=sys.stderr); sys.exit(2)
"""


def ruleset(rid, contexts=(("Review Gate", None),), include=("~DEFAULT_BRANCH",), enforcement="active"):
    checks = [{"context": c, **({"integration_id": i} if i is not None else {})} for c, i in contexts]
    return {"id": rid, "name": f"rs{rid}", "target": "branch", "enforcement": enforcement,
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
    for p in workflows or {}:  # unlisted paths get the fake's JSON 404
        api[f"repos/{REPO}/contents/{p}?ref={default}"] = {
            "status": 200, "body": {"type": "file", "path": p, "name": p.rsplit("/", 1)[1], "sha": "0" * 40}}
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
YML = ".github/workflows/review-gate.yml"
PROBE = f"repos/{REPO}/contents/{YML}?ref=main"

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
        self.assertIn("OK 'Review Gate' (required on main) has its producer: the review-gate workflow "
                      ".github/workflows/review-gate.yml is present on 'main' (its trigger and branch filters are not "
                      "analyzed)", proc.stdout)

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
            f"repos/{REPO}/contents/{YML}?ref=staging": {"status": 200, "body": {"type": "file", "path": YML}}})
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

    def test_non_actions_integration_id_is_skipped(self):
        for proc, calls in self.both(fixture([ruleset(1, (("Review Gate", 99999),))], None)):
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("pins 'Review Gate' to integration 99999 (not GitHub Actions); producer check skipped",
                          proc.stdout)
            self.assertNotIn(PROBE, calls)

    def test_other_required_context_warns_not_verified(self):
        fx = fixture([ruleset(1, (("Review Gate", None), ("CI / test", None)))], GATE)
        for proc, _ in self.both(fx):
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("WARN required check 'CI / test': producer not verified (generic producer analysis is out "
                          "of scope)", proc.stdout)
            self.assertIn("other branches are out of scope", proc.stdout)

    def test_unverified_probe_statuses_and_shapes_warn_never_fail(self):
        """Only a 200 file object at the requested path is present, and only a JSON 404 is absent."""
        cases = {
            "HTTP 200, a list, not a file at": {PROBE: {"status": 200, "body": [{"type": "file", "path": YML}]}},
            "HTTP 200, a str, not a file at": {PROBE: {"status": 200, "body": "review-gate.yml"}},
            "HTTP 200, a NoneType, not a file at": {PROBE: {"status": 200, "body": None}},
            "HTTP 200, type 'symlink' at path": {PROBE: {"status": 200, "body": {"type": "symlink", "path": YML}}},
            "HTTP 200, type 'submodule' at path": {PROBE: {"status": 200, "body": {"type": "submodule", "path": YML}}},
            "at path '.github/workflows/ci.yml', not a file at": {
                PROBE: {"status": 200, "body": {"type": "file", "path": ".github/workflows/ci.yml"}}},
            "HTTP 200, unparsable body": {PROBE: {"status": 200, "raw": "<html>"}},
            "HTTP 403)": {PROBE: {"status": 403, "body": {"message": "Resource not accessible"}}},
            "HTTP 403, rate limited": {PROBE: {"status": 403, "headers": {"X-Ratelimit-Remaining": "0"},
                                               "body": {"message": "API rate limit exceeded"}}},
            "HTTP 429, rate limited": {PROBE: {"status": 429, "body": {"message": "slow down"}}},
            "HTTP 500": {PROBE: {"status": 500, "body": {"message": "Server Error"}}},
            "error connecting": {PROBE: {"transient": True}},
            "HTTP 404, missing ref": {PROBE: {"status": 404, "body": {"message": "No commit found for the ref main"}}},
            "HTTP 404, unparsable body": {PROBE: {"status": 404, "raw": "<html>Not Found</html>"}},
            "default branch 'main' is not readable (HTTP 404": {
                f"repos/{REPO}/branches/main": {"status": 404, "body": {"message": "Branch not found"}}},
        }
        for needle, extra in cases.items():
            for proc, _ in self.both(fixture([ruleset(1)], NO_GATE, extra=extra)):
                with self.subTest(case=needle):
                    self.assertEqual(proc.returncode, 0, proc.stdout)
                    self.assertEqual(lines(proc, "FAIL"), [])
                    warn = lines(proc, "WARN producer of 'Review Gate'")
                    self.assertEqual(len(warn), 1, proc.stdout)
                    self.assertIn(needle, warn[0])

    def test_a_present_yaml_gate_is_ok_when_the_yml_probe_is_unverified(self):
        fx = fixture([ruleset(1)], {".github/workflows/review-gate.yaml": GATE_YML},
                     extra={PROBE: {"status": 500, "body": {"message": "Server Error"}}})
        for proc, _ in self.both(fx):
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("review-gate.yaml is present on 'main'", proc.stdout)

    def test_an_absent_yml_with_an_unverified_yaml_probe_warns_never_fails(self):
        yaml_probe = f"repos/{REPO}/contents/.github/workflows/review-gate.yaml?ref=main"
        fx = fixture([ruleset(1)], NO_GATE, extra={yaml_probe: {"status": 500, "body": {"message": "Server Error"}}})
        for proc, _ in self.both(fx):
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertNotIn("FAIL", proc.stdout)
            self.assertIn("WARN producer of 'Review Gate'", proc.stdout)
            self.assertIn("review-gate.yaml (HTTP 500", proc.stdout)

    def test_unreadable_rulesets_warn_and_say_the_producer_check_is_skipped(self):
        fx = fixture([ruleset(1)], NO_GATE, extra={
            f"repos/{REPO}/rulesets?per_page=100&page=1": {"status": 403, "body": {"message": "denied"}}})
        for proc, _ in self.both(fx):
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("WARN could not list rulesets (HTTP 403;", proc.stdout)
            self.assertIn("Review Gate producer checks are skipped", proc.stdout)


DETAIL, LIST, BRANCH = (f"repos/{REPO}/rulesets/1", f"repos/{REPO}/rulesets?per_page=100&page=1",
                        f"repos/{REPO}/branches/main")
TARGETS = ("branch", "tag", "push", "repository")
WELL_FORMED = {  # every ruleset field the doctor reads, each holding a value of its documented type
    "id": 1, "name": "rs1", "target": "branch", "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH", "refs/heads/staging"], "exclude": ["refs/heads/x"]}},
    "rules": [
        {"type": "required_status_checks",
         "parameters": {"required_status_checks": [{"context": "Review Gate", "integration_id": 15368}]}},
        {"type": "pull_request", "parameters": {"required_review_thread_resolution": True}},
    ],
}
JUNK = [None, 0, 1, True, "", "x", [], {}, [None], [1], {"a": 1}]
DELETE = "<deleted>"


def key_paths(v, path=()):
    yield path
    for k, x in (v.items() if isinstance(v, dict) else enumerate(v) if isinstance(v, list) else ()):
        yield from key_paths(x, path + (k,))


def mutations(body):
    """(path, good value, junk, mutated body) for every key path and every junk value, plus deleting each key."""
    for path in key_paths(body):
        good = body
        for k in path:
            good = good[k]
        for junk in JUNK + ([DELETE] if path and isinstance(path[-1], str) else []):
            if not path:
                yield path, good, junk, junk
                continue
            out = copy.deepcopy(body)
            parent = out
            for k in path[:-1]:
                parent = parent[k]
            if junk == DELETE:
                del parent[path[-1]]
            else:
                parent[path[-1]] = junk
            yield path, good, junk, out


def well_typed(good, junk):
    """True when junk has the type the doctor requires where good sits: same scalar type (bool is not int), an
    empty list where a list sits; never an object (its required keys are missing) and never a deletion."""
    if junk == DELETE or isinstance(good, dict):
        return False
    return junk == [] if isinstance(good, list) else type(junk) is type(good)


class FuzzEveryApiShape(unittest.TestCase):
    """Generated coverage: junk at every key path of each well-formed GitHub response, run with the option.

    Each mutation must give rc 0 with no traceback and the consumer reported unverified, or, where the junk
    keeps the documented type (or the key is optional or never read), a result with no unverified line."""

    def walk(self, base, site, body, classify):
        """classify(path, good, junk) -> "same" (stdout equals the baseline), "valid" or "invalid"."""
        def run(m):
            fx = copy.deepcopy(base)
            if site == "labels":
                fx["labels"] = m[3]
            else:
                fx["api"][site] = {"status": base["api"].get(site, {}).get("status", 200), "body": m[3]}
            return m, run_doctor(fx, FLAG)[0]
        baseline = run_doctor(base, FLAG)[0]
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
            results = list(pool.map(run, mutations(body)))
        self.assertGreater(len(results), len(JUNK))
        for (path, good, junk, _), proc in results:
            yield classify(path, good, junk), proc, baseline, {"path": path, "junk": junk}

    def check(self, results, unverified, invalid_rc=(0,)):
        for kind, proc, baseline, case in results:
            with self.subTest(**case, kind=kind):
                if kind == "same":
                    self.assertEqual(proc.stdout, baseline.stdout)
                    self.assertEqual(proc.returncode, baseline.returncode)
                elif kind == "valid":
                    self.assertIn(proc.returncode, (0, 1), proc.stdout)
                    self.assertNotIn(unverified, proc.stdout)
                else:
                    self.assertIn(proc.returncode, invalid_rc, proc.stdout)
                    self.assertIn(unverified, proc.stdout)

    def test_ruleset_detail(self):
        base = fixture([ruleset(1)], NO_GATE, extra={DETAIL: {"status": 200, "body": WELL_FORMED}})
        self.assertIn("FAIL 'Review Gate' (required on main/staging)", run_doctor(base, FLAG)[0].stdout)

        def classify(path, good, junk):
            if path in (("id",), ("name",)):
                return "same"  # the summary list supplies id and name; the detail's copies are never read
            if path[-1:] == ("integration_id",) and junk == DELETE:
                return "same"  # optional, and absent means unpinned, which this doctor analyses like Actions
            if path == ("target",):
                return "valid" if junk in TARGETS else "invalid"
            return "valid" if well_typed(good, junk) else "invalid"
        results = list(self.walk(base, DETAIL, WELL_FORMED, classify))
        self.check(results, "WARN ruleset 'rs1' unverified")
        for kind, proc, _, case in results:
            if kind == "invalid":
                with self.subTest(**case):
                    self.assertEqual(lines(proc, "FAIL"), [])
                    self.assertNotIn("OK ruleset 'rs1'", proc.stdout)
                    self.assertIn("(saw 1 unverified)", proc.stdout)

    def test_rulesets_list(self):
        base = fixture([ruleset(1)], NO_GATE)
        results = self.walk(base, LIST, [{"id": 1, "name": "rs1"}], lambda p, g, j: "valid" if well_typed(g, j)
                            else "invalid")
        self.check(results, "WARN could not list rulesets")

    def test_labels(self):
        base = fixture([ruleset(1)], GATE)
        results = list(self.walk(base, "labels", [{"name": "review:high"}],
                                 lambda p, g, j: "valid" if well_typed(g, j) else "invalid"))
        self.check(results, "WARN label 'review:high' unverified")
        for kind, proc, _, case in results:
            with self.subTest(**case):
                self.assertEqual(proc.returncode, 0, proc.stdout)  # labels feed no FAIL
                if kind == "invalid":
                    self.assertNotIn("OK label", proc.stdout)

    def test_branch(self):
        base = fixture([ruleset(1)], NO_GATE)  # only "a JSON object" is read from the branch body
        results = self.walk(base, BRANCH, {"name": "main"},
                            lambda p, g, j: "same" if p or isinstance(j, dict) else "invalid")
        self.check(results, "WARN producer of 'Review Gate' (required on main) not verified: default branch")

    def test_contents_file_body(self):
        base = fixture([ruleset(1)], GATE)
        body = base["api"][PROBE]["body"]
        results = self.walk(base, PROBE, body, lambda p, g, j: "same" if p in (("name",), ("sha",)) else "invalid")
        self.check(results, "WARN producer of 'Review Gate' (required on main) not verified")

    def test_contents_404_body(self):
        base = fixture([ruleset(1)], NO_GATE, extra={PROBE: {"status": 404, "body": {"message": "Not Found"}}})
        results = self.walk(base, PROBE, {"message": "Not Found"},  # absent needs an object with a string message
                            lambda p, g, j: "same" if p == ("message",) and well_typed(g, j) else "invalid")
        self.check(results, "WARN producer of 'Review Gate' (required on main) not verified")


class NamedRegressions(unittest.TestCase):
    """Codex high on 8170af0: each gave ruleset OK then producer FAIL, or a traceback."""

    def run_detail(self, **over):
        fx = fixture([ruleset(1)], NO_GATE, extra={DETAIL: {"status": 200, "body": {**WELL_FORMED, **over}}})
        proc, _ = run_doctor(fx, FLAG)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(lines(proc, "FAIL"), [])
        self.assertNotIn("OK ruleset 'rs1'", proc.stdout)
        return proc

    def test_falsey_exclude_and_empty_parameters_and_string_resolution(self):
        rules = WELL_FORMED["rules"]
        for over, needle in (
                ({"conditions": {"ref_name": {"include": ["~ALL"], "exclude": 0}}}, "conditions.ref_name"),
                ({"rules": [{**rules[0], "parameters": []}, rules[1]]}, "rule 'required_status_checks' parameters"),
                ({"rules": [rules[0], {**rules[1], "parameters": {"required_review_thread_resolution": "true"}}]},
                 "rule 'pull_request' parameters have no boolean required_review_thread_resolution")):
            with self.subTest(needle=needle):
                self.assertIn(f"WARN ruleset 'rs1' unverified: {needle}", self.run_detail(**over).stdout)

    def test_target(self):
        self.assertIn("WARN ruleset 'rs1' unverified: target [] is not one of", self.run_detail(target=[]).stdout)
        self.assertIn("WARN ruleset 'rs1' targets tag, not branches; ignored", self.run_detail(target="tag").stdout)

    def test_a_404_message_that_is_not_a_string_is_unverified(self):
        """Codex high on b36dcab: a 404 with a null, bool, int or list message counted as absent and FAILed."""
        for message in (None, True, 404, ["Not Found"]):
            fx = fixture([ruleset(1)], NO_GATE, extra={PROBE: {"status": 404, "body": {"message": message}}})
            with self.subTest(message=message):
                proc, _ = run_doctor(fx, FLAG)
                self.assertEqual(proc.returncode, 0, proc.stdout)
                self.assertEqual(lines(proc, "FAIL"), [])
                self.assertIn("not an error object with a string message", proc.stdout)

    def test_a_lone_surrogate_ref_pattern_is_unverified(self):
        """Codex high on b36dcab: the re.error text held the surrogate and printing it raised UnicodeEncodeError."""
        proc = self.run_detail(conditions={"ref_name": {"include": ["[\udfff-a]"], "exclude": []}})
        self.assertIn("WARN ruleset 'rs1' unverified: conditions.ref_name holds a pattern this doctor cannot read",
                      proc.stdout)

    def test_uncompilable_ref_pattern(self):
        proc = self.run_detail(conditions={"ref_name": {"include": ["[z-a]"], "exclude": []}})
        self.assertIn("WARN ruleset 'rs1' unverified: conditions.ref_name holds a pattern this doctor cannot read",
                      proc.stdout)

    def test_undecodable_gh_output_at_every_call_site(self):
        for site in ("nameWithOwner", "label", "defaultBranchRef", LIST, DETAIL, BRANCH, PROBE,
                     f"repos/{REPO}/contents/.github/workflows/review-gate.yaml?ref=main"):
            fx = fixture([ruleset(1)], NO_GATE)  # well-formed, this FAILs; an undecodable byte must not
            fx["ff"] = site
            with self.subTest(site=site):
                proc, _ = run_doctor(fx, FLAG)  # asserts no traceback
                if site == "label":  # the label list feeds no FAIL
                    self.assertIn("WARN label 'review:high' unverified", proc.stdout)
                    self.assertEqual(proc.returncode, 1, proc.stdout)
                else:
                    self.assertEqual(proc.returncode, 0, proc.stdout)
                    self.assertEqual(lines(proc, "FAIL"), [])

    def test_undecodable_json_at_every_call_site(self):
        """claude-sonnet on 31a8b7d: a huge int or deep nesting raised ValueError or RecursionError."""
        for raw in ("1" * 6000, "[" * 200000):
            for site in ("label", LIST, DETAIL, BRANCH, PROBE):
                fx = fixture([ruleset(1)], NO_GATE)
                if site == "label":
                    fx["labels_raw"] = raw
                else:
                    fx["api"][site] = {"status": 200, "raw": raw}
                with self.subTest(site=site, raw=raw[:3]):
                    proc, _ = run_doctor(fx, FLAG)  # asserts no traceback
                    if site == "label":
                        self.assertIn("WARN label 'review:high' unverified", proc.stdout)
                        self.assertEqual(proc.returncode, 1, proc.stdout)
                    else:
                        self.assertEqual(proc.returncode, 0, proc.stdout)
                        self.assertEqual(lines(proc, "FAIL"), [])


class InstallerHint(unittest.TestCase):
    def test_merge_to_the_default_branch_comes_before_requiring_the_check(self):
        with tempfile.TemporaryDirectory() as repo:
            out = subprocess.run([sys.executable, str(INSTALLER)], cwd=repo, capture_output=True, text=True).stdout
        merge = out.index("1. merge these files to the default branch")
        self.assertLess(merge, out.index("2. Only then add 'Review Gate' as a required status check"))
        self.assertIn(f"doctor-review-gate.py {FLAG}", out)


if __name__ == "__main__":
    unittest.main()
