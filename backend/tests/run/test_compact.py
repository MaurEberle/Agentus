from app.run.compact import (
    TRUNCATED_NOTE,
    compact_transcript,
    rewrite_with_state,
    window_pressure,
)
from app.runtime.models import ChatMessage, ToolCall


class _Mem:
    def __init__(self) -> None:
        self.raised = {"m": 8000}
        self.loaded: dict = {}
        self.thinking: dict = {}


class _Llm:
    model = "m"
    max_tokens = None
    num_ctx = None


def _tool(name: str, args: str, body: str, call_id: str) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id=call_id, name=name, arguments=args)],
        ),
        ChatMessage(role="tool", content=body, name=name, tool_call_id=call_id),
    ]


def test_duplicate_tool_results_keep_the_latest() -> None:
    messages = [
        ChatMessage(role="system", content="sys"),
        *_tool("file_access", '{"action":"read","path":"a.xlsx"}', "SHEET-ONE" * 50, "1"),
        *_tool("file_access", '{"action":"read","path":"a.xlsx"}', "SHEET-TWO", "2"),
    ]
    assert compact_transcript(messages, budget=1000)
    assert "superseded" in (messages[2].content or "")
    assert messages[4].content == "SHEET-TWO"


def test_oversized_draft_is_replaced() -> None:
    messages = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="assistant", content="draft " * 5000),
    ]
    assert compact_transcript(messages, budget=1000)
    assert messages[1].content == TRUNCATED_NOTE


def test_pressure_uses_the_last_prompt_when_the_estimate_is_low() -> None:
    messages = [ChatMessage(role="user", content="short")]
    assert window_pressure(messages, _Llm(), _Mem(), last_prompt_tokens=7500, last_context_max=8000)
    assert not window_pressure(messages, _Llm(), _Mem())


def test_state_keeps_the_latest_tool_result() -> None:
    messages = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="clean the sheet"),
        ChatMessage(role="assistant", content="long draft " * 100),
        *_tool("excel_read_sheet", '{"path":"a.xlsx"}', "LATEST-ROWS", "9"),
    ]
    rewritten = rewrite_with_state(messages, "task: clean. errors: zip.")
    blob = "\n".join(message.content or "" for message in rewritten)
    assert "sys" in blob
    assert "clean the sheet" in blob
    assert "LATEST-ROWS" in blob
    assert "task: clean. errors: zip." in blob
    assert "long draft" not in blob
