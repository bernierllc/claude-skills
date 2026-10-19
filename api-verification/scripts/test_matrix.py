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


def test_run_refuses_remote_host():
    code, _, err = cli(["run", "--base-url", "https://api.example.com"])
    assert code == 2 and "refusing" in err


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests passed")
