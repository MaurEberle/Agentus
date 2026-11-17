"""Package E: start/stop race (M1), background cleanup (M2), resident models (M3),
finish guarantee (M5), chat abort (M6), file attempts (M8)."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from app.run.controller import get_controller
from app.runtime.errors import RuntimeApiError
from app.runtime.models import CompletionRequest, CompletionResult
from tests.run.conftest import mini_doc


def _save(doc: dict) -> None:
    from app.db import init
    from app.db.engine import utc_now
    from app.db.networks import NetworkRow, upsert_network
    from app.settings.models import AppSettingsPatch
    from app.settings.service import patch_settings

    init()
    upsert_network(
        NetworkRow(
            id="net-1",
            name="mini",
            description=None,
            tags=[],
            document=doc,
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    patch_settings(AppSettingsPatch(active_network_id="net-1"))


def _wait_for(check, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------- M1 start gate
def test_second_start_while_the_first_still_runs_is_busy(api_env, monkeypatch) -> None:
    _save(mini_doc(startMessage="go"))
    ctrl = get_controller()
    entered = threading.Event()
    release = threading.Event()

    def _slow_index(compiled, data_dir):
        entered.set()
        release.wait(timeout=5)

    monkeypatch.setattr(ctrl, "_index_knowledge", _slow_index)
    first: dict = {}
    worker = threading.Thread(target=lambda: first.update(ctrl.start()), daemon=True)
    worker.start()
    assert entered.wait(timeout=5)
    ctrl.stop()
    assert ctrl.service_status == "stopped"
    # The first start() has not returned yet: a second one must not clear its stop flag.
    from app.http.errors import AppError

    with pytest.raises(AppError) as err:
        ctrl.start()
    assert err.value.message_key == "run.busy"
    release.set()
    worker.join(timeout=5)
    assert first.get("serviceStatus") == "stopped"
    assert ctrl.thread is None
    assert ctrl.is_busy() is False


# ---------------------------------------------------------------- M2 status before cleanup
def test_finish_reports_stopped_before_the_model_cleanup(api_env, monkeypatch) -> None:
    _save(mini_doc(startMessage="go"))
    ctrl = get_controller()
    gate = threading.Event()
    seen_status: list[str] = []

    def _slow_release(settings, compiled):
        seen_status.append(ctrl.service_status)
        gate.wait(timeout=5)
        return []

    monkeypatch.setattr("app.run.vram.release_network", _slow_release)
    ctrl.start()
    assert ctrl.thread is not None
    ctrl.thread.join(timeout=3)
    # The run is over and reported as stopped while the model cleanup still hangs.
    assert ctrl.thread.is_alive() is False
    assert ctrl.service_status == "stopped"
    assert _wait_for(lambda: bool(seen_status))
    assert not gate.is_set()
    gate.set()
    ctrl.wait_cleanup(timeout=5)


def test_closing_the_app_does_not_preload_the_help_model(api_env, monkeypatch) -> None:
    from app.settings.models import AppSettingsPatch
    from app.settings.service import patch_settings

    _save(mini_doc(requireInput=True))
    patch_settings(AppSettingsPatch(help_chat={"provider": "ollama", "model": "helper"}))
    loaded: list[str] = []
    monkeypatch.setattr("app.runtime.ollama.ensure_loaded", lambda tag, **k: loaded.append(tag))
    ctrl = get_controller()
    ctrl.start()
    ctrl.stop(closing=True)
    ctrl.wait_cleanup(timeout=5)
    assert loaded == []
    ctrl.start()
    ctrl.stop()
    ctrl.wait_cleanup(timeout=5)
    assert loaded == ["helper"]


def test_teardown_leaves_models_of_other_programs(api_env, monkeypatch) -> None:
    from app.run.vram import release_network

    unloaded: list[str] = []
    monkeypatch.setattr(
        "app.runtime.ollama.list_loaded_models",
        lambda *a, **k: ["llama3.2:1b", "foreign:7b", "helper:latest"],
    )
    monkeypatch.setattr("app.runtime.ollama.unload", lambda tag, **k: unloaded.append(tag))
    llm = SimpleNamespace(provider="ollama", model="llama3.2:1b")
    compiled = SimpleNamespace(agents={"ag": SimpleNamespace(llm=llm)}, orchestrator=None, by_id={})
    settings = SimpleNamespace(help_chat=SimpleNamespace(provider="ollama", model="helper", embedding_model=""))
    assert release_network(settings, compiled) == ["llama3.2:1b"]
    assert unloaded == ["llama3.2:1b"]


# ---------------------------------------------------------------- M3 resident models
def test_switching_between_two_fitting_models_does_not_unload(monkeypatch) -> None:
    from app.run import turn_runtime

    gib = 1024**3
    resident = {"writer": (3 * gib, 3 * gib), "saver": (2 * gib, 2 * gib)}
    released: list[str] = []
    monkeypatch.setattr("app.runtime.ollama.resident_index", lambda *a, **k: dict(resident))
    monkeypatch.setattr(turn_runtime, "_inference_pool_bytes", lambda: 12 * gib)
    monkeypatch.setattr(
        "app.run.vram.release_others",
        lambda settings, compiled, current=None: released.append(current) or [],
    )
    monkeypatch.setattr("app.settings.service.load_settings", lambda: SimpleNamespace())
    for model in ("writer", "saver", "writer"):
        turn_runtime._prepare_resident(SimpleNamespace(), SimpleNamespace(provider="ollama", model=model, base_url=None))
    assert released == []
    # A model that does not fit next to the others still frees the card.
    turn_runtime._SEEN_VRAM["huge"] = 10 * gib
    turn_runtime._prepare_resident(SimpleNamespace(), SimpleNamespace(provider="ollama", model="huge", base_url=None))
    assert released == ["huge"]


def test_unknown_vram_keeps_the_old_unload(monkeypatch) -> None:
    from app.run import turn_runtime

    released: list[str] = []
    monkeypatch.setattr("app.runtime.ollama.resident_index", lambda *a, **k: {})
    monkeypatch.setattr(turn_runtime, "_inference_pool_bytes", lambda: 0)
    monkeypatch.setattr(
        "app.run.vram.release_others",
        lambda settings, compiled, current=None: released.append(current) or [],
    )
    monkeypatch.setattr("app.settings.service.load_settings", lambda: SimpleNamespace())
    turn_runtime._prepare_resident(SimpleNamespace(), SimpleNamespace(provider="ollama", model="m", base_url=None))
    assert released == ["m"]


# ---------------------------------------------------------------- M5 finish guarantee
def test_run_ends_even_when_the_end_log_fails(api_env, monkeypatch) -> None:
    from app.run import orchestrator_loop

    _save(mini_doc(startMessage="go"))
    real_emit = orchestrator_loop.emit_log

    def _emit(level, message, *args, **kwargs):
        if message in {"run.succeeded", "run.failed", "run.cancelled"}:
            raise OSError("disk full")
        return real_emit(level, message, *args, **kwargs)

    monkeypatch.setattr(orchestrator_loop, "emit_log", _emit)
    ctrl = get_controller()
    ctrl.start()
    assert ctrl.thread is not None
    ctrl.thread.join(timeout=5)
    assert ctrl.thread.is_alive() is False
    assert ctrl.service_status == "stopped"


# ---------------------------------------------------------------- M6 chat abort
def test_stop_generating_waits_for_the_next_message(api_env, monkeypatch) -> None:
    from app.db.runs import get_run
    from tests.run.test_validate import _orchestrator_doc

    in_call = threading.Event()
    calls = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        calls["n"] += 1
        if calls["n"] == 1:
            in_call.set()
            # A long answer that only ends when the chat says stop.
            while not (should_abort and should_abort()):
                time.sleep(0.01)
            raise RuntimeApiError("run.cancelled")
        return CompletionResult(content='{"action":"finish","text":"Fertig."}', model=req.model, finish_reason="stop")

    monkeypatch.setattr("app.runtime.completions.complete_live", _complete)
    _save(_orchestrator_doc())
    ctrl = get_controller()
    started = ctrl.start()
    ctrl.send_chat("Hallo")
    assert in_call.wait(timeout=5)
    ctrl.abort_chat()
    assert _wait_for(lambda: ctrl._wait_ask is not None)
    assert ctrl.service_status == "running"
    messages = [m.message_key for m in ctrl.conversation]
    assert "monitoring.chat.aborted" in messages
    ctrl.send_chat("weiter")
    assert ctrl.thread is not None
    ctrl.thread.join(timeout=5)
    stored = get_run(started["runId"])
    assert stored is not None
    assert stored["outcome"] == "succeeded"
    assert calls["n"] == 2


def test_abort_while_waiting_does_not_cut_the_next_answer(api_env) -> None:
    from tests.run.test_validate import _orchestrator_doc

    _save(_orchestrator_doc())
    ctrl = get_controller()
    ctrl.start()
    # Nothing generates yet: the run waits for the first message.
    ctrl.abort_chat()
    assert ctrl.abort_generation.is_set() is False
    ctrl.stop()


# ---------------------------------------------------------------- M8 file attempts
def _fact(action: str, path: str, ok: bool):
    from app.run.memory import FileFact

    return FileFact(tool="file_access", action=action, path=path, ok=ok)


def test_a_fixed_write_is_not_a_tool_failure() -> None:
    from app.run.dispatch import unresolved_file_failures

    files = [_fact("write", "a.txt", False), _fact("write", "a.txt", True)]
    assert unresolved_file_failures(files) == []
    files = [_fact("read", "missing.txt", False), _fact("write", "b.txt", True)]
    assert unresolved_file_failures(files) == []
    files = [_fact("write", "a.txt", True), _fact("edit", "c.txt", False)]
    assert [fact.path for fact in unresolved_file_failures(files)] == ["c.txt"]


def test_a_reading_agent_with_a_text_answer_is_no_missed_write() -> None:
    from app.run.dispatch import _count_file_attempt
    from app.run.memory import AgentRecord, RunMemory

    memory = RunMemory()
    agent = SimpleNamespace(node_id="ag", tool_kinds=["file_access"])
    compiled = SimpleNamespace(orchestrator=None)
    for _ in range(4):
        record = AgentRecord(agent_id="ag", name="Leser", task="fasse zusammen", has_tools=True)
        record.files = [_fact("read", "notes.md", True)]
        record.finished = True
        record.text = "Zusammenfassung"
        _count_file_attempt(compiled, memory, agent, record)
    assert memory.misses.get("ag", 0) == 0
    assert memory.takeover is None
