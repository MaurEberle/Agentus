from app.help.visible import ThinkStripper, strip_think


def test_closed_block_is_removed() -> None:
    assert strip_think("<think>geheim</think>\n\nDie Palette liegt links.") == (
        "Die Palette liegt links."
    )


def test_case_and_split_tags_stay_hidden() -> None:
    tool = ThinkStripper()
    assert tool.feed("<THI") == ""
    assert tool.feed("NK>noch ") == ""
    assert tool.feed("intern</thi") == ""
    assert tool.feed("nk>\nAntwort") == "Antwort"
    assert tool.finish() == ""


def test_unclosed_block_is_dropped() -> None:
    tool = ThinkStripper()
    assert tool.feed("Vorher <think>geheim") == "Vorher "
    assert tool.finish() == ""


def test_dangling_tag_start_is_not_shown() -> None:
    tool = ThinkStripper()
    assert tool.feed("Antwort <thi") == "Antwort "
    assert tool.finish() == ""


def test_text_around_a_block_stays() -> None:
    assert strip_think("Siehe <think>x</think> die Fläche.") == "Siehe  die Fläche."
