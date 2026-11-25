"""Architect sessions: model locks, GPU check, start, stop, idle end, help chat pause.

fix/netz-architekt/entwurf.md, 9. One session runs at a time; its chat and draft stay in the
database, so an ended session can be continued (it starts again, with the GPU check).
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.common.components import catalog_hash
from app.common.types import NEEDS_CREDENTIAL, PROVIDERS
from app.db import architect as store
from app.db.engine import utc_now
from app.http.errors import AppError

log = logging.getLogger("agentus.architect")

IDLE_SECONDS = 15 * 60
IDLE_WARN_SECONDS = 60
MIN_PARAMETERS_B = 4.0
SMALL_PARAMETERS_B = 14.0
SHORT_CONTEXT = 32_768
ARCHITECT_CONTEXT = 32_768
_WATCH_EVERY = 15.0


@dataclass
class ModelCheck:
    ok: bool
    reasons: list[str] = field(default_factory=list)  # architect.model.* keys that block
    warnings: list[str] = field(default_factory=list)
    parameters_b: float | None = None
    context: int | None = None
    local: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "parametersB": self.parameters_b,
            "context": self.context,
            "local": self.local,
        }


@dataclass
class GpuCheck:
    need_bytes: int
    free_vram_bytes: int
    free_ram_bytes: int
    fits: bool
    can_force: bool
    network_running: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "needBytes": self.need_bytes,
            "freeVramBytes": self.free_vram_bytes,
            "freeRamBytes": self.free_ram_bytes,
            "fits": self.fits,
            "canForce": self.can_force,
            "networkRunning": self.network_running,
        }


@dataclass
class Active:
    session_id: str
    provider: str
    model: str
    credential_id: str | None
    local: bool
    num_ctx: int | None
    slow: bool
    last_input: float
    generating: bool = False
    abort: threading.Event = field(default_factory=threading.Event)


_active: Active | None = None
_lock = threading.Lock()
_watcher: threading.Thread | None = None


def parameters_b(raw: str | None) -> float | None:
    text = (raw or "").strip().upper().replace(",", ".")
    try:
        if text.endswith("B"):
            return float(text[:-1])
        if text.endswith("M"):
            return float(text[:-1]) / 1000
    except ValueError:
        return None
    return None


def check_model(provider: str, model: str, credential_id: str | None) -> ModelCheck:
    """E-3: Ollama models need tool calling and at least 4B; cloud providers need a credential."""
    if provider not in PROVIDERS or not (model or "").strip():
        return ModelCheck(ok=False, reasons=["architect.model.missing"])
    if provider != "ollama":
        if provider in NEEDS_CREDENTIAL and not credential_id:
            return ModelCheck(ok=False, reasons=["architect.model.noCredential"])
        return ModelCheck(ok=True)
    from app.llm.catalog import list_installed
    from app.runtime.ollama import tag_key

    installed = list_installed()
    if installed.message_key:
        return ModelCheck(ok=False, reasons=["architect.model.ollamaDown"], local=True)
    item = next((row for row in installed.items if tag_key(row.name) == tag_key(model)), None)
    if item is None:
        return ModelCheck(ok=False, reasons=["architect.model.notInstalled"], local=True)
    size = parameters_b(item.parameter_size)
    reasons: list[str] = []
    warnings: list[str] = []
    if not item.tools:
        reasons.append("architect.model.noTools")
    if size is not None and size < MIN_PARAMETERS_B:
        reasons.append("architect.model.tooSmall")
    elif size is not None and size < SMALL_PARAMETERS_B:
        warnings.append("architect.model.small")
    if item.context_length and item.context_length < SHORT_CONTEXT:
        warnings.append("architect.model.shortContext")
    return ModelCheck(
        ok=not reasons,
        reasons=reasons,
        warnings=warnings,
        parameters_b=size,
        context=item.context_length,
        local=True,
    )


def _context_for(model_context: int | None) -> int:
    return min(model_context or ARCHITECT_CONTEXT, ARCHITECT_CONTEXT)


def check_gpu(model: str, num_ctx: int) -> GpuCheck:
    """Does the model with this context fit in free VRAM, or at least in VRAM and RAM together?"""
    from app.run.resources import latest
    from app.runtime.vram_est import estimate_vram_bytes, vram_profile
    from app.settings.service import is_run_busy

    snap = latest()
    gpus = [gpu for gpu in snap.gpus or [] if gpu.inference]
    free_vram = sum(max(0, gpu.vram_total_bytes - gpu.vram_used_bytes) for gpu in gpus)
    free_ram = max(0, snap.ram_total_bytes - snap.ram_used_bytes)
    need = 0
    try:
        profile = vram_profile(model)
        if profile is not None:
            need = estimate_vram_bytes(profile, num_ctx=num_ctx)
    except Exception:
        log.debug("vram estimate failed for %s", model, exc_info=True)
    if need <= 0:
        from app.llm.catalog import list_installed
        from app.runtime.ollama import tag_key

        item = next((row for row in list_installed().items if tag_key(row.name) == tag_key(model)), None)
        need = int((item.size_bytes or 0) * 1.2) if item else 0
    if _resident(model):
        free_vram += need
    # A local embedding model for the examples shares the GPU (entwurf.md, 6.3).
    need += _embedding_need()
    return GpuCheck(
        need_bytes=need,
        free_vram_bytes=free_vram,
        free_ram_bytes=free_ram,
        fits=need <= free_vram,
        can_force=need <= free_vram + free_ram,
        network_running=is_run_busy(),
    )


def _embedding_need() -> int:
    from app.settings.service import load_settings

    settings = load_settings().architect
    model = (settings.embedding_model or "").strip()
    if settings.embedding_provider != "ollama" or not model or _resident(model):
        return 0
    try:
        from app.llm.catalog import list_installed
        from app.runtime.ollama import tag_key

        item = next((row for row in list_installed().items if tag_key(row.name) == tag_key(model)), None)
    except Exception:
        return 0
    return int((item.size_bytes or 0) * 1.2) if item else 0


def _resident(model: str) -> bool:
    try:
        from app.runtime.ollama import resident_index, tag_key

        return tag_key(model) in resident_index()
    except Exception:
        return False


def _help_local() -> bool:
    from app.settings.service import load_settings

    return load_settings().help_chat.provider == "ollama"


def help_paused() -> bool:
    """E-16: the help chat pauses only when the architect and the help chat both run locally."""
    with _lock:
        active = _active
    return bool(active and active.local and _help_local())


def _pause_help() -> None:
    from app.help.abort import abort_current
    from app.help.status import effective_help_model
    from app.runtime.ollama import unload

    abort_current()
    model = effective_help_model()
    if model:
        try:
            unload(model, wait=False)
        except Exception:
            log.debug("unloading the help model failed", exc_info=True)


def create(provider: str, model: str, credential_id: str | None) -> store.ArchitectSessionRow:
    now = utc_now()
    row = store.ArchitectSessionRow(
        id=str(uuid.uuid4()),
        title="",
        provider=provider,
        model=model.strip(),
        credential_id=credential_id or None,
        catalog_hash=catalog_hash(),
        state="ended",
        created_at=now,
        updated_at=now,
    )
    store.insert_session(row)
    return row


def require(session_id: str) -> store.ArchitectSessionRow:
    row = store.get_session(session_id)
    if row is None:
        raise AppError("architect.notFound", status_code=404)
    return row


def start(
    session_id: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    credential_id: str | None = None,
    force_slow: bool = False,
    confirm_running: bool = False,
) -> dict[str, Any]:
    """Start a session (E-7, E-20). Raises 409 with the check when the GPU or a running network says no."""
    global _active
    row = require(session_id)
    if provider:
        row.provider, row.model, row.credential_id = provider, (model or row.model).strip(), credential_id
    checked = check_model(row.provider, row.model, row.credential_id)
    if not checked.ok:
        raise AppError("architect.model.blocked", status_code=409, details={"model": checked.as_dict()})
    num_ctx = _context_for(checked.context) if checked.local else None
    slow = False
    if checked.local:
        if _help_local():
            _pause_help()
        gpu = check_gpu(row.model, num_ctx or ARCHITECT_CONTEXT)
        if not gpu.fits:
            if not gpu.can_force:
                raise AppError("architect.gpu.tooLarge", status_code=409, details={"gpu": gpu.as_dict(), "model": checked.as_dict()})
            if not force_slow:
                raise AppError("architect.gpu.short", status_code=409, details={"gpu": gpu.as_dict(), "model": checked.as_dict()})
            slow = True
        if gpu.network_running and not confirm_running:
            raise AppError("architect.networkRunning", status_code=409, details={"gpu": gpu.as_dict(), "model": checked.as_dict()})
    with _lock:
        previous = _active
    if previous is not None and previous.session_id != session_id:
        # A new chat on the same local model takes it over loaded; unloading would only reload it.
        same = previous.local and checked.local and previous.model == row.model
        stop(previous.session_id, reason="replaced", unload=not same)
    row.state = "active"
    row.updated_at = utc_now()
    row.last_input_at = row.updated_at
    store.save_session(row)
    with _lock:
        _active = Active(
            session_id=row.id,
            provider=row.provider,
            model=row.model,
            credential_id=row.credential_id,
            local=checked.local,
            num_ctx=num_ctx,
            slow=slow,
            last_input=time.monotonic(),
        )
    _ensure_watcher()
    _remember_choice(row)
    return {"model": checked.as_dict(), "slow": slow}


def _remember_choice(row: store.ArchitectSessionRow) -> None:
    from app.settings.models import AppSettingsPatch
    from app.settings.service import patch_settings

    try:
        patch_settings(
            AppSettingsPatch(architect={"provider": row.provider, "model": row.model, "credentialId": row.credential_id})
        )
    except Exception:
        log.debug("remembering the architect model failed", exc_info=True)


def stop(session_id: str | None = None, *, reason: str = "user", unload: bool = True) -> None:
    """End the active session: abort, unload a local model (unless the next session keeps it), free the help chat."""
    global _active
    with _lock:
        active = _active
        if active is None or (session_id is not None and active.session_id != session_id):
            active = None
        else:
            _active = None
    if session_id is not None:
        row = store.get_session(session_id)
        if row is not None and row.state != "ended":
            row.state = "ended"
            row.updated_at = utc_now()
            store.save_session(row)
    if active is None:
        return
    active.abort.set()
    log.info("architect session %s ended (%s)", active.session_id, reason)
    if active.local and unload:
        from app.runtime.ollama import unload

        try:
            unload(active.model, wait=False)
        except Exception:
            log.debug("unloading the architect model failed", exc_info=True)


def active() -> Active | None:
    with _lock:
        return _active


def touch(session_id: str) -> None:
    with _lock:
        if _active is not None and _active.session_id == session_id:
            _active.last_input = time.monotonic()


def set_generating(session_id: str, value: bool) -> threading.Event | None:
    with _lock:
        if _active is None or _active.session_id != session_id:
            return None
        _active.generating = value
        if value:
            _active.abort = threading.Event()
        _active.last_input = time.monotonic()
        return _active.abort


def abort(session_id: str) -> None:
    with _lock:
        if _active is not None and _active.session_id == session_id:
            _active.abort.set()


def status() -> dict[str, Any]:
    with _lock:
        current = _active
    if current is None:
        return {"active": None, "helpPaused": False}
    idle = time.monotonic() - current.last_input
    return {
        "active": {
            "sessionId": current.session_id,
            "provider": current.provider,
            "model": current.model,
            "local": current.local,
            "slow": current.slow,
            "generating": current.generating,
            "idleSeconds": int(idle),
            "idleLimitSeconds": IDLE_SECONDS,
            "idleWarnSeconds": IDLE_WARN_SECONDS,
        },
        "helpPaused": current.local and _help_local(),
    }


def end_idle(now: float | None = None) -> bool:
    """E-15: end the session after 15 minutes without input and without a running answer."""
    with _lock:
        current = _active
    if current is None or current.generating:
        return False
    if (now if now is not None else time.monotonic()) - current.last_input < IDLE_SECONDS:
        return False
    stop(current.session_id, reason="idle")
    return True


def _watch() -> None:
    while True:
        time.sleep(_WATCH_EVERY)
        try:
            end_idle()
        except Exception:
            log.debug("architect idle check failed", exc_info=True)


def _ensure_watcher() -> None:
    global _watcher
    if _watcher is not None and _watcher.is_alive():
        return
    _watcher = threading.Thread(target=_watch, name="architect-idle", daemon=True)
    _watcher.start()


def reset_for_tests() -> None:
    global _active
    with _lock:
        _active = None
