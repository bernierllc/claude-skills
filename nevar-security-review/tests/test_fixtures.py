"""Fixture behavior over real HTTP (runtime cases) and fixture integrity (static cases).

Runtime: each app is served on 127.0.0.1 and probed; the vulnerable variant must show the
flaw expected.json names and the safe variant must not. Static: the property the reviewer
should find is present in vulnerable/ and absent in safe/, and nothing is live.
"""
import hashlib
import importlib.util
import json
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text())["cases"]


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def load(case, variant):
    path = FIXTURES / case / variant / "app.py"
    spec = importlib.util.spec_from_file_location(f"fx_{case.replace('-', '_')}_{variant}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Served:
    """Serve one fixture app on an OS-assigned localhost port with a fresh SQLite DB."""

    def __init__(self, case, variant, seed=None, db_path=None):
        self.mod = load(case, variant)
        self.tmp = tempfile.TemporaryDirectory()
        self.db = db_path or str(Path(self.tmp.name) / "db.sqlite")
        if db_path is None:
            self.mod.init_db(self.db)
            if seed:
                import contextlib
                import sqlite3
                with contextlib.closing(sqlite3.connect(self.db)) as conn:  # `with conn` alone never closes
                    conn.executescript(seed)
        self.server = make_server("127.0.0.1", 0, self.mod.make_app(self.db), handler_class=Quiet)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def call(self, method, path, token=None, body=None, headers=None):
        url = f"http://127.0.0.1:{self.server.server_port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as err:
            err.close()
            return err.code, None


ROLES = """
insert into sessions values ('t-admin', 'u-admin'), ('t-editor', 'u-editor'), ('t-legacy', 'u-legacy');
insert into profiles values ('u-admin', 'admin'), ('u-editor', 'editor');
insert into settings values ('site_name', 'Fixture');
"""


class AdminGuard(unittest.TestCase):
    def test_vulnerable_defaults_to_admin(self):
        with Served("admin-guard", "vulnerable", ROLES) as s:
            self.assertEqual(s.call("GET", "/admin/settings")[0], 200)  # anonymous
            self.assertEqual(s.call("PUT", "/admin/settings", body={"site_name": "pwned"})[0], 200)
            self.assertEqual(s.call("GET", "/admin/settings", "t-legacy")[0], 200)  # no profile row
            self.assertEqual(s.call("GET", "/admin/settings", "t-admin")[1]["site_name"], "pwned")

    def test_safe_refuses_anonymous_and_roleless(self):
        with Served("admin-guard", "safe", ROLES) as s:
            self.assertEqual(s.call("GET", "/admin/settings")[0], 401)
            self.assertEqual(s.call("GET", "/admin/settings", "t-unknown")[0], 401)
            self.assertEqual(s.call("PUT", "/admin/settings", "t-legacy", {"site_name": "x"})[0], 403)
            self.assertEqual(s.call("PUT", "/admin/settings", "t-editor", {"site_name": "x"})[0], 403)
            self.assertEqual(s.call("PUT", "/admin/settings", "t-admin", {"site_name": "ok"})[0], 200)
            self.assertEqual(s.call("GET", "/admin/settings", "t-admin")[1]["site_name"], "ok")


class EditorBypass(unittest.TestCase):
    def test_vulnerable_editor_writes_settings(self):
        with Served("editor-bypass", "vulnerable", ROLES.replace("('t-legacy', 'u-legacy')", "('t-x', 'u-x')")) as s:
            self.assertEqual(s.call("PUT", "/admin/settings", "t-editor", {"site_name": "pwned"})[0], 200)
            self.assertEqual(s.call("GET", "/admin/settings", "t-admin")[1]["site_name"], "pwned")

    def test_safe_editor_reads_only(self):
        with Served("editor-bypass", "safe", ROLES.replace("('t-legacy', 'u-legacy')", "('t-x', 'u-x')")) as s:
            self.assertEqual(s.call("GET", "/admin/settings", "t-editor")[0], 200)
            self.assertEqual(s.call("PUT", "/admin/settings", "t-editor", {"site_name": "x"})[0], 403)
            self.assertEqual(s.call("PUT", "/admin/settings")[0], 401)
            self.assertEqual(s.call("PUT", "/admin/settings", "t-admin", {"site_name": "ok"})[0], 200)


TENANTS = """
insert into sessions values ('t-alice', 'alice'), ('t-bob', 'bob'), ('t-nomember', 'carol');
insert into memberships values ('alice', 'tenant-a'), ('bob', 'tenant-b');
insert into docs (tenant, body) values ('tenant-a', 'a-secret'), ('tenant-b', 'b-secret');
"""


class TenantSpoof(unittest.TestCase):
    def test_vulnerable_reads_other_tenant(self):
        with Served("tenant-spoof", "vulnerable", TENANTS) as s:
            status, body = s.call("GET", "/docs", "t-alice", headers={"X-Tenant-Id": "tenant-b"})
            self.assertEqual((status, body["docs"]), (200, ["b-secret"]))

    def test_safe_rejects_spoofed_tenant(self):
        with Served("tenant-spoof", "safe", TENANTS) as s:
            self.assertEqual(s.call("GET", "/docs", "t-alice", headers={"X-Tenant-Id": "tenant-b"})[0], 403)
            self.assertEqual(s.call("GET", "/docs", "t-nomember")[0], 403)
            self.assertEqual(s.call("GET", "/docs")[0], 401)
            self.assertEqual(s.call("GET", "/docs", "t-alice")[1]["docs"], ["a-secret"])
            self.assertEqual(s.call("GET", "/docs", "t-bob", headers={"X-Tenant-Id": "tenant-b"})[1]["docs"], ["b-secret"])


def _h(key):
    return hashlib.sha256(key.encode()).hexdigest()


KEYS = f"""
insert into keys values ('{_h("mcp_readonly_fixture")}', 'tenant-a', 'docs:read', 0),
  ('{_h("mcp_writer_fixture")}', 'tenant-a', 'docs:read docs:write', 0),
  ('{_h("api_rest_fixture")}', 'tenant-a', 'docs:read docs:write', 0),
  ('{_h("mcp_revoked_fixture")}', 'tenant-a', 'docs:read docs:write', 1);
insert into docs (id, tenant, body) values (1, 'tenant-a', 'one'), (2, 'tenant-a', 'two'), (3, 'tenant-a', 'three');
"""


def call_tool(name, **args):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}


