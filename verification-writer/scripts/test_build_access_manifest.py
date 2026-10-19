#!/usr/bin/env python3
"""Self-check for build-access-manifest.py. Run: python3 test_build_access_manifest.py

Behavior under test: given page, REST, MCP and flow docs, the manifest carries
each entry with the declared visibility; undeclared means draft; contradictions
and duplicates surface as findings instead of being papered over.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "build_access_manifest", Path(__file__).with_name("build-access-manifest.py")
)
bam = importlib.util.module_from_spec(_spec)
sys.modules["build_access_manifest"] = bam
_spec.loader.exec_module(bam)


def write(root: Path, rel: str, frontmatter: str) -> None:
    p = root / "docs" / "verification" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{frontmatter}\n---\n\n# doc\n")


def fixture(root: Path) -> None:
    write(root, "pages/home.md", """path: /
generated_by: verification-writer@3.5.0
access:
  public: true
  auth_model: none
  visibility: public
user_types: [visitor]
affected_paths: [app/page.tsx]""")
    write(root, "pages/admin.md", """path: /admin
access:
  public: false
  auth_model: rbac
  required_roles: [admin]
  visibility: admin""")
    write(root, "api/list-events.md", """surface: rest
method: get
path: /v1/events
access:
  public: false
  auth_model: oauth-scope
  required_scopes: [events.read]
  tier: pro
  visibility: public""")  # publicly documented, authenticated API: valid
    write(root, "mcp/send-email.md", """surface: mcp
tool: send_email
access:
  public: false
  auth_model: oauth-scope
  required_scopes: [mail.send]""")  # no visibility => draft
    write(root, "flows/onboarding.md", """id: onboarding
user_types: [member]
access:
  public: true
  visibility: bogus""")


def by_id(manifest: dict) -> dict:
    return {e["id"]: e for e in manifest["entries"]}


def test_every_surface_lands_with_declared_visibility():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        fixture(root)
        m = bam.build(root)
        e = by_id(m)
        assert e["/"]["surface"] == "page" and e["/"]["visibility"] == "public"
        assert e["/admin"]["visibility"] == "admin" and e["/admin"]["roles"] == ["admin"]
        assert e["GET /v1/events"]["surface"] == "rest"
        assert e["GET /v1/events"]["scopes"] == ["events.read"]
        assert e["send_email"]["surface"] == "mcp"
        assert e["/"]["affected_paths"] == ["app/page.tsx"]
        assert e["/"]["user_types"] == ["visitor"]


def test_undeclared_visibility_is_draft_not_inferred():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        fixture(root)
        e = by_id(bam.build(root))
        assert e["send_email"]["visibility"] == "draft"  # scoped + undeclared, never guessed public


def test_findings_for_contradiction_invalid_value_and_duplicates():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        fixture(root)
        write(root, "pages/home-copy.md", "path: /\naccess:\n  public: true")
        write(root, "pages/members.md", "path: /members\naccess:\n  required_roles: [member]\n  visibility: public")
        findings = bam.build(root)["findings"]
        kinds = {(f["kind"], f["id"]) for f in findings}
        assert ("visibility-contradicts-access", "/members") in kinds, kinds
        assert ("visibility-contradicts-access", "GET /v1/events") not in kinds, kinds  # docs-public authenticated API
        assert ("invalid-visibility", "onboarding") in kinds, kinds
        assert ("duplicate-entry", "/") in kinds, kinds
        assert by_id(bam.build(root))["onboarding"]["visibility"] == "draft"


def test_check_mode_detects_stale_manifest_and_write_is_idempotent():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        fixture(root)
        assert bam.main(["--root", str(root), "--quiet"]) == 0
        first = (root / bam.MANIFEST_REL).read_text()
        assert bam.main(["--root", str(root), "--quiet"]) == 0
        assert (root / bam.MANIFEST_REL).read_text() == first
        assert bam.main(["--root", str(root), "--check", "--quiet"]) == 0
        write(root, "pages/new.md", "path: /new\naccess:\n  public: true\n  visibility: public")
        assert bam.main(["--root", str(root), "--check", "--quiet"]) == 2
        manifest = json.loads(first)
        order = [(e["surface"], e["id"]) for e in manifest["entries"]]
        assert order == sorted(order), order


def test_fail_on_findings_exit_code():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        fixture(root)
        assert bam.main(["--root", str(root), "--quiet", "--fail-on-findings"]) == 2


def test_gated_by_flows_into_manifest():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        write(root, "pages/inbound.md", "path: /inbound\naccess:\n  public: true\n  gated_by: [INBOUND_ROUTING_ENABLED]\n  visibility: draft")
        write(root, "pages/plain.md", "path: /plain\naccess:\n  public: true")
        e = by_id(bam.build(root))
        assert e["/inbound"]["gated_by"] == ["INBOUND_ROUTING_ENABLED"] and e["/plain"]["gated_by"] == []


def test_sibling_entries_with_same_paths_must_agree_on_gated_by():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        write(root, "pages/a.md", "path: /a\naffected_paths: [src/x.tsx]\naccess:\n  gated_by: [FLAG]")
        write(root, "pages/b.md", "path: /b\naffected_paths: [src/x.tsx]\naccess:\n  public: true")
        kinds = {(f["kind"], f["id"]) for f in bam.build(root)["findings"]}
        assert kinds == {("gated-by-inconsistent", "/a"), ("gated-by-inconsistent", "/b")}, kinds


def test_unsupported_surface_is_a_finding():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        write(root, "api/x.md", "surface: REST\nmethod: get\npath: /x\naccess:\n  public: true")
        m = bam.build(root)
        assert [f["kind"] for f in m["findings"]] == ["invalid-surface"] and m["entries"] == [], m


def test_comment_after_quoted_scalar_is_stripped():
    fm = bam.parse_frontmatter('path: "/v1/users" # route\nnote: "a # b"\n')
    assert fm["path"] == "/v1/users" and fm["note"] == "a # b", fm


def test_block_lists_crlf_bom_and_hash_in_quotes():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        p = root / "docs/verification/api/x.md"
        p.parent.mkdir(parents=True)
        p.write_bytes(("\ufeff---\r\nsurface: api\r\nmethod: get\r\npath: \"/s #1\"\r\naffected_paths:\r\n  - src/a.ts\r\n"
                       "access:\r\n  public: false\r\n  required_roles:\r\n    - admin\r\n    - ops\r\n  visibility: public\r\n---\r\n").encode())
        m = bam.build(root)
        e = m["entries"][0]
        assert e["surface"] == "rest" and e["id"] == "GET /s #1", e
        assert e["roles"] == ["admin", "ops"] and e["affected_paths"] == ["src/a.ts"], e
        assert m["findings"] == [], m["findings"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests passed")
