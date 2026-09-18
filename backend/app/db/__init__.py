"""Persistence surface. Domain modules import functions here — no sqlite3."""

from app.db.blob import pack_f32, unpack_f32
from app.db.bootstrap import (
    Bootstrap,
    StoreFiles,
    WindowGeom,
    get_data_location,
    load_bootstrap,
    save_bootstrap,
    save_window,
    set_data_dir,
)
from app.db.engine import close_all, open_all, reset, transaction
from app.db.errors import (
    ConfigError,
    NotFound,
    PersistError,
    StoreUnavailable,
    VaultError,
)
from app.db.paths import APP_DIR_NAME, RAG_DIR_NAME, default_data_dir, local_app_data


def init() -> Bootstrap:
    bootstrap = load_bootstrap()
    from app.db.engine import set_bootstrap

    set_bootstrap(bootstrap)
    open_all()
    try:
        from app.install_seed import bundled_help_docs, seed_help_documents

        bundled = bundled_help_docs()
        if bundled is not None:
            seed_help_documents(bootstrap.data_dir, bundled=bundled)
    except Exception:
        pass
    return bootstrap


__all__ = [
    "APP_DIR_NAME",
    "RAG_DIR_NAME",
    "Bootstrap",
    "ConfigError",
    "NotFound",
    "PersistError",
    "StoreFiles",
    "StoreUnavailable",
    "VaultError",
    "WindowGeom",
    "close_all",
    "default_data_dir",
    "get_data_location",
    "init",
    "load_bootstrap",
    "local_app_data",
    "open_all",
    "pack_f32",
    "reset",
    "save_bootstrap",
    "save_window",
    "set_data_dir",
    "transaction",
    "unpack_f32",
]