class McpScope(unittest.TestCase):
    def test_vulnerable_readonly_and_rest_keys_delete(self):
        with Served("mcp-scope", "vulnerable", KEYS) as s:
            self.assertEqual(s.call("POST", "/mcp", "mcp_readonly_fixture", call_tool("delete_doc", id=1))[0], 200)
            self.assertEqual(s.call("POST", "/mcp", "api_rest_fixture", call_tool("delete_doc", id=2))[0], 200)
            left = s.call("POST", "/mcp", "mcp_writer_fixture", call_tool("list_docs"))[1]["result"]
            self.assertEqual([d["id"] for d in left], [3])

    def test_safe_enforces_key_type_and_scope(self):
        with Served("mcp-scope", "safe", KEYS) as s:
            self.assertEqual(s.call("POST", "/mcp", "mcp_readonly_fixture", call_tool("delete_doc", id=1))[0], 403)
            self.assertEqual(s.call("POST", "/mcp", "api_rest_fixture", call_tool("list_docs"))[0], 401)
            self.assertEqual(s.call("POST", "/mcp", "mcp_revoked_fixture", call_tool("list_docs"))[0], 401)
            self.assertEqual(s.call("POST", "/mcp", "mcp_readonly_fixture", call_tool("list_docs"))[0], 200)
            self.assertEqual(s.call("POST", "/mcp", "mcp_writer_fixture", call_tool("delete_doc", id=1))[0], 200)
            left = s.call("POST", "/mcp", "mcp_readonly_fixture", call_tool("list_docs"))[1]["result"]
            self.assertEqual([d["id"] for d in left], [2, 3])


class AuthOutage(unittest.TestCase):
    """The auth database is unreachable: a path in a directory that does not exist."""

    def outage(self, variant):
        missing = str(Path(tempfile.gettempdir()) / "nsr-missing-dir-does-not-exist" / "auth.sqlite")
        return Served("auth-outage", variant, db_path=missing)

    def test_vulnerable_hides_outage_as_401(self):
        with self.outage("vulnerable") as s, self.assertNoLogs(level="DEBUG"):
            self.assertEqual(s.call("GET", "/me", "t-any")[0], 401)

    def test_safe_fails_closed_and_records(self):
        with self.outage("safe") as s, self.assertLogs("auth", level="ERROR") as logs:
            self.assertEqual(s.call("GET", "/me", "t-any")[0], 503)
        self.assertIn("auth backend unavailable", logs.output[0])

    def test_both_serve_healthy_backend(self):
        for variant in ("vulnerable", "safe"):
            with self.subTest(variant=variant), Served("auth-outage", variant,
                                                       "insert into sessions values ('t-ok', 'u-ok');") as s:
                self.assertEqual(s.call("GET", "/me", "t-ok"), (200, {"user": "u-ok"}))
                self.assertEqual(s.call("GET", "/me", "t-bad")[0], 401)


