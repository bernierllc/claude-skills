#!/usr/bin/env python3
"""Self-check for scan-versions.py. Run: python3 test_scan_versions.py

Covers the integrity pass and doc discovery — the logic that decides whether a
verification item is visible to downstream consumers at all.
"""

import importlib.util
import json
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
            "scan_version": sv.SCAN_VERSION - 1,
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


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests passed")
