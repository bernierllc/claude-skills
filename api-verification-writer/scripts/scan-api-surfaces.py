#!/usr/bin/env python3
"""
scan-api-surfaces.py — Deterministic inventory of a repo's REST and MCP surfaces.

Sources, most authoritative first:
  1. OpenAPI/Swagger spec (JSON; YAML needs PyYAML, otherwise a finding says so)
  2. MCP `tools/list` dump (JSON) captured from a running test server
  3. Framework route scan (Next.js route files, Express-style, FastAPI/Flask)

It never contacts a server. Capture the MCP listing with the MCP SDK client or
Inspector CLI and pass the file via --mcp-tools.

Where sources disagree the disagreement is a finding, not something to hide:
  undocumented-route    route in code, absent from the spec
  spec-without-route    spec operation with no matching route in code
  no-security-declared  spec operation with no security at all (confirm it is public)
  mcp-no-description / mcp-no-annotations / mcp-no-output-schema

Output: JSON on stdout {operations, mcp_tools, findings}. Exit 0 always unless a
source file is unreadable (exit 1); --fail-on-findings exits 2 on any finding.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
SKIP_DIRS = {".git", "node_modules", ".worktrees", "dist", "build", ".next", "__pycache__",
             "venv", ".venv", "coverage", "tests", "test", "__tests__"}
SPEC_NAMES = ("openapi.json", "openapi.yaml", "openapi.yml", "swagger.json",
              "docs/openapi.json", "docs/openapi.yaml", "docs/openapi.yml",
              "api/openapi.json", "api/openapi.yaml", "public/openapi.json")

EXPRESS_RE = re.compile(
    r"""\b(?:app|router|server|fastify|api|route[sr]?)\s*\.\s*(get|post|put|patch|delete)\s*\(\s*['"`]([^'"`]+)['"`]""")
PY_RE = re.compile(r"""@\s*\w+\s*\.\s*(get|post|put|patch|delete)\s*\(\s*['"]([^'"]+)['"]""")
FLASK_RE = re.compile(r"""@\s*\w+\s*\.route\s*\(\s*['"]([^'"]+)['"](?:[^)]*methods\s*=\s*\[([^\]]*)\])?""")
NEXT_METHOD_RE = re.compile(
    r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")


def normalize(path: str) -> str:
    p = re.sub(r"\[\.\.\.(\w+)\]", r"{\1}", path)      # [...slug]
    p = re.sub(r"\[(\w+)\]", r"{\1}", p)                # [id]
    p = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", p)         # <int:id>
    p = re.sub(r"(?<![{\w]):(\w+)", r"{\1}", p)         # :id
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"


def load_spec(path: Path, findings: list[dict]) -> dict | None:
    text = path.read_text(errors="replace")
    if path.suffix == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
    except ImportError:
        findings.append({"kind": "yaml-spec-unreadable", "file": str(path),
                         "detail": "YAML spec found but PyYAML is not installed; "
                                   "export it to JSON or `pip install pyyaml`"})
        return None
    return yaml.safe_load(text)


def scan_spec(spec: dict, source: str, findings: list[dict]) -> list[dict]:
    ops: list[dict] = []
    global_security = spec.get("security")
    for raw_path, item in (spec.get("paths") or {}).items():
        for method in METHODS:
            op = (item or {}).get(method)
            if not isinstance(op, dict):
                continue
            sec = op["security"] if "security" in op else global_security
            scopes = sorted({s for req in (sec or []) for v in req.values() for s in (v or [])})
            declared = sec is not None
            public = declared and sec == []
            entry = {
                "surface": "rest", "source": "openapi", "file": source,
                "method": method.upper(), "path": normalize(raw_path),
                "operation_id": op.get("operationId"),
                "summary": op.get("summary") or op.get("description"),
                "security_declared": declared, "explicitly_public": public,
                "security_schemes": sorted({k for req in (sec or []) for k in req}),
                "scopes": scopes,
            }
            ops.append(entry)
            if not declared:
                findings.append({"kind": "no-security-declared", "id": f"{entry['method']} {entry['path']}",
                                 "detail": "no operation-level or global security; confirm this is intentionally public"})
    return ops


def scan_mcp(path: Path, findings: list[dict]) -> list[dict]:
    data = json.loads(path.read_text())
    tools = data.get("tools") if isinstance(data, dict) else data
    out = []
    for t in tools or []:
        ann = t.get("annotations") or {}
        entry = {"surface": "mcp", "source": "tools/list", "file": str(path), "tool": t.get("name"),
                 "description": t.get("description"), "annotations": ann,
                 "has_input_schema": bool(t.get("inputSchema")),
                 "has_output_schema": bool(t.get("outputSchema"))}
        out.append(entry)
        if not t.get("description"):
            findings.append({"kind": "mcp-no-description", "id": t.get("name"), "detail": "tool has no description"})
        if not any(k in ann for k in ("readOnlyHint", "destructiveHint")):
            findings.append({"kind": "mcp-no-annotations", "id": t.get("name"),
                             "detail": "no readOnlyHint/destructiveHint; clients cannot tell safe from destructive"})
        if not t.get("outputSchema"):
            findings.append({"kind": "mcp-no-output-schema", "id": t.get("name"), "detail": "no outputSchema (low)"})
    return out


def iter_code_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".mjs", ".py") \
                and not any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            yield p


def scan_code(root: Path) -> list[dict]:
    routes: list[dict] = []
    for p in iter_code_files(root):
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue  # unreadable file in a best-effort scan; the spec/tools sources still apply
        m = re.search(r"(?:^|/)app/(.*)/route\.(?:ts|js)$", rel) or re.search(r"(?:^|/)pages/(api/.*)\.(?:ts|js)$", rel)
        if m and p.suffix in (".ts", ".js"):
            path = normalize(m.group(1).removesuffix("/index"))
            methods = NEXT_METHOD_RE.findall(text) or (["GET"] if "pages/api" in rel else [])
            for meth in methods:
                routes.append({"method": meth, "path": path, "file": rel, "framework": "next"})
            continue
        for meth, path in EXPRESS_RE.findall(text) if p.suffix != ".py" else []:
            routes.append({"method": meth.upper(), "path": normalize(path), "file": rel, "framework": "express-style"})
        if p.suffix == ".py":
            for meth, path in PY_RE.findall(text):
                routes.append({"method": meth.upper(), "path": normalize(path), "file": rel, "framework": "fastapi-style"})
            for path, methods in FLASK_RE.findall(text):
                for meth in re.findall(r"[A-Za-z]+", methods or "") or ["GET"]:
                    routes.append({"method": meth.upper(), "path": normalize(path), "file": rel, "framework": "flask"})
    return routes


def same_route(spec_path: str, code_path: str) -> bool:
    """Code paths often omit a mount prefix, so accept a suffix match on segment boundaries."""
    return spec_path == code_path or spec_path.endswith(code_path if code_path != "/" else "\0")


def drift(spec_ops: list[dict], code_routes: list[dict], findings: list[dict]) -> None:
    if not spec_ops or not code_routes:
        return
    for r in code_routes:
        if not any(o["method"] == r["method"] and same_route(o["path"], r["path"]) for o in spec_ops):
            findings.append({"kind": "undocumented-route", "id": f"{r['method']} {r['path']}", "file": r["file"],
                             "detail": "route exists in code but not in the OpenAPI spec"})
    for o in spec_ops:
        if not any(o["method"] == r["method"] and same_route(o["path"], r["path"]) for r in code_routes):
            findings.append({"kind": "spec-without-route", "id": f"{o['method']} {o['path']}",
                             "detail": "in the spec but no matching route found by the code scan (the scan is heuristic; verify)"})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--openapi", action="append", default=[], help="spec path (repeatable); default: auto-discover")
    ap.add_argument("--mcp-tools", action="append", default=[], help="tools/list JSON dump (repeatable)")
    ap.add_argument("--no-code-scan", action="store_true")
    ap.add_argument("--fail-on-findings", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    findings: list[dict] = []
    spec_paths = [Path(p) for p in args.openapi] or [root / n for n in SPEC_NAMES if (root / n).is_file()]
    spec_ops: list[dict] = []
    try:
        for sp in spec_paths:
            spec = load_spec(sp, findings)
            if spec:
                spec_ops += scan_spec(spec, str(sp.relative_to(root)) if sp.is_relative_to(root) else str(sp), findings)
        mcp_tools = [t for mp in args.mcp_tools for t in scan_mcp(Path(mp), findings)]
    except (OSError, json.JSONDecodeError) as exc:
        print(f"scan-api-surfaces: cannot read a source file: {exc}", file=sys.stderr)
        return 1

    code_routes = [] if args.no_code_scan else scan_code(root)
    drift(spec_ops, code_routes, findings)
    print(json.dumps({"operations": spec_ops, "code_routes": code_routes, "mcp_tools": mcp_tools,
                      "findings": findings}, indent=2))
    return 2 if (args.fail_on_findings and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
