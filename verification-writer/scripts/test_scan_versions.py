#!/usr/bin/env python3
"""Self-check for scan-versions.py. Run: python3 test_scan_versions.py

Covers the integrity pass and doc discovery — the logic that decides whether a
verification item is visible to downstream consumers at all.
"""

import importlib.util
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


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests passed")
