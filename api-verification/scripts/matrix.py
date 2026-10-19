#!/usr/bin/env python3
"""
matrix.py — Role/scope access matrix for REST and MCP surfaces.

  guard     refuse a base URL that is not a local/test host
  plan      access-manifest.json x principals.json -> expected allow/deny matrix
  run       probe REST entries against --base-url as each principal -> results JSON
  evaluate  compare results JSON (REST from `run`, MCP from your own client) to the plan

Expectation, per entry and principal:
  visibility public                      -> allowed
  access.public true (or documented public with no gate) -> allowed
  entry declares roles/scopes/permissions-> allowed iff the principal holds a match for each declared kind
  non-public, nothing specific declared  -> allowed iff the principal has a token (is not anonymous)
Allowed = response status not in {401, 403}; denied = 401 or 403 (`--denied-status` widens it, e.g. 302 to a login
page: redirects are never followed). No answer at all is a `no-response` mismatch. A 404/400 from a
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
DEFAULT_DENIED = "401,403"


def host_is_local(host: str) -> bool:
    if host == "localhost" or host.endswith(LOCAL_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or (ip.is_private and not ip.is_link_local)  # 169.254.169.254 is a cloud metadata service


def guard(base_url: str) -> str | None:
    """Return a refusal message, or None when the host is acceptable."""
    host = urlparse(base_url).hostname or ""
    allowed = {h.strip() for h in os.environ.get(ALLOW_ENV, "").split(",") if h.strip()}
    if host_is_local(host) or host in allowed:
        return None
    return (f"refusing {host!r}: not a loopback/private/.local/.test/.internal host. "
            f"Point at a local or staging stack, or list it in {ALLOW_ENV} if it is a safe test environment.")


def expected(entry: dict, principal: dict) -> bool:
    # access.public is who may reach the operation; visibility only says who may read its docs
    if entry.get("public") is True:
        return True
    held = {"roles": principal.get("roles") or [], "scopes": principal.get("scopes") or [],
            "permissions": principal.get("permissions") or []}
    required = {k: entry.get(k) or [] for k in held}
    tier = entry.get("tier")
    gated = any(required.values()) or bool(tier)
    if not gated and entry["visibility"] == "public" and entry.get("public") is None:
        return True  # documented public, nothing gates it
    if not principal.get("token_env"):
        return False  # no token is sent, so this principal is anonymous whatever roles it lists
    return all(not required[k] or bool(set(required[k]) & set(held[k])) for k in held) and \
        (not tier or principal.get("tier") == tier)


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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Report a 30x as-is: following it could re-send the token to a host the guard never checked."""
    def redirect_request(self, *a, **kw):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def probe(base_url: str, entry_id: str, token: str | None) -> int | None:
    """HTTP status, or None when the server did not answer."""
    method, path = entry_id.split(" ", 1)
    url = base_url.rstrip("/") + re.sub(r"\{[^}]+\}", "verify-probe", path)
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with OPENER.open(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError):
        return None  # recorded as no-response by evaluate; one dead route must not discard the rest


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


def evaluate(plan: list[dict], results: list[dict], denied: set[int] | None = None,
             skipped: frozenset[str] = frozenset()) -> list[dict]:
    denied = denied or {401, 403}
    got = {(r["id"], r["principal"]): r["status"] for r in results}
    tested = {row.get("surface") for row in plan if (row["id"], row["principal"]) in got}  # a surface never run is not a failure
    out = []
    for row in plan:
        key = (row["id"], row["principal"])
        if key not in got:
            if row.get("surface") in tested and row["id"] not in skipped:
                out.append({**row, "status": None, "kind": "missing-result"})
            continue
        if got[key] is None:
            out.append({**row, "status": None, "kind": "no-response"})
            continue
        allowed = got[key] not in denied
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
            s.add_argument("--denied-status", default=DEFAULT_DENIED,
                           help="statuses meaning 'denied' (default 401,403; add 302 for cookie apps that redirect to /login)")
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
        res = load(args.results)
        mismatches = evaluate(plan, res["results"], {int(c) for c in args.denied_status.split(",")},
                              frozenset(res.get("skipped_mutating", [])))
        print(json.dumps({"mismatches": mismatches}, indent=2))
        return 2 if mismatches else 0
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"matrix: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
