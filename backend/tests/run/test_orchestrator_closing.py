"""Dev Team run, 2026-11-17 (20:30): stopped at 24 agent calls without a word, tool XML in the chat.

The closing turn at the step limit, maxAgentCalls on the node, tool calls written
as text, read_many with a list in ``path``, and the missing runs.memory column.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.db.runs import list_logs
from app.run.orchestrate import invented_tool_action
from app.runtime.models import CompletionResult, ToolCall
from app.tools.models import ExecuteResult
from tests.run.test_harness import _drive, _orch_files_doc


def _messages(stored: dict) -> list[str]:
    return [row["message"] for row in list_logs(stored["id"])]


def _is_orch(req) -> bool:
    return "You orchestrate" in (req.messages[0].content or "")


def _blob(req) -> str:
    return "\n".join(message.content or "" for message in req.messages)


def _ok(text: str) -> CompletionResult:
    return CompletionResult(content=text, model="m", finish_reason="stop")


def _chat(stored: dict) -> list[str]:
    return [item["content"] for item in (stored["chat"] or [])]


def test_the_step_limit_leaves_one_turn_for_a_summary(monkeypatch, api_env) -> None:
    doc = _orch_files_doc()
    next(node for node in doc["nodes"] if node["id"] == "orch")["data"]["maxAgentCalls"] = 2
    calls = {"agent": 0}
    closing: dict = {}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            calls["agent"] += 1
            return _ok("Teil fertig.")
        if "You have used all 2 agent calls" in _blob(req):
            closing["tools"] = req.tools
            return _ok('{"action":"finish","text":"Gebaut ist Teil 1 und 2. Offen: Review."}')
        return _ok('{"action":"call","agent":"Schreiber","task":"weiter"}')

    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.stepLimit"
    assert calls["agent"] == 2
    assert closing["tools"] is None
    assert "Gebaut ist Teil 1 und 2. Offen: Review." in _chat(stored)
    assert "run.orchestrator.stepClose" in _messages(stored)


def test_a_closing_turn_without_summary_still_ends(monkeypatch, api_env) -> None:
    doc = _orch_files_doc()
    next(node for node in doc["nodes"] if node["id"] == "orch")["data"]["maxAgentCalls"] = 1
    rounds = {"orch": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("Teil fertig.")
        rounds["orch"] += 1
        if rounds["orch"] == 1:
            return _ok('{"action":"call","agent":"Schreiber","task":"teil"}')
        return _ok('{"action":"think","text":"Ich rufe trotzdem noch einmal."}' if rounds["orch"] % 2 else
                   '{"action":"call","agent":"Schreiber","task":"noch einmal"}')

    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.stepLimit"
    # The refused call, then two closing decisions without a summary.
    assert rounds["orch"] == 4


def test_tool_markup_as_text_never_reaches_the_chat(monkeypatch, api_env) -> None:
    executed: list[str] = []

    def _execute(kind, *, config, args, secret=None):
        executed.append(str(args.get("path")))
        return ExecuteResult(ok=True, result={"path": str(args.get("path")), "text": "x"})

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)
    xml = (
        "<tool_call>\n<function=file_access>\n<parameter=action>\nread\n</parameter>\n"
        "<parameter=path>\nsrc/styles/global.scss\n</parameter>\n</function>\n</tool_call>"
    )
    state = {"read": 0, "decide_note": False}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("Teil fertig.")
        blob = _blob(req)
        if "characters:" not in blob:
            return _ok('{"action":"call","agent":"Schreiber","task":"teil"}')
        if "Your tools are used up for this step" in blob:
            state["decide_note"] = True
            return _ok('{"action":"finish","text":"Fertig."}')
        if req.tools:
            first = state["read"]
            state["read"] += 4
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id=f"r{first + i}", name="file_access", arguments=f'{{"action":"read","path":"f{first + i}"}}')
                    for i in range(4)
                ],
                model="m",
                finish_reason="tool_calls",
            )
        # The read budget is used up; the model writes the next read as markup.
        return _ok(xml)

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert state["decide_note"] is True
    assert len(executed) == 15
    assert not any("<tool_call>" in text for text in _chat(stored))


def test_tool_calls_written_as_text_are_recognised() -> None:
    assert invented_tool_action("<function=file_access><parameter=action>write</parameter>") == "write"
    assert invented_tool_action("<function=terminal><parameter=command>npm test</parameter>") == "run"
    assert invented_tool_action("<function=web_search><parameter=query>x</parameter>") == "use"
    assert invented_tool_action('{"name": "file_access", "arguments": {"action": "read", "path": "a"}}') == "read"
    # Control markup and decision tools are not tool steps.
    assert invented_tool_action("<function=call><parameter=agent>Junior</parameter>") is None
    assert invented_tool_action('{"name": "call_agent", "arguments": {"agent": "Junior"}}') is None


def test_read_many_takes_a_list_written_into_path(tmp_path: Path) -> None:
    from app.tools.file_access_tool import run

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.ts").write_text("a", encoding="utf-8")
    (tmp_path / "src" / "b.ts").write_text("b", encoding="utf-8")
    cfg = {"rootPath": str(tmp_path)}
    as_text = run(cfg, {"action": "read_many", "path": json.dumps(["src/a.ts", "src/b.ts"])})
    assert as_text.ok, as_text.error_key
    assert [item["path"] for item in as_text.result["files"]] == ["src/a.ts", "src/b.ts"]
    assert run(cfg, {"action": "read_many", "paths": ["src/a.ts"]}).ok
    assert run(cfg, {"action": "read_many", "path": "src/a.ts, src/b.ts"}).ok


def test_a_missing_runs_memory_column_is_added(tmp_path: Path) -> None:
    from app.db.migrate import migrate

    conn = sqlite3.connect(str(tmp_path / "history.sqlite"), isolation_level=None)
    conn.row_factory = sqlite3.Row
    # The broken store from 2026-11-17: version 3 recorded, "briefing" instead of "memory".
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
    conn.executemany("INSERT INTO schema_migrations (version) VALUES (?)", [(1,), (2,), (3,)])
    conn.execute(
        "CREATE TABLE runs (id TEXT PRIMARY KEY, network_id TEXT NOT NULL, network_name TEXT NOT NULL, "
        "started_at TEXT NOT NULL, ended_at TEXT, outcome TEXT NOT NULL, updated_at TEXT, briefing TEXT)"
    )
    migrate("history", conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    assert {"memory", "briefing", "updated_at"} <= columns
    migrate("history", conn)  # idempotent
    conn.close()
