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
        kinds = {(f["kind"], f["id"]) for f in res["findings"]}
        assert ("undocumented-route", "POST /v1/secret/{id}") in kinds, kinds
        assert ("undocumented-route", "DELETE /v1/events/{id}") in kinds, kinds
        assert ("spec-without-route", "GET /v1/ghost") in kinds, kinds
        assert ("mcp-no-description", "mystery") in kinds and ("mcp-no-annotations", "mystery") in kinds
        assert not any(k == "mcp-no-annotations" and i == "send_email" for k, i in kinds)
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


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests passed")
