from app.run.orchestrate import match_agent, needs_repair, orchestrator_instructions, parse_orchestrator_action


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


def test_truncated_call_json_still_calls() -> None:
    # The task string is closed; the object is cut off after the next quote, as in the Storymaker run.
    raw = '{"action":"call","agent":"Autor","task":"Schreibe eine freundliche Kindergeschichte.","'
    parsed = parse_orchestrator_action(raw)
    assert parsed["action"] == "call"
    assert parsed["agent"] == "Autor"
    assert parsed["task"] == "Schreibe eine freundliche Kindergeschichte."


def test_prose_call_addresses_the_agent() -> None:
    parsed = parse_orchestrator_action(
        'Call agent-7fef4344 with the full German story under the title "Der Tiger auf dem Bauernhof".'
    )
    assert parsed["action"] == "call"
    assert parsed["agent"] == "agent-7fef4344"
    assert "Der Tiger auf dem Bauernhof" in parsed["task"]


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
    assert "overview" in text
    assert "parallel" not in text


def test_decision_inside_think_is_kept_when_nothing_else_is_visible() -> None:
    raw = '<think>{"action":"call","agent":"Autor","task":"Titel neu schreiben"}</think>'
    parsed = parse_orchestrator_action(raw)
    assert parsed["action"] == "call"
    assert parsed["agent"] == "Autor"
    assert parsed["task"] == "Titel neu schreiben"


def test_visible_reply_wins_over_a_call_hidden_in_think() -> None:
    raw = '<think>{"action":"call","agent":"Autor","task":"neu"}</think>\nDie Geschichte ist fertig.'
    parsed = parse_orchestrator_action(raw)
    assert parsed["action"] == "reply"
    assert parsed["text"] == "Die Geschichte ist fertig."


def test_empty_turn_needs_repair() -> None:
    assert needs_repair(parse_orchestrator_action("<think>nur nachgedacht</think>"))
    assert needs_repair({"action": "ask", "text": ""})
    assert needs_repair({"action": "reply", "text": "Call agent with the story"})
    assert needs_repair({"action": "reply", "text": "Hallo"}) is False


def test_match_agent_by_id_or_name() -> None:
    roster = [("ag", "Schreiber"), ("other", "Prüfer")]
    assert match_agent("ag", roster) == "ag"
    assert match_agent("schreiber", roster) == "ag"
    assert match_agent("nein", roster) is None
