#!/usr/bin/env python3
"""Verify each hooks.json version matches its sibling SKILL.md version.

Exits non-zero (and prints a list of mismatches) if any skill that has a
hooks.json file disagrees with its SKILL.md frontmatter version.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTMATTER_VERSION_RE = re.compile(r"^version:\s*['\"]?([^'\"\s]+)['\"]?\s*$", re.MULTILINE)


def skill_version(skill_md: Path) -> str | None:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    frontmatter = text[3:end]
    m = FRONTMATTER_VERSION_RE.search(frontmatter)
    return m.group(1) if m else None


def hooks_version(hooks_json: Path) -> str | None:
    data = json.loads(hooks_json.read_text(encoding="utf-8"))
    v = data.get("version")
    return str(v) if v is not None else None


def main() -> int:
    mismatches: list[str] = []
    missing: list[str] = []

    for hooks_path in REPO_ROOT.rglob("hooks.json"):
        if any(part in {".git", "node_modules"} for part in hooks_path.parts):
            continue
        skill_path = hooks_path.with_name("SKILL.md")
        if not skill_path.exists():
            continue

        try:
            hv = hooks_version(hooks_path)
        except json.JSONDecodeError as exc:
            missing.append(f"{hooks_path.relative_to(REPO_ROOT)}: invalid JSON ({exc})")
            continue
        sv = skill_version(skill_path)

        if hv is None:
            missing.append(f"{hooks_path.relative_to(REPO_ROOT)}: no 'version' field")
            continue
        if sv is None:
            missing.append(f"{skill_path.relative_to(REPO_ROOT)}: no 'version' in frontmatter")
            continue
        if hv != sv:
            mismatches.append(
                f"{skill_path.parent.relative_to(REPO_ROOT)}: "
                f"SKILL.md={sv}  hooks.json={hv}"
            )

    if not mismatches and not missing:
        return 0

    print("Hook/skill version check failed:", file=sys.stderr)
    for m in mismatches:
        print(f"  mismatch: {m}", file=sys.stderr)
    for m in missing:
        print(f"  error:    {m}", file=sys.stderr)
    print(
        "\nBump SKILL.md and hooks.json together so both `version` fields match.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