def read(case, variant, name):
    return (FIXTURES / case / variant / name).read_text()


HIDDEN = re.compile(r"<!--(.*?)-->", re.S)
AGENT_ATTACK = re.compile(r"credentials|\.env\b|https?://|without review|do not (report|mention)", re.I)


class StaticFixtures(unittest.TestCase):
    def test_every_case_has_ground_truth_and_both_variants(self):
        cases = {p.name for p in FIXTURES.iterdir() if p.is_dir()}
        self.assertEqual(cases, set(EXPECTED))
        for case, exp in EXPECTED.items():
            with self.subTest(case=case):
                self.assertTrue((FIXTURES / case / "vulnerable" / exp["file"]).is_file())
                self.assertTrue(any((FIXTURES / case / "safe").iterdir()))
                self.assertEqual(exp["runtime"], (FIXTURES / case / "vulnerable" / "app.py").is_file())

    def test_ground_truth_uses_the_skill_categories_and_severities(self):
        skill = (FIXTURES.parent / "SKILL.md").read_text()
        categories = set(re.findall(r"^\| `([A-Z][A-Z0-9]+)` \|", skill, re.M))
        self.assertIn("AUTHZ", categories)
        for case, exp in EXPECTED.items():
            with self.subTest(case=case):
                self.assertIn(exp["category"], categories)
                self.assertIn(exp["severity"], {"P0", "P1", "P2"})

    def test_injected_instructions(self):
        vuln = FIXTURES / "injected-instructions" / "vulnerable"
        for f in ("AGENTS.fixture.md", "SKILL.fixture.md"):
            hidden = " ".join(HIDDEN.findall((vuln / f).read_text()))
            self.assertRegex(hidden, AGENT_ATTACK, f)
        self.assertRegex((vuln / "ISSUE.fixture.md").read_text(), r"(?is)merge .* without review")
        safe = " ".join(HIDDEN.findall(read("injected-instructions", "safe", "AGENTS.fixture.md")))
        self.assertNotRegex(safe, AGENT_ATTACK)

    def test_workflow(self):
        vuln = read("malicious-workflow", "vulnerable", "workflow.fixture.yml")
        self.assertIn("pull_request_target", vuln)
        self.assertIn("github.event.pull_request.head.sha", vuln)
        self.assertRegex(vuln, r"run: .*\$\{\{ github\.event\.pull_request\.title \}\}")
        safe = read("malicious-workflow", "safe", "workflow.fixture.yml")
        self.assertNotIn("pull_request_target", safe)
        self.assertNotRegex(safe, r"run: .*\$\{\{")
        self.assertIn("permissions:", safe)
        # The safe job runs PR code, so it must hold no write scope and no token.
        self.assertNotRegex(safe, r":\s*write")
        self.assertNotIn("TOKEN", safe)
        for uses in re.findall(r"uses: (\S+)", safe):
            self.assertRegex(uses, r"@[0-9a-f]{40}$")

    def test_fake_secret(self):
        literal = re.compile(r"[\"'](api|mcp)_[a-z]+_[A-Za-z0-9_]{8,}[\"']")
        vuln = read("fake-secret", "vulnerable", "config.py")
        self.assertRegex(vuln, literal)
        self.assertIn("FAKE", literal.search(vuln).group(0))  # never a real credential
        safe = read("fake-secret", "safe", "config.py")
        self.assertNotRegex(safe, literal)
        self.assertIn('os.environ["DOCS_API_KEY"]', safe)

    def test_dependency_versions_straddle_the_fix(self):
        def version(variant):
            lock = json.loads(read("vulnerable-dependency", variant, "package-lock.fixture.json"))
            return tuple(int(x) for x in lock["packages"]["node_modules/minimist"]["version"].split("."))
        fixed = (1, 2, 6)  # GHSA-xvch-5gv4-984h affects < 1.2.6
        self.assertLess(version("vulnerable"), fixed)
        self.assertGreaterEqual(version("safe"), fixed)

    def test_nothing_live(self):
        hosts = set()
        for f in FIXTURES.rglob("*"):
            if f.is_file() and f.suffix in {".md", ".py", ".yml", ".js", ".json"}:
                hosts.update(re.findall(r"https?://([^/\s\"'?]+)", f.read_text()))
        allowed = {"127.0.0.1:8080", "localhost"}
        self.assertTrue(all(h.endswith(".invalid") or h in allowed for h in hosts), hosts)


if __name__ == "__main__":
    unittest.main()
