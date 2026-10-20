#!/usr/bin/env python3
"""Self-check for scan-api-surfaces.py. Run: python3 test_scan_api_surfaces.py

Behavior under test: spec, MCP dump and code routes are merged; disagreements
between them become findings; path params normalize across frameworks.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location("scan_api_surfaces", Path(__file__).with_name("scan-api-surfaces.py"))
sas = importlib.util.module_from_spec(_spec)
sys.modules["scan_api_surfaces"] = sas
_spec.loader.exec_module(sas)


def build_repo(root: Path) -> None:
    (root / "openapi.json").write_text(json.dumps({
        "security": [{"bearer": ["events.read"]}],
        "paths": {
            "/v1/events": {"get": {"summary": "List events"}},
            "/v1/health": {"get": {"security": []}},
            "/v1/ghost": {"get": {}},
        }}))
    (root / "src").mkdir()
    (root / "src/routes.ts").write_text(
        "app.get('/v1/events', h)\napp.post('/v1/secret/:id', h)\napp.get('/health', h)\n")
    (root / "app/v1/events/[id]").mkdir(parents=True)
    (root / "app/v1/events/[id]/route.ts").write_text("export async function DELETE() {}\n")
    (root / "tools.json").write_text(json.dumps({"tools": [
        {"name": "send_email", "description": "Send", "annotations": {"destructiveHint": True}, "outputSchema": {}},
        {"name": "mystery"}]}))


def run(root: Path) -> dict:
    out = []
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert sas.main(["--root", str(root), "--mcp-tools", str(root / "tools.json")]) == 0
    return json.loads(buf.getvalue())


def test_normalize():
    assert sas.normalize("/a/:id/[slug]/<int:n>/{x}/") == "/a/{id}/{slug}/{n}/{x}"


def test_findings():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        build_repo(root)
        res = run(root)
        mcp = {f["kind"]: f for f in res["findings"] if f["kind"].startswith("mcp-")}
        assert mcp["mcp-no-description"]["tools"] == ["mystery"] and mcp["mcp-no-annotations"]["tools"] == ["mystery"]
        assert "send_email" not in mcp["mcp-no-annotations"]["tools"]
        assert mcp["mcp-no-output-schema"]["tools"] == ["send_email", "mystery"]  # empty outputSchema counts as missing
        assert mcp["mcp-no-output-schema"]["mutating_tools"] == ["send_email"]
        assert sas.MUTATING_RE.match("delete_sender") and not sas.MUTATING_RE.match("list_domains")
        kinds = {(f["kind"], f["id"]) for f in res["findings"] if not f["kind"].startswith("mcp-")}
        assert ("undocumented-route", "POST /v1/secret/{id}") in kinds, kinds
        assert ("undocumented-route", "DELETE /v1/events/{id}") in kinds, kinds
        assert ("spec-without-route", "GET /v1/ghost") in kinds, kinds
        # /health in code matches the spec's /v1/health by suffix; global security covers /v1/events
        assert ("undocumented-route", "GET /health") not in kinds
        ops = {(o["method"], o["path"]): o for o in res["operations"]}
        assert ops[("GET", "/v1/events")]["scopes"] == ["events.read"]
        assert ops[("GET", "/v1/health")]["explicitly_public"] is True


def scan(root: Path, *extra: str) -> tuple[int, dict]:
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        code = sas.main(["--root", str(root), *extra])
    return code, (json.loads(buf.getvalue()) if buf.getvalue() else {})


def test_wrong_spec_gives_one_finding_not_noise():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "openapi.json").write_text(json.dumps({"security": [], "paths": {"/legacy/a": {"get": {}}}}))
        (root / "src").mkdir()
        (root / "src/r.ts").write_text("".join(f"app.get('/api/v1/r{i}', h)\n" for i in range(5)))
        _, res = scan(root)
        assert [f["kind"] for f in res["findings"]] == ["spec-code-mismatch"], res["findings"]


def test_routes_without_any_spec_are_flagged():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "src").mkdir()
        (root / "src/r.ts").write_text("app.get('/api/v1/a', h)\n")
        _, res = scan(root)
        assert [f["kind"] for f in res["findings"]] == ["spec-missing"], res["findings"]


def test_empty_security_alternative_is_public_and_scoped_no_spec_gives_one_finding():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "openapi.json").write_text(json.dumps({"paths": {"/api/v1/x": {"get": {"security": [{}, {"k": []}]}}}}))
        _, res = scan(root)
        assert res["operations"][0]["explicitly_public"] is True
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "src").mkdir()
        (root / "src/r.ts").write_text("app.get('/api/v1/a', h)\n")
        _, res = scan(root, "--prefix", "/api/v1")
        assert [f["kind"] for f in res["findings"]] == ["spec-missing"], res["findings"]


def test_prefix_scopes_out_internal_routes():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "openapi.json").write_text(json.dumps({"security": [{"k": []}], "paths": {"/api/v1/a": {"get": {}}}}))
        (root / "src").mkdir()
        (root / "src/r.ts").write_text("app.get('/api/v1/a', h)\napp.get('/api/staff/x', h)\napp.get('/api/v1/b', h)\n")
        _, res = scan(root)
        assert {f["id"] for f in res["findings"]} == {"GET /api/staff/x", "GET /api/v1/b"}
        _, res = scan(root, "--prefix", "/api/v1")
        assert {f["id"] for f in res["findings"]} == {"GET /api/v1/b"}, res["findings"]


def test_directory_spec_is_a_clear_error_and_remote_url_refused():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "spec").mkdir()
        assert scan(root, "--openapi", str(root / "spec"))[0] == 1
        assert scan(root, "--openapi", "https://api.example.com/openapi.json")[0] == 1


def test_test_named_dir_is_scanned_nested_checkout_skipped_dupes_and_options_dropped():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "openapi.json").write_text(json.dumps({"security": [], "paths": {"/api/v1/x/test": {"post": {}}}}))
        (root / "app/api/v1/x/test").mkdir(parents=True)
        (root / "app/api/v1/x/test/route.ts").write_text("export async function POST() {}\nexport async function OPTIONS() {}\n")
        (root / "src").mkdir()
        (root / "src/a.test.ts").write_text("app.get('/api/v1/from-test-file', h)\n")
        (root / "src/mcp.ts").write_text("app.post('/api/v1/mcp', h)\n")
        stale = root / ".claude/worktrees/old"
        (stale / "app/api/v1/x/test").mkdir(parents=True)
        (stale / ".git").write_text("gitdir: elsewhere")
        (stale / "app/api/v1/x/test/route.ts").write_text("export async function POST() {}\n")
        (stale / "app/api/v1/marketing").mkdir()
        (stale / "app/api/v1/marketing/route.ts").write_text("export async function GET() {}\n")
        _, res = scan(root)
        assert res["skipped_nested_repos"] == [".claude/worktrees/old"]
        assert [(r["method"], r["path"]) for r in res["code_routes"] if "x/test" in r["path"]] == [("POST", "/api/v1/x/test")]
        assert not any("from-test-file" in r["path"] or "marketing" in r["path"] for r in res["code_routes"])
        assert {f["id"] for f in res["findings"]} == {"POST /api/v1/mcp"}, res["findings"]
        _, res = scan(root, "--exclude", "/api/v1/mcp")
        assert res["findings"] == [], res["findings"]


def test_param_names_next_groups_non_dict_spec_and_client_calls():
    assert sas.normalize("(api)/v1/users/[id]/@modal") == "/v1/users/{id}"
    assert sas.same_route("/v1/users/{userId}", "/v1/users/{id}")
    assert sas.local_host("127.0.0.1") and not sas.local_host("169.254.169.254")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "openapi.json").write_text("[]")
        assert scan(root)[0] == 1
        (root / "openapi.json").write_text(json.dumps({"security": [], "paths": {"/u": {"get": {}}}}))
        (root / "src").mkdir()
        (root / "src/c.ts").write_text("const r = await api.get('/u2')\napp.get('/u', h)\n")
        assert scan(root)[1]["findings"] == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests passed")


def test_exclude_silences_spec_without_route_for_that_path():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "openapi.json").write_text(json.dumps({"security": [], "paths": {"/api/v1/a": {"get": {}}, "/api/v1/openapi.json": {"get": {}}}}))
        (root / "src").mkdir()
        (root / "src/r.ts").write_text("app.get('/api/v1/a', h)\n")
        _, res = scan(root)
        assert [f["id"] for f in res["findings"]] == ["GET /api/v1/openapi.json"], res["findings"]
        _, res = scan(root, "--exclude", "/api/v1/openapi.json")
        assert res["findings"] == [], res["findings"]


def test_exclude_drops_security_finding_and_never_suffix_matches_short_paths():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "openapi.json").write_text(json.dumps({"paths": {"/api/v1/mcp": {"post": {}}, "/users": {"get": {}}, "/{id}": {"get": {}}}}))
        (root / "src").mkdir()
        _, res = scan(root, "--exclude", "/api/v1/mcp", "--exclude", "/api/v1/admin/users", "--exclude", "/api/v1/users/{id}")
        assert {f["id"] for f in res["findings"]} == {"GET /users", "GET /{id}"}, res["findings"]
