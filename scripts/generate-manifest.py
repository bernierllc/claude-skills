#!/usr/bin/env python3
"""Walk all skill directories, read SKILL.md frontmatter, and output skills-manifest.json."""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_frontmatter(filepath: Path) -> dict | None:
    """Extract YAML frontmatter from a SKILL.md file."""
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None

    frontmatter = {}
    for line in match.group(1).splitlines():
        # Simple key: value parser (handles quoted and unquoted values)
        kv = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if kv:
            key = kv.group(1)
            value = kv.group(2).strip()
            # Strip surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            frontmatter[key] = value
    return frontmatter


def main():
    repo_root = Path(__file__).resolve().parent.parent
    skills = {}

    for skill_md in sorted(repo_root.rglob("SKILL.md")):
        fm = parse_frontmatter(skill_md)
        if fm and "name" in fm:
            entry = {
                "version": fm.get("version", "0.0.0"),
                "description": fm.get("description", ""),
            }
            if "author" in fm:
                entry["author"] = fm["author"]
            skills[fm["name"]] = entry

    manifest = {
        "manifestVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "skills": skills,
    }

    output_path = repo_root / "skills-manifest.json"
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output_path} with {len(skills)} skills")


if __name__ == "__main__":
    main()
