"""install-workflow.py must not downgrade a repo's vendored aec detector.

Row: https://app.notion.com/p/41a4efecc95a81388f71da096a699f71 (origin: nevar-integrations PR #11).
"""
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
# Only the claude-skills repo has its mirrors (scripts/, .github/) and this manifest beside the skill; an
# installed skill directory (e.g. nevar-fund's) has neither, so tests that need that layout skip there.
IN_CLAUDE_SKILLS = (SKILL.parent / "skills-manifest.json").is_file()
NOT_CLAUDE_SKILLS = "needs the claude-skills repo layout (skills-manifest.json beside the skill)"
INSTALLER = SKILL / "scripts" / "install-workflow.py"


def install(repo, *args):
    return subprocess.run([sys.executable, str(INSTALLER), *args], cwd=repo, capture_output=True, text=True)


DETECTOR = (SKILL / "scripts" / "check-forged-gate-names.py").read_bytes()
SIGNATURE = b"def forged(check_runs, run_lookup, protected=None):"
assert SIGNATURE in DETECTOR
# a newer/custom detector the bundled wrapper runs against
COMPATIBLE = b"# newer aec copy\n" + DETECTOR
# #105 Codex P2: these define every name the wrapper uses, yet the wrapper cannot run against them
INCOMPATIBLE = DETECTOR.replace(SIGNATURE, b"def forged(check_runs, run_lookup):")  # old 2-arg forged
INCOMPATIBLE_VARIANTS = (
    INCOMPATIBLE,
    b"# custom\nPROTECTED = {}\ndef forged(c, l, protected=None): return []\n"
    b"def _gh_run_lookup(repo): return None\ndef _load_check_runs(text): return []\n",  # no Review Gate entry
    b"# old custom detector\nPROTECTED = {}\ndef forged(c, l): return []\n",
    b"def broken(:\n",
    DETECTOR.replace(SIGNATURE, b"def forged(check_runs, run_lookup, protected=None, *, audit):"),  # required kw-only
)


