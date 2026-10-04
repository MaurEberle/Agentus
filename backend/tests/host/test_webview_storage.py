from __future__ import annotations

from pathlib import Path

from app.db.paths import webview_storage_dir
from app.host.window import webview_start_kwargs


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


def test_webview_debug_follows_dev_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path))
    monkeypatch.setenv("AGENTUS_NETWORK_DEV", "1")
    kwargs = webview_start_kwargs(icon_path="app.ico")
    assert kwargs["debug"] is True
    assert kwargs["icon"] == "app.ico"
    assert kwargs["private_mode"] is False
