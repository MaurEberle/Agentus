from __future__ import annotations

from pathlib import Path

import pytest

from app.db import init
from app.db.bootstrap import get_data_location, set_data_dir
from app.db.errors import ConfigError
from app.db.paths import RAG_DIR_NAME
from app.db.settings import get_settings, put_settings


def test_env_data_dir_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_dir = tmp_path / "envdata"
    monkeypatch.setenv("AGENTUS_NETWORK_DATA_DIR", str(env_dir))
    bootstrap = init()
    loc = get_data_location()
    assert loc["source"] == "env"
    assert loc["readOnly"] is True
    assert Path(loc["dataDir"]) == env_dir.resolve()
    assert bootstrap.data_dir == env_dir.resolve()
    with pytest.raises(ConfigError) as err:
        set_data_dir(tmp_path / "other")
    assert err.value.message_key == "dataDir.readOnly"


def test_set_data_dir_copy_keeps_source(tmp_path: Path) -> None:
    init()
    put_settings({"ollamaBaseUrl": "http://127.0.0.1:11434"})
    src = get_data_location()
    src_dir = Path(src["dataDir"])
    rag = src_dir / RAG_DIR_NAME / "intro.md"
    rag.write_text("# hi", encoding="utf-8")

    dest = tmp_path / "copied"
    loc = set_data_dir(dest, copy=True)
    dest_dir = Path(loc["dataDir"])
    assert dest_dir == dest.resolve()
    assert (src_dir / "settings.sqlite").is_file()
    assert (dest_dir / "settings.sqlite").is_file()
    assert (dest_dir / RAG_DIR_NAME / "intro.md").is_file()
    assert rag.is_file()
    assert get_settings() == {"ollamaBaseUrl": "http://127.0.0.1:11434"}


def test_set_data_dir_without_copy_is_empty(tmp_path: Path) -> None:
    init()
    put_settings({"ollamaBaseUrl": "http://127.0.0.1:11434"})
    src_dir = Path(get_data_location()["dataDir"])
    dest = tmp_path / "empty-target"
    set_data_dir(dest, copy=False)
    assert get_settings() is None
    assert (src_dir / "settings.sqlite").is_file()


@pytest.mark.parametrize("root", [Path("C:\\"), Path("C:/"), Path("/")])
def test_set_data_dir_rejects_drive_root(root: Path) -> None:
    init()
    with pytest.raises(ConfigError) as err:
        set_data_dir(root)
    assert err.value.message_key == "dataDir.invalidPath"
