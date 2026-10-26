#!/usr/bin/env python3
"""Self-check for scan-versions.py. Run: python3 test_scan_versions.py

Covers the integrity pass and doc discovery — the logic that decides whether a
verification item is visible to downstream consumers at all.
"""

import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "scan_versions", Path(__file__).with_name("scan-versions.py")
)
sv = importlib.util.module_from_spec(_spec)
sys.modules["scan_versions"] = sv  # @dataclass resolves annotations via sys.modules
_spec.loader.exec_module(sv)


def test_scan_items_flags_duplicates_and_malformed():
    doc = "\n".join(
        [
            "- [ ] [smoke] **EVT-01** Do a thing --- It happens. *Expected: success*",
            "- [ ] [smoke] **EVT-01** Do it again --- It happens. *Expected: success*",
            "- [ ] [standard] **EVT-02** No separator here. *Expected: success*",
            "- [ ] [standard] **EVT-03** Missing the tail --- nothing follows",
            "- [ ] plain checklist line with no id",
            "- [ ] [standard] **OTHER-01** Wrong namespace --- x. *Expected: success*",
        ]
    )
    r = sv.scan_items(doc, "EVT")
    assert r["item_ids"] == ["EVT-01", "EVT-02", "EVT-03", "OTHER-01"], r["item_ids"]
    assert r["duplicate_item_ids"] == ["EVT-01"]
    assert r["namespace_mismatches"] == ["OTHER-01"]
    reasons = [m["reason"] for m in r["malformed_items"]]
    assert reasons == ["missing-separator", "missing-expected", "no-bold-id"], reasons


def test_scan_items_accepts_lowercase_id_suffixes():
    """Downstream parses `OSB-03b`, so reporting it malformed is a false positive."""
    doc = "- [ ] [standard] **OSB-03b** Do a thing --- It happens. *Expected: success*"
    r = sv.scan_items(doc, "OSB")
    assert r["item_ids"] == ["OSB-03b"], r["item_ids"]
    assert r["malformed_items"] == [], r["malformed_items"]


def test_scan_items_ignores_fenced_code():
    doc = "\n".join(["```markdown", "- [ ] example line with no id", "```"])
    assert sv.scan_items(doc, None)["malformed_items"] == []


def test_build_integrity_flags_cross_doc_namespace_collision():
    a = sv.FileResult(path="a.md", sha256="x", scanned_at="now", id_namespace="USC")
    b = sv.FileResult(path="b.md", sha256="y", scanned_at="now", id_namespace="USC")
    c = sv.FileResult(path="c.md", sha256="z", scanned_at="now", id_namespace="EVT")
    integrity = sv.build_integrity([a, b, c])
    assert integrity["duplicate_namespaces"] == [
        {"id_namespace": "USC", "docs": ["a.md", "b.md"]}
    ]
    assert integrity["error_count"] == 1


def test_discover_files_covers_root_docs_and_skips_reports():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pages").mkdir()
        (root / "findings").mkdir()
        for rel in ("index.md", "README.md", "shared.md", "01-legacy.md",
                    "pages/login.md", "findings/report.md"):
            (root / rel).write_text("x")
        found = {str(p.relative_to(root)) for p in sv.discover_files(root)}
        assert found == {"shared.md", "01-legacy.md", "pages/login.md"}, found


def test_cache_entry_without_item_ids_is_refreshed():
    stale = {"sha256": "abc", "scanned_at": "2999-01-01T00:00:00Z"}
    assert sv.cache_entry_fresh(stale, "abc") is False
    fresh = {**stale, "item_ids": []}
    assert sv.cache_entry_fresh(fresh, "abc") is True


