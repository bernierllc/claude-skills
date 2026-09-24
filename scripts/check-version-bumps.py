#!/usr/bin/env python3
"""Fail when a skill changed but its SKILL.md version did not go up.

Usage: check-version-bumps.py [BASE_REF]   (default: origin/main)

A skill is the deepest directory containing a SKILL.md. Any change inside it
counts, not just SKILL.md: `aec` installs the whole directory and upgrades on
the frontmatter version, so an unbumped change to a reference file or script
never reaches installed copies.

Matching a changed skill to its BASE_REF version:
  1. Same path — the directory's SKILL.md existed at BASE_REF. Covers edits and
     `name:` changes.
  2. Moved — no SKILL.md at that path on BASE_REF: match by frontmatter `name:`
     against base skills whose directory is gone at HEAD. Name, not git rename
     detection, so a move plus a large rewrite is still caught. More than one
     candidate fails as ambiguous; none means a new skill, which is skipped.
Deleted skills are skipped.

Runs against the git repo containing the current working directory.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath

from frontmatter import frontmatter_field, frontmatter_version


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def nul_split(out: str) -> list[str]:
    # -z output: NUL-separated, so paths with spaces survive.
    return [p for p in out.split("\0") if p]


def skill_mds(paths: list[str]) -> list[PurePosixPath]:
    return [p for p in map(PurePosixPath, paths) if p.name == "SKILL.md" and p.parent != PurePosixPath(".")]


def parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    changed = map(PurePosixPath, nul_split(git("diff", "--name-only", "--no-renames", "-z", f"{base}...HEAD")))

    # Deepest first, so nested skills own their files.
    skill_dirs = sorted(
        (p.parent for p in skill_mds(nul_split(git("ls-files", "-z", "*SKILL.md")))),
        key=lambda d: len(d.parts),
        reverse=True,
    )
    touched: dict[PurePosixPath, list[str]] = {}
    for path in changed:
        owner = next((d for d in skill_dirs if d in path.parents), None)
        if owner is not None:
            touched.setdefault(owner, []).append(str(path))
    if not touched:
        print(f"Version bumps OK (0 changed skill(s) vs {base})")
        return 0

    head_dirs = set(skill_dirs)
    base_skills: dict[PurePosixPath, str] = {
        p.parent: git("show", f"{base}:{p}")
        for p in skill_mds(nul_split(git("ls-tree", "-r", "-z", "--name-only", base)))
    }

    failures = []
    for skill_dir, files in sorted(touched.items()):
        head_text = git("show", f"HEAD:{skill_dir}/SKILL.md")
        name = frontmatter_field(head_text, "name")
        if skill_dir in base_skills:
            base_text = base_skills[skill_dir]
        else:
            moved_from = [
                d for d, text in base_skills.items()
                if d not in head_dirs and name is not None and frontmatter_field(text, "name") == name
            ]
            if len(moved_from) > 1:
                shown = ", ".join(map(str, sorted(moved_from)))
                failures.append(f"  {skill_dir} ({name}): moved from an ambiguous source ({shown})")
                continue
            if not moved_from:
                continue  # new skill
            base_text = base_skills[moved_from[0]]
        old, new = frontmatter_version(base_text), frontmatter_version(head_text)
        if old is None or new is None:
            failures.append(f"  {skill_dir}: no frontmatter version (base={old}, head={new})")
            continue
        try:
            bumped = parse(new) > parse(old)
        except ValueError:
            failures.append(f"  {skill_dir}: unparseable version (base={old}, head={new})")
            continue
        if not bumped:
            shown = ", ".join(files[:3]) + (f" (+{len(files) - 3} more)" if len(files) > 3 else "")
            failures.append(f"  {skill_dir}: changed ({shown}) but version stayed {old} -> {new}")

    if failures:
        print("Skills changed without a version bump:")
        print("\n".join(failures))
        print("\nBump `version:` in each SKILL.md (patch/minor/major per CLAUDE.md), then run")
        print("scripts/generate-manifest.py and commit both.")
        return 1
    print(f"Version bumps OK ({len(touched)} changed skill(s) vs {base})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
