from __future__ import annotations

from pathlib import Path

from app.db.paths import webview_storage_dir
from app.host.window import spa_window_url, webview_start_kwargs


def test_webview_storage_sits_next_to_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTUS_NETWORK_DEV", raising=False)
    folder = webview_storage_dir()
    assert folder == tmp_path / "webview"
    kwargs = webview_start_kwargs(icon_path=None)
    assert kwargs["private_mode"] is False
    assert kwargs["gui"] == "edgechromium"
    assert kwargs["debug"] is False
    assert Path(kwargs["storage_path"]) == folder
    assert folder.is_dir()


def test_spa_window_url_uses_index_mtime(tmp_path: Path, monkeypatch) -> None:
    dist = tmp_path / "spa"
    dist.mkdir()
    index = dist / "index.html"
    index.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setenv("AGENTUS_NETWORK_STATIC_DIR", str(dist))
    stamp = str(int(index.stat().st_mtime))
    assert spa_window_url(8765) == f"http://127.0.0.1:8765/?v={stamp}"


def test_webview_debug_follows_dev_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path))
    monkeypatch.setenv("AGENTUS_NETWORK_DEV", "1")
    kwargs = webview_start_kwargs(icon_path="app.ico")
    assert kwargs["debug"] is True
    assert kwargs["icon"] == "app.ico"
    assert kwargs["private_mode"] is False
