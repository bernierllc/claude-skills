#!/usr/bin/env python3
"""
matrix.py — Role/scope access matrix for REST and MCP surfaces.

  guard     refuse a base URL that is not a local/test host
  plan      access-manifest.json x principals.json -> expected allow/deny matrix
  run       probe REST entries against --base-url as each principal -> results JSON
  evaluate  compare results JSON (REST from `run`, MCP from your own client) to the plan

Expectation, per entry and principal:
  visibility public                      -> allowed
  entry declares roles / scopes          -> allowed iff the principal holds a match for each declared kind
  non-public, nothing specific declared  -> allowed iff the principal has a token (is not anonymous)
Allowed = response status not in {401, 403}; denied = 401 or 403. A 404/400 from a
placeholder path id still proves the auth gate let the request through.

principals.json holds env var NAMES only, never tokens:
  {"principals": {"anonymous": {}, "viewer": {"roles": ["viewer"], "token_env": "VERIFY_VIEWER_TOKEN"}}}

Stdlib only. Exit: 0 ok · 1 usage/IO · 2 guard refused or mismatches found.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
LOCAL_SUFFIXES = (".local", ".localhost", ".test", ".internal")
ALLOW_ENV = "API_VERIFICATION_ALLOWED_HOSTS"
DENIED = {401, 403}


def host_is_local(host: str) -> bool:
    if host == "localhost" or host.endswith(LOCAL_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def guard(base_url: str) -> str | None:
    """Return a refusal message, or None when the host is acceptable."""
    host = urlparse(base_url).hostname or ""
    allowed = {h.strip() for h in os.environ.get(ALLOW_ENV, "").split(",") if h.strip()}
    if host_is_local(host) or host in allowed:
        return None
    return (f"refusing {host!r}: not a loopback/private/.local/.test/.internal host. "
            f"Point at a local or staging stack, or list it in {ALLOW_ENV} if it is a safe test environment.")


def expected(entry: dict, principal: dict) -> bool:
    if entry["visibility"] == "public":
        return True
    roles, scopes = entry.get("roles") or [], entry.get("scopes") or []
    if roles or scopes:
        return (not roles or bool(set(roles) & set(principal.get("roles") or []))) and \
               (not scopes or bool(set(scopes) & set(principal.get("scopes") or [])))
    return bool(principal.get("token_env"))


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def make_plan(manifest: dict, principals: dict) -> list[dict]:
    rows = []
    for e in manifest["entries"]:
        if e["surface"] not in ("rest", "mcp"):
            continue
        for name, p in sorted(principals["principals"].items()):
            rows.append({"surface": e["surface"], "id": e["id"], "principal": name,
                         "expect_allowed": expected(e, p)})
    return rows


def probe(base_url: str, entry_id: str, token: str | None) -> int:
    method, path = entry_id.split(" ", 1)
    url = base_url.rstrip("/") + re.sub(r"\{[^}]+\}", "verify-probe", path)
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


def cmd_run(args) -> int:
    refusal = guard(args.base_url)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2
    principals = load(args.principals)
    results, skipped = [], []
    for row in make_plan(load(args.manifest), principals):
        if row["surface"] != "rest":
            continue
        if row["id"].split(" ", 1)[0] not in SAFE_METHODS and not args.allow_mutating:
            skipped.append(row["id"])
            continue
        env = principals["principals"][row["principal"]].get("token_env")
        token = os.environ.get(env) if env else None
        if env and not token:
            print(f"env var {env} for principal {row['principal']!r} is not set", file=sys.stderr)
            return 1
        results.append({"id": row["id"], "principal": row["principal"],
                        "status": probe(args.base_url, row["id"], token)})
    print(json.dumps({"results": results, "skipped_mutating": sorted(set(skipped))}, indent=2))
    return 0


def evaluate(plan: list[dict], results: list[dict]) -> list[dict]:
    got = {(r["id"], r["principal"]): r["status"] for r in results}
    out = []
    for row in plan:
        key = (row["id"], row["principal"])
        if key not in got:
            continue
        allowed = got[key] not in DENIED
        if allowed != row["expect_allowed"]:
            out.append({**row, "status": got[key],
                        "kind": "over-permissive" if allowed else "over-restrictive"})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("guard"); g.add_argument("base_url")
    for name in ("plan", "run", "evaluate"):
        s = sub.add_parser(name)
        s.add_argument("--manifest", default="docs/verification/access-manifest.json")
        s.add_argument("--principals", default="docs/verification/principals.json")
        if name == "run":
            s.add_argument("--base-url", required=True)
            s.add_argument("--allow-mutating", action="store_true", help="also probe POST/PUT/PATCH/DELETE")
        if name == "evaluate":
            s.add_argument("--results", required=True)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "guard":
            msg = guard(args.base_url)
            print(msg or "ok")
            return 2 if msg else 0
        if args.cmd == "run":
            return cmd_run(args)
        plan = make_plan(load(args.manifest), load(args.principals))
        if args.cmd == "plan":
            print(json.dumps(plan, indent=2))
            return 0
        mismatches = evaluate(plan, load(args.results)["results"])
        print(json.dumps({"mismatches": mismatches}, indent=2))
        return 2 if mismatches else 0
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"matrix: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
