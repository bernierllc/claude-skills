"""Shared SKILL.md frontmatter parsing for the repo's gate scripts."""
from __future__ import annotations

import re


def frontmatter_field(text: str, field: str) -> str | None:
    """Return a scalar field from a SKILL.md's leading frontmatter, if present."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    m = re.search(rf"^{re.escape(field)}:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", text[3:end], re.MULTILINE)
    return m.group(1) if m else None


def frontmatter_version(text: str) -> str | None:
    return frontmatter_field(text, "version")
