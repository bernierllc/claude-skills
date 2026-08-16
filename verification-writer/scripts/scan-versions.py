#!/usr/bin/env python3
"""
scan-versions.py — Deterministic version scanner for verification docs.

Walks docs/verification/, reads YAML frontmatter from page/flow/shared docs,
and reports which version of verification-writer produced each one. Uses an
on-disk SHA-256 cache to avoid re-scanning unchanged files.

Also runs a deterministic integrity pass over the docs it scans. Four defect
classes silently destroy downstream item coverage, because the playwright
manifest keys items by ID in a single global map and skips lines it cannot
parse:

  duplicate-item-id      two items in one doc share an ID
  duplicate-namespace    two docs declare the same `id_namespace`
  namespace-mismatch     an item ID does not start with the doc's namespace
  malformed-item         a checklist line is not Format A (missing bold ID,
                         missing ` --- ` separator, or missing *Expected:*)
  frontmatter-missing    (already reported) — every item in the doc is invisible

Output: JSON summary on stdout for the agent to consume. Optional --quiet
suppresses output (used by post-edit hooks).

Exit codes:
  0 — scan completed successfully
  1 — fatal error (missing dirs, malformed cache, etc.)
  2 — integrity errors found and --fail-on-integrity was passed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CACHE_TTL_DAYS = 7
CACHE_FILENAME = ".scan-cache.json"
GITIGNORE_ENTRY = "docs/verification/.scan-cache.json"
STAMP_REGEX = re.compile(r"^verification-writer@(\d+\.\d+\.\d+)$")
FORMAT_A_REGEX = re.compile(r"^- \[[ x]\] (\[\w+\] )?\*\*[A-Z][A-Z0-9-]+\*\*")
CHECKLIST_LINE_REGEX = re.compile(r"^\s*- \[[ x]\] ")
ITEM_ID_REGEX = re.compile(r"^\s*- \[[ x]\] (?:\[\w+\] )?\*\*([A-Z][A-Z0-9-]*)\*\*")
FORMAT_A_FULL_REGEX = re.compile(
    r"^\s*- \[[ x]\] (?:\[\w+\] )?\*\*[A-Z][A-Z0-9-]*\*\* .+ --- .+\*Expected:.+\*"
)
FENCE_REGEX = re.compile(r"^\s*```")
EXCLUDED_TOP_FILES = {"index.md", "README.md"}
EXCLUDED_DIRS = {"findings", "logs", "visualizations"}


@dataclass
class FileResult:
    path: str
    sha256: str
    scanned_at: str
    frontmatter_version: str | None = None
    skill_version: str | None = None  # e.g. "verification-writer@3.2.0"
    inferred_version: str | None = None  # set when fingerprinted, not stamped
    fingerprint_inferred: bool = False
    issues: list[str] = field(default_factory=list)
    has_affected_paths: bool = False
    id_namespace: str | None = None
    item_ids: list[str] = field(default_factory=list)
    duplicate_item_ids: list[str] = field(default_factory=list)
    namespace_mismatches: list[str] = field(default_factory=list)
    malformed_items: list[dict[str, Any]] = field(default_factory=list)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_frontmatter_block(text: str) -> str | None:
    """Return the raw YAML body between leading --- and closing ---, or None."""
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return None
    rest = text[4:] if text.startswith("---\n") else text[5:]
    end = rest.find("\n---")
    if end == -1:
        return None
    return rest[:end]


# Top-level key detection: a non-indented `key:` line, ignoring comments.
TOP_LEVEL_KEY_REGEX = re.compile(r"^([A-Za-z_][\w-]*):", re.MULTILINE)
SCALAR_KEY_REGEX = re.compile(
    r"^([A-Za-z_][\w-]*):\s*(.+?)\s*(?:#.*)?$", re.MULTILINE
)


def frontmatter_keys_and_scalars(body: str) -> tuple[set[str], dict[str, str]]:
    """Return (set of top-level keys, dict of top-level scalar key -> value).

    We only need top-level key presence for fingerprinting and the scalar values
    of `version` and `generated_by`. This avoids any YAML parser dependency.
    """
    keys: set[str] = set()
    scalars: dict[str, str] = {}
    for line in body.splitlines():
        if not line or line.startswith(" ") or line.startswith("\t"):
            continue
        stripped = line.split("#", 1)[0].rstrip()
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", stripped)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        keys.add(key)
        if value and not value.startswith("[") and not value.startswith("{"):
            scalars[key] = value.strip('"').strip("'")
        if value.startswith("[") and value.endswith("]"):
            # inline list — record presence only
            scalars[key] = value
    return keys, scalars


def has_format_a_items(text: str) -> bool:
    for line in text.splitlines():
        if FORMAT_A_REGEX.match(line):
            return True
    return False


def scan_items(text: str, namespace: str | None) -> dict[str, Any]:
    """Walk checklist lines and report ID and Format A integrity defects.

    Returns item_ids (in document order, deduplicated), duplicate_item_ids,
    namespace_mismatches, and malformed_items (line number + reason).
    """
    seen: set[str] = set()
    item_ids: list[str] = []
    duplicates: list[str] = []
    mismatches: list[str] = []
    malformed: list[dict[str, Any]] = []
    in_fence = False

    for lineno, line in enumerate(text.splitlines(), start=1):
        if FENCE_REGEX.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not CHECKLIST_LINE_REGEX.match(line):
            continue

        m = ITEM_ID_REGEX.match(line)
        if not m:
            malformed.append({"line": lineno, "reason": "no-bold-id", "text": line.strip()})
            continue
        if not FORMAT_A_FULL_REGEX.match(line):
            reason = "missing-separator" if " --- " not in line else "missing-expected"
            malformed.append({"line": lineno, "reason": reason, "text": line.strip()})
            # Still record the ID — the item exists, it just won't parse downstream.

        item_id = m.group(1)
        if item_id in seen:
            duplicates.append(item_id)
        else:
            seen.add(item_id)
            item_ids.append(item_id)
        if namespace and not item_id.startswith(namespace):
            mismatches.append(item_id)

    return {
        "item_ids": item_ids,
        "duplicate_item_ids": sorted(set(duplicates)),
        "namespace_mismatches": sorted(set(mismatches)),
        "malformed_items": malformed,
    }


def fingerprint_version(keys: set[str] | None, body_text: str) -> str:
    """Walk the version-fingerprints table to assign a best-guess version.

    Order matters — most specific first. Mirrors version-fingerprints.md.
    """
    if keys is not None:
        if "affected_paths" in keys:
            return "3.3.0"
        if "id_namespace" in keys:
            return "3.2.0"
        if "generated_by" in keys:
            return "3.1.0"
        return "3.0.0"
    if has_format_a_items(body_text):
        return "2.x"
    return "pre-3.0.0"


def discover_files(verification_root: Path) -> list[Path]:
    """Every verification doc under the root, excluding report/log directories.

    Walks the whole tree rather than a fixed pages/ + flows/ list: docs that
    live at the verification root or in a project-specific subdirectory hold
    real checklist items, and anything not scanned here is invisible to both
    the version report and the integrity pass.
    """
    files: list[Path] = []
    for p in sorted(verification_root.rglob("*.md")):
        if not p.is_file():
            continue
        rel = p.relative_to(verification_root)
        if rel.parts[0] in EXCLUDED_DIRS:
            continue
        if len(rel.parts) == 1 and rel.name in EXCLUDED_TOP_FILES:
            continue
        files.append(p)
    return files


def load_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.is_file():
        return {}
    try:
        return json.loads(cache_path.read_text())
    except json.JSONDecodeError:
        # Corrupt cache — treat as empty, will be rewritten
        return {}


def save_cache(cache_path: Path, data: dict[str, Any]) -> None:
    cache_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def cache_entry_fresh(entry: dict[str, Any], current_sha: str) -> bool:
    if entry.get("sha256") != current_sha:
        return False
    if "item_ids" not in entry:
        return False  # pre-integrity-pass cache entry — re-scan to populate it
    scanned_at = entry.get("scanned_at")
    if not scanned_at:
        return False
    try:
        ts = datetime.fromisoformat(scanned_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = datetime.now(timezone.utc) - ts
    return age.days < CACHE_TTL_DAYS


def ensure_gitignore(repo_root: Path) -> bool:
    """Ensure docs/verification/.scan-cache.json is gitignored. Returns True if added."""
    gi = repo_root / ".gitignore"
    if gi.is_file():
        existing = gi.read_text()
        if GITIGNORE_ENTRY in existing or ".scan-cache.json" in existing:
            return False
        sep = "" if existing.endswith("\n") else "\n"
        gi.write_text(existing + sep + GITIGNORE_ENTRY + "\n")
        return True
    gi.write_text(GITIGNORE_ENTRY + "\n")
    return True


def scan_file(path: Path, cache: dict[str, Any], rel_key: str) -> FileResult:
    sha = sha256_of(path)
    cached = cache.get(rel_key)
    if cached and cache_entry_fresh(cached, sha):
        return FileResult(
            path=rel_key,
            sha256=sha,
            scanned_at=cached["scanned_at"],
            frontmatter_version=cached.get("frontmatter_version"),
            skill_version=cached.get("skill_version"),
            inferred_version=cached.get("inferred_version"),
            fingerprint_inferred=cached.get("fingerprint_inferred", False),
            issues=list(cached.get("issues", [])),
            has_affected_paths=cached.get("has_affected_paths", False),
            id_namespace=cached.get("id_namespace"),
            item_ids=list(cached.get("item_ids", [])),
            duplicate_item_ids=list(cached.get("duplicate_item_ids", [])),
            namespace_mismatches=list(cached.get("namespace_mismatches", [])),
            malformed_items=list(cached.get("malformed_items", [])),
        )

    text = path.read_text(errors="replace")
    body = extract_frontmatter_block(text)
    issues: list[str] = []
    skill_version: str | None = None
    fingerprint_inferred = False
    inferred_version: str | None = None
    frontmatter_version: str | None = None
    has_affected_paths = False
    id_namespace: str | None = None

    if body is None:
        issues.append("frontmatter-missing")
        inferred_version = fingerprint_version(None, text)
        fingerprint_inferred = True
    else:
        keys, scalars = frontmatter_keys_and_scalars(body)
        frontmatter_version = scalars.get("version")
        has_affected_paths = "affected_paths" in keys
        id_namespace = scalars.get("id_namespace")
        if not id_namespace:
            issues.append("id_namespace-missing")
        stamp = scalars.get("generated_by")
        if stamp:
            m = STAMP_REGEX.match(stamp)
            if m:
                skill_version = stamp
            else:
                issues.append("generated_by-malformed")
                inferred_version = fingerprint_version(keys, text)
                fingerprint_inferred = True
        else:
            issues.append("stamp-missing")
            inferred_version = fingerprint_version(keys, text)
            fingerprint_inferred = True

    item_scan = scan_items(text, id_namespace)

    return FileResult(
        path=rel_key,
        sha256=sha,
        scanned_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        frontmatter_version=frontmatter_version,
        skill_version=skill_version,
        inferred_version=inferred_version,
        fingerprint_inferred=fingerprint_inferred,
        issues=issues,
        has_affected_paths=has_affected_paths,
        id_namespace=id_namespace,
        item_ids=item_scan["item_ids"],
        duplicate_item_ids=item_scan["duplicate_item_ids"],
        namespace_mismatches=item_scan["namespace_mismatches"],
        malformed_items=item_scan["malformed_items"],
    )


def result_to_cache(r: FileResult) -> dict[str, Any]:
    return {
        "sha256": r.sha256,
        "scanned_at": r.scanned_at,
        "frontmatter_version": r.frontmatter_version,
        "skill_version": r.skill_version,
        "inferred_version": r.inferred_version,
        "fingerprint_inferred": r.fingerprint_inferred,
        "issues": r.issues,
        "has_affected_paths": r.has_affected_paths,
        "id_namespace": r.id_namespace,
        "item_ids": r.item_ids,
        "duplicate_item_ids": r.duplicate_item_ids,
        "namespace_mismatches": r.namespace_mismatches,
        "malformed_items": r.malformed_items,
    }


def build_integrity(results: list[FileResult]) -> dict[str, Any]:
    """Cross-doc and per-doc integrity report.

    Namespace collisions are the cross-doc case: two docs claiming the same
    `id_namespace` will mint colliding item IDs, and a downstream manifest keyed
    globally by ID keeps only whichever doc synced last.
    """
    by_namespace: dict[str, list[str]] = {}
    for r in results:
        if r.id_namespace:
            by_namespace.setdefault(r.id_namespace, []).append(r.path)

    duplicate_namespaces = [
        {"id_namespace": ns, "docs": sorted(paths)}
        for ns, paths in sorted(by_namespace.items())
        if len(paths) > 1
    ]
    duplicate_item_ids = [
        {"path": r.path, "ids": r.duplicate_item_ids}
        for r in results
        if r.duplicate_item_ids
    ]
    namespace_mismatches = [
        {"path": r.path, "id_namespace": r.id_namespace, "ids": r.namespace_mismatches}
        for r in results
        if r.namespace_mismatches
    ]
    malformed_items = [
        {"path": r.path, "items": r.malformed_items}
        for r in results
        if r.malformed_items
    ]
    missing_namespace = [r.path for r in results if "id_namespace-missing" in r.issues]

    error_count = (
        len(duplicate_namespaces)
        + sum(len(d["ids"]) for d in duplicate_item_ids)
        + sum(len(d["ids"]) for d in namespace_mismatches)
        + sum(len(d["items"]) for d in malformed_items)
    )

    return {
        "error_count": error_count,
        "total_items": sum(len(r.item_ids) for r in results),
        "duplicate_namespaces": duplicate_namespaces,
        "duplicate_item_ids": duplicate_item_ids,
        "namespace_mismatches": namespace_mismatches,
        "malformed_items": malformed_items,
        "missing_id_namespace": missing_namespace,
    }


def build_summary(results: list[FileResult], current_skill_version: str) -> dict[str, Any]:
    total = len(results)
    stamped = [r for r in results if r.skill_version]
    current_target = f"verification-writer@{current_skill_version}"
    current = sum(1 for r in stamped if r.skill_version == current_target)
    stale = [r for r in stamped if r.skill_version != current_target]
    missing_frontmatter = [r for r in results if "frontmatter-missing" in r.issues]
    stamp_missing = [r for r in results if "stamp-missing" in r.issues]
    no_affected_paths = [r for r in results if not r.has_affected_paths]
    integrity = build_integrity(results)

    return {
        "summary": {
            "total": total,
            "current": current,
            "stale": len(stale),
            "missing_frontmatter": len(missing_frontmatter),
            "stamp_missing": len(stamp_missing),
            "no_affected_paths": len(no_affected_paths),
            "current_skill_version": current_skill_version,
            "integrity_errors": integrity["error_count"],
        },
        "integrity": integrity,
        "stale": [
            {
                "path": r.path,
                "skill_version": r.skill_version,
                "frontmatter_version": r.frontmatter_version,
            }
            for r in stale
        ],
        "missing_frontmatter": [r.path for r in missing_frontmatter],
        "stamp_missing": [
            {"path": r.path, "inferred_version": r.inferred_version}
            for r in stamp_missing
        ],
        "no_affected_paths": [r.path for r in no_affected_paths],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=".",
        help="Repo root (default: current directory). Verification docs are expected at <root>/docs/verification/.",
    )
    parser.add_argument(
        "--current-version",
        required=True,
        help="Current verification-writer version (e.g., 3.3.0). The scanner reports drift against this.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress JSON output. Cache is still updated. Used by post-edit hooks.",
    )
    parser.add_argument(
        "--fail-on-integrity",
        action="store_true",
        help="Exit 2 if the integrity pass finds any error (duplicate item IDs, "
             "duplicate id_namespace across docs, namespace mismatches, malformed items). "
             "Use in blocking hooks and CI; the default is report-only.",
    )
    parser.add_argument(
        "--no-gitignore-touch",
        action="store_true",
        help="Skip the .gitignore auto-touch step.",
    )
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    verification_root = repo_root / "docs" / "verification"

    if not verification_root.is_dir():
        sys.stderr.write(
            f"ERROR: docs/verification/ not found at {verification_root}\n"
        )
        return 1

    if not args.no_gitignore_touch:
        ensure_gitignore(repo_root)

    cache_path = verification_root / CACHE_FILENAME
    cache_data = load_cache(cache_path)
    file_cache = cache_data.get("files", {}) if isinstance(cache_data, dict) else {}

    files = discover_files(verification_root)
    results: list[FileResult] = []
    new_file_cache: dict[str, Any] = {}

    for f in files:
        rel = str(f.relative_to(repo_root))
        r = scan_file(f, file_cache, rel)
        results.append(r)
        new_file_cache[rel] = result_to_cache(r)

    output = {
        "scan_version": 1,
        "scanned_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "files": new_file_cache,
    }
    save_cache(cache_path, output)

    summary = build_summary(results, args.current_version)

    if not args.quiet:
        json.dump(summary, sys.stdout, indent=2)
        sys.stdout.write("\n")

    errors = summary["integrity"]["error_count"]
    if errors and args.fail_on_integrity:
        sys.stderr.write(
            f"ERROR: {errors} verification doc integrity error(s). "
            "Re-run without --quiet for the full report.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
