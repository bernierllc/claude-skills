#!/usr/bin/env python3
"""Walk all skill directories, read SKILL.md frontmatter, and output skills-manifest.json.

With --check, write nothing and exit non-zero if the committed manifest's
`skills` block disagrees with the SKILL.md files on disk. `generatedAt` is
deliberately excluded from the comparison — it changes on every run and would
make the check unusable in CI.
"""

import json
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


def build_skills(repo_root: Path) -> dict:
    """Derive the manifest's `skills` block from every SKILL.md on disk."""
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

    return skills


def check(repo_root: Path, output_path: Path) -> int:
    if not output_path.exists():
        print(f"{output_path.name} is missing — run scripts/generate-manifest.py")
        return 1

    on_disk = build_skills(repo_root)
    committed = json.loads(output_path.read_text(encoding="utf-8")).get("skills", {})
    if on_disk == committed:
        print(f"{output_path.name} is up to date ({len(on_disk)} skills)")
        return 0

    for name in sorted(set(on_disk) - set(committed)):
        print(f"  missing from manifest: {name} ({on_disk[name]['version']})")
    for name in sorted(set(committed) - set(on_disk)):
        print(f"  stale manifest entry:  {name}")
    for name in sorted(set(on_disk) & set(committed)):
        if on_disk[name] != committed[name]:
            print(
                f"  drifted: {name} manifest={committed[name]['version']} "
                f"SKILL.md={on_disk[name]['version']}"
            )
    print("\nRun scripts/generate-manifest.py and commit the result.")
    return 1


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    output_path = repo_root / "skills-manifest.json"

    if "--check" in sys.argv[1:]:
        return check(repo_root, output_path)

    skills = build_skills(repo_root)
    manifest = {
        "manifestVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "skills": skills,
    }
    # Literal UTF-8 (descriptions contain em dashes) so regenerating an unchanged
    # tree produces no diff. Skill order follows the sorted SKILL.md paths above.
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {output_path} with {len(skills)} skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
