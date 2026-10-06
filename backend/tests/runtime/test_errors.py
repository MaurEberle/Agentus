from app.runtime.errors import RuntimeApiError, truncated_tool_call_name


def test_truncated_tool_call_name_reads_llama_server_detail() -> None:
    exc = RuntimeApiError(
        "runtime.badRequest",
        detail=(
            'llama-server returned invalid tool call arguments for '
            '"mcp__abc__write_file": unexpected end of JSON input'
        ),
    )
    assert truncated_tool_call_name(exc) == "mcp__abc__write_file"


def test_truncated_tool_call_name_ignores_other_bad_requests() -> None:
    assert truncated_tool_call_name(RuntimeApiError("runtime.badRequest", detail="invalid model")) is None
    assert truncated_tool_call_name(RuntimeApiError("runtime.timeout")) is None
    assert truncated_tool_call_name(RuntimeError("nope")) is None


def test_truncated_tool_call_name_without_tool_name() -> None:
    exc = RuntimeApiError("runtime.badRequest", detail="invalid tool call arguments")
    assert truncated_tool_call_name(exc) == "tool"
