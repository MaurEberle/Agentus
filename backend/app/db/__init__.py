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
from app.db.engine import close_all, open_all, reset, transaction, utc_now
from app.db.errors import (
    ConfigError,
    NotFound,
    PersistError,
    StoreUnavailable,
    VaultError,
)
from app.db.paths import APP_DIR_NAME, RAG_DIR_NAME, default_data_dir, local_app_data


_atexit_registered = False


def _persist_on_exit() -> None:
    try:
        from app.db.runs import complete_run
        from app.run.controller import get_controller

        ctrl = get_controller()
        if ctrl.is_busy() and ctrl.run_id:
            ctrl.stop_event.set()
            ctrl.abort_generation.set()
            complete_run(ctrl.run_id, outcome="cancelled", ended_at=utc_now())
    except Exception:
        pass
    try:
        from app.db.runs import abandon_orphaned_runs

        abandon_orphaned_runs()
    except Exception:
        pass


def init() -> Bootstrap:
    bootstrap = load_bootstrap()
    from app.db.engine import set_bootstrap

    set_bootstrap(bootstrap)
    open_all()
    try:
        from app.db.runs import abandon_orphaned_runs, repair_interrupted_ended_at

        abandon_orphaned_runs()
        repair_interrupted_ended_at()
    except Exception:
        pass
    global _atexit_registered
    if not _atexit_registered:
        import atexit

        atexit.register(_persist_on_exit)
        _atexit_registered = True
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
