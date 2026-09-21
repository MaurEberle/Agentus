from app.help.prompt import answer_language_name, system_prompt


def test_unknown_locale_answers_in_english() -> None:
    assert answer_language_name(None) == "English"
    assert answer_language_name("zz") == "English"
    text = system_prompt("zz")
    assert "APP LANGUAGE: English" in text
    assert "Do not cite help documents" in text
    assert "Never write a <think> block" in text


def test_known_locale_names_the_app_language() -> None:
    assert answer_language_name("de-DE") == "German"
    assert "APP LANGUAGE: German" in system_prompt("de")
    assert "write the entire answer in English" in system_prompt("ja")