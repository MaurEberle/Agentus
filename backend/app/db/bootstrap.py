"""YAML pointer file + data-dir switch. No secrets."""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from app.common.types import STORE_IDS, DataDirSource
from app.db.errors import ConfigError
from app.db.paths import (
    RAG_DIR_NAME,
    default_config_path,
    default_data_dir,
    env_data_dir,
    is_invalid_data_dir,
    portable_root,
)

StoreSource = DataDirSource


@dataclass
class StoreFiles:
    settings: str = "settings.sqlite"
    help: str = "help.sqlite"
    workspace: str = "workspace.sqlite"
    history: str = "history.sqlite"


@dataclass
class WindowGeom:
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    maximized: bool = False


@dataclass
class Bootstrap:
    data_dir: Path
    stores: StoreFiles
    window: WindowGeom
    source: StoreSource
    config_path: Path
    read_only_data_dir: bool
    yaml_data_dir: Path = field(repr=False)


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return default


def _store_files(raw: object) -> StoreFiles:
    data = raw if isinstance(raw, dict) else {}
    defaults = StoreFiles()
    return StoreFiles(
        settings=str(data.get("settings") or defaults.settings),
        help=str(data.get("help") or defaults.help),
        workspace=str(data.get("workspace") or defaults.workspace),
        history=str(data.get("history") or defaults.history),
    )


def _window(raw: object) -> WindowGeom:
    data = raw if isinstance(raw, dict) else {}
    return WindowGeom(
        x=_as_int(data.get("x"), 0),
        y=_as_int(data.get("y"), 0),
        w=_as_int(data.get("w"), 0),
        h=_as_int(data.get("h"), 0),
        maximized=bool(data.get("maximized", False)),
    )


def _resolve_data_dir(raw: object, *, fallback: Path) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        return fallback.resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = fallback.parent / path
    return path.expanduser().resolve()


def _read_raw(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        json_path = path.with_suffix(".json")
        if json_path.is_file():
            path = json_path
        else:
            return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return {}
    try:
        if path.suffix.lower() == ".json":
            import json

            loaded = json.loads(text)
        else:
            loaded = yaml.safe_load(text)
    except (yaml.YAMLError, ValueError, TypeError):
        return None
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        return None
    return loaded


def _dump_text(path: Path, raw: dict[str, Any]) -> str:
    if path.suffix.lower() == ".json":
        import json

        return json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
    return yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _payload(data_dir: Path, stores: StoreFiles, window: WindowGeom, existing: dict[str, Any]) -> dict[str, Any]:
    out = dict(existing)
    out["dataDir"] = str(data_dir)
    out["stores"] = asdict(stores)
    out["window"] = asdict(window)
    return out


def save_bootstrap(bootstrap: Bootstrap) -> None:
    existing = _read_raw(bootstrap.config_path) or {}
    yaml_dir = bootstrap.yaml_data_dir if bootstrap.source == "env" else bootstrap.data_dir
    raw = _payload(yaml_dir, bootstrap.stores, bootstrap.window, existing)
    _atomic_write(bootstrap.config_path, _dump_text(bootstrap.config_path, raw))


def load_bootstrap() -> Bootstrap:
    config_path = default_config_path()
    portable = portable_root()
    fallback_data = default_data_dir()
    raw = _read_raw(config_path)
    corrupt_or_missing = raw is None
    if raw is None:
        raw = {}
    rewrite = corrupt_or_missing or "dataDir" not in raw

    stores = _store_files(raw.get("stores"))
    window = _window(raw.get("window"))
    yaml_data_dir = _resolve_data_dir(raw.get("dataDir"), fallback=fallback_data)

    env_dir = env_data_dir()
    if env_dir is not None:
        source: StoreSource = "env"
        data_dir = env_dir
        read_only = True
    elif portable is not None:
        source = "portable"
        data_dir = yaml_data_dir if raw.get("dataDir") else fallback_data
        read_only = True
    elif rewrite:
        source = "default"
        data_dir = yaml_data_dir
        read_only = False
    else:
        source = "config"
        data_dir = yaml_data_dir
        read_only = False

    bootstrap = Bootstrap(
        data_dir=data_dir,
        stores=stores,
        window=window,
        source=source,
        config_path=config_path,
        read_only_data_dir=read_only,
        yaml_data_dir=yaml_data_dir,
    )
    if rewrite:
        save_bootstrap(bootstrap)
    return bootstrap


def save_window(geom: WindowGeom) -> None:
    from app.db.engine import get_bootstrap, set_bootstrap

    try:
        current = get_bootstrap()
    except Exception:
        current = load_bootstrap()
    updated = Bootstrap(
        data_dir=current.data_dir,
        stores=current.stores,
        window=geom,
        source=current.source,
        config_path=current.config_path,
        read_only_data_dir=current.read_only_data_dir,
        yaml_data_dir=current.yaml_data_dir,
    )
    save_bootstrap(updated)
    set_bootstrap(updated)


def get_data_location() -> dict[str, Any]:
    from app.db.engine import get_bootstrap, store_statuses

    bootstrap = get_bootstrap()
    return {
        "dataDir": str(bootstrap.data_dir),
        "source": bootstrap.source,
        "readOnly": bootstrap.read_only_data_dir,
        "stores": store_statuses(),
    }


def set_data_dir(path: str | Path, *, copy: bool = False) -> dict[str, Any]:
    from app.db.engine import close_all, get_bootstrap, open_all, set_bootstrap

    bootstrap = get_bootstrap()
    if bootstrap.read_only_data_dir:
        raise ConfigError("dataDir.readOnly")
    resolved = Path(path).expanduser().resolve()
    if is_invalid_data_dir(resolved):
        raise ConfigError("dataDir.invalidPath")
    resolved.mkdir(parents=True, exist_ok=True)

    source_dir = Path(bootstrap.data_dir)
    close_all()
    if copy:
        for store in STORE_IDS:
            name = getattr(bootstrap.stores, store)
            src = source_dir / name
            if src.is_file():
                shutil.copy2(src, resolved / name)
        rag_src = source_dir / RAG_DIR_NAME
        if rag_src.is_dir():
            shutil.copytree(rag_src, resolved / RAG_DIR_NAME, dirs_exist_ok=True)

    updated = Bootstrap(
        data_dir=resolved,
        stores=bootstrap.stores,
        window=bootstrap.window,
        source="config",
        config_path=bootstrap.config_path,
        read_only_data_dir=False,
        yaml_data_dir=resolved,
    )
    save_bootstrap(updated)
    set_bootstrap(updated)
    open_all()
    return get_data_location()
