from app.help.prompt import answer_language_name, system_prompt


def test_unknown_locale_answers_in_english() -> None:
    assert answer_language_name(None) == "English"
    assert answer_language_name("zz") == "English"
    text = system_prompt("zz")
    assert "APP LANGUAGE: English" in text
    assert "Do not cite help documents" in text
    assert "Never write a <think> block" in text
    assert "WEB SEARCH is off" in text


def test_known_locale_names_the_app_language() -> None:
    assert answer_language_name("de-DE") == "German"
    assert "APP LANGUAGE: German" in system_prompt("de")
    assert "write the entire answer in English" in system_prompt("ja")


def test_system_prompt_names_web_search_when_enabled() -> None:
    text = system_prompt("de", web_search_enabled=True)
    assert "WEB SEARCH is on" in text
    assert "WEB RESULTS win for facts that are not about this app" in text
    assert "Never say you have no web search" in text
    assert "WEB SEARCH is off" not in text