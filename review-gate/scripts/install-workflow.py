#!/usr/bin/env python3
"""Copy templates/review-gate.yml into the current repo's .github/workflows/."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    src = skill_root / "templates" / "review-gate.yml"
    if not src.is_file():
        print(f"missing template: {src}", file=sys.stderr)
        return 1
    dest_dir = Path.cwd() / ".github" / "workflows"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "review-gate.yml"
    if dest.exists() and "--force" not in sys.argv:
        print(f"already exists: {dest} (pass --force to overwrite)")
        return 0
    shutil.copy2(src, dest)
    print(f"wrote {dest}")
    print("Next: add 'Review Gate' as a required status check on staging/main rulesets.")
    print("Doctor: python3", skill_root / "scripts" / "doctor-review-gate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
