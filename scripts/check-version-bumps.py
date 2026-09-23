#!/usr/bin/env python3
"""Fail when a skill changed but its SKILL.md version did not go up.

Usage: check-version-bumps.py [BASE_REF]   (default: origin/main)

A skill is the deepest directory containing a SKILL.md. Any change inside it
counts, not just SKILL.md: `aec` installs the whole directory and upgrades on
the frontmatter version, so an unbumped change to a reference file or script
never reaches installed copies. New skills (no SKILL.md at BASE_REF) and
deleted skills are skipped. A renamed or moved skill is compared against its
old path, so a move is not mistaken for a new skill.

Runs against the git repo containing the current working directory.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath

from frontmatter import frontmatter_version


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    # -z: NUL-separated, so paths with spaces survive. Each entry is a status
    # followed by one path, or two (old, new) for renames and copies.
    fields = git("diff", "--name-status", "-M", "-z", f"{base}...HEAD").split("\0")[:-1]
    changed: list[PurePosixPath] = []
    renamed_from: dict[str, str] = {}  # new path -> old path
    i = 0
    while i < len(fields):
        status = fields[i]
        if status[0] in "RC":
            old, new = fields[i + 1], fields[i + 2]
            renamed_from[new] = old
            changed.append(PurePosixPath(new))
            i += 3
        else:
            changed.append(PurePosixPath(fields[i + 1]))
            i += 2

    skill_dirs = sorted(
        (p.parent for p in map(PurePosixPath, git("ls-files", "-z", "*SKILL.md").split("\0"))
         if p.name == "SKILL.md" and p.parent != PurePosixPath(".")),
        key=lambda d: len(d.parts),
        reverse=True,  # deepest first, so nested skills win
    )

    touched: dict[PurePosixPath, list[str]] = {}
    for path in changed:
        owner = next((d for d in skill_dirs if d in path.parents), None)
        if owner is not None:
            touched.setdefault(owner, []).append(str(path))

    failures = []
    for skill_dir, files in sorted(touched.items()):
        skill_md = f"{skill_dir}/SKILL.md"
        try:
            base_text = git("show", f"{base}:{renamed_from.get(skill_md, skill_md)}")
        except subprocess.CalledProcessError:
            continue  # new skill
        head_text = git("show", f"HEAD:{skill_md}")
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
