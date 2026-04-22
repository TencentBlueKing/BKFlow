from __future__ import annotations

import importlib.util
import json
from io import BytesIO
from pathlib import Path


def _load_serve():
    path = Path("prototypes/serve.py")
    spec = importlib.util.spec_from_file_location("prototype_serve", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_handler(serve):
    handler = object.__new__(serve.PrototypeRequestHandler)
    handler.wfile = BytesIO()
    handler.send_response = lambda *args, **kwargs: None
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda *args, **kwargs: None
    handler.send_error = lambda *args, **kwargs: None
    return handler


def test_list_html_files_groups_new_sections(tmp_path, monkeypatch):
    serve = _load_serve()
    for section in ["masters", "features", "examples"]:
        root = tmp_path / section
        root.mkdir()
        (root / "index.html").write_text("<!doctype html>", encoding="utf-8")
        monkeypatch.setattr(serve, f"{section.upper()}_DIR", str(root))

    items = serve.list_html_files()
    sections = {section for section, _ in items}

    assert sections == {"masters", "features", "examples"}


def test_latest_mtime_scans_new_roots(tmp_path, monkeypatch):
    serve = _load_serve()
    for section in ["masters", "features", "examples", "assets"]:
        root = tmp_path / section
        root.mkdir()
        (root / "index.html").write_text("<!doctype html>", encoding="utf-8")
        monkeypatch.setattr(serve, f"{section.upper()}_DIR", str(root))

    mtime = serve.latest_mtime_under((serve.MASTERS_DIR, serve.FEATURES_DIR, serve.EXAMPLES_DIR, serve.ASSETS_DIR))

    assert isinstance(mtime, float)


def test_directory_url_injects_reload(tmp_path, monkeypatch):
    serve = _load_serve()
    root = tmp_path / "prototypes"
    foo = root / "masters" / "foo"
    foo.mkdir(parents=True)
    (foo / "index.html").write_text("<html><body>foo</body></html>", encoding="utf-8")
    monkeypatch.setattr(serve, "PROTOTYPES_ROOT", str(root))
    monkeypatch.setattr(serve, "MASTERS_DIR", str(root / "masters"))
    monkeypatch.setattr(serve, "FEATURES_DIR", str(root / "features"))
    monkeypatch.setattr(serve, "EXAMPLES_DIR", str(root / "examples"))
    monkeypatch.setattr(serve, "ASSETS_DIR", str(root / "assets"))

    captured = {}

    def fake_send_html_with_reload(self, full_path):
        captured["path"] = full_path
        self.wfile.write(serve.inject_reload_script(b"<html><body>foo</body></html>"))

    monkeypatch.setattr(serve.PrototypeRequestHandler, "_send_html_with_reload", fake_send_html_with_reload)

    handler = _make_handler(serve)
    handler.path = "/masters/foo/"
    serve.PrototypeRequestHandler.do_GET(handler)
    body = handler.wfile.getvalue().decode("utf-8")

    assert "foo" in body
    assert "fetch('/api/mtime')" in body
    assert captured["path"].endswith("masters/foo/index.html")


def test_root_index_only_lists_active_sections_even_if_output_exists(tmp_path, monkeypatch):
    serve = _load_serve()
    root = tmp_path / "prototypes"
    masters = root / "masters"
    features = root / "features"
    examples = root / "examples"
    output = root / "output"
    assets = root / "assets"
    for directory in [masters, features, examples, output, assets]:
        directory.mkdir(parents=True)
    (output / "legacy.html").write_text("<html><body>retired output</body></html>", encoding="utf-8")

    monkeypatch.setattr(serve, "PROTOTYPES_ROOT", str(root))
    monkeypatch.setattr(serve, "MASTERS_DIR", str(masters))
    monkeypatch.setattr(serve, "FEATURES_DIR", str(features))
    monkeypatch.setattr(serve, "EXAMPLES_DIR", str(examples))
    monkeypatch.setattr(serve, "ASSETS_DIR", str(assets))

    handler = _make_handler(serve)
    serve.PrototypeRequestHandler._send_index(handler)
    body = handler.wfile.getvalue().decode("utf-8")

    assert body.startswith("<!DOCTYPE html>")
    assert "BKFlow 原型展厅" in body
    assert "Feature 展区" in body
    assert "代表页面" in body
    assert "工具资源" in body
    assert "masters/" in body
    assert "features/" in body
    assert "examples/component-showcase.html" in body
    assert "fetch('/api/mtime')" in body
    assert "retired output" not in body
    assert "/output/legacy.html" not in body


def test_api_mtime_ignores_retired_output_directory(tmp_path, monkeypatch):
    serve = _load_serve()
    root = tmp_path / "prototypes"
    masters = root / "masters"
    features = root / "features"
    examples = root / "examples"
    output = root / "output"
    assets = root / "assets"
    for directory in [masters, features, examples, output, assets]:
        directory.mkdir(parents=True)
    (masters / "foo.html").write_text("<html></html>", encoding="utf-8")
    (output / "legacy.html").write_text("<html></html>", encoding="utf-8")
    (assets / "style.css").write_text("body{}", encoding="utf-8")

    monkeypatch.setattr(serve, "PROTOTYPES_ROOT", str(root))
    monkeypatch.setattr(serve, "MASTERS_DIR", str(masters))
    monkeypatch.setattr(serve, "FEATURES_DIR", str(features))
    monkeypatch.setattr(serve, "EXAMPLES_DIR", str(examples))
    monkeypatch.setattr(serve, "ASSETS_DIR", str(assets))

    mtimes = {
        str(masters): 10.0,
        str(features): 11.0,
        str(examples): 12.0,
        str(output): 13.0,
        str(assets): 14.0,
        str(masters / "foo.html"): 20.0,
        str(output / "legacy.html"): 50.0,
        str(assets / "style.css"): 40.0,
    }

    def fake_getmtime(path):
        return mtimes[str(path)]

    monkeypatch.setattr(serve.os.path, "getmtime", fake_getmtime)

    handler = _make_handler(serve)
    serve.PrototypeRequestHandler._send_mtime_json(handler)
    first = json.loads(handler.wfile.getvalue().decode("utf-8"))
    (output / "legacy.html").unlink()
    del mtimes[str(output / "legacy.html")]
    mtimes[str(output)] = 99.0
    handler = _make_handler(serve)
    serve.PrototypeRequestHandler._send_mtime_json(handler)
    second = json.loads(handler.wfile.getvalue().decode("utf-8"))

    assert first["mtime"] == 40
    assert second["mtime"] == 40
