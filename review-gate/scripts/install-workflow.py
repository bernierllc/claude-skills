#!/usr/bin/env python3
"""Copy the review-gate workflow + trusted checker into the current repo."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# Vendored byte-identical from agents-environment-config. A differing repo copy is replaced (with
# --force) only when it is a known older aec version; a newer or custom one is KEPT.
VENDORED = "check-forged-gate-names.py"
# sha256 of every aec scripts/check-forged-gate-names.py before dba592db (aec #154). 7dff1b48 is
# aec 46580fa/7561972, the copy review-gate 3.2.0/3.2.1 bundled. Add the old hash on each re-vendor.
KNOWN_OLD = frozenset({
    "7dff1b48f058d0e1d6a0089e0376b768ce44d276a5929a9eb2e1b166d1c32f74",  # aec 46580fa, 7561972
    "f71a599eba2d177c59ac5990a6291475eb48cb2cb6dba730327ba70ed7c5d2db",  # aec b84feda
    "6524947e719fc820bf371527880cab689c65fe71fe84108e1a4e88e3a8c97330",  # aec 9abcdae
    "f4b52a7ed9e44a6921ed17dcc8c99076f0baf4734d7f42879c72cff0abdb4932",  # aec bd3b923
    "38ff18b9ea81d5d952ff7a040207f57308d0610d1882489a8e522e9cd76efcb7",  # aec aa2bbb3
    "9c9bb27b42012952bfb74f82f17e804bf49b6afdc0a21b7d5471513a200438f5",  # aec a9be4dd
    "33315bb0adb6e535ff98ee7105e3fe91fec9797a7d67446c634ab94c814163ce",  # aec 5054ef7
    "06cae65f3e93f2bca211ed248969392d07331a2cd396084d4481ceea56117c65",  # aec dba592db, review-gate 3.2.2/3.2.3
})


# Every script copied into a repo's scripts/. doctor-review-gate.py reads this tuple, so the two cannot drift.
# The workflow loads the first three from the default branch. lint-review-body.py is for authors (it imports
# the checker beside it); the workflow never runs it.
VENDORED_SCRIPTS = ("check-review-gate.py", "check-forged-gate-names.py", "check-forged-review-gate.py",
                    "lint-review-body.py")


WRAPPER = "check-forged-review-gate.py"
# What the bundled wrapper calls on the detector. Checked by parsing, never by running: the
# installer runs on a developer machine and must not execute repo code (#105 Codex P1).
WRAPPER_FUNCS = {"forged": 3, "_gh_run_lookup": 1, "_load_check_runs": 1}  # name -> positional args used


def _detector_compatible(path: Path) -> bool:
    """True when the detector defines what the bundled wrapper calls, with call-compatible
    signatures, and a PROTECTED dict literal with a non-empty `Review Gate` entry."""
    try:
        tree = ast.parse(path.read_bytes())
    except (SyntaxError, ValueError):
        return False
    funcs, protected = {}, None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            funcs[node.name] = node.args
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PROTECTED" for t in node.targets):
            protected = node.value
    for name, used in WRAPPER_FUNCS.items():
        args = funcs.get(name)
        if args is None:
            return False
        if any(d is None for d in args.kw_defaults):
            return False  # a required keyword-only arg the wrapper never passes
        positional = args.posonlyargs + args.args
        required = len(positional) - len(args.defaults)
        if not (required <= used <= len(positional) or (args.vararg and required <= used)):
            return False
    if not isinstance(protected, ast.Dict):
        return False
    entry = next((v for k, v in zip(protected.keys, protected.values)
                  if isinstance(k, ast.Constant) and k.value == "Review Gate"), None)
    return isinstance(entry, ast.Set) and bool(entry.elts)


def keeps_detector(dest: Path) -> bool:
    """True when dest, a detector differing from this skill's, is one --force keeps (newer or custom aec copy)."""
    return hashlib.sha256(dest.read_bytes()).hexdigest() not in KNOWN_OLD and _detector_compatible(dest)


def _backup(dest: Path) -> Path:
    """Save dest beside itself under a name no earlier backup holds (never overwrites one)."""
    data = dest.read_bytes()
    for n in range(1000):
        backup = dest.with_name(dest.name + (".custom.bak" if n == 0 else f".custom.{n}.bak"))
        try:
            with open(backup, "xb") as out:
                out.write(data)
            return backup
        except FileExistsError:
            continue
    raise SystemExit(f"error: 1000 backups of {dest} already exist; clean them up first")


