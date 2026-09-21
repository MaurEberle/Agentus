from app.run.orchestrate import match_agent, orchestrator_instructions, parse_orchestrator_action


def test_parse_actions() -> None:
    assert parse_orchestrator_action('{"action":"ask","text":"Welche Sprache?"}') == {
        "action": "ask",
        "text": "Welche Sprache?",
        "agent": "",
        "task": "",
    }
    fenced = '```json\n{"action":"call","agent":"ag","task":"schreib"}\n```'
    parsed = parse_orchestrator_action(fenced)
    assert parsed["action"] == "call"
    assert parsed["agent"] == "ag"
    assert parsed["task"] == "schreib"


def test_plain_text_is_a_reply() -> None:
    assert parse_orchestrator_action("Hallo")["action"] == "reply"
    assert parse_orchestrator_action("Hallo")["text"] == "Hallo"


def test_instructions_name_each_channel_and_stay_sequential() -> None:
    text = orchestrator_instructions("leite", [("ag", "Schreiber", "schreibe")])
    assert "one agent at a time" in text
    assert "private channel" in text
    assert "id: ag" in text
    assert "parallel" not in text


def test_match_agent_by_id_or_name() -> None:
    roster = [("ag", "Schreiber"), ("other", "Prüfer")]
    assert match_agent("ag", roster) == "ag"
    assert match_agent("schreiber", roster) == "ag"
    assert match_agent("nein", roster) is None
