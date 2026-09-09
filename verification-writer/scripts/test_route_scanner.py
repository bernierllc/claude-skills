"""Tests for route-scanner's app-dir detection.

The on-file-edit hook runs `route-scanner.py --quiet` with no path argument,
so the default has to find the App Router root itself. It used to hardcode
`./app`, which meant the hook died on every `src/app` project.
"""

import importlib.util

from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "route_scanner", Path(__file__).parent / "route-scanner.py"
)
route_scanner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(route_scanner)




def test_default_prefers_src_app(tmp_path, monkeypatch):
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "app").mkdir()
    monkeypatch.chdir(tmp_path)
    assert route_scanner.default_app_dir() == "./src/app"


def test_default_falls_back_to_app(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    monkeypatch.chdir(tmp_path)
    assert route_scanner.default_app_dir() == "./app"


def test_default_names_app_when_neither_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert route_scanner.default_app_dir() == "./app"
