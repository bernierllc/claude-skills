#!/usr/bin/env python3
"""
Route scanner for Next.js App Router projects.

Walks the app/ directory and produces a JSON manifest of all routes,
including metadata about layouts, error boundaries, loading states,
and dynamic segments.

Usage:
    python3 route-scanner.py [app_dir]

    app_dir: Path to the app/ directory (default: ./app)

Output:
    JSON array of route objects to stdout.
"""

import json
import os
import re
import sys
from pathlib import Path


# Next.js App Router conventions
PAGE_FILES = {"page.tsx", "page.ts", "page.jsx", "page.js"}
LAYOUT_FILES = {"layout.tsx", "layout.ts", "layout.jsx", "layout.js"}
ERROR_FILES = {"error.tsx", "error.ts", "error.jsx", "error.js"}
LOADING_FILES = {"loading.tsx", "loading.ts", "loading.jsx", "loading.js"}
NOT_FOUND_FILES = {"not-found.tsx", "not-found.ts", "not-found.jsx", "not-found.js"}
API_FILES = {"route.tsx", "route.ts", "route.jsx", "route.js"}

# Pattern for dynamic segments: [param], [...param], [[...param]]
DYNAMIC_SEGMENT = re.compile(r"\[(?:\.\.\.)?(\w+)\]")
CATCH_ALL = re.compile(r"\[\.\.\.(\w+)\]")
OPTIONAL_CATCH_ALL = re.compile(r"\[\[\.\.\.(\w+)\]\]")

# Route groups: (groupName) — no URL segment
ROUTE_GROUP = re.compile(r"^\(.*\)$")


def dir_to_url_segment(dirname: str) -> str | None:
    """Convert a directory name to a URL segment.

    Returns None for route groups (parenthesized names).
    """
    if ROUTE_GROUP.match(dirname):
        return None  # Route group — no URL segment
    return dirname


def find_file_in_set(directory: Path, file_set: set[str]) -> str | None:
    """Find the first matching file from a set in a directory."""
    for fname in file_set:
        fpath = directory / fname
        if fpath.exists():
            return str(fpath)
    return None


def find_nearest_ancestor_file(
    directory: Path, app_root: Path, file_set: set[str]
) -> str | None:
    """Walk up from directory to app_root looking for a file."""
    current = directory
    while current >= app_root:
        result = find_file_in_set(current, file_set)
        if result:
            return result
        current = current.parent
    return None


def extract_dynamic_segments(url_path: str) -> list[dict]:
    """Extract dynamic segment info from a URL path."""
    segments = []
    for part in url_path.split("/"):
        if OPTIONAL_CATCH_ALL.match(part):
            segments.append(
                {"name": OPTIONAL_CATCH_ALL.match(part).group(1),
                 "type": "optional-catch-all"}
            )
        elif CATCH_ALL.match(part):
            segments.append(
                {"name": CATCH_ALL.match(part).group(1),
                 "type": "catch-all"}
            )
        elif DYNAMIC_SEGMENT.match(part):
            segments.append(
                {"name": DYNAMIC_SEGMENT.match(part).group(1),
                 "type": "dynamic"}
            )
    return segments


def extract_api_methods(filepath: str) -> list[str]:
    """Extract exported HTTP methods from an API route file."""
    methods = []
    try:
        with open(filepath, "r") as f:
            content = f.read()
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
            # Match: export async function GET, export function GET,
            #        export const GET
            if re.search(
                rf"export\s+(?:async\s+)?(?:function|const)\s+{method}\b", content
            ):
                methods.append(method)
    except (IOError, UnicodeDecodeError):
        pass
    return methods


def scan_routes(app_dir: str) -> list[dict]:
    """Scan an app/ directory and return route manifests."""
    app_root = Path(app_dir).resolve()
    if not app_root.is_dir():
        print(f"Error: {app_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    routes = []

    for dirpath_str, dirnames, filenames in os.walk(app_root):
        dirpath = Path(dirpath_str)

        # Skip hidden directories and node_modules
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d != "node_modules" and d != "__tests__"
        ]

        # Check for page files (UI routes)
        page_file = find_file_in_set(dirpath, PAGE_FILES)
        if page_file:
            # Build URL path
            rel = dirpath.relative_to(app_root)
            segments = []
            for part in rel.parts:
                url_seg = dir_to_url_segment(part)
                if url_seg is not None:
                    segments.append(url_seg)

            url_path = "/" + "/".join(segments) if segments else "/"

            routes.append({
                "type": "page",
                "path": url_path,
                "file": str(Path(page_file).relative_to(app_root.parent)),
                "layout": _relative_or_none(
                    find_nearest_ancestor_file(dirpath, app_root, LAYOUT_FILES),
                    app_root.parent,
                ),
                "error_boundary": _relative_or_none(
                    find_nearest_ancestor_file(dirpath, app_root, ERROR_FILES),
                    app_root.parent,
                ),
                "loading": _relative_or_none(
                    find_file_in_set(dirpath, LOADING_FILES)
                    or find_nearest_ancestor_file(
                        dirpath.parent, app_root, LOADING_FILES
                    ),
                    app_root.parent,
                ),
                "not_found": _relative_or_none(
                    find_file_in_set(dirpath, NOT_FOUND_FILES),
                    app_root.parent,
                ),
                "dynamic_segments": extract_dynamic_segments(url_path),
            })

        # Check for API route files
        api_file = find_file_in_set(dirpath, API_FILES)
        if api_file:
            rel = dirpath.relative_to(app_root)
            segments = []
            for part in rel.parts:
                url_seg = dir_to_url_segment(part)
                if url_seg is not None:
                    segments.append(url_seg)

            url_path = "/" + "/".join(segments) if segments else "/"

            routes.append({
                "type": "api",
                "path": url_path,
                "file": str(Path(api_file).relative_to(app_root.parent)),
                "methods": extract_api_methods(api_file),
                "dynamic_segments": extract_dynamic_segments(url_path),
            })

    # Sort: pages first, then API; alphabetically within each group
    routes.sort(key=lambda r: (0 if r["type"] == "page" else 1, r["path"]))
    return routes


def _relative_or_none(filepath: str | None, base: Path) -> str | None:
    """Convert absolute path to relative, or return None."""
    if filepath is None:
        return None
    try:
        return str(Path(filepath).relative_to(base))
    except ValueError:
        return filepath


def main():
    app_dir = sys.argv[1] if len(sys.argv) > 1 else "./app"
    routes = scan_routes(app_dir)
    print(json.dumps(routes, indent=2))

    # Summary to stderr
    pages = [r for r in routes if r["type"] == "page"]
    apis = [r for r in routes if r["type"] == "api"]
    no_error_boundary = [r for r in pages if r.get("error_boundary") is None]
    no_loading = [r for r in pages if r.get("loading") is None]
    dynamic = [r for r in routes if r.get("dynamic_segments")]

    print(f"\n--- Route Summary ---", file=sys.stderr)
    print(f"Pages: {len(pages)}", file=sys.stderr)
    print(f"API routes: {len(apis)}", file=sys.stderr)
    print(f"Dynamic routes: {len(dynamic)}", file=sys.stderr)
    print(f"Pages without error boundary: {len(no_error_boundary)}", file=sys.stderr)
    print(f"Pages without loading state: {len(no_loading)}", file=sys.stderr)


if __name__ == "__main__":
    main()
