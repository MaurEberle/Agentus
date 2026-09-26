from app.run.briefing import FileFact, RunBriefing, turn_over_budget
from app.run.limits import AGENT_TURN_TOKEN_BUDGET
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import ToolCall


def test_writer_text_stays_the_source_for_a_tool_agent() -> None:
    briefing = RunBriefing()
    story = "Anfang. " + ("satz " * 80) + "MARKIERUNG-ENDE"
    briefing.record(agent_id="autor", name="Autor", has_tools=False, text=story, files=[])
    briefing.record(
        agent_id="save",
        name="Translate",
        has_tools=True,
        text="vereinfacht ganz anders",
        files=[],
    )
    delivered = briefing.agent_task("save", "speichere drei dateien", has_tools=True)
    assert "MARKIERUNG-ENDE" in delivered
    assert "vereinfacht" not in delivered
    again = briefing.agent_task("autor", "titel korrigieren", has_tools=False)
    assert "MARKIERUNG-ENDE" in again
    assert "vereinfacht" not in again


def test_orchestrator_overview_hides_the_full_story() -> None:
    briefing = RunBriefing()
    briefing.add_user("eine geschichte")
    story = "Anfang. " + ("satz " * 80) + "MARKIERUNG-ENDE"
    briefing.record(agent_id="autor", name="Autor", has_tools=False, text=story, files=[])
    briefing.record(
        agent_id="save",
        name="Translate",
        has_tools=True,
        text="",
        files=[FileFact(label="file_access write", ok=True, path="Bimbo/en.txt", size=40)],
    )
    messages = briefing.orchestrator_messages("protocol")
    joined = "\n".join(message.content or "" for message in messages)
    assert "MARKIERUNG-ENDE" not in joined
    assert "Opening: Anfang." in joined
    assert "Bimbo/en.txt" in joined
    assert "eine geschichte" in joined
    assert messages[0].role == "system"


def test_failed_tool_call_stays_open_without_replacing_the_source() -> None:
    briefing = RunBriefing()
    briefing.record(agent_id="autor", name="Autor", has_tools=False, text="HONIG", files=[])
    briefing.record(
        agent_id="save",
        name="Translate",
        has_tools=True,
        text="fertig",
        files=[FileFact(label="file_access write", ok=False, path="Bimbo/en.txt")],
    )
    assert briefing.source_id == "autor"
    assert briefing.open_tool_agent == "save"
    assert "Last call did not finish the tool work." in briefing.overview()
    assert "HONIG" in briefing.agent_task("save", "nochmal", has_tools=True)


def test_a_saved_file_closes_the_agent_even_when_another_write_failed() -> None:
    briefing = RunBriefing()
    briefing.record(
        agent_id="save",
        name="Translate",
        has_tools=True,
        text="",
        files=[
            FileFact(label="file_access write", ok=False, path="story/de.txt"),
            FileFact(label="file_access write", ok=True, path="story/de.txt", size=100),
            FileFact(label="file_access write", ok=True, path="story/en.txt", size=90),
            FileFact(label="file_access mkdir", ok=True, path="story"),
        ],
    )
    assert briefing.open_tool_agent == ""
    assert "Last call did not finish the tool work." not in briefing.overview()
    briefing.record(agent_id="save", name="Translate", has_tools=True, text="", files=[])
    assert briefing.open_tool_agent == ""


def test_a_successful_delete_closes_the_agent() -> None:
    briefing = RunBriefing()
    briefing.record(
        agent_id="save",
        name="Translate",
        has_tools=True,
        text="",
        files=[
            FileFact(label="file_access delete", ok=False, path="story/alt.txt"),
            FileFact(label="file_access delete", ok=True, path="story/alt.txt"),
        ],
    )
    assert briefing.open_tool_agent == ""


def test_mkdir_or_read_without_a_change_stays_open() -> None:
    briefing = RunBriefing()
    briefing.record(
        agent_id="save",
        name="Translate",
        has_tools=True,
        text="",
        files=[
            FileFact(label="file_access mkdir", ok=True, path="story"),
            FileFact(label="file_access read", ok=True, path="story/de.txt"),
        ],
    )
    assert briefing.open_tool_agent == "save"


def test_only_failed_calls_stay_open() -> None:
    briefing = RunBriefing()
    briefing.record(
        agent_id="save",
        name="Translate",
        has_tools=True,
        text="",
        files=[FileFact(label="file_access delete", ok=False, path="story/alt.txt")],
    )
    assert briefing.open_tool_agent == "save"


def test_turn_budget_counts_tool_arguments() -> None:
    huge = "x" * ((AGENT_TURN_TOKEN_BUDGET + 10) * 4)
    messages = [
        LlmMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="1", name="file_access", arguments=huge)],
        )
    ]
    assert turn_over_budget(messages)
    assert turn_over_budget([LlmMessage(role="user", content="kurz")]) is False