def test_stale_scan_version_discards_whole_cache():
    """A cache written by an older parser must not survive a scanner change.

    The per-file entries are keyed on the doc's sha256 alone, so a doc whose
    bytes have not changed would keep reporting whatever the old parsers found
    — which is how a fixed item-ID regex stayed invisible and the report kept
    citing 64 defects that no longer existed.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vroot = root / "docs" / "verification" / "pages"
        vroot.mkdir(parents=True)
        doc = vroot / "widgets.md"
        doc.write_text(
            "---\nid_namespace: WID\n---\n\n"
            "- [ ] [smoke] **WID-01** Do a thing --- It happens. *Expected: success*\n"
        )

        cache_path = root / "docs" / "verification" / sv.CACHE_FILENAME
        rel = str(doc.relative_to(root))
        cache_path.write_text(json.dumps({
            "scan_version": 3,
            "scanned_at": "2999-01-01T00:00:00Z",
            "files": {rel: {
                "sha256": sv.sha256_of(doc),
                "scanned_at": "2999-01-01T00:00:00Z",
                "item_ids": [],
                "malformed_items": ["phantom defect from the old parser"],
            }},
        }))

        argv = sys.argv
        sys.argv = ["scan-versions.py", "--root", str(root),
                    "--current-version", "3.4.4", "--quiet", "--no-gitignore-touch"]
        try:
            sv.main()
        finally:
            sys.argv = argv

        written = json.loads(cache_path.read_text())
        assert written["scan_version"] == sv.SCAN_VERSION, written["scan_version"]
        entry = written["files"][rel]
        assert entry["malformed_items"] == [], entry["malformed_items"]
        assert entry["item_ids"] == ["WID-01"], entry["item_ids"]


def test_api_verification_writer_stamp_is_not_malformed():
    with tempfile.TemporaryDirectory() as d:
        doc = Path(d) / "list-events.md"
        doc.write_text("---\nid_namespace: EVT\ngenerated_by: api-verification-writer@1.0.0\n---\n"
                       "- [ ] [smoke] **EVT-01** Call it --- It works. *Expected: success*\n")
        r = sv.scan_file(doc, {}, "docs/verification/api/list-events.md")
        assert "generated_by-malformed" not in r.issues, r.issues
        assert r.skill_version is None  # not ours to version-check
        assert r.item_ids == ["EVT-01"], r.item_ids


def test_narrative_api_doc_needs_no_id_namespace():
    with tempfile.TemporaryDirectory() as d:
        doc = Path(d) / "list-events.md"
        doc.write_text("---\ngenerated_by: api-verification-writer@1.0.0\n---\n# List events\n")
        r = sv.scan_file(doc, {}, "docs/verification/api/list-events.md")
        assert "id_namespace-missing" not in r.issues, r.issues
        r = sv.scan_file(doc, {}, "docs/verification/pages/list-events.md")  # the exemption is for api/ and mcp/ docs only
        assert "id_namespace-missing" in r.issues, r.issues



def test_current_version_defaults_to_the_skill_md_version():
    skill_md = Path(sv.__file__).resolve().parent.parent / "SKILL.md"
    declared = re.search(r"^version:\s*[\"']?([0-9][^\s\"']*)", skill_md.read_text(), re.M).group(1)
    assert sv.skill_version() == declared
    import json as _json
    hooks = _json.loads((skill_md.parent / "hooks.json").read_text())
    assert not any("--current-version" in h["command"] for h in hooks["hooks"])  # a pinned number goes stale


def test_skill_version_tolerates_a_v_prefix_and_prerelease_tag():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "scripts").mkdir()
        (Path(d) / "SKILL.md").write_text("---\nname: x\nversion: v3.6.6-beta\n---\n")
        real = sv.__file__
        sv.__file__ = str(Path(d) / "scripts" / "scan-versions.py")
        try:
            assert sv.skill_version() == "3.6.6"
        finally:
            sv.__file__ = real


def test_sibling_docs_are_recognised_in_a_real_run():
    import contextlib, io
    with tempfile.TemporaryDirectory() as d:
        api = Path(d) / "docs" / "verification" / "api" / "events"
        api.mkdir(parents=True)
        (api / "get-events.md").write_text("---\ngenerated_by: api-verification-writer@1.0.0\naffected_paths:\n  - \"src/a.ts\"\n---\n# GET /events\n")
        out = io.StringIO()
        argv = sys.argv
        sys.argv = ["scan-versions", "--root", d, "--current-version", "3.7.8"]
        try:
            with contextlib.redirect_stdout(out):
                sv.main()
        finally:
            sys.argv = argv
        report = json.loads(out.getvalue())
        assert report["integrity"]["missing_id_namespace"] == [], report["integrity"]
        assert report["summary"]["stale"] == 0, report["summary"]


def test_cache_from_the_sibling_bug_is_discarded():
    import contextlib, io

    def run(root):
        out, argv = io.StringIO(), sys.argv
        sys.argv = ["scan-versions", "--root", root, "--current-version", "3.7.9"]
        try:
            with contextlib.redirect_stdout(out):
                sv.main()
        finally:
            sys.argv = argv
        return json.loads(out.getvalue())

    with tempfile.TemporaryDirectory() as d:
        vroot = Path(d) / "docs" / "verification"
        (vroot / "api").mkdir(parents=True)
        (vroot / "api" / "x.md").write_text("---\ngenerated_by: api-verification-writer@1.0.0\n---\n# X\n")
        run(d)
        cache_path = vroot / sv.CACHE_FILENAME
        cache = json.loads(cache_path.read_text())
        cache["scan_version"] = 3  # what the buggy release wrote
        cache["files"]["docs/verification/api/x.md"]["issues"] = ["id_namespace-missing"]
        cache_path.write_text(json.dumps(cache))
        assert run(d)["integrity"]["missing_id_namespace"] == []


def test_missing_skill_md_asks_for_current_version():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "scripts").mkdir()
        real = sv.__file__
        sv.__file__ = str(Path(d) / "scripts" / "scan-versions.py")
        try:
            sv.skill_version()
            raise AssertionError("expected SystemExit")
        except SystemExit as e:
            assert "--current-version" in str(e), e
        finally:
            sv.__file__ = real


def test_summary_buckets_add_up_to_total():
    """Every doc lands in exactly one of current/stale/other_skill/missing/stamp buckets."""
    with tempfile.TemporaryDirectory() as d:
        v = Path(d) / "docs" / "verification"
        (v / "api").mkdir(parents=True)
        (v / "pages").mkdir()
        item = "- [ ] [smoke] **{n}-01** Do it --- Works. *Expected: success*\n"
        (v / "pages" / "cur.md").write_text("---\nid_namespace: CUR\ngenerated_by: verification-writer@3.7.10\n---\n" + item.format(n="CUR"))
        (v / "pages" / "old.md").write_text("---\nid_namespace: OLD\ngenerated_by: verification-writer@3.4.4\n---\n" + item.format(n="OLD"))
        (v / "pages" / "nostamp.md").write_text("---\nid_namespace: NOS\n---\n" + item.format(n="NOS"))
        (v / "pages" / "bad.md").write_text("---\nid_namespace: BAD\ngenerated_by: nonsense\n---\n" + item.format(n="BAD"))
        (v / "pages" / "nofm.md").write_text(item.format(n="NOF"))
        (v / "api" / "x.md").write_text("---\ngenerated_by: api-verification-writer@1.0.0\n---\n# X\n")
        out, argv = io.StringIO(), sys.argv
        sys.argv = ["scan-versions", "--root", d, "--current-version", "3.7.10"]
        try:
            with contextlib.redirect_stdout(out):
                sv.main()
        finally:
            sys.argv = argv
        s = json.loads(out.getvalue())["summary"]
        parts = ("current", "stale", "other_skill", "missing_frontmatter", "stamp_missing", "stamp_malformed")
        assert sum(s[k] for k in parts) == s["total"] == 6, s
        assert (s["current"], s["stale"], s["other_skill"]) == (1, 1, 1), s


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests passed")


def test_current_version_defaults_to_the_skill_md_version():
    skill_md = Path(sv.__file__).resolve().parent.parent / "SKILL.md"
    declared = re.search(r"^version:\s*[\"']?([0-9][^\s\"']*)", skill_md.read_text(), re.M).group(1)
    assert sv.skill_version() == declared
    import json as _json
    hooks = _json.loads((skill_md.parent / "hooks.json").read_text())
    assert not any("--current-version" in h["command"] for h in hooks["hooks"])  # a pinned number goes stale


def test_skill_version_tolerates_a_v_prefix_and_prerelease_tag():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "scripts").mkdir()
        (Path(d) / "SKILL.md").write_text("---\nname: x\nversion: v3.6.6-beta\n---\n")
        real = sv.__file__
        sv.__file__ = str(Path(d) / "scripts" / "scan-versions.py")
        try:
            assert sv.skill_version() == "3.6.6"
        finally:
            sv.__file__ = real
