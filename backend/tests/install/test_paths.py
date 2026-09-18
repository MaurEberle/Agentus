from __future__ import annotations

import sys
from pathlib import Path

from app.http.paths import static_dir


def test_static_dir_env(tmp_path: Path, monkeypatch) -> None:
    dist = tmp_path / "spa"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setenv("AGENTUS_NETWORK_STATIC_DIR", str(dist))
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert static_dir() == dist.resolve()


def test_static_dir_env_without_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTUS_NETWORK_STATIC_DIR", str(tmp_path / "missing"))
    assert static_dir() is None


def test_static_dir_frozen_meipass(tmp_path: Path, monkeypatch) -> None:
    meipass = tmp_path / "meipass"
    dist = meipass / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.delenv("AGENTUS_NETWORK_STATIC_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    assert static_dir() == dist.resolve()


def test_static_dir_dev_with_repo_dist(monkeypatch) -> None:
    monkeypatch.delenv("AGENTUS_NETWORK_STATIC_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    repo_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    found = static_dir()
    if (repo_dist / "index.html").is_file():
        assert found == repo_dist.resolve()
    else:
        assert found is None
