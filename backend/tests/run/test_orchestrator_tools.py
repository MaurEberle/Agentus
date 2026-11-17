"""Dev Team run, 2026-11-17: the orchestrator built the app itself with a terminal whose folder was gone.

Reading files only before a failure, the sectioned prompt, the orientation limit,
same-error withdrawal, switched-off tools and the folder check before a run.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.db.runs import list_logs
from app.runtime.models import CompletionResult, ToolCall
from app.tools.models import ExecuteResult
from tests.run.test_harness import _can_write, _drive, _linear_file_doc, _orch_files_doc


def _messages(stored: dict) -> list[str]:
    return [row["message"] for row in list_logs(stored["id"])]


def _payloads(stored: dict, message: str) -> list[dict]:
    return [row["payload"] or {} for row in list_logs(stored["id"]) if row["message"] == message]


def _is_orch(req) -> bool:
    return "You orchestrate" in (req.messages[0].content or "")


_DECISIONS = {"call_agent", "ask_user", "reply", "finish"}


def _names(req) -> list[str]:
    """Own tools offered, without the decision tools that come with them."""
    names = [str((item.get("function") or {}).get("name")) for item in (req.tools or [])]
    return [name for name in names if name not in _DECISIONS]


def _ok(text: str) -> CompletionResult:
    return CompletionResult(content=text, model="m", finish_reason="stop")


def _calls(*items: tuple[str, str]) -> CompletionResult:
    return CompletionResult(
        content=None,
        tool_calls=[ToolCall(id=f"c{i}", name=name, arguments=args) for i, (name, args) in enumerate(items)],
        model="m",
        finish_reason="tool_calls",
    )


def _with_terminal(doc: dict) -> dict:
    doc["nodes"].append(
        {
            "id": "term",
            "type": "tool",
            "position": {"x": 0, "y": 0},
            "data": {"kind": "terminal", "rootPath": "C:/stories", "terminalPrograms": ["git", "npm"]},
        }
    )
    doc["edges"].append(
        {"id": "eterm", "source": "term", "sourceHandle": "tool", "target": "orch", "targetHandle": "tool"}
    )
    return doc


def _record_execute(monkeypatch) -> list[dict]:
    executed: list[dict] = []

    def _execute(kind, *, config, args, secret=None):
        del config, secret
        executed.append({"kind": kind, **dict(args or {})})
        return ExecuteResult(ok=True, result={"path": ".", "entries": []})

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)
    return executed


def test_before_a_failure_the_orchestrator_reads_files_and_has_no_terminal(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    first: dict = {}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("erledigt")
        if not first:
            first["system"] = req.messages[0].content or ""
            first["names"] = _names(req)
            assert not _can_write(req)
            return _calls(("terminal", '{"command":"npm create vite@latest ."}'), ("file_access", '{"action":"tree","path":"."}'))
        return _ok('{"action":"finish","text":"Fertig."}')

    stored = _drive(monkeypatch, _complete, doc=_with_terminal(_orch_files_doc()))
    assert stored["outcome"] == "succeeded"
    assert first["names"] == ["file_access"]
    system = first["system"]
    assert "# Your tools: reading files only" in system
    assert "Tool name: terminal." not in system and "Write (" not in system
    assert "After an agent call failed you also get file changes and the terminal" in system
    # The terminal call never ran; the tree did.
    assert [item["kind"] for item in executed] == ["file_access"]
    locked = _payloads(stored, "run.orchestrator.toolLocked")
    assert locked == [{"name": "terminal", "error": "tool.notOffered"}]


def test_after_a_failure_the_terminal_opens(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    seen: list[list[str]] = []

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("")  # empty result: the agent call failed
        seen.append(_names(req))
        if any(message.role == "tool" for message in req.messages):
            return _ok('{"action":"finish","text":"Fertig."}')
        if "terminal" in _names(req):
            assert "Tool name: terminal." in (req.messages[0].content or "")
            return _calls(("terminal", '{"command":"git status"}'))
        return _ok('{"action":"call","agent":"Schreiber","task":"schreib"}')

    stored = _drive(monkeypatch, _complete, doc=_with_terminal(_orch_files_doc()))
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert seen[0] == ["file_access"]
    assert "terminal" in seen[1]
    assert [item["kind"] for item in executed] == ["terminal"]


def test_looking_around_before_the_first_call_is_limited(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    state = {"orch": 0, "after_cap": None, "read": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("erledigt")
        state["orch"] += 1
        blob = "\n".join(message.content or "" for message in req.messages)
        if "characters:" in blob:
            return _ok('{"action":"finish","text":"Fertig."}')
        if req.tools:
            state["read"] += 4
            first = state["read"]
            return _calls(*[("file_access", f'{{"action":"read","path":"f{first + i}.txt"}}') for i in range(4)])
        state["after_cap"] = "No more tools until you have called an agent" in blob
        return _ok('{"action":"call","agent":"Schreiber","task":"schreib"}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert len(executed) == 10
    assert state["after_cap"] is True
    assert _payloads(stored, "run.orchestrator.orientationCap") == [{"calls": 10}]


def test_the_same_error_three_times_withdraws_the_tool(monkeypatch, api_env) -> None:
    executed: list[str] = []

    def _execute(kind, *, config, args, secret=None):
        del kind, config, secret
        executed.append(str(args.get("path")))
        return ExecuteResult(ok=False, error_key="tools.fileAccess.notFound")

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)
    after: dict = {}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("erledigt")
        blob = "\n".join(message.content or "" for message in req.messages)
        if "is withdrawn for the rest of this decision" in blob:
            after["names"] = _names(req)
            return _ok('{"action":"finish","text":"Fertig."}')
        if "characters:" in blob:
            return _calls(*[("file_access", f'{{"action":"read","path":"x{i}.txt"}}') for i in range(5)])
        return _ok('{"action":"call","agent":"Schreiber","task":"schreib"}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert executed == ["x0.txt", "x1.txt", "x2.txt"]
    assert after["names"] == []
    assert _payloads(stored, "run.orchestrator.toolWithdrawn") == [
        {"name": "file_access", "error": "tools.fileAccess.notFound"}
    ]


def test_a_tool_without_its_folder_is_switched_off_for_the_run(monkeypatch, api_env, tmp_path: Path) -> None:
    doc = _linear_file_doc()
    files = next(node for node in doc["nodes"] if node["id"] == "files")
    files["data"] = {"kind": "terminal", "rootPath": str(tmp_path / "gone"), "terminalPrograms": ["git"]}
    seen: list[dict] = []
    offered: list[list[str]] = []

    def _complete(req, should_abort=None, on_progress=None):
        offered.append(_names(req))
        tool_messages = [m for m in req.messages if m.role == "tool"]
        if len(tool_messages) == 1:
            seen.append(json.loads(tool_messages[0].content or "{}"))
            # From memory, the model calls it once more.
            return _calls(("terminal", '{"command":"git status"}'))
        if len(tool_messages) == 2:
            seen.append(json.loads(tool_messages[1].content or "{}"))
            return _ok("Ohne Terminal fertig.")
        return _calls(("terminal", '{"command":"git status"}'))

    stored = _drive(monkeypatch, _complete, doc=doc, user_texts=())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert seen[0]["errorKey"] == "tools.terminal.rootNotDir"
    assert "does not exist" in seen[0]["hint"] and "switched off for the rest of this run" in seen[0]["hint"]
    assert seen[1]["error"] == "tool.disabled"
    assert offered[0] == ["terminal"] and offered[1] == []
    assert _payloads(stored, "run.tool.disabled") == [{"name": "terminal", "error": "tools.terminal.rootNotDir"}]


def test_a_missing_tool_folder_fails_validation(monkeypatch, tmp_path: Path) -> None:
    from app.run import validate as validate_module
    from app.run.graph_models import AgentNetworkDocument

    monkeypatch.setattr(validate_module, "folder_exists", lambda path: Path(path).is_dir())
    doc = _with_terminal(_orch_files_doc())
    for node in doc["nodes"]:
        if node["id"] == "files":
            node["data"]["rootPath"] = str(tmp_path)
        if node["id"] == "term":
            node["data"]["rootPath"] = str(tmp_path / "hello5")
    errors = validate_module.validate_document(AgentNetworkDocument.model_validate(doc), data_dir="C:/data")
    keys = [(error.message_key, error.node_id) for error in errors]
    assert keys == [("graph.terminal.rootMissing", "term")]
    (tmp_path / "hello5").mkdir()
    assert validate_module.validate_document(AgentNetworkDocument.model_validate(doc), data_dir="C:/data") == []
