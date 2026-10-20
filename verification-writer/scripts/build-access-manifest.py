#!/usr/bin/env python3
"""
build-access-manifest.py — Merge verification-doc `access:` frontmatter into one
machine-readable audience manifest.

Reads docs/verification/{pages,api,mcp}/**/*.md and writes
docs/verification/access-manifest.json. The manifest, not an agent's judgment,
says what is public, internal, admin-only or still a draft. Consumers: the
customer and internal docs agents, llms.txt / sitemap / MCP-index build steps,
and CI.

Rules (deliberately boring, so the output is predictable):
  * `access.visibility` is read, never inferred. Absent => `draft`.
  * `public | internal | admin | draft` are the only values; anything else is a
    finding and the entry is treated as `draft`.
  * A `public` entry whose own `access:` says otherwise (public: false, required
    roles/permissions/scopes, a tier gate) is a finding: either the visibility
    or the auth declaration is wrong. Neither is silently "fixed".
  * Two docs claiming the same surface+id is a finding.

Stdlib only; the frontmatter subset parsed here is the one verification-writer
emits (scalars, inline lists, one nested mapping level).

Exit codes: 0 ok · 1 fatal · 2 findings present and --fail-on-findings, or
--check found the manifest stale.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

VISIBILITIES = ("public", "internal", "admin", "draft")
SURFACE_DIRS = {"pages": "page", "api": "rest", "mcp": "mcp"}  # flows carry no access block, so they are not manifest entries
MANIFEST_REL = "docs/verification/access-manifest.json"


def split_frontmatter(text: str) -> str | None:
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else None


def parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw in ("", "~", "null"):
        return None
    if raw in ("true", "false"):
        return raw == "true"
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [parse_scalar(p) for p in inner.split(",")] if inner else []
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def strip_comment(line: str) -> str:
    """Drop a trailing ` # comment`, ignoring any # inside quotes."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def parse_frontmatter(body: str) -> dict[str, Any]:
    """Top-level scalars/lists plus one nested mapping level (e.g. `access:`)."""
    out: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    last: tuple[dict[str, Any], str] | None = None  # key awaiting `- item` block-list lines
    for line in body.splitlines():
        code = strip_comment(line)
        if not code.strip() or code.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s*-\s+(.*)$", code)
        if item and last is not None:
            container, key = last
            if not isinstance(container.get(key), list):
                container[key] = []
            container[key].append(parse_scalar(item.group(1)))
            continue
        indented = code[0] in " \t"
        m = re.match(r"^\s*([A-Za-z0-9_-]+):\s*(.*)$", code)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if indented and current is not None:
            current[key] = parse_scalar(value)
            last = (current, key) if value == "" else None
        elif not indented:
            if value == "":
                current = {}
                out[key] = current
                last = (out, key)  # becomes a list if `- item` lines follow, else stays a mapping
            else:
                current = None
                out[key] = parse_scalar(value)
                last = None
    return out


def as_list(value: Any) -> list[str]:
    if value is None or value == {}:
        return []
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


def entry_id(surface: str, fm: dict[str, Any], rel: Path) -> str:
    if surface == "rest" and fm.get("method") and fm.get("path"):
        return f"{str(fm['method']).upper()} {fm['path']}"
    for key in ("tool", "path", "id"):
        if fm.get(key):
            return str(fm[key])
    return rel.with_suffix("").as_posix()


def build_entry(
    surface: str, fm: dict[str, Any], rel: Path, findings: list[dict[str, str]]
) -> dict[str, Any]:
    access = fm.get("access") if isinstance(fm.get("access"), dict) else {}
    eid = entry_id(surface, fm, rel)

    visibility = access.get("visibility")
    if visibility is None:
        visibility = "draft"
    elif visibility not in VISIBILITIES:
        findings.append(
            {
                "kind": "invalid-visibility",
                "id": eid,
                "file": rel.as_posix(),
                "detail": f"visibility {visibility!r} is not one of {'|'.join(VISIBILITIES)}; treated as draft",
            }
        )
        visibility = "draft"

    roles = as_list(access.get("required_roles"))
    scopes = as_list(access.get("required_scopes"))
    permissions = as_list(access.get("required_permissions"))
    tier = access.get("tier")

    mfa = access.get("mfa_required")
    if mfa is not None and not isinstance(mfa, bool):  # "True"/"yes" must not silently drop a security gate
        findings.append({"kind": "invalid-mfa-required", "id": eid, "file": rel.as_posix(),
                         "detail": f"mfa_required {mfa!r} is not a lowercase true/false; treated as true so the gate is not lost"})
        mfa = True
    mfa = bool(mfa)
    if mfa and access.get("public") is True:
        findings.append({"kind": "mfa-contradicts-public", "id": eid, "file": rel.as_posix(),
                         "detail": "access.public is true but mfa_required is true; the matrix cannot expect both"})

    if visibility == "public" and surface == "page":  # for REST/MCP, visibility is who reads the docs, not who may call
        contradictions = []
        if access.get("public") is False:
            contradictions.append("access.public is false")
        if roles or scopes or permissions:
            contradictions.append("it declares required roles/scopes/permissions")
        if tier:
            contradictions.append(f"it is tier-gated ({tier})")
        if mfa:
            contradictions.append("it requires MFA")
        if contradictions:
            findings.append(
                {
                    "kind": "visibility-contradicts-access",
                    "id": eid,
                    "file": rel.as_posix(),
                    "detail": "visibility is public but " + " and ".join(contradictions),
                }
            )

    gates = as_list(access.get("gated_by"))
    if visibility == "public" and gates and access.get("gates_confirmed_on") is not True:
        findings.append({"kind": "public-gated-by-flag", "id": eid, "file": rel.as_posix(),
                         "detail": f"visibility is public but it is gated_by {gates}; confirm every gate is on in production, then set access.gates_confirmed_on: true, otherwise set visibility internal"})

    return {
        "surface": surface,
        "id": eid,
        "file": rel.as_posix(),
        "visibility": visibility,
        "auth_model": access.get("auth_model"),
        "endpoint": access.get("endpoint"),
        "public": access.get("public"),
        "roles": roles,
        "scopes": scopes,
        "permissions": permissions,
        "tier": tier,
        "mfa_required": mfa,
        "gated_by": as_list(access.get("gated_by")),
        "user_types": as_list(fm.get("user_types")),
        "affected_paths": as_list(fm.get("affected_paths")),
    }


def collect(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    vroot = root / "docs" / "verification"
    entries: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    for dirname, surface in {**SURFACE_DIRS, "flows": None}.items():  # flows are linted but never become entries
        base = vroot / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if path.name.startswith(".") or path.name in ("index.md", "README.md"):
                continue
            rel = path.relative_to(root)
            body = split_frontmatter(path.read_text(errors="replace"))
            if body is None:
                findings.append(
                    {
                        "kind": "frontmatter-missing",
                        "id": rel.as_posix(),
                        "file": rel.as_posix(),
                        "detail": "no frontmatter" + ("" if surface is None else "; entry omitted from the manifest"),
                    }
                )
                continue
            fm = parse_frontmatter(body)
            for key in ("affected_paths", "related"):
                if re.search(rf"^{key}:[ \t]*\[(?![ \t]*\])", body, re.M):
                    findings.append({"kind": "frontmatter-flow-list", "id": rel.as_posix(), "file": rel.as_posix(),
                                     "detail": f"{key} is a flow-style list; write a block list with quoted entries"})
            if surface is None:
                continue
            entry_surface = {"api": "rest"}.get(str(fm.get("surface") or surface), str(fm.get("surface") or surface))
            if entry_surface not in SURFACE_DIRS.values():
                findings.append({"kind": "invalid-surface", "id": rel.as_posix(), "file": rel.as_posix(),
                                 "detail": f"surface {entry_surface!r} is not one of {'|'.join(SURFACE_DIRS.values())}; entry omitted"})
                continue
            entries.append(build_entry(entry_surface, fm, rel, findings))

    seen: dict[tuple[str, str], str] = {}
    for e in entries:
        key = (e["surface"], e["id"])
        if key in seen:
            findings.append(
                {
                    "kind": "duplicate-entry",
                    "id": e["id"],
                    "file": e["file"],
                    "detail": f"also declared in {seen[key]}",
                }
            )
        else:
            seen[key] = e["file"]

    by_paths: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for e in entries:
        if e["affected_paths"]:
            by_paths.setdefault(tuple(sorted(e["affected_paths"])), []).append(e)
    for group in by_paths.values():
        gates = {tuple(sorted(e["gated_by"])) for e in group}
        if len(gates) > 1:
            for e in group:
                findings.append(
                    {
                        "kind": "gated-by-inconsistent",
                        "id": e["id"],
                        "file": e["file"],
                        "detail": "shares identical affected_paths with "
                        + ", ".join(o["id"] for o in group if o is not e)
                        + " but declares a different gated_by",
                    }
                )

    entries.sort(key=lambda e: (e["surface"], e["id"], e["file"]))
    return entries, findings


def git_sha(root: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        # best-effort: a non-git checkout or hung git must not block manifest generation
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


def build(root: Path) -> dict[str, Any]:
    entries, findings = collect(root)
    return {"generated_from": git_sha(root), "entries": entries, "findings": findings}


def comparable(manifest: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in manifest.items() if k != "generated_from"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--check", action="store_true", help="fail if the committed manifest is stale; write nothing")
    ap.add_argument("--fail-on-findings", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / "docs" / "verification").is_dir():
        print("build-access-manifest: no docs/verification/ in " + str(root), file=sys.stderr)
        return 1

    manifest = build(root)
    target = root / MANIFEST_REL

    if args.check:
        try:
            current = json.loads(target.read_text())
        except (OSError, json.JSONDecodeError):
            print(f"{MANIFEST_REL} is missing or unreadable; run build-access-manifest.py", file=sys.stderr)
            return 2
        if comparable(current) != comparable(manifest):
            print(f"{MANIFEST_REL} is stale; run build-access-manifest.py and commit it", file=sys.stderr)
            return 2
    else:
        target.write_text(json.dumps(manifest, indent=2) + "\n")

    if not args.quiet:
        counts: dict[str, int] = {}
        for e in manifest["entries"]:
            counts[e["visibility"]] = counts.get(e["visibility"], 0) + 1
        if manifest["entries"] and set(counts) == {"draft"}:
            print("note: every entry is draft; no visibility has been declared, so this is no data, not a verdict", file=sys.stderr)
        print(json.dumps({"entries": len(manifest["entries"]), "by_visibility": counts,
                          "findings": manifest["findings"]}, indent=2))

    return 2 if (args.fail_on_findings and manifest["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