def _copy(src: Path, dest: Path, force: bool) -> bool:
    """Return True if written. Skip existing unless force; never replace a newer or custom vendored detector."""
    if dest.is_file() and dest.read_bytes() == src.read_bytes():
        print(f"unchanged: {dest}")
        return False
    if src.name == VENDORED and dest.is_file() and keeps_detector(dest):
        print(f"KEPT {dest}: it differs from this skill's copy (vendored from aec) and is not a known "
              f"older version, so it was not overwritten. If yours is older, copy scripts/{VENDORED} "
              "from the newest agents-environment-config by hand.", file=sys.stderr)
        return False
    if src.name == VENDORED and dest.is_file() and force and not _detector_compatible(dest):
        backup = _backup(dest)
        print(f"REPLACED {dest}: the bundled {WRAPPER} cannot run against it; your copy is saved as {backup}.",
              file=sys.stderr)
    elif dest.exists() and not force:
        print(f"already exists: {dest} (pass --force to overwrite)")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"wrote {dest}")
    return True


VENDORED_SKILL = Path(".claude") / "skills" / "review-gate"  # a repo-tracked copy of this skill (aec project install)


def skill_version(skill_dir: Path) -> tuple[int, ...] | None:
    """The SKILL.md frontmatter version as an int tuple; None when SKILL.md or its version line is missing.
    Raises ValueError for anything but dotted digits (a prerelease, `3..20`): unknown is never "older"."""
    try:
        m = re.search(r"\A---\n(?:.*\n)*?version:[ \t]*(.*?)[ \t]*\n", (skill_dir / "SKILL.md").read_text())
    except OSError:
        return None
    if m and not re.fullmatch(r"\d+(\.\d+)*", m.group(1)):
        raise ValueError(f"unparseable version {m.group(1)!r} in {skill_dir / 'SKILL.md'}")
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def hooks_version(skill_dir: Path) -> str:
    try:
        return str(json.loads((skill_dir / "hooks.json").read_text()).get("version"))
    except (OSError, ValueError, AttributeError) as e:
        return f"unreadable ({e})"


def dotted(version: tuple[int, ...] | None) -> str:
    return ".".join(map(str, version)) if version else "unknown"


def _replace_problem(skill_root: Path, root: Path, dest: Path) -> str | None:
    """Why `dest` may not be deleted, mirroring aec's install chokepoint (aec/lib/filesystem.py
    check_install_paths + confine.escapes, and remove_installed_item's never-delete-the-source guard): no
    symlink from below the repo root down to dest (stricter than aec for dest itself: a vendored copy is a
    tracked directory, so a link there is refused, not replaced), dest inside the repo, no source overlap."""
    node = root
    for part in dest.relative_to(root).parts:
        node = node / part
        if node.is_symlink():
            return f"{node} is a symlink, so the copy it reaches is not this repo's"
    real, src = dest.resolve(), skill_root.resolve()
    if root.resolve() not in real.parents:
        return f"{real} is outside {root.resolve()}"
    if src in real.parents or real in src.parents:
        return f"it overlaps this installer's own skill at {src}"
    return None


def refresh_vendored_skill(skill_root: Path, root: Path, force: bool) -> bool:
    """Replace an OLDER repo-tracked copy of this skill as one unit, the way `aec install skill` does, so no
    file from an old release is left beside new ones. The old tree is moved aside only once the complete new
    one exists, and is restored if the swap fails; a run cut off mid-swap is undone by the next run. False (with
    the reason on stderr) when it refused or failed."""
    dest = root / VENDORED_SKILL
    backup = dest.with_name(dest.name + ".old")  # a fixed name, so the next run finds a swap that was cut off
    if backup.exists() or backup.is_symlink():
        problem = "it is a symlink" if backup.is_symlink() else _replace_problem(skill_root, root, dest)
        if problem or dest.exists() or dest.is_symlink():
            # refuse rather than delete: fewer lines than a guarded delete, and it may hold the only local edits
            print(f"error: {backup} is left from an earlier refresh{f' ({problem})' if problem else ''}; keep the "
                  f"right copy at {dest}, delete the other, then rerun. Nothing was changed.", file=sys.stderr)
            return False
        backup.rename(dest)
        print(f"recovered {dest} from {backup}, left by an interrupted refresh")
    if not dest.is_dir() or dest.resolve() == skill_root:
        return True
    try:
        have, want = skill_version(dest), skill_version(skill_root)
    except ValueError as e:
        print(f"error: {e}; not replacing {dest}. Fix the version line or replace the copy by hand.", file=sys.stderr)
        return False
    if want is None or have is None:
        print(f"error: cannot read the version of {dest if have is None else skill_root}; not replacing it",
              file=sys.stderr)
        return False
    if have > want or (have == want and hooks_version(dest) == dotted(have)):
        return True  # current or newer: never downgrade a copy someone vendored on purpose
    if not force:
        print(f"stale: {VENDORED_SKILL} is {dotted(have)} (hooks.json {hooks_version(dest)}), this release is "
              f"{dotted(want)}; pass --force to replace the whole directory")
        return True
    # Check-then-use: valid for a trusted, static filesystem under the repo root. The staging and backup names
    # below are fixed siblings of this confined dest, so they are covered by the same check.
    problem = _replace_problem(skill_root, root, dest)
    if problem:
        print(f"error: refusing to replace {dest}: {problem}. Nothing was deleted.", file=sys.stderr)
        return False
    new = Path(tempfile.mkdtemp(prefix=f".{dest.name}.new-", dir=dest.parent))
    try:
        shutil.copytree(skill_root, new, ignore=shutil.ignore_patterns(".*", "__pycache__"), dirs_exist_ok=True)
    except (OSError, shutil.Error) as e:
        shutil.rmtree(new, ignore_errors=True)  # our own partial temp copy; the old tree was never touched
        print(f"error: could not copy {skill_root} ({e}); {dest} is unchanged", file=sys.stderr)
        return False
    try:
        dest.rename(backup)
    except OSError as e:
        shutil.rmtree(new, ignore_errors=True)  # our own temp copy; dest was never moved
        print(f"error: could not move {dest} aside ({e}); it is unchanged", file=sys.stderr)
        return False
    try:
        new.rename(dest)
    except OSError as e:
        shutil.rmtree(new, ignore_errors=True)  # our own temp copy
        try:
            backup.rename(dest)
        except OSError as e2:
            print(f"error: could not swap in the new copy ({e}) or move the old one back ({e2}); {dest} is ABSENT and "
                  f"the old copy is at {backup}. Restore it: mv {shlex.quote(str(backup))} {shlex.quote(str(dest))} "
                  "(the next run of this installer also does that)", file=sys.stderr)
            return False
        print(f"error: could not swap in the new copy ({e}); {dest} is unchanged", file=sys.stderr)
        return False
    try:
        shutil.rmtree(backup)
    except OSError as e:
        print(f"refreshed {dest}, but the old copy is kept at {backup} ({e}); delete it before committing",
              file=sys.stderr)
    print(f"refreshed {dest} ({dotted(have)} -> {dotted(want)}); commit the whole directory")
    return True


