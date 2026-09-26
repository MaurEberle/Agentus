from app.run.memory import (
    FileFact,
    RunMemory,
    ToolEvent,
    file_fact,
    record_tool,
    reused_file_result,
)


def test_status_line_hides_the_manuscript() -> None:
    memory = RunMemory()
    memory.add_user("Hallo")
    record = memory.begin_call("ag", "Schreiber", "schreib", False)
    record.text = "GEHEIMES-MANUSKRIPT"
    record.finished = True
    blob = memory.prompt_text("system")
    assert "GEHEIMES-MANUSKRIPT" not in blob
    assert "characters: 19" in blob
    assert "Hallo" in blob


def test_orchestrator_tool_lines_hide_the_result() -> None:
    memory = RunMemory()
    memory.note_own_tool(
        ToolEvent(name="file_access", arguments="{}", ok=True, result="ROHER-LISTE"),
        FileFact(tool="file_access", action="list", path=".", ok=True),
    )
    memory.note_own_tool(
        ToolEvent(name="calculator", arguments="{}", ok=True, result="42"),
        None,
    )
    blob = memory.prompt_text("system")
    assert "ROHER-LISTE" not in blob
    assert "42" not in blob
    assert ". list ok" in blob
    assert "calculator ok" in blob
    assert memory.to_dict()["ownTools"][0]["result"] == "ROHER-LISTE"


def test_rejected_body_stays_out_of_the_prompt() -> None:
    memory = RunMemory()
    memory.reject("MÜLL-BODY", "unreadable")
    memory.add_note("Reply with one JSON object.")
    assert memory.exposes_rejected("system") is False
    assert memory.to_dict()["rejected"][0]["body"] == "MÜLL-BODY"


def test_anomaly_is_one_slice_and_then_cleared() -> None:
    memory = RunMemory()
    record = memory.begin_call("ag", "Schreiber", "schreib", False)
    record.error = "runtime.timeout"
    memory.set_anomaly(record)
    blob = memory.prompt_text("system")
    assert "Anomaly for Schreiber (ag)." in blob
    assert "runtime.timeout" in blob
    assert "GEHEIM" not in blob
    memory.clear_anomaly()
    assert "Anomaly" not in memory.prompt_text("system")


def test_anomaly_text_only_when_the_failed_file_has_no_path() -> None:
    memory = RunMemory()
    record = memory.begin_call("t", "Save", "speichere", True)
    record.text = "X" * 500
    record.error = "tool failed"
    record.files.append(FileFact(tool="file_access", action="write", path="", ok=False))
    memory.set_anomaly(record)
    blob = memory.prompt_text("system")
    assert "text:\n" + ("X" * 400) in blob
    assert "X" * 401 not in blob

    other = RunMemory()
    failed = other.begin_call("t", "Save", "speichere", True)
    failed.text = "Y" * 80
    failed.error = "tool failed"
    failed.files.append(FileFact(tool="file_access", action="write", path="a.txt", ok=False))
    other.set_anomaly(failed)
    shown = other.prompt_text("system")
    assert "a.txt" in shown
    assert "Y" * 20 not in shown


def test_tool_agent_prose_is_not_a_source() -> None:
    memory = RunMemory()
    memory.add_user("DIALOG-DARF-NICHT-AN-DEN-AGENTEN")
    record = memory.begin_call("t", "Save", "speichere", True)
    record.text = "EIGENE-PROSA"
    record.finished = True
    choice = memory.resolve_source("", [("t", "Save")])
    assert choice.text == ""
    assert choice.auto is False
    message = memory.agent_message("t", "speichere", True, choice.text)
    assert "speichere" in message
    assert "EIGENE-PROSA" not in message
    assert "DIALOG-DARF-NICHT" not in message


def test_one_writer_is_attached_automatically() -> None:
    memory = RunMemory()
    writer = memory.begin_call("w", "Autor", "schreib", False)
    writer.text = "QUELLTEXT"
    writer.finished = True
    choice = memory.resolve_source("", [("w", "Autor"), ("t", "Save")])
    assert choice.auto is True
    assert choice.text == "QUELLTEXT"
    message = memory.agent_message("t", "speichere", True, choice.text)
    assert "QUELLTEXT" in message
    assert "Source text" in message


def test_two_writers_without_source_name_ids_only() -> None:
    memory = RunMemory()
    first = memory.begin_call("a", "A", "eins", False)
    first.text = "TEXT-A"
    second = memory.begin_call("b", "B", "zwei", False)
    second.text = "TEXT-B"
    choice = memory.resolve_source("", [("a", "A"), ("b", "B")])
    assert choice.ambiguous == ["a", "b"]
    assert choice.text == ""


def test_explicit_source_picks_that_text() -> None:
    memory = RunMemory()
    first = memory.begin_call("a", "A", "eins", False)
    first.text = "TEXT-A"
    second = memory.begin_call("b", "B", "zwei", False)
    second.text = "TEXT-B"
    choice = memory.resolve_source("b", [("a", "A"), ("b", "B")])
    assert choice.text == "TEXT-B"
    assert choice.auto is False
    missing = memory.resolve_source("nein", [("a", "A")])
    assert missing.missing == "nein"


def test_writer_sees_only_its_own_earlier_text() -> None:
    memory = RunMemory()
    memory.add_user("DIALOG-DARF-NICHT-AN-DEN-AGENTEN")
    record = memory.begin_call("a", "Autor", "schreib", False)
    record.text = "EIGENER-TEXT"
    record.finished = True
    message = memory.agent_message("a", "nochmal", False, "")
    assert "EIGENER-TEXT" in message
    assert "DIALOG-DARF-NICHT" not in message


def test_continuation_skips_tool_arguments() -> None:
    memory = RunMemory()
    record = memory.begin_call("t", "Save", "speichere", True)
    record_tool(
        record,
        ToolEvent(name="file_access", arguments='{"secret":"ARG-GEHEIM"}', ok=True, result="wrote"),
        file_fact(
            "file_access",
            {"action": "write", "path": "out.txt"},
            {"result": {"path": "out.txt", "bytes": 12}},
            ok=True,
        ),
    )
    message = memory.continuation_message("t", "speichere", True, "QUELLTEXT")
    assert "ARG-GEHEIM" not in message
    assert "wrote" not in message
    assert "QUELLTEXT" in message
    assert "out.txt" in message
    assert "Do not repeat" in message
    reused = reused_file_result(record, "write", "out.txt")
    assert reused is not None
    assert reused["ok"] is True
    assert reused["result"]["reused"] is True
    assert reused["result"]["bytes"] == 12
    assert reused_file_result(record, "write", "other.txt") is None
    assert reused_file_result(record, "delete", "out.txt") is None