class VendoredDetector(unittest.TestCase):
    def test_incompatible_custom_detector_refuses_without_force(self):
        # 3.2.8 P2: a KEPT detector the upgraded wrapper cannot use would fail every gate run
        with tempfile.TemporaryDirectory() as repo:
            dest = Path(repo) / "scripts" / "check-forged-gate-names.py"
            dest.parent.mkdir()
            for variant in INCOMPATIBLE_VARIANTS:
                with self.subTest(variant=variant[:40]):
                    dest.write_bytes(variant)
                    proc = install(repo)
                    self.assertEqual(proc.returncode, 1, proc.stderr)
                    self.assertIn("cannot run against", proc.stderr)
                    self.assertEqual(dest.read_bytes(), variant)
                    self.assertFalse((Path(repo) / "scripts" / "check-forged-review-gate.py").exists())
                    self.assertFalse((Path(repo) / ".github").exists())

    def test_the_installer_never_executes_the_repo_detector(self):
        # #105 Codex P1: compatibility is decided by parsing; repo code never runs on install
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as side:
            marker = Path(side) / "ran"
            dest = Path(repo) / "scripts" / "check-forged-gate-names.py"
            dest.parent.mkdir()
            for body in (b"open(%r, 'w').close()\nraise SystemExit(0)\n" % str(marker).encode(),
                         COMPATIBLE + b"\nopen(%r, 'w').close()\n" % str(marker).encode()):
                with self.subTest(body=body[:30]):
                    dest.write_bytes(body)
                    install(repo)
                    install(repo, "--force")
                    self.assertFalse(marker.exists())

    def test_incompatible_custom_detector_is_backed_up_and_replaced_with_force(self):
        with tempfile.TemporaryDirectory() as repo:
            dest = Path(repo) / "scripts" / "check-forged-gate-names.py"
            dest.parent.mkdir()
            dest.write_bytes(INCOMPATIBLE)
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(dest.read_bytes(), (SKILL / "scripts" / dest.name).read_bytes())
            self.assertEqual(dest.with_name(dest.name + ".custom.bak").read_bytes(), INCOMPATIBLE)
            self.assertIn("REPLACED", proc.stderr)

    def test_a_second_forced_replacement_keeps_the_first_backup(self):
        # #105 Codex P2: the first custom copy must survive a later forced upgrade of a second one
        with tempfile.TemporaryDirectory() as repo:
            dest = Path(repo) / "scripts" / "check-forged-gate-names.py"
            dest.parent.mkdir()
            first, second = INCOMPATIBLE_VARIANTS[1], INCOMPATIBLE_VARIANTS[2]
            dest.write_bytes(first)
            self.assertEqual(install(repo, "--force").returncode, 0)
            dest.write_bytes(second)
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(dest.with_name(dest.name + ".custom.bak").read_bytes(), first)
            self.assertEqual(dest.with_name(dest.name + ".custom.1.bak").read_bytes(), second)

    def test_differing_repo_detector_is_left_untouched_even_with_force(self):
        with tempfile.TemporaryDirectory() as repo:
            dest = Path(repo) / "scripts" / "check-forged-gate-names.py"
            dest.parent.mkdir()
            dest.write_bytes(COMPATIBLE)
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(dest.read_bytes(), COMPATIBLE)
            self.assertIn("KEPT", proc.stderr)
            # everything else is still (re)installed
            self.assertEqual((Path(repo) / "scripts" / "check-forged-review-gate.py").read_bytes(),
                             (SKILL / "scripts" / "check-forged-review-gate.py").read_bytes())

    def test_the_3_2_19_pinless_detector_is_replaced_with_force(self):
        # 3.2.20: its map had set() for the main-via-staging guard job, so the job rejected its own run; a repo
        # vendored from 3.2.4-3.2.19 must be upgraded by --force, not KEPT as a "newer or custom" copy.
        old = subprocess.run(["git", "show", "0d3a553:review-gate/scripts/check-forged-gate-names.py"],
                             cwd=SKILL, capture_output=True)
        if old.returncode:
            self.skipTest("no git history (vendored layout)")
        with tempfile.TemporaryDirectory() as repo:
            dest = Path(repo) / "scripts" / "check-forged-gate-names.py"
            dest.parent.mkdir()
            dest.write_bytes(old.stdout)
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(dest.read_bytes(), (SKILL / "scripts" / "check-forged-gate-names.py").read_bytes())
            self.assertNotIn("KEPT", proc.stdout)

    def test_known_older_vendored_detector_is_replaced_with_force(self):
        # #87 Codex P1: the 3.2.1-bundled detector (aec 46580fa) must be upgraded, not KEPT.
        import importlib.util
        spec = importlib.util.spec_from_file_location("iw", INSTALLER)
        iw = importlib.util.module_from_spec(spec); spec.loader.exec_module(iw)
        old = subprocess.run(["git", "show", "f599564b:review-gate/scripts/check-forged-gate-names.py"],
                             cwd=SKILL, capture_output=True)
        if old.returncode:
            self.skipTest("no git history (vendored layout)")
        import hashlib
        self.assertIn(hashlib.sha256(old.stdout).hexdigest(), iw.KNOWN_OLD)
        with tempfile.TemporaryDirectory() as repo:
            dest = Path(repo) / "scripts" / "check-forged-gate-names.py"
            dest.parent.mkdir()
            dest.write_bytes(old.stdout)
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(dest.read_bytes(), (SKILL / "scripts" / "check-forged-gate-names.py").read_bytes())
            self.assertNotIn("KEPT", proc.stderr)

    def test_byte_identical_detector_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            dest = Path(repo) / "scripts" / "check-forged-gate-names.py"
            before = dest.stat().st_mtime_ns
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("unchanged: " + str(dest.resolve()), proc.stdout)
            self.assertEqual(dest.stat().st_mtime_ns, before)

    def test_fresh_repo_gets_the_skill_copy(self):
        with tempfile.TemporaryDirectory() as repo:
            proc = install(repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual((Path(repo) / "scripts" / "check-forged-gate-names.py").read_bytes(),
                             (SKILL / "scripts" / "check-forged-gate-names.py").read_bytes())
            self.assertNotIn("KEPT", proc.stderr)

    def test_linter_is_vendored_and_runs_beside_the_checker(self):
        with tempfile.TemporaryDirectory() as repo:
            proc = install(repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            linter = Path(repo) / "scripts" / "lint-review-body.py"
            self.assertEqual(linter.read_bytes(), (SKILL / "scripts" / "lint-review-body.py").read_bytes())
            bad = subprocess.run([sys.executable, str(linter)], input="## Review\n\n- x\n", capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1, bad.stderr)
            self.assertIn("PR body line 3:", bad.stderr)

    @unittest.skipUnless(IN_CLAUDE_SKILLS, NOT_CLAUDE_SKILLS)
    def test_this_repo_mirrors_are_byte_identical(self):
        # claude-skills runs its own gate from scripts/ and .github/workflows/; they must equal the skill's copies.
        root = SKILL.parent
        for name in ("check-review-gate.py", "check-forged-gate-names.py", "check-forged-review-gate.py",
                     "lint-review-body.py"):
            self.assertEqual((root / "scripts" / name).read_bytes(), (SKILL / "scripts" / name).read_bytes(), name)
        for linter in (root / "scripts" / "lint-review-body.py", SKILL / "scripts" / "lint-review-body.py"):
            self.assertTrue(os.access(linter, os.X_OK), linter)
        self.assertEqual((root / ".github" / "workflows" / "review-gate.yml").read_bytes(),
                         (SKILL / "templates" / "review-gate.yml").read_bytes())


DOCTOR = SKILL / "scripts" / "doctor-review-gate.py"


def doctor_script_lines(repo, env=None, *args):
    proc = subprocess.run([sys.executable, str(DOCTOR), *args], cwd=repo, capture_output=True, text=True, env=env)
    return proc, [line for line in proc.stdout.splitlines() if " scripts/" in line and "workflows" not in line]


class DoctorVendoredDrift(unittest.TestCase):
    """doctor-review-gate.py compares every vendored script with the skill's copy (3.2.12)."""

    def test_fresh_install_reports_every_vendored_script_ok(self):
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            proc, lines = doctor_script_lines(repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(lines, [f"OK vendored script scripts/{n}" for n in installer().VENDORED_SCRIPTS])

    def test_without_gh_the_local_checks_run_and_doctor_warns(self):
        # 3.2.13: a machine without the GitHub CLI used to crash with FileNotFoundError after the local checks
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as empty_path:
            install(repo)
            proc, lines = doctor_script_lines(repo, env={**os.environ, "PATH": empty_path})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertIn("WARN gh (GitHub CLI) not found; skip label and ruleset checks", proc.stdout)
            self.assertEqual(lines, [f"OK vendored script scripts/{n}" for n in installer().VENDORED_SCRIPTS])

    @unittest.skipUnless(IN_CLAUDE_SKILLS, NOT_CLAUDE_SKILLS + " and its git history")
    def test_an_old_checker_and_a_missing_linter_warn(self):
        old = subprocess.run(["git", "show", "bce2e9c0:review-gate/scripts/check-review-gate.py"],
                             cwd=SKILL, capture_output=True, check=True).stdout  # review-gate 3.2.10
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            (Path(repo) / "scripts" / "check-review-gate.py").write_bytes(old)
            (Path(repo) / "scripts" / "lint-review-body.py").unlink()
            proc, lines = doctor_script_lines(repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("WARN scripts/check-review-gate.py differs from the skill; re-run "
                          "install-workflow.py --force and merge it to the default branch", lines)
            self.assertIn("WARN missing scripts/lint-review-body.py; re-run install-workflow.py and merge it "
                          "to the default branch", lines)
            self.assertIn("OK vendored script scripts/check-forged-review-gate.py", lines)
            # one line per vendored script, taken from the installer's own list
            self.assertEqual(len(lines), len(installer().VENDORED_SCRIPTS), lines)


class InstalledSkillLayout(unittest.TestCase):
    """The skill's tests also run from an installed skill directory, without the claude-skills tree."""

    @unittest.skipUnless(IN_CLAUDE_SKILLS, "already running from an installed skill directory")
    def test_module_skips_repo_layout_tests_outside_claude_skills(self):
        with tempfile.TemporaryDirectory() as d:
            skill = Path(d) / "skills" / "review-gate"
            shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns("__pycache__"))
            proc = subprocess.run([sys.executable, "-m", "unittest", "-v", "test_install_workflow"],
                                  cwd=skill / "tests", capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertRegex(proc.stderr, r"test_this_repo_mirrors_are_byte_identical .*skipped 'needs the claude-skills")
            self.assertNotIn("FileNotFoundError", proc.stderr)


def installer():
    spec = importlib.util.spec_from_file_location("install_workflow", INSTALLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod



class DoctorStrict(unittest.TestCase):
    """3.2.14: --strict exits 1 on workflow or vendored-script drift; the default run still exits 0."""

    def no_gh(self):
        self._path = tempfile.TemporaryDirectory()
        self.addCleanup(self._path.cleanup)
        return {**os.environ, "PATH": self._path.name}  # local checks only, as in CI without a token

    def test_checker_vendored_without_closer_permissions_fails_strict(self):
        src = (SKILL / "scripts" / "check-review-gate.py").read_text()
        start = src.index("def closer_permissions(")
        stale = src[:start] + src[src.index("\ndef ", start + 1) + 1:]  # an old copy without the function
        self.assertNotIn("def closer_permissions(", stale)
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            (Path(repo) / "scripts" / "check-review-gate.py").write_text(stale)
            default, _ = doctor_script_lines(repo, self.no_gh())
            strict, lines = doctor_script_lines(repo, self.no_gh(), "--strict")
            self.assertEqual(default.returncode, 0, default.stdout)
            self.assertEqual(strict.returncode, 1, strict.stdout)
            self.assertIn("WARN scripts/check-review-gate.py differs from the skill; re-run "
                          "install-workflow.py --force and merge it to the default branch", lines)
            self.assertIn("FAIL --strict: 1 workflow/vendored-script problem(s) above", strict.stdout)

    def test_fresh_install_passes_strict(self):
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            proc, _ = doctor_script_lines(repo, self.no_gh(), "--strict")
            self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_missing_workflow_and_script_fail_strict(self):
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            (Path(repo) / ".github" / "workflows" / "review-gate.yml").unlink()
            (Path(repo) / "scripts" / "lint-review-body.py").unlink()
            proc, _ = doctor_script_lines(repo, self.no_gh(), "--strict")
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("FAIL --strict: 2 ", proc.stdout)

    def test_a_kept_newer_aec_detector_passes_strict(self):
        # the installer keeps it, so --strict must not fail a repo for what --force would not change
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            (Path(repo) / "scripts" / "check-forged-gate-names.py").write_bytes(COMPATIBLE)
            proc, lines = doctor_script_lines(repo, self.no_gh(), "--strict")
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertTrue(any(line.startswith("WARN scripts/check-forged-gate-names.py differs") for line in lines))


class DoctorJob(unittest.TestCase):
    """3.2.19: --doctor-job writes a no-clone job that runs the repo's own vendored doctor --strict."""

    def test_written_only_on_request(self):
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            self.assertFalse((Path(repo) / ".github" / "workflows" / "review-gate-doctor.yml").exists())
            install(repo, "--doctor-job")
            written = (Path(repo) / ".github" / "workflows" / "review-gate-doctor.yml").read_bytes()
            self.assertEqual(written, (SKILL / "templates" / "review-gate-doctor.yml").read_bytes())

    def test_job_clones_nothing_and_runs_the_vendored_doctor_strict(self):
        import yaml
        text = (SKILL / "templates" / "review-gate-doctor.yml").read_text()
        self.assertNotIn("git clone", text)  # 3.2.18 cloned claude-skills main at run time
        self.assertNotIn("github.com/", text)
        wf = yaml.safe_load(text)
        self.assertEqual(wf[True], "pull_request")  # YAML 1.1 reads the `on` key as True
        self.assertEqual(wf["permissions"], {"contents": "read"})
        steps = wf["jobs"]["doctor"]["steps"]
        self.assertEqual(steps[0]["uses"], "actions/checkout@v7")
        self.assertEqual(steps[0]["with"], {"persist-credentials": False})
        run = steps[1]["run"]
        self.assertIn("python3 .claude/skills/review-gate/scripts/doctor-review-gate.py --strict", run)
        self.assertNotIn("${{", run)  # nothing from the event is interpolated into the shell

    def run_step(self, repo):
        import yaml
        run = yaml.safe_load((SKILL / "templates" / "review-gate-doctor.yml").read_text())["jobs"]["doctor"]["steps"][1]["run"]
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        env = {**os.environ, "PATH": f"{empty.name}:{os.path.dirname(shutil.which('python3'))}:/usr/bin:/bin"}
        env.pop("GH_TOKEN", None)
        return subprocess.run(["bash", "-c", run], cwd=repo, capture_output=True, text=True, env=env)

    def test_step_passes_in_a_repo_with_a_current_vendored_skill(self):
        with tempfile.TemporaryDirectory() as repo:
            vendor(repo)
            install(repo)
            proc = self.run_step(repo)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_step_fails_closed_naming_the_fix_without_a_vendored_skill(self):
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            proc = self.run_step(repo)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("::error::", proc.stdout)
            self.assertIn("aec install skill review-gate", proc.stdout)


def skill_version(skill_dir):
    for line in (Path(skill_dir) / "SKILL.md").read_text().splitlines()[1:]:
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("no version")


def one_release_behind(version):
    major, minor, patch = (int(x) for x in version.split("."))
    return f"{major}.{minor}.{patch - 1}"


def vendor(repo, version=None):
    """Track a copy of this skill at .claude/skills/review-gate, optionally stamped with an older version."""
    dest = Path(repo) / ".claude" / "skills" / "review-gate"
    shutil.copytree(SKILL, dest, ignore=shutil.ignore_patterns(".*", "__pycache__"))
    if version:
        current = skill_version(SKILL)
        for name in ("SKILL.md", "hooks.json"):
            f = dest / name
            f.write_text(f.read_text().replace(current, version, 1))
        (dest / "scripts" / "dropped-in-a-later-release.py").write_text("# only the old copy has this\n")
    return dest


# Runs the real installer with --force and a fault at the swap: just before the staged copy is renamed
# into place, either SIGKILL the process or make .claude/skills read-only (so that rename and the
# rename back both fail). An audit hook is the fault point; no installer code is replaced.
SWAP_FAULT = """
import os, runpy, signal, sys
installer, action, parent = sys.argv[1:4]
def hook(event, args):
    if event == "os.rename" and ".new-" in os.fsdecode(args[0]):
        if action == "kill":
            os.kill(os.getpid(), signal.SIGKILL)
        os.chmod(parent, 0o555)
sys.addaudithook(hook)
sys.argv = [installer, "--force"]
runpy.run_path(installer, run_name="__main__")
"""


def install_at_swap(repo, action):
    parent = Path(repo) / ".claude" / "skills"
    return subprocess.run([sys.executable, "-c", SWAP_FAULT, str(INSTALLER), action, str(parent)],
                          cwd=repo, capture_output=True, text=True)


def tree(d):
    d = Path(d)
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and not any(x.startswith(".") for x in p.relative_to(d).parts)}


class VendoredSkillRefresh(unittest.TestCase):
    """3.2.19: the tracked .claude/skills/review-gate is refreshed as ONE unit, never file by file."""

    def test_force_replaces_a_copy_one_release_behind_as_a_whole(self):
        with tempfile.TemporaryDirectory() as repo:
            dest = vendor(repo, one_release_behind(skill_version(SKILL)))
            self.assertTrue((dest / "scripts" / "dropped-in-a-later-release.py").is_file())
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(tree(dest), tree(SKILL))  # stale-only file gone, every file current
            old, new = one_release_behind(skill_version(SKILL)), skill_version(SKILL)
            self.assertIn(f".claude/skills/review-gate ({old} -> {new}); commit the whole directory", proc.stdout)

    def test_without_force_a_stale_copy_is_left_whole_and_named(self):
        with tempfile.TemporaryDirectory() as repo:
            old = one_release_behind(skill_version(SKILL))
            dest = vendor(repo, old)
            before = tree(dest)
            proc = install(repo)
            self.assertEqual(tree(dest), before)
            self.assertIn(f".claude/skills/review-gate is {old}", proc.stdout)
            self.assertIn("--force", proc.stdout)

    def test_a_current_or_newer_copy_is_never_touched(self):
        with tempfile.TemporaryDirectory() as repo:
            dest = vendor(repo, "99.0.0")
            before = tree(dest)
            install(repo, "--force")
            self.assertEqual(tree(dest), before)

    def test_force_repairs_an_equal_version_whose_hooks_json_disagrees(self):
        # #138 P2: the doctor names --force as the fix for this; equal SKILL.md versions must not stop it
        with tempfile.TemporaryDirectory() as repo:
            dest = vendor(repo)
            hooks = dest / "hooks.json"
            hooks.write_text(hooks.read_text().replace(skill_version(SKILL), one_release_behind(skill_version(SKILL)), 1))
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(tree(dest), tree(SKILL))

    def test_an_unparseable_vendored_version_is_refused_and_named_never_replaced(self):
        # #138 P2: a prerelease or garbled version is not "older"; nothing is deleted and the exit says why
        for bad in ("3.2.20-rc.1", "3..20"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as repo:
                dest = vendor(repo, bad)
                (dest / "untracked-local-notes.md").write_text("keep me\n")
                before = tree(dest)
                proc = install(repo, "--force")
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn(f"unparseable version {bad!r}", proc.stderr)
                self.assertEqual(tree(dest), before)

    def test_a_failed_copy_leaves_the_old_tree_and_its_untracked_files_intact(self):
        # #138 P1: the old copy is only moved aside once the complete replacement exists
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
            src = Path(tmp) / "review-gate"
            shutil.copytree(SKILL, src, ignore=shutil.ignore_patterns(".*", "__pycache__"))
            (src / "scripts" / "dangling.py").symlink_to(Path(tmp) / "missing-target.py")  # copytree cannot copy it
            dest = vendor(repo, one_release_behind(skill_version(SKILL)))
            (dest / "untracked-local-notes.md").write_text("keep me\n")
            before = tree(dest)
            proc = subprocess.run([sys.executable, str(src / "scripts" / "install-workflow.py"), "--force"],
                                  cwd=repo, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertEqual(tree(dest), before)
            self.assertIn("could not copy", proc.stderr)
            self.assertEqual([p.name for p in dest.parent.iterdir()], ["review-gate"])  # no temp dir left behind

    def test_a_refresh_killed_between_the_renames_is_recovered_by_the_next_run(self):
        # #138 P1 round 2: SIGKILL after the old copy moved aside and before the new one moved in
        with tempfile.TemporaryDirectory() as repo:
            dest = vendor(repo, one_release_behind(skill_version(SKILL)))
            killed = install_at_swap(repo, "kill")
            self.assertEqual(killed.returncode, -signal.SIGKILL, killed.stdout + killed.stderr)
            self.assertFalse(dest.exists())  # the window under test
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("recovered", proc.stdout)
            self.assertEqual(tree(dest), tree(SKILL))
            self.assertFalse(dest.with_name("review-gate.old").exists())

    def test_a_leftover_backup_beside_a_present_copy_is_refused_and_both_survive(self):
        with tempfile.TemporaryDirectory() as repo:
            dest = vendor(repo, one_release_behind(skill_version(SKILL)))
            backup = shutil.copytree(dest, dest.with_name("review-gate.old"))
            before = tree(dest)
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("review-gate.old is left from an earlier refresh", proc.stderr)
            self.assertEqual((tree(dest), tree(backup)), (before, before))

    @unittest.skipIf(os.geteuid() == 0, "root writes into a read-only directory")
    def test_a_failed_rollback_says_the_copy_is_absent_and_names_the_backup(self):
        # #138 P1 round 2: never "unchanged" when neither rename back worked
        with tempfile.TemporaryDirectory() as repo:
            dest = vendor(repo, one_release_behind(skill_version(SKILL)))
            try:
                proc = install_at_swap(repo, "readonly")
            finally:
                dest.parent.chmod(0o755)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertNotIn("unchanged", proc.stderr)
            self.assertIn("ABSENT", proc.stderr)
            self.assertRegex(proc.stderr, r"mv \S+/review-gate\.old \S+/review-gate\b")
            self.assertFalse(dest.exists())
            self.assertTrue(dest.with_name("review-gate.old").is_dir())

    def test_a_symlinked_skills_parent_is_refused_and_the_external_copy_survives(self):
        # #138 P1: a shared install reached through .claude/skills -> elsewhere must never be deleted
        with tempfile.TemporaryDirectory() as shared, tempfile.TemporaryDirectory() as repo:
            external = vendor(shared, one_release_behind(skill_version(SKILL)))
            (external / "untracked-local-notes.md").write_text("keep me\n")
            before = tree(external)
            (Path(repo) / ".claude").mkdir()
            (Path(repo) / ".claude" / "skills").symlink_to(external.parent)
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("refusing to replace", proc.stderr)
            self.assertEqual(tree(external), before)

    def test_a_symlinked_vendored_copy_is_refused_and_its_target_survives(self):
        with tempfile.TemporaryDirectory() as shared, tempfile.TemporaryDirectory() as repo:
            external = vendor(shared, one_release_behind(skill_version(SKILL)))
            before = tree(external)
            (Path(repo) / ".claude" / "skills").mkdir(parents=True)
            (Path(repo) / ".claude" / "skills" / "review-gate").symlink_to(external)
            proc = install(repo, "--force")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("refusing to replace", proc.stderr)
            self.assertEqual(tree(external), before)

    def test_a_symlinked_copy_reporting_the_current_version_is_refused_with_and_without_force(self):
        # 3.2.20 (hub cop P1): confinement runs before the version compare, so a symlinked copy that reports
        # the release (or newer) cannot read as "current" and be skipped.
        for version in (skill_version(SKILL), "99.0.0"):
            for flags in ((), ("--force",)):
                with self.subTest(version=version, flags=flags), \
                        tempfile.TemporaryDirectory() as shared, tempfile.TemporaryDirectory() as repo:
                    external = vendor(shared, version)
                    before = tree(external)
                    (Path(repo) / ".claude" / "skills").mkdir(parents=True)
                    (Path(repo) / ".claude" / "skills" / "review-gate").symlink_to(external)
                    proc = install(repo, *flags)
                    self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                    self.assertIn("refusing to replace", proc.stderr)
                    self.assertEqual(tree(external), before)

    def test_overlapping_source_and_destination_are_refused(self):
        # #138 P1: replacing a tree that contains the installer's own skill (or sits inside it) destroys the source
        with tempfile.TemporaryDirectory() as tmp:
            outer = vendor(Path(tmp) / "repo", one_release_behind(skill_version(SKILL)))
            inner = outer / "nested" / "review-gate"  # dest contains source
            shutil.copytree(SKILL, inner, ignore=shutil.ignore_patterns(".*", "__pycache__"))
            src_holder = Path(tmp) / "skill" / "review-gate"  # source contains dest
            shutil.copytree(SKILL, src_holder, ignore=shutil.ignore_patterns(".*", "__pycache__"))
            nested_repo = src_holder / "consumer"
            vendor(nested_repo, one_release_behind(skill_version(SKILL)))
            for installer, repo in ((inner, Path(tmp) / "repo"), (src_holder, nested_repo)):
                with self.subTest(repo=str(repo)):
                    dest = repo / ".claude" / "skills" / "review-gate"
                    before = tree(dest)
                    proc = subprocess.run([sys.executable, str(installer / "scripts" / "install-workflow.py"), "--force"],
                                          cwd=repo, capture_output=True, text=True)
                    self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                    self.assertIn("refusing to replace", proc.stderr)
                    self.assertEqual(tree(dest), before)


class SymlinkedDestinations(unittest.TestCase):
    """3.2.21: the installer never writes through a symlink, and never trusts one before an early return."""

    # (destination relative to the repo, extra installer flags that make the installer write it)
    DESTINATIONS = (
        (Path(".github") / "workflows" / "review-gate.yml", ()),
        (Path("scripts") / "check-review-gate.py", ()),
        (Path("scripts") / "check-forged-gate-names.py", ()),
        (Path(".github") / "workflows" / "review-gate-doctor.yml", ("--doctor-job",)),
    )

    def test_a_symlinked_destination_is_refused_with_and_without_force_and_its_target_is_untouched(self):
        for rel, extra in self.DESTINATIONS:
            template = (SKILL / "templates" / rel.name) if rel.suffix == ".yml" else (SKILL / "scripts" / rel.name)
            other = COMPATIBLE if rel.name == "check-forged-gate-names.py" else b"other bytes\n"  # a detector main() accepts
            # outside with other bytes, outside with the bytes the installer would write, and inside the repo
            for target, content in (("outside", other), ("outside", template.read_bytes()), ("inside", other)):
                for flags in ((), ("--force",)):
                    with self.subTest(dest=str(rel), target=target, same=content == template.read_bytes(), flags=flags), \
                            tempfile.TemporaryDirectory() as side, tempfile.TemporaryDirectory() as repo:
                        linked = Path(repo) / rel
                        linked.parent.mkdir(parents=True, exist_ok=True)
                        real = (Path(side) if target == "outside" else Path(repo)) / "linked-target.txt"
                        real.write_bytes(content)
                        linked.symlink_to(real)
                        proc = install(repo, *flags, *extra)
                        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                        self.assertIn("refusing to write", proc.stderr)
                        self.assertIn("symlink", proc.stderr)
                        self.assertEqual(real.read_bytes(), content)
                        self.assertTrue(linked.is_symlink())

    def test_a_dangling_symlinked_destination_is_not_written_through(self):
        for flags in ((), ("--force",)):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as side, tempfile.TemporaryDirectory() as repo:
                outside = Path(side) / "not-yet.yml"
                linked = Path(repo) / ".github" / "workflows" / "review-gate.yml"
                linked.parent.mkdir(parents=True)
                linked.symlink_to(outside)
                proc = install(repo, *flags)
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertFalse(outside.exists())

    def test_a_symlinked_parent_directory_is_refused_and_nothing_lands_outside(self):
        for parent in (Path("scripts"), Path(".github")):
            for flags in ((), ("--force",)):
                with self.subTest(parent=str(parent), flags=flags), \
                        tempfile.TemporaryDirectory() as side, tempfile.TemporaryDirectory() as repo:
                    (Path(repo) / parent).symlink_to(side)
                    proc = install(repo, *flags)
                    self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                    self.assertIn("refusing to write", proc.stderr)
                    self.assertEqual(list(Path(side).iterdir()), [])

    def test_a_vendored_copy_symlinked_to_the_running_skill_is_refused_and_the_skill_is_untouched(self):
        # 3.2.21: dest.resolve() == skill_root returned True before the symlink check, so this reported success
        before = tree(SKILL)
        for flags in ((), ("--force",)):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as repo:
                (Path(repo) / ".claude" / "skills").mkdir(parents=True)
                link = Path(repo) / ".claude" / "skills" / "review-gate"
                link.symlink_to(SKILL)
                proc = install(repo, *flags)
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn("refusing to replace", proc.stderr)
                self.assertTrue(link.is_symlink())
                self.assertEqual(tree(SKILL), before)

    def test_real_files_still_install_and_a_forced_reinstall_stays_real(self):
        with tempfile.TemporaryDirectory() as repo:
            for flags in ((), ("--force",), ("--force", "--doctor-job")):
                proc = install(repo, *flags)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            for rel, _ in self.DESTINATIONS:
                self.assertTrue((Path(repo) / rel).is_file() and not (Path(repo) / rel).is_symlink(), rel)

    def test_an_installer_run_from_its_own_vendored_copy_still_installs(self):
        # the equal-to-skill-root early return survives, now behind the symlink check: a REAL vendored directory
        with tempfile.TemporaryDirectory() as repo:
            vendor(repo)
            vendored_installer = Path(repo) / ".claude" / "skills" / "review-gate" / "scripts" / "install-workflow.py"
            before = tree(vendored_installer.parents[1])
            proc = subprocess.run([sys.executable, str(vendored_installer), "--force"], cwd=repo,
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(tree(vendored_installer.parents[1]), before)
            self.assertTrue((Path(repo) / ".github" / "workflows" / "review-gate.yml").is_file())


class DoctorVersionParity(unittest.TestCase):
    """3.2.19: doctor FAILS when the vendored skill is older than the release it runs from."""

    def no_gh(self):
        self._path = tempfile.TemporaryDirectory()
        self.addCleanup(self._path.cleanup)
        return {**os.environ, "PATH": self._path.name}

    def test_vendored_copy_one_release_behind_fails_without_strict_and_prints_the_fix(self):
        with tempfile.TemporaryDirectory() as repo:
            old = one_release_behind(skill_version(SKILL))
            vendor(repo, old)
            install(repo)
            proc, _ = doctor_script_lines(repo, self.no_gh())
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn(f"FAIL .claude/skills/review-gate is {old}, this release is {skill_version(SKILL)}", proc.stdout)
            self.assertIn(f"python3 {SKILL / 'scripts' / 'install-workflow.py'} --force", proc.stdout)

    def test_hooks_json_disagreeing_with_skill_md_fails(self):
        with tempfile.TemporaryDirectory() as repo:
            dest = vendor(repo)
            hooks = dest / "hooks.json"
            hooks.write_text(hooks.read_text().replace(skill_version(SKILL), one_release_behind(skill_version(SKILL)), 1))
            install(repo)
            proc, _ = doctor_script_lines(repo, self.no_gh())
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("FAIL .claude/skills/review-gate/hooks.json", proc.stdout)

    def test_unparseable_vendored_version_fails_naming_it_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as repo:
            vendor(repo, "3..20")
            install(repo)
            proc, _ = doctor_script_lines(repo, self.no_gh())
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("FAIL unparseable version '3..20'", proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)

    def test_current_vendored_copy_passes(self):
        with tempfile.TemporaryDirectory() as repo:
            vendor(repo)
            install(repo)
            proc, _ = doctor_script_lines(repo, self.no_gh(), "--strict")
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn(f"OK vendored skill .claude/skills/review-gate {skill_version(SKILL)}", proc.stdout)

    def test_doctor_names_the_rerun_command(self):
        with tempfile.TemporaryDirectory() as repo:
            install(repo)
            proc, _ = doctor_script_lines(repo, self.no_gh())
            self.assertIn("does not re-run when a thread is resolved or a review lands", proc.stdout)
            self.assertIn("gh pr edit <n> --remove-label review:high && gh pr edit <n> --add-label review:high",
                          proc.stdout)


class PublicRepoRunbook(unittest.TestCase):
    """3.2.19: installing into a PUBLIC repo prints the Actions-policy runbook (Dec 2, 2026)."""

    def install_with_gh(self, visibility):
        stub_dir = tempfile.TemporaryDirectory()
        self.addCleanup(stub_dir.cleanup)
        gh = Path(stub_dir.name) / "gh"  # third-party CLI stub: answers `gh repo view --json visibility`
        gh.write_text(f"#!/bin/sh\necho {visibility}\n")
        gh.chmod(0o755)
        repo = tempfile.TemporaryDirectory()
        self.addCleanup(repo.cleanup)
        env = {**os.environ, "PATH": f"{stub_dir.name}:{os.environ['PATH']}"}
        return subprocess.run([sys.executable, str(INSTALLER)], cwd=repo.name, capture_output=True, text=True, env=env)

    def test_public_repo_prints_the_allowlist_runbook(self):
        out = self.install_with_gh("PUBLIC").stdout
        self.assertIn("PUBLIC repo", out)
        self.assertIn("pull_request_target", out)
        self.assertIn(".github/workflows/review-gate.yml", out)
        self.assertIn("<owner>/<repo>", out)
        self.assertIn("Review Gate - PR #<n>", out)

    def test_private_repo_prints_no_runbook(self):
        self.assertNotIn("PUBLIC repo", self.install_with_gh("PRIVATE").stdout)


if __name__ == "__main__":
    unittest.main()