PUBLIC_RUNBOOK = """\
PUBLIC repo: GitHub's Actions event policy (Dec 2, 2026) blocks pull_request_target in public repos by
default, and Review Gate runs on pull_request_target. Before requiring it:
  1. In the org or repo Actions policy (Settings > Actions), allow .github/workflows/review-gate.yml to
     run on pull_request_target for <owner>/<repo>.
  2. Open a test PR and confirm a 'Review Gate - PR #<n>' run appears.
  3. Only then add 'Review Gate' as a required status check."""


def repo_visibility(root: Path) -> str | None:
    """PUBLIC / PRIVATE / INTERNAL from gh, or None when gh is missing or cannot tell."""
    if shutil.which("gh") is None:
        return None
    try:
        out = subprocess.run(["gh", "repo", "view", "--json", "visibility", "-q", ".visibility"], cwd=root,
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"could not read repo visibility ({e})", file=sys.stderr)
        return None
    return out.stdout.strip().upper() or None if out.returncode == 0 else None


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    force = "--force" in sys.argv
    workflow_src = skill_root / "templates" / "review-gate.yml"
    doctor_src = skill_root / "templates" / "review-gate-doctor.yml"
    script_srcs = [skill_root / "scripts" / name for name in VENDORED_SCRIPTS]
    for src in (workflow_src, doctor_src, *script_srcs):
        if not src.is_file():
            print(f"missing: {src}", file=sys.stderr)
            return 1

    root = Path.cwd()
    detector = root / "scripts" / VENDORED
    if (not force and detector.is_file() and detector.read_bytes() != (skill_root / "scripts" / VENDORED).read_bytes()
            and not _detector_compatible(detector)):
        # refuse before writing anything: an upgraded wrapper beside this detector fails every gate run
        print(f"error: the bundled {WRAPPER} cannot run against {detector}. Rerun with --force to replace it "
              "(your copy is backed up), or update it from the newest agents-environment-config.",
              file=sys.stderr)
        return 1
    if not refresh_vendored_skill(skill_root, root, force):
        return 1
    _copy(workflow_src, root / ".github" / "workflows" / "review-gate.yml", force)
    # Scripts must live on the default branch; the workflow loads only that ref.
    for src in script_srcs:
        _copy(src, root / "scripts" / src.name, force)
    if "--doctor-job" in sys.argv:  # opt-in CI drift check; not a required check (see the template header)
        _copy(doctor_src, root / ".github" / "workflows" / "review-gate-doctor.yml", force)
    visibility = repo_visibility(root)
    if visibility == "PUBLIC":
        print(PUBLIC_RUNBOOK)
    elif visibility is None:
        print("Could not read this repo's visibility with gh. If it is public:\n" + PUBLIC_RUNBOOK)
    print("Next: add 'Review Gate' as a required status check on staging/main rulesets.")
    print("Doctor: python3", skill_root / "scripts" / "doctor-review-gate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
