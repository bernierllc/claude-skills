#!/usr/bin/env python3
"""Fail when README.md's skill list drifts from the SKILL.md files on disk.

Every skill must appear in README.md as a link to its SKILL.md
(`[**name**](path/SKILL.md)`), and every such link must point at a SKILL.md
that exists. Eight skills once shipped without a README entry because nothing
checked this.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from frontmatter import frontmatter_field

LINK = re.compile(r"\[\*\*([\w-]+)\*\*\]\(([^)\s]+)\)")
SKIP = {"node_modules", ".worktrees", ".git"}


def skills_on_disk(root: Path) -> dict[str, str]:
    """name -> SKILL.md path relative to root."""
    out = {}
    for f in sorted(root.rglob("SKILL.md")):
        if SKIP & set(f.relative_to(root).parts):
            continue
        name = frontmatter_field(f.read_text(encoding="utf-8"), "name")
        if name:
            out[name] = f.relative_to(root).as_posix()
    return out


def problems(root: Path) -> list[str]:
    readme = (root / "README.md").read_text(encoding="utf-8")
    linked = {name: path for name, path in LINK.findall(readme)}
    errors = []
    for name, path in skills_on_disk(root).items():
        if name not in linked:
            errors.append(f"{name}: not in README.md; add `[**{name}**]({path})` under its category")
        elif linked[name] != path:
            errors.append(f"{name}: README.md links {linked[name]}, but the skill is at {path}")
    for name, path in linked.items():
        if not (root / path).is_file():
            errors.append(f"{name}: README.md links {path}, which does not exist")
    return errors


def main() -> int:
    errors = problems(Path(__file__).resolve().parent.parent)
    if errors:
        print("README.md skill list is out of date:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    print("README.md lists and links every skill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
