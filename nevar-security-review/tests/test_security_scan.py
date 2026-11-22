"""Security Scan template: workflow shape, the driver, and its contract with review-gate's lane.

The contract tests load review-gate's check-security-scan.py and require that the template's
file name, job name, annotation title, config dir and notice format are exactly what the lane
trusts, so the two skills cannot drift apart.

Integration tests run the real scanners when SECURITY_SCAN_BIN_DIR names a directory holding
gitleaks, osv-scanner and zizmor (and SEMGREP_BIN a semgrep binary); osv-scanner queries
osv.dev, so it also needs SECURITY_SCAN_NETWORK=1. Without them those tests skip.

Requires pyyaml (CI pins 6.0.2). Without it the module fails at import instead of skipping:
the workflow-shape tests are the trust checks, so a missing parser must not read as a pass.
"""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml  # CI installs pyyaml 6.0.2 before this step

SKILL = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL / "templates"
WORKFLOW = TEMPLATES / "review-gate-security-scan.yml"
CONFIG = TEMPLATES / "security-scan"
FIXTURES = SKILL / "fixtures"
LANE = SKILL.parent / "review-gate" / "scripts" / "check-security-scan.py"
TREE = "a" * 40


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scan = load("security_scan_driver", CONFIG / "scan.py")


class LaneContract(unittest.TestCase):
    """The template is exactly what review-gate's security lane trusts."""

    @classmethod
    def setUpClass(cls):
        cls.lane = load("check_security_scan", LANE)

    def test_marker_and_names(self):
        self.assertEqual(self.lane.TRUSTED, (".github/workflows/" + WORKFLOW.name, "pull_request_target"))
        self.assertEqual(self.lane.CONFIG_DIR, "security-scan")
        self.assertEqual(scan.CONFIG_REL, ".github/" + self.lane.CONFIG_DIR)
        self.assertEqual(self.lane.ANNOTATION, "security-scan")

    def test_every_notice_is_one_the_lane_parses(self):
        for o in scan.OUTCOMES:
            line = scan.notice(o, TREE)
            m = re.fullmatch(r"::notice title=([^:]+)::(.*)", line)
            self.assertEqual(m.group(1), self.lane.ANNOTATION)
            parsed = self.lane.OUTCOME.fullmatch(m.group(2).strip())
            self.assertEqual((parsed.group(1), parsed.group(2)), (o, TREE))
        self.assertEqual(set(scan.OUTCOMES), {"passed", "not-applicable", "findings", "scanner-error"})
        self.assertEqual(self.lane.PASSING, {"passed", "not-applicable"})

    def test_job_name_is_the_lane_name(self):
        wf = yaml.safe_load(WORKFLOW.read_text())
        self.assertEqual([j["name"] for j in wf["jobs"].values()], [self.lane.NAME])


class WorkflowShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text()
        cls.wf = yaml.safe_load(cls.text)
        (cls.job,) = cls.wf["jobs"].values()

    def test_trigger_is_pull_request_target_only(self):
        on = self.wf[True]  # PyYAML reads the bare `on` key as boolean True, as YAML 1.1 does
        self.assertEqual(list(on), ["pull_request_target"])
        self.assertEqual(on["pull_request_target"]["types"], ["opened", "synchronize", "reopened", "ready_for_review"])

    def test_least_privilege(self):
        self.assertEqual(self.wf["permissions"], {})
        self.assertEqual(self.job["permissions"], {"contents": "read", "pull-requests": "read"})

    def test_single_job_without_if_or_concurrency(self):
        self.assertEqual(len(self.wf["jobs"]), 1)
        self.assertNotIn("concurrency", self.wf)
        self.assertNotIn("concurrency", self.job)
        self.assertNotIn("if", self.job)
        self.assertFalse(any("if" in s or "continue-on-error" in s for s in self.job["steps"]))
        self.assertNotIn("continue-on-error", self.job)
        self.assertIsInstance(self.job["timeout-minutes"], int)

    def test_actions_pinned_by_commit(self):
        uses = [s["uses"] for s in self.job["steps"] if "uses" in s]
        self.assertTrue(uses)
        for u in uses:
            self.assertRegex(u, r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")

    def test_checkouts(self):
        base, head = [s["with"] for s in self.job["steps"] if "uses" in s]
        self.assertEqual(base, {"ref": "${{ github.event.repository.default_branch }}", "path": "base",
                                "persist-credentials": False})
        self.assertEqual(head, {"ref": "${{ github.event.pull_request.head.sha }}", "path": "head",
                                "persist-credentials": False})

    def test_no_expression_inside_run_scripts(self):
        for s in self.job["steps"]:
            if "run" in s:
                self.assertNotIn("${{", s["run"], s.get("name"))
                self.assertTrue(s["run"].startswith("set -euo pipefail"), s.get("name"))

    def test_scanners_pinned_and_driver_from_base(self):
        install, run_step = [s for s in self.job["steps"] if "run" in s]
        env = install["env"]
        for tool in ("GITLEAKS", "OSV", "ZIZMOR"):
            self.assertRegex(env[tool], r"^https://github\.com/[\w.-]+/[\w.-]+/releases/download/v[\d.]+/")
            self.assertRegex(env[tool + "_SHA256"], r"^[0-9a-f]{64}$")
            self.assertIn(f'"${tool}_SHA256"', install["run"])
        self.assertIn("sha256sum -c", install["run"])
        image = r"^semgrep/semgrep:[\d.]+@sha256:[0-9a-f]{64}$"
        self.assertRegex(env["SEMGREP_IMAGE"], image)
        self.assertEqual(run_step["env"]["SEMGREP_IMAGE"], env["SEMGREP_IMAGE"])
        self.assertIn('python3 -I "$BASE_DIR/.github/security-scan/scan.py"', run_step["run"])

    def test_config_tree_is_complete(self):
        self.assertEqual(sorted(p.name for p in CONFIG.iterdir() if p.name != "__pycache__"),
                         ["exceptions.json", "gitleaks.toml", "osv-scanner.toml", "scan.py", "semgrep.yml"])
        active, expired = scan.load_exceptions(CONFIG / "exceptions.json", dt.date(2026, 1, 1))
        self.assertEqual((active, expired), ([], []))
        rules = yaml.safe_load((CONFIG / "semgrep.yml").read_text())["rules"]
        self.assertTrue(all("." not in r["id"] for r in rules))  # parse_semgrep keeps the last dotted segment


class Inputs(unittest.TestCase):
    def test_safe_rel(self):
        self.assertEqual(scan.safe_rel("a/b.py"), "a/b.py")
        for bad in ("", "/etc/passwd", "../x", "a/../../x", ".git/config", "a\\b", "a\x00b"):
            self.assertIsNone(scan.safe_rel(bad), bad)

    def api(self, files, head="h1"):
        pages = [files[i:i + 100] for i in range(0, len(files), 100)] or [[]]
        if len(files) % 100 == 0 and files:
            pages.append([])

        def api(path):
            if "/files?" in path:
                return pages[int(path.rsplit("page=", 1)[1]) - 1]
            return {"head": {"sha": head}}
        return api

    def test_list_changed_paginates_and_skips_removed(self):
        files = [{"filename": f"f{i}.py", "status": "modified"} for i in range(150)]
        files.append({"filename": "gone.py", "status": "removed"})
        got = scan.list_changed(self.api(files), "o/r", 1, "h1")
        self.assertEqual(len(got), 150)
        self.assertNotIn("gone.py", got)

    # Codex P1 on 6ed2a9d: a deleted or renamed-away dependency file must still be not-covered
    def test_list_changed_keeps_removed_and_renamed_dependency_files(self):
        files = [{"filename": "package-lock.json", "status": "removed"},
                 {"filename": "archived.txt", "status": "renamed", "previous_filename": "requirements.txt"},
                 {"filename": "new.py", "status": "renamed", "previous_filename": "old.py"}]
        got = scan.list_changed(self.api(files), "o/r", 1, "h1")
        self.assertEqual(got, ["archived.txt", "new.py", "package-lock.json", "requirements.txt"])
        with tempfile.TemporaryDirectory() as t:
            head, st = Path(t) / "head", Path(t) / "st"
            head.mkdir(); st.mkdir()
            (head / "archived.txt").write_text("x\n"); (head / "new.py").write_text("x = 1\n")
            staged, _ = scan.stage(head, got, st)
            skipped = [r for r in got if r not in staged]
            (st / "exceptions.json").write_text(json.dumps({"version": 1, "exceptions": []}))
            with mock.patch.object(scan, "scan_one", lambda *a: []):
                _, found, _ = scan.scan(staged, st, st, st, dt.date(2026, 1, 1), skipped)
        self.assertEqual(sorted(f["path"] for f in found if f["rule"] == "not-covered"),
                         ["package-lock.json", "requirements.txt"])

    def test_list_changed_fails_closed(self):
        with self.assertRaisesRegex(scan.ScanError, "head moved"):
            scan.list_changed(self.api([{"filename": "a", "status": "added"}], head="h2"), "o/r", 1, "h1")
        with self.assertRaisesRegex(scan.ScanError, "API cap"):
            scan.list_changed(self.api([{"filename": f"f{i}", "status": "added"} for i in range(3000)]),
                              "o/r", 1, "h1")
        with self.assertRaisesRegex(scan.ScanError, "unsafe"):
            scan.list_changed(self.api([{"filename": "../x", "status": "added"}]), "o/r", 1, "h1")
        with self.assertRaisesRegex(scan.ScanError, "non-list"):
            scan.list_changed(lambda p: {"message": "Not Found"}, "o/r", 1, "h1")

    def test_stage_copies_renames_and_skips_links(self):
        with tempfile.TemporaryDirectory() as t:
            head, st = Path(t, "head"), Path(t, "stage")
            (head / "src").mkdir(parents=True)
            (head / "src" / "a.py").write_text("x = 1\n")
            (head / ".gitleaksignore").write_text("everything\n")
            Path(t, "outside").mkdir()
            Path(t, "outside", "s.txt").write_text("secret\n")
            os.symlink(Path(t, "outside", "s.txt"), head / "link.txt")
            os.symlink(Path(t, "outside"), head / "dirlink")
            rels = ["src/a.py", ".gitleaksignore", "link.txt", "dirlink/s.txt", "missing.py"]
            staged, notes = scan.stage(head, rels, st)
            self.assertEqual(staged, ["src/a.py", ".gitleaksignore"])
            self.assertTrue((st / ".gitleaksignore.author-copy").is_file())
            self.assertFalse((st / ".gitleaksignore").exists())
            self.assertFalse((st / "link.txt").exists() or (st / "dirlink").exists())
            self.assertEqual(len(notes), 3)

    # Codex P1 x2: a PR path with the reserved suffix would collide with a renamed config, or
    # inherit another path's exact-path exception through real_path's strip; it fails closed
    def test_stage_rejects_the_reserved_suffix(self):
        with tempfile.TemporaryDirectory() as t:
            head, st = Path(t, "head"), Path(t, "stage")
            head.mkdir()
            for name in (".gitleaksignore", ".gitleaksignore.author-copy", "fixture.txt.author-copy"):
                (head / name).write_text("x\n")
            for rels in ([".gitleaksignore", ".gitleaksignore.author-copy"], ["fixture.txt.author-copy"]):
                with self.assertRaisesRegex(scan.ScanError, "reserves"):
                    scan.stage(head, rels, st)
            self.assertFalse(st.exists() and any(st.iterdir()))  # rejected before anything is copied

    def test_semgrep_targets_only_languages_with_rules(self):
        rules = yaml.safe_load((TEMPLATES / "security-scan" / "semgrep.yml").read_text())["rules"]
        langs = {lang for r in rules for lang in r["languages"]}
        by_ext = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
                  ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript"}
        self.assertEqual(set(by_ext), scan.CODE_EXT)
        self.assertTrue(set(by_ext.values()) <= langs, langs)
        self.assertEqual(scan.applicable("semgrep", ["main.go", "a.rb", "b.sh", "c.py"]), ["c.py"])

    def test_real_path(self):
        st = Path("/w/stage")
        self.assertEqual(scan.real_path("/w/stage/a/.gitleaks.toml.author-copy", st), "a/.gitleaks.toml")
        self.assertEqual(scan.real_path("./b.py", st), "b.py")
        self.assertEqual(scan.real_path("/src/c.py", st), "c.py")

    def test_applicable(self):
        docs = ["README.md", "docs/a.md"]
        self.assertEqual(scan.applicable("gitleaks", docs), docs)  # secrets in docs still count
        for s in ("osv-scanner", "zizmor", "semgrep"):
            self.assertEqual(scan.applicable(s, docs), [])
        self.assertEqual(scan.applicable("osv-scanner", ["app/package-lock.json", "package.json"]),
                         ["app/package-lock.json"])
        # the names osv-scanner 2.7.0 reads as requirements files, probed: case-sensitive, base name only
        reqs = ["requirements.txt", "a/requirements-dev.txt", "dev-requirements.txt", "requirements_test.txt"]
        not_reqs = ["reqs.txt", "requirements/dev.txt", "requirements.in", "requirements-dev.TXT", "foo.txt"]
        self.assertEqual(scan.applicable("osv-scanner", reqs + not_reqs), reqs)
        self.assertEqual(scan.applicable("zizmor", [".github/workflows/ci.yml", "x/action.yml", "ci.yml"]),
                         [".github/workflows/ci.yml", "x/action.yml"])
        self.assertEqual(scan.applicable("semgrep", ["a.py", "b.ts", "c.md"]), ["a.py", "b.ts"])


class Parsers(unittest.TestCase):
    st = Path("/w/stage")

    # Codex bot P1: osv-scanner exit 128 is "no packages found", so nothing was checked
    def test_osv_no_packages_is_a_finding_not_a_pass(self):
        real = scan.run
        scan.run = lambda argv, cwd=None, ok=(0,): (128, "")
        try:
            got = scan.scan_one("osv-scanner", ["app/poetry.lock"], Path("/cfg"), self.st, Path("/w"))
        finally:
            scan.run = real
        self.assertEqual(got, [{"scanner": "osv-scanner", "rule": "no-packages", "path": "app/poetry.lock"},
                               {"scanner": "osv-scanner", "rule": "not-covered", "path": "app/poetry.lock"}])

    # Cop P1 on 12dc7a7: OSV exits 0 when one input yields nothing (here a broken lockfile)
    # and another has packages, so every input is accounted for on its own
    def test_osv_each_input_must_yield_packages(self):
        st = str(self.st)
        rep = {"results": [{"source": {"path": f"{st}/svc/go.mod"}, "packages": [{"package": {"name": "m"}}]}]}
        real, argvs = scan.run, []
        scan.run = lambda argv, cwd=None, ok=(0,): (argvs.append(argv), (0, json.dumps(rep)))[1]
        try:
            got = scan.scan_one("osv-scanner", ["app/poetry.lock", "svc/go.mod"], Path("/cfg"), self.st, Path("/w"))
            rep["results"].append({"source": {"path": f"{st}/app/poetry.lock"}, "packages": [{}]})
            both = scan.scan_one("osv-scanner", ["app/poetry.lock", "svc/go.mod"], Path("/cfg"), self.st, Path("/w"))
        finally:
            scan.run = real
        read = lambda fs: [f for f in fs if f["rule"] != "not-covered"]
        self.assertEqual(read(got), [{"scanner": "osv-scanner", "rule": "no-packages", "path": "app/poetry.lock"}])
        self.assertEqual(read(both), [])
        # Codex P1 on c849c19: without --all-packages a clean lockfile has no result entry at all
        self.assertTrue(all("--all-packages" in a for a in argvs))

    def test_gitleaks(self):
        got = scan.parse_gitleaks([{"RuleID": "r", "File": "/w/stage/c.py", "Secret": "REDACTED"}], self.st)
        self.assertEqual(got, [{"scanner": "gitleaks", "rule": "r", "path": "c.py"}])

    def test_osv(self):
        rep = {"results": [{"source": {"path": "/w/stage/package-lock.json"},
                            "packages": [{"vulnerabilities": [{"id": "GHSA-x"}, {"id": "GHSA-y"}]}]}]}
        self.assertEqual([f["rule"] for f in scan.parse_osv(rep, self.st)], ["GHSA-x", "GHSA-y"])

    def test_zizmor(self):
        rep = [{"ident": "artipacked", "locations": [{"symbolic": {"key": {"Local": {"verbatim_path": ".github/workflows/ci.yml"}}}}]}]
        self.assertEqual(scan.parse_zizmor(rep, self.st),
                         [{"scanner": "zizmor", "rule": "artipacked", "path": ".github/workflows/ci.yml"}])

    def test_semgrep_fails_closed_on_unscanned_targets(self):
        rep = {"results": [{"check_id": "cfg.python-eval-exec", "path": "a.py"}],
               "errors": [{"type": "Syntax error", "path": "b.py"}],
               "paths": {"scanned": ["a.py"]}}
        got = scan.parse_semgrep(rep, self.st, ["a.py", "b.py", "c.py"])
        self.assertEqual([(f["rule"], f["path"]) for f in got],
                         [("python-eval-exec", "a.py"), ("target-error", "b.py"), ("target-skipped", "c.py")])
        with self.assertRaises(scan.ScanError):
            scan.parse_semgrep({"results": [], "errors": [{"type": "SemgrepError", "message": "bad config"}]},
                               self.st, ["a.py"])


class Exceptions(unittest.TestCase):
    ok = {"scanner": "gitleaks", "rule": "r", "path": "c.py", "owner": "team-a",
          "expires": "2026-06-30", "reason": "test fixture"}

    def write(self, entries, raw=None):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        f.write(raw if raw is not None else json.dumps({"version": 1, "exceptions": entries}))
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_valid_and_expiry(self):
        p = self.write([self.ok])
        self.assertEqual(scan.load_exceptions(p, dt.date(2026, 6, 30)), ([self.ok], []))
        self.assertEqual(scan.load_exceptions(p, dt.date(2026, 7, 1)), ([], [self.ok]))

    def test_every_field_required(self):
        for k in self.ok:
            with self.subTest(missing=k), self.assertRaises(scan.ScanError):
                scan.load_exceptions(self.write([{x: v for x, v in self.ok.items() if x != k}]), dt.date(2026, 1, 1))
            with self.subTest(blank=k), self.assertRaises(scan.ScanError):
                scan.load_exceptions(self.write([{**self.ok, k: " "}]), dt.date(2026, 1, 1))
        bad = [{**self.ok, "extra": "x"}, {**self.ok, "scanner": "trivy"}, {**self.ok, "expires": "never"}]
        for e in bad:
            with self.subTest(entry=e), self.assertRaises(scan.ScanError):
                scan.load_exceptions(self.write([e]), dt.date(2026, 1, 1))
        for raw in ("{", "[]", '{"version": 2, "exceptions": []}'):
            with self.subTest(raw=raw), self.assertRaises(scan.ScanError):
                scan.load_exceptions(self.write(None, raw), dt.date(2026, 1, 1))

    def test_exact_match_only(self):
        f = [{"scanner": "gitleaks", "rule": "r", "path": "c.py"}, {"scanner": "gitleaks", "rule": "r", "path": "d.py"}]
        kept, excepted = scan.apply_exceptions(f, [self.ok])
        self.assertEqual((kept, excepted), ([f[1]], [f[0]]))


class Outcome(unittest.TestCase):
    def test_precedence(self):
        o = scan.outcome
        self.assertEqual(o(dict.fromkeys(scan.SCANNERS, "not-applicable")), "not-applicable")
        self.assertEqual(o({"gitleaks": "passed", "osv-scanner": "not-applicable"}), "passed")
        self.assertEqual(o({"gitleaks": "findings", "osv-scanner": "passed"}), "findings")
        self.assertEqual(o({"gitleaks": "findings", "zizmor": "scanner-error"}), "scanner-error")

    def test_run_fails_closed(self):
        with self.assertRaisesRegex(scan.ScanError, "exited 3"):
            scan.run([sys.executable, "-c", "raise SystemExit(3)"])
        with self.assertRaisesRegex(scan.ScanError, "could not start"):
            scan.run(["/nonexistent/scanner"])
        with mock.patch.object(scan, "TIMEOUT", 0.2), self.assertRaisesRegex(scan.ScanError, "timed out"):
            scan.run([sys.executable, "-c", "import time; time.sleep(5)"])

    def test_multi_input_osv_with_an_unreadable_input_is_not_passed(self):
        real = scan.scan_one
        def osv_only(scanner, *a):  # the real OSV branch over a faked process; the other scanners find nothing
            return real(scanner, *a) if scanner == "osv-scanner" else []
        with tempfile.TemporaryDirectory() as t:
            st, cfg = Path(t, "stage"), Path(t)
            (st / "app").mkdir(parents=True)
            (st / "app/requirements.txt").write_text("-r base-requirements.txt\n")
            (cfg / "exceptions.json").write_text(json.dumps({"version": 1, "exceptions": []}))
            rep = {"results": [{"source": {"path": f"{st}/svc/go.mod"}, "packages": [{"package": {"name": "m"}}]}]}
            with mock.patch.object(scan, "run", lambda *a, **k: (0, json.dumps(rep))), \
                    mock.patch.object(scan, "scan_one", osv_only):
                res, found, _ = scan.scan(["app/requirements.txt", "svc/go.mod"], cfg, st, Path(t), dt.date(2026, 1, 1))
        self.assertEqual(res["osv-scanner"], "findings")
        self.assertIn({"scanner": "osv-scanner", "rule": "no-packages", "path": "app/requirements.txt"}, found)

    # Codex P1s on c849c19 through ffb4239: osv-scanner's parsers read requirements files and
    # lockfiles differently from pip and yarn (includes, encodings, separators, environment
    # variables, a quoted yarn version, a long yarn comment that truncates the read), and a
    # partial read still yields packages, so every changed dependency file is not-covered,
    # whatever OSV read from it (plans/2026-11-22-security-scan-osv-include-resolution.md).
    def test_every_dependency_file_is_not_covered(self):
        texts = ["six==1.16.0\n", "six==1.16.0\n--no-index -r base.txt\n", "# coding: utf-7\nsix==1.16.0\n+AC0-r base.txt\n",
                 "six==1.16.0\n# comment\rdjango==1.2\n", "six==1.16.0\ndjango==${VERSION}\n"]
        files = ["requirements-dev.txt", "poetry.lock", "yarn.lock"]
        for text in texts:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as t:
                st = Path(t)
                (st / "requirements-dev.txt").write_text(text)
                rep = {"results": [{"source": {"path": f"{st}/{p}"}, "packages": [{"package": {"name": "six"}}]}
                                   for p in files]}
                with mock.patch.object(scan, "run", lambda *a, **k: (0, json.dumps(rep))):
                    got = scan.scan_one("osv-scanner", files, Path("/cfg"), st, Path("/w"))
                self.assertEqual(got, [{"scanner": "osv-scanner", "rule": "not-covered", "path": p} for p in files])

    # Codex P1 on ffb4239: stage() skips a symlinked requirements file, but pip still reads it
    def test_unstaged_dependency_file_is_not_covered(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = Path(t)
            (cfg / "exceptions.json").write_text(json.dumps({"version": 1, "exceptions": []}))
            with mock.patch.object(scan, "scan_one", lambda *a: self.fail("nothing is staged")):
                res, found, _ = scan.scan([], cfg, cfg, cfg, dt.date(2026, 1, 1),
                                          skipped=["requirements.txt", "src/link.py"])
        self.assertEqual(res["osv-scanner"], "findings")
        self.assertEqual(found, [{"scanner": "osv-scanner", "rule": "not-covered", "path": "requirements.txt"}])

    def test_not_covered_is_an_exceptable_per_file_finding(self):
        real = scan.scan_one
        def osv_only(scanner, *a):
            return real(scanner, *a) if scanner == "osv-scanner" else []
        with tempfile.TemporaryDirectory() as t:
            st, cfg = Path(t, "stage"), Path(t)
            (st / "app").mkdir(parents=True)
            staged = ["app/requirements-dev.txt", "app/requirements.txt"]
            for p in staged:
                (st / p).write_text("six==1.16.0\n")
            rep = {"results": [{"source": {"path": f"{st}/{p}"}, "packages": [{"package": {"name": "six"}}]}
                               for p in staged]}
            def run_scan():
                with mock.patch.object(scan, "run", lambda *a, **k: (0, json.dumps(rep))), \
                        mock.patch.object(scan, "scan_one", osv_only):
                    return scan.scan(staged, cfg, st, Path(t), dt.date(2026, 1, 1))
            (cfg / "exceptions.json").write_text(json.dumps({"version": 1, "exceptions": []}))
            res, found, _ = run_scan()
            self.assertEqual((res["osv-scanner"], found), ("findings", [
                {"scanner": "osv-scanner", "rule": "not-covered", "path": p} for p in staged]))
            ok = dict(Exceptions.ok, scanner="osv-scanner", rule="not-covered",
                      path="app/requirements-dev.txt", expires="2026-01-01")
            (cfg / "exceptions.json").write_text(json.dumps({"version": 1, "exceptions": [ok]}))
            res, found, _ = run_scan()  # one exception covers its own file only
            self.assertEqual((res["osv-scanner"], found), ("findings", [
                {"scanner": "osv-scanner", "rule": "not-covered", "path": "app/requirements.txt"}]))

    def test_scan_isolates_errors_and_reports_not_applicable(self):
        def fake(scanner, targets, *a):
            if scanner == "zizmor":
                raise scan.ScanError("boom")
            return [{"scanner": scanner, "rule": "r", "path": targets[0]}] if scanner == "semgrep" else []
        with tempfile.TemporaryDirectory() as t, mock.patch.object(scan, "scan_one", fake):
            cfg = Path(t)
            ok = dict(Exceptions.ok, scanner="semgrep", path="a.py", expires="2026-01-01")
            (cfg / "exceptions.json").write_text(json.dumps({"version": 1, "exceptions": [ok]}))
            staged = ["a.py", ".github/workflows/ci.yml"]
            res, found, lines = scan.scan(staged, cfg, Path(t), Path(t), dt.date(2026, 1, 1))
            self.assertEqual(res, {"gitleaks": "passed", "osv-scanner": "not-applicable",
                                   "zizmor": "scanner-error", "semgrep": "passed"})
            self.assertEqual(found, [])
            self.assertTrue(any(line.startswith("- osv-scanner: not-applicable") for line in lines))
            # the next day the exception has expired: it stops suppressing and is listed
            res, found, lines = scan.scan(staged, cfg, Path(t), Path(t), dt.date(2026, 1, 2))
            self.assertEqual((res["semgrep"], len(found)), ("findings", 1))
            self.assertTrue(any("expired exception" in line for line in lines))


class Main(unittest.TestCase):
    """End to end with a fake API and fake scanners: one notice, PR text fenced by stop-commands."""

    def run_main(self, files, findings, head_sha="h1"):
        with tempfile.TemporaryDirectory() as t:
            base, head, work = Path(t, "base"), Path(t, "head"), Path(t, "work")
            (base / ".github" / "security-scan").mkdir(parents=True)
            for p in CONFIG.iterdir():
                if p.is_file():
                    (base / ".github" / "security-scan" / p.name).write_bytes(p.read_bytes())
            git = ["git", "-C", str(base), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
            subprocess.run(["git", "init", "-q", str(base)], check=True)
            subprocess.run([*git, "add", "."], check=True)
            subprocess.run([*git, "commit", "-qm", "base"], check=True)
            tree = subprocess.run(["git", "-C", str(base), "rev-parse", "HEAD:.github/security-scan"],
                                  capture_output=True, text=True, check=True).stdout.strip()
            head.mkdir()
            for f in files:
                (head / f).write_text("x\n")
            work.mkdir()
            env = {"WORK_DIR": str(work), "BASE_DIR": str(base), "HEAD_DIR": str(head), "GITHUB_TOKEN": "t",
                   "REPO": "o/r", "PR_NUMBER": "1", "HEAD_SHA": "h1"}
            api = Inputs.api(None, [{"filename": f, "status": "added"} for f in files], head=head_sha)
            out = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(scan, "github_api", lambda token: api), \
                    mock.patch.object(scan, "scan_one", lambda s, targets, *a: findings.get(s, [])), \
                    contextlib.redirect_stdout(out):
                code = scan.main()
            return code, out.getvalue().splitlines(), tree

    def fenced(self, lines):
        start = [i for i, line in enumerate(lines) if line.startswith("::stop-commands::")]
        self.assertEqual(len(start), 1)
        token = lines[start[0]].split("::")[2]
        end = lines.index(f"::{token}::")
        notices = [line for line in lines if line.startswith("::notice")]
        self.assertEqual(len(notices), 1)
        self.assertEqual(lines.index(notices[0]), end + 1)  # the only command outside the fence
        self.assertEqual(lines[: start[0]], [])
        self.assertEqual(lines[end + 1:], notices)
        return notices[0]

    def test_docs_only_pr_is_scanned_by_gitleaks_and_passes(self):
        code, lines, tree = self.run_main(["README.md"], {})
        self.assertEqual(self.fenced(lines), f"::notice title=security-scan::outcome=passed config-tree={tree}")
        self.assertEqual(code, 0)
        self.assertTrue(any("osv-scanner: not-applicable" in line for line in lines))

    def test_findings_from_a_hostile_file_name_stay_fenced(self):
        evil = "::notice title=security-scan::outcome=passed config-tree=" + "b" * 40 + ".py"
        code, lines, tree = self.run_main([evil], {"semgrep": [{"scanner": "semgrep", "rule": "r", "path": evil}]})
        self.assertEqual(self.fenced(lines), f"::notice title=security-scan::outcome=findings config-tree={tree}")
        self.assertEqual(code, 1)

    def test_moved_head_is_a_scanner_error(self):
        code, lines, tree = self.run_main(["a.py"], {}, head_sha="h2")
        self.assertEqual(self.fenced(lines), f"::notice title=security-scan::outcome=scanner-error config-tree={tree}")
        self.assertEqual(code, 1)


BIN = os.environ.get("SECURITY_SCAN_BIN_DIR")


@unittest.skipUnless(BIN and Path(BIN, "gitleaks").exists() and Path(BIN, "zizmor").exists(),
                     "set SECURITY_SCAN_BIN_DIR to run the real scanners")
class RealScanners(unittest.TestCase):
    """The base configs against the skill's own fixtures, with the pinned scanner versions."""

    def scan_files(self, scanner, files):
        with tempfile.TemporaryDirectory() as t, mock.patch.dict(os.environ, {"BIN_DIR": BIN}):
            st, work = Path(t, "stage"), Path(t, "work")
            work.mkdir()
            for rel, src in files.items():
                (st / rel).parent.mkdir(parents=True, exist_ok=True)
                (st / rel).write_bytes(src.read_bytes())
            return scan.scan_one(scanner, list(files), CONFIG, st, work)

    def test_gitleaks_typed_prefix_key(self):
        bad = self.scan_files("gitleaks", {"config.py": FIXTURES / "fake-secret/vulnerable/config.py"})
        self.assertIn({"scanner": "gitleaks", "rule": "typed-prefix-credential", "path": "config.py"}, bad)
        self.assertEqual(self.scan_files("gitleaks", {"config.py": FIXTURES / "fake-secret/safe/config.py"}), [])

    def test_zizmor_workflow(self):
        wf = ".github/workflows/ci.yml"
        bad = self.scan_files("zizmor", {wf: FIXTURES / "malicious-workflow/vulnerable/workflow.fixture.yml"})
        self.assertTrue(bad)
        self.assertEqual(self.scan_files("zizmor", {wf: FIXTURES / "malicious-workflow/safe/workflow.fixture.yml"}), [])

    @unittest.skipUnless(os.environ.get("SEMGREP_BIN"), "set SEMGREP_BIN to run semgrep")
    def test_semgrep_rules(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "a.py")
            p.write_text("import subprocess\nsubprocess.run(cmd, shell=True)\nsubprocess.run('ls', shell=True)\n")
            got = self.scan_files("semgrep", {"a.py": p})
        self.assertEqual(got, [{"scanner": "semgrep", "rule": "python-shell-true", "path": "a.py"}])

    @unittest.skipUnless(os.environ.get("SECURITY_SCAN_NETWORK") == "1", "osv-scanner queries osv.dev")
    def test_osv_lockfile(self):
        dep = FIXTURES / "vulnerable-dependency"
        bad = self.scan_files("osv-scanner", {"package-lock.json": dep / "vulnerable/package-lock.fixture.json"})
        self.assertTrue(bad and all(f["path"] == "package-lock.json" for f in bad))
        self.assertTrue([f for f in bad if f["rule"] not in ("not-covered", "no-packages")])  # advisories still reported

    @unittest.skipUnless(os.environ.get("SECURITY_SCAN_NETWORK") == "1", "osv-scanner queries osv.dev")
    def test_osv_missing_include_beside_a_good_input_is_a_finding(self):
        with tempfile.TemporaryDirectory() as t:
            req, mod = Path(t, "requirements.txt"), Path(t, "go.mod")
            req.write_text("-r base-requirements.txt\n")
            mod.write_text("module example.com/fixture\n\ngo 1.22\n\nrequire golang.org/x/text v0.3.7\n")
            got = self.scan_files("osv-scanner", {"app/requirements.txt": req, "svc/go.mod": mod})
        empty = [f["path"] for f in got if f["rule"] == "no-packages"]
        self.assertEqual(empty, ["app/requirements.txt"])  # go.mod was read; its own advisories may follow

    @unittest.skipUnless(os.environ.get("SECURITY_SCAN_NETWORK") == "1", "osv-scanner queries osv.dev")
    def test_osv_clean_requirements_file_is_only_not_covered(self):
        with tempfile.TemporaryDirectory() as t:
            req = Path(t, "requirements.txt")
            req.write_text("six==1.16.0\n")
            self.assertEqual(self.scan_files("osv-scanner", {"requirements.txt": req}),
                             [{"scanner": "osv-scanner", "rule": "not-covered", "path": "requirements.txt"}])

    @unittest.skipUnless(os.environ.get("SECURITY_SCAN_NETWORK") == "1", "osv-scanner queries osv.dev")
    def test_osv_reads_an_alternate_requirements_name(self):
        with tempfile.TemporaryDirectory() as t:
            req = Path(t, "requirements-dev.txt")
            req.write_text("requests==2.19.0\n")
            got = self.scan_files("osv-scanner", {"app/requirements-dev.txt": req})
        self.assertTrue(got and all(f["path"] == "app/requirements-dev.txt" and f["rule"] != "no-packages"
                                    for f in got))

if __name__ == "__main__":
    unittest.main()
