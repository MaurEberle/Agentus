from app.run.orchestrate import match_agent, orchestrator_instructions, parse_orchestrator_action, reject_reason


def test_parse_actions() -> None:
    assert parse_orchestrator_action('{"action":"ask","text":"Welche Sprache?"}') == {
        "action": "ask",
        "text": "Welche Sprache?",
        "agent": "",
        "task": "",
        "source": "",
    }
    fenced = '```json\n{"action":"call","agent":"ag","task":"schreib"}\n```'
    parsed = parse_orchestrator_action(fenced)
    assert parsed["action"] == "call"
    assert parsed["agent"] == "ag"
    assert parsed["task"] == "schreib"


def test_plain_text_is_a_reply() -> None:
    assert parse_orchestrator_action("Hallo")["action"] == "reply"
    assert parse_orchestrator_action("Hallo")["text"] == "Hallo"


def test_truncated_call_json_still_calls() -> None:
    # The task string is closed; the object is cut off after the next quote, as in the Storymaker run.
    raw = '{"action":"call","agent":"Autor","task":"Schreibe eine freundliche Kindergeschichte.","'
    parsed = parse_orchestrator_action(raw)
    assert parsed["action"] == "call"
    assert parsed["agent"] == "Autor"
    assert parsed["task"] == "Schreibe eine freundliche Kindergeschichte."


def test_prose_call_is_not_a_call() -> None:
    raw = 'Call agent-7fef4344 with the full German story under the title "Der Tiger auf dem Bauernhof".'
    parsed = parse_orchestrator_action(raw)
    assert parsed["action"] == "reply"
    assert reject_reason(raw) == "unreadable"


def test_think_only_control_is_empty() -> None:
    raw = '<think>{"action":"call","agent":"ag","task":"schreib"}</think>'
    assert reject_reason(raw) == "empty"


def test_empty_ask_is_rejected() -> None:
    raw = '{"action":"ask","text":""}'
    assert reject_reason(raw) == "empty"


def test_pasted_story_with_broken_quotes_is_not_a_call() -> None:
    story = "Wort " * 80 + 'fragte: "hallo" und weiter'
    raw = '{"action":"call","agent":"Translate","task":"' + story + '"}'
    parsed = parse_orchestrator_action(raw)
    assert parsed["action"] == "reply"


def test_instructions_name_each_channel_and_stay_sequential() -> None:
    text = orchestrator_instructions("leite", [("ag", "Schreiber", "schreibe")])
    assert "one agent at a time" in text
    assert "private channel" in text
    assert "id: ag" in text
    assert "parallel" not in text
    assert "not in this prompt" in text
    assert "status line" in text


def test_match_agent_by_id_or_name() -> None:
    roster = [("ag", "Schreiber"), ("other", "Prüfer")]
    assert match_agent("ag", roster) == "ag"
    assert match_agent("schreiber", roster) == "ag"
    assert match_agent("nein", roster) is None
