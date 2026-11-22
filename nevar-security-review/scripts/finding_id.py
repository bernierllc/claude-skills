#!/usr/bin/env python3
"""Print a stable finding id: NSR-<CATEGORY>-<8 hex>.

Usage: finding_id.py <category> <repo-relative path> <route-or-symbol>

The id hashes category, normalized path and symbol, never line numbers, so it survives
edits that move code. Same inputs always give the same id.
"""
import hashlib
import re
import sys

CATEGORY = re.compile(r"^[A-Z][A-Z0-9]{1,15}$")


def finding_id(category: str, path: str, symbol: str) -> str:
    category = category.strip().upper()
    if not CATEGORY.match(category):
        raise ValueError(f"category must be 2-16 letters/digits, got {category!r}")
    path = path.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or path.startswith("/") or ".." in path.split("/"):
        raise ValueError(f"path must be repo-relative, got {path!r}")
    symbol = symbol.strip()
    if not symbol:
        raise ValueError("symbol must not be empty")
    digest = hashlib.sha256(f"{category}\0{path}\0{symbol}".encode()).hexdigest()[:8]
    return f"NSR-{category}-{digest}"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    try:
        print(finding_id(*argv))
    except ValueError as exc:
        print(f"finding_id: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
