#!/usr/bin/env python3
"""Self-check for matrix.py. Run: python3 test_matrix.py

Behavior under test: the guard refuses non-local hosts; expectations follow
visibility/roles/scopes; `run` against a real local server flags an endpoint that
ignores its auth declaration; mutating methods are skipped by default.
"""

import contextlib, importlib.util, io, json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_spec = importlib.util.spec_from_file_location("matrix", Path(__file__).with_name("matrix.py"))
mx = importlib.util.module_from_spec(_spec)
sys.modules["matrix"] = mx
_spec.loader.exec_module(mx)

MANIFEST = {"entries": [
    {"surface": "rest", "id": "GET /open", "visibility": "public", "roles": [], "scopes": []},
    {"surface": "rest", "id": "GET /admin", "visibility": "admin", "roles": ["admin"], "scopes": []},
    {"surface": "rest", "id": "GET /leaky", "visibility": "admin", "roles": ["admin"], "scopes": []},
    {"surface": "rest", "id": "DELETE /thing/{id}", "visibility": "admin", "roles": ["admin"], "scopes": []},
    {"surface": "page", "id": "/", "visibility": "public", "roles": [], "scopes": []}]}
PRINCIPALS = {"principals": {"anonymous": {}, "root": {"roles": ["admin"], "token_env": "T_ROOT"},
                             "viewer": {"roles": ["viewer"], "token_env": "T_VIEW"}}}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        auth = self.headers.get("Authorization")
        code = 200 if self.path == "/open" or self.path == "/leaky" else \
            (401 if not auth else 403 if auth != "Bearer root" else 200)
        self.send_response(code); self.end_headers()
    def log_message(self, *a): pass


def cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mx.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_guard():
    assert mx.guard("http://localhost:3000") is None
    assert mx.guard("http://127.0.0.1:8080") is None
    assert mx.guard("http://10.1.2.3") is None
    assert mx.guard("http://app.test") is None
    assert mx.guard("https://api.example.com") is not None
    assert mx.guard("http://169.254.169.254/latest") is not None  # cloud metadata
    os.environ[mx.ALLOW_ENV] = "staging.example.com"
    try:
        assert mx.guard("https://staging.example.com") is None
    finally:
        del os.environ[mx.ALLOW_ENV]


def test_expectations():
    plan = {(r["id"], r["principal"]): r["expect_allowed"] for r in mx.make_plan(MANIFEST, PRINCIPALS)}
    assert plan[("GET /open", "anonymous")] is True
    assert plan[("GET /admin", "root")] is True and plan[("GET /admin", "viewer")] is False
    assert plan[("GET /admin", "anonymous")] is False
    assert not any(k[0] == "/" for k in plan)  # pages are not API surfaces


def test_public_flag_and_permissions_drive_expectations():
    entries = [
        {"id": "GET /hook", "visibility": "draft", "public": True},
        {"id": "GET /abac", "visibility": "internal", "permissions": ["billing.read"]}]
    p = {"principals": {"anonymous": {}, "plain": {"token_env": "T"},
                        "billing": {"token_env": "T", "permissions": ["billing.read"]}}}
    plan = {(r["id"], r["principal"]): r["expect_allowed"]
            for r in mx.make_plan({"entries": [dict(e, surface="rest") for e in entries]}, p)}
    assert plan[("GET /hook", "anonymous")] is True
    assert plan[("GET /abac", "plain")] is False and plan[("GET /abac", "billing")] is True


def test_documented_public_but_gated_and_tier():
    gated = {"id": "GET /g", "visibility": "public", "public": None, "roles": ["admin"], "surface": "rest"}
    tiered = {"id": "GET /t", "visibility": "internal", "tier": "pro", "surface": "rest"}
    p = {"principals": {"anonymous": {}, "root": {"roles": ["admin"], "token_env": "T"},
                        "pro": {"token_env": "T", "tier": "pro"}, "free": {"token_env": "T", "tier": "free"}}}
    plan = {(r["id"], r["principal"]): r["expect_allowed"] for r in mx.make_plan({"entries": [gated, tiered]}, p)}
    assert plan[("GET /g", "anonymous")] is False and plan[("GET /g", "root")] is True
    assert plan[("GET /t", "pro")] is True and plan[("GET /t", "free")] is False


def test_mfa_requirement_needs_an_mfa_principal():
    e = {"id": "POST /m", "visibility": "internal", "public": False, "scopes": ["w"], "mfa_required": True, "surface": "rest"}
    p = {"principals": {"plain": {"scopes": ["w"], "token_env": "T"}, "mfa": {"scopes": ["w"], "token_env": "T", "mfa": True}}}
    plan = {r["principal"]: r["expect_allowed"] for r in mx.make_plan({"entries": [e]}, p)}
    assert plan == {"plain": False, "mfa": True}


def test_mfa_only_and_documented_public_entries_still_gate():
    only = {"id": "GET /o", "visibility": "public", "public": None, "mfa_required": True, "surface": "rest"}
    p = {"principals": {"anonymous": {}, "plain": {"token_env": "T"}, "mfa": {"token_env": "T", "mfa": True},
                        "str": {"token_env": "T", "mfa": "true"}}}
    plan = {r["principal"]: r["expect_allowed"] for r in mx.make_plan({"entries": [only]}, p)}
    assert plan == {"anonymous": False, "plain": False, "mfa": True, "str": False}


