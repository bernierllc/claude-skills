"""Shared SKILL.md frontmatter parsing for the repo's gate scripts."""
from __future__ import annotations

import re

VERSION_RE = re.compile(r"^version:\s*['\"]?([^'\"\s]+)['\"]?\s*$", re.MULTILINE)


def frontmatter_version(text: str) -> str | None:
    """Return the `version:` value from a SKILL.md's leading frontmatter, if any."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    m = VERSION_RE.search(text[3:end])
    return m.group(1) if m else None
