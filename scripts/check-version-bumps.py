#!/usr/bin/env python3
"""Fail when a skill changed but its SKILL.md version did not go up.

Usage: check-version-bumps.py [BASE_REF]   (default: origin/main)

A skill is the deepest directory containing a SKILL.md. Any change inside it
counts, not just SKILL.md: `aec` installs the whole directory and upgrades on
the frontmatter version, so an unbumped change to a reference file or script
never reaches installed copies.

Skills are matched to BASE_REF by their frontmatter `name:` (what `aec` and
skills-manifest.json key on), not by path, so a moved or renamed directory is
still compared against its old version however much it was rewritten. A name
absent at BASE_REF is a new skill and is skipped; deleted skills are skipped.

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

    base_versions: dict[str, str | None] = {}
    for p in skill_mds(nul_split(git("ls-tree", "-r", "-z", "--name-only", base))):
        text = git("show", f"{base}:{p}")
        name = frontmatter_field(text, "name")
        if name:
            base_versions[name] = frontmatter_version(text)

    failures = []
    for skill_dir, files in sorted(touched.items()):
        head_text = git("show", f"HEAD:{skill_dir}/SKILL.md")
        name = frontmatter_field(head_text, "name")
        if name is None:
            failures.append(f"  {skill_dir}: SKILL.md has no frontmatter name")
            continue
        if name not in base_versions:
            continue  # new skill
        old, new = base_versions[name], frontmatter_version(head_text)
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
            failures.append(f"  {skill_dir} ({name}): changed ({shown}) but version stayed {old} -> {new}")

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