def test_absent_rows_fail_unless_skipped_or_surface_untested():
    plan = [{"surface": "rest", "id": "GET /a", "principal": "anonymous", "expect_allowed": True},
            {"surface": "rest", "id": "GET /a", "principal": "root", "expect_allowed": True},
            {"surface": "rest", "id": "DELETE /a", "principal": "root", "expect_allowed": True},
            {"surface": "mcp", "id": "tool", "principal": "root", "expect_allowed": True}]
    got = [{"id": "GET /a", "principal": "anonymous", "status": 200}]
    kinds = [(m["id"], m["kind"]) for m in mx.evaluate(plan, got, None, frozenset({"DELETE /a"}))]
    assert kinds == [("GET /a", "missing-result")], kinds


def test_auth_kinds():
    import urllib.request
    for auth, header, value in [(None, "Authorization", "Bearer t"), ({"kind": "header", "name": "X-API-Key"}, "X-API-Key", "t"),
                                ({"kind": "cookie", "name": "sid"}, "Cookie", "sid=t")]:
        req = urllib.request.Request("http://localhost/x")
        mx.apply_auth(req, "t", auth or {})
        assert req.get_header(header.capitalize()) == value, (auth, req.headers)


def test_run_end_to_end_flags_leak_and_skips_mutating():
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as d:
        m, p = Path(d, "m.json"), Path(d, "p.json")
        m.write_text(json.dumps(MANIFEST)); p.write_text(json.dumps(PRINCIPALS))
        os.environ.update(T_ROOT="root", T_VIEW="viewer")
        try:
            code, out, _ = cli(["run", "--manifest", str(m), "--principals", str(p),
                                "--base-url", f"http://127.0.0.1:{srv.server_port}"])
            assert code == 0
            res = json.loads(out)
            assert res["skipped_mutating"] == ["DELETE /thing/{id}"]
            r = Path(d, "r.json"); r.write_text(out)
            code, out, _ = cli(["evaluate", "--manifest", str(m), "--principals", str(p), "--results", str(r)])
            bad = {(x["id"], x["principal"], x["kind"]) for x in json.loads(out)["mismatches"]}
            assert code == 2
            assert bad == {("GET /leaky", "anonymous", "over-permissive"), ("GET /leaky", "viewer", "over-permissive")}, bad
        finally:
            srv.shutdown()


class Redirecting(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(302); self.send_header("Location", "http://127.0.0.1:1/login"); self.end_headers()
    def log_message(self, *a): pass


def test_redirects_not_followed_no_response_recorded_and_tokenless_role_is_anonymous():
    plan = {(r["id"], r["principal"]): r["expect_allowed"]
            for r in mx.make_plan(MANIFEST, {"principals": {"ghost": {"roles": ["admin"]}}})}
    assert plan[("GET /admin", "ghost")] is False  # no token_env => no token sent => anonymous
    srv = HTTPServer(("127.0.0.1", 0), Redirecting)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        assert mx.probe(base, "GET /admin", None) == 302
        assert mx.probe("http://127.0.0.1:1", "GET /admin", None) is None
    finally:
        srv.shutdown()
    row = [{"id": "GET /admin", "principal": "anonymous", "expect_allowed": False}]
    assert mx.evaluate(row, [{"id": "GET /admin", "principal": "anonymous", "status": 302}])[0]["kind"] == "over-permissive"
    assert mx.evaluate(row, [{"id": "GET /admin", "principal": "anonymous", "status": 302}], {302}) == []
    assert mx.evaluate(row, [{"id": "GET /admin", "principal": "anonymous", "status": None}])[0]["kind"] == "no-response"


def test_run_refuses_remote_host():
    code, _, err = cli(["run", "--base-url", "https://api.example.com"])
    assert code == 2 and "refusing" in err


def test_auth_model_mismatch_flags_off_server_error_and_endpoint():
    mcp = {"surface": "mcp", "id": "send_email", "visibility": "public", "auth_model": "oauth-scope",
           "endpoint": "/api/v1/inbox/mcp", "gated_by": ["INBOX_ENABLED"]}
    rest = {"surface": "rest", "id": "GET /v1/x", "visibility": "admin", "auth_model": "api-key", "roles": [], "scopes": []}
    pr = {"principals": {"apikey": {"token_env": "T", "auth_model": "api-key"},
                         "oauth": {"token_env": "T", "auth_model": "oauth-scope"},
                         "untyped": {"token_env": "T"}}}
    plan = {(r["id"], r["principal"]): r for r in mx.make_plan({"entries": [mcp, rest]}, pr, frozenset({"INBOX_ENABLED"}))}
    assert plan[("GET /v1/x", "apikey")]["expect_allowed"] is True
    assert plan[("GET /v1/x", "oauth")]["expect_allowed"] is False  # wrong key kind
    assert plan[("GET /v1/x", "untyped")]["expect_allowed"] is True  # no auth_model declared: no check
    assert plan[("send_email", "oauth")]["endpoint"] == "/api/v1/inbox/mcp" and plan[("send_email", "oauth")]["flag_off"]
    assert "flag_off" not in plan[("GET /v1/x", "apikey")]
    flag_row = [plan[("send_email", "oauth")]]
    res = lambda st: [{"id": "send_email", "principal": "oauth", "status": st}]
    assert mx.evaluate(flag_row, res(404)) == [] and mx.evaluate(flag_row, res(403)) == []
    assert mx.evaluate(flag_row, res(200))[0]["kind"] == "flag-off-reachable"
    row = [{"id": "GET /a", "principal": "p", "expect_allowed": True}]
    assert mx.evaluate(row, [{"id": "GET /a", "principal": "p", "status": 500}])[0]["kind"] == "server-error"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests passed")
