"""Rejected terminal commands stay in the agent's prompt (Coder_Team run, 2026-11-20: 174 rejections)."""

from __future__ import annotations

from app.run.terminal_lessons import FileReach, alternatives, block, lesson
from app.runtime.models import CompletionRequest, CompletionResult, ToolCall

_ALL_FILES = FileReach(
    actions=["list", "stat", "read", "read_many", "write", "mkdir", "delete", "edit", "move", "search", "tree"],
    write=True,
    delete=True,
)


def test_alternatives_name_only_what_the_agent_has() -> None:
    lines = alternatives(["npm", "node"], "C:/p", _ALL_FILES)
    text = "\n".join(lines)
    assert "- grep, findstr: file_access search with text" in text
    assert "- cat, type, head, tail: file_access read" in text
    assert "- ls, dir, find: file_access list, tree or search." in text
    assert "- cd, pwd: not needed; every command runs in C:/p." in text
    assert "inline code is rejected" in text and "npm run build" in text
    assert "one program per call" in text
    # An allowed program is not listed as unavailable.
    assert "- dir, find, tree:" in "\n".join(alternatives(["npm", "ls"], "C:/p", _ALL_FILES))
    reading = FileReach(actions=["list", "read", "search", "tree"], write=False, delete=False)
    text = "\n".join(alternatives(["npm"], "C:/p", reading))
    assert "- mkdir: not available; that file action is switched off." in text
    assert "- grep, findstr: file_access search with text" in text
    without = "\n".join(alternatives(["python"], "C:/p", None))
    assert "- grep, findstr: not available; you have no file tool." in without
    assert "npm run build" not in without


def test_one_line_per_kind_of_mistake() -> None:
    def _lesson(command: str, key: str):
        return lesson(command, key, programs=["npm", "node", "python"], root="C:/p", files=_ALL_FILES)

    key, line = _lesson('grep -n "x" dist/a.css', "tools.terminal.notGranted")
    assert key == "search" and line.startswith('`grep -n "x" dist/a.css`: grep is not allowed here.')
    assert "Use file_access search with text" in line
    assert _lesson("findstr x a.css", "tools.terminal.notGranted")[0] == "search"
    assert _lesson("cat a.css", "tools.terminal.notGranted")[0] == "read"
    key, line = _lesson("git status", "tools.terminal.notGranted")
    assert key == "program:git" and "Allowed programs: npm, node, python." in line
    key, line = _lesson("node -e \"console.log(1)\"", "tools.terminal.inlineCode")
    assert key == "inline" and "inline code (-e, -c, --eval) is rejected" in line
    assert _lesson("npm run build | grep error", "tools.terminal.shellSyntax")[0] == "pipe"
    assert _lesson("npm install && npm run build", "tools.terminal.shellSyntax")[0] == "chain"
    assert _lesson("npm run build > out.txt", "tools.terminal.shellSyntax")[0] == "redirect"
    assert _lesson("cd src && npm test", "tools.terminal.shellSyntax")[0] == "cd"
    assert _lesson("git -C ../other status", "tools.terminal.outsideRoot")[0] == "outside"
    assert _lesson("npm run build", "tools.terminal.timeout") is None
    assert len(_lesson("grep " + "x" * 200, "tools.terminal.notGranted")[1]) < 200
    assert block([]) == ""


def _terminal_doc(root) -> dict:
    from tests.run.test_validate import _orchestrator_doc

    doc = _orchestrator_doc()
    doc["nodes"].extend(
        [
            {
                "id": "term",
                "type": "tool",
                "position": {"x": 0, "y": 0},
                "data": {"kind": "terminal", "rootPath": str(root), "terminalPrograms": ["python"]},
            },
            {
                "id": "files",
                "type": "tool",
                "position": {"x": 0, "y": 0},
                "data": {"kind": "file_access", "rootPath": str(root)},
            },
        ]
    )
    doc["edges"].extend(
        [
            {"id": "et", "source": "term", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"},
            {"id": "ef", "source": "files", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"},
        ]
    )
    return doc


def test_a_rejected_command_stays_in_the_prompt_for_this_and_the_next_call(monkeypatch, api_env, tmp_path) -> None:
    from app.db.runs import list_logs
    from tests.run.test_harness import _drive

    seen: dict = {"agent": [], "orch": 0, "requests": []}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            seen["orch"] += 1
            if seen["orch"] <= 2:
                return CompletionResult(
                    content='{"action":"call","agent":"Schreiber","task":"Prüfe die Styles."}', model="m", finish_reason="stop"
                )
            return CompletionResult(content='{"action":"finish","text":"Fertig."}', model="m", finish_reason="stop")
        seen["agent"].append(system)
        seen["requests"].append(list(req.messages))
        if len(seen["agent"]) == 1:
            # First call, first step: a command the terminal does not allow.
            return CompletionResult(
                content=None,
                tool_calls=[ToolCall(id="g", name="terminal", arguments='{"command": "grep -n card src/app.css"}')],
                model="m",
                finish_reason="tool_calls",
            )
        return CompletionResult(content="Geprüft.", model="m", finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_terminal_doc(tmp_path))
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    first, after = seen["agent"][0], seen["agent"][1]
    # The next call of the agent starts again with system and task only.
    starts = [index for index, request in enumerate(seen["requests"]) if len(request) == 2]
    next_call = seen["agent"][starts[1]]
    # A: before any mistake the prompt says what to use instead.
    assert "- grep, findstr: file_access search with text" in first
    assert "# Rejected earlier in this run" not in first
    # B: within the call the system prompt stays as it was (run 51a45408: a change there made
    # hybrid models read the whole transcript again); the lesson comes with the tool result.
    assert after == first
    tool_result = [message for message in seen["requests"][1] if message.role == "tool"][-1].content or ""
    assert (
        "Remember for the rest of this task: `grep -n card src/app.css`: grep is not allowed here. "
        "Use file_access search with text"
    ) in tool_result
    # C: the next call of the same agent starts with it.
    assert "`grep -n card src/app.css`: grep is not allowed here." in next_call
    lessons = [row["payload"] for row in list_logs(stored["id"]) if row["message"] == "run.agent.terminalLesson"]
    assert lessons == [{"kind": "search", "lessons": 1}]


def test_the_chat_masks_message_params() -> None:
    """Review finding 2: the briefing text went to the chat as a parameter, unmasked."""
    from app.db.engine import utc_now
    from app.run.controller import RunController
    from app.run.models import ChatMessage

    ctrl = RunController()
    ctrl.remember_chat(
        ChatMessage(
            id="m1",
            runId="",
            role="assistant",
            content="Background: key=sk-abcdefghijklmnop",
            createdAt=utc_now(),
            messageKey="monitoring.chat.briefing",
            messageParams={"text": "key=sk-abcdefghijklmnop", "count": 3},
        )
    )
    msg = ctrl.conversation[-1]
    assert msg.content == "Background: key=sk-***"
    assert msg.message_params == {"text": "key=sk-***", "count": 3}
