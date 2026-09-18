from __future__ import annotations

from pathlib import Path

import yaml

from app.db import init
from app.db.bootstrap import get_data_location
from app.db.engine import get_bootstrap
from app.db.paths import RAG_DIR_NAME, default_config_path, local_app_data


def test_init_creates_pointer_stores_and_docs_dir() -> None:
    bootstrap = init()
    home = local_app_data()
    config = default_config_path()
    assert config.is_file()
    assert bootstrap.data_dir == home / "data"
    assert (bootstrap.data_dir / "settings.sqlite").is_file()
    assert (bootstrap.data_dir / "help.sqlite").is_file()
    assert (bootstrap.data_dir / "workspace.sqlite").is_file()
    assert (bootstrap.data_dir / "history.sqlite").is_file()
    assert (bootstrap.data_dir / RAG_DIR_NAME).is_dir()
    loc = get_data_location()
    assert loc["source"] in {"default", "config"}
    assert loc["readOnly"] is False
    ids = {item["id"] for item in loc["stores"]}
    assert ids == {"settings", "help", "workspace", "history"}
    assert all(item["state"] == "ok" for item in loc["stores"])


def test_corrupt_yaml_is_replaced() -> None:
    config = default_config_path()
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("{ this is not: [ yaml", encoding="utf-8")
    init()
    raw = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    assert "dataDir" in raw
    assert get_bootstrap().data_dir.is_dir()


def test_no_sqlite_outside_db() -> None:
    root = Path(__file__).resolve().parents[2] / "app"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if "db" in path.parts and path.parts[path.parts.index("app") + 1] == "db":
            continue
        text = path.read_text(encoding="utf-8")
        if "sqlite3" in text:
            offenders.append(str(path.relative_to(root.parent)))
    assert offenders == []
