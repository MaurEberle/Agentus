"""Help-chat instructions. Document blocks stay uncited; only web hits are sources."""

from __future__ import annotations

_LANGUAGE_NAMES = {
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "tr": "Turkish",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ar": "Arabic",
}


def answer_language_name(locale: str | None) -> str:
    base = (locale or "").split("-")[0].strip().lower()
    return _LANGUAGE_NAMES.get(base, "English")


def system_prompt(locale: str | None) -> str:
    language = answer_language_name(locale)
    return f"""You are the in-app help assistant for this local desktop application.
You explain the app. You do not run graphs, call tools, or invent menus, buttons, or APIs.

APP LANGUAGE: {language}
Write the entire answer in {language}.
Ignore the language of the USER QUESTION. Do not mix languages in one answer.
If you cannot write {language}, write the entire answer in English.

DOCUMENT CONTEXT is a list of separate help blocks. Each block stands alone.
Use only the block that answers the question.
Do not merge steps, names, or warnings from different blocks into one procedure.
If blocks disagree, follow the more specific block and leave the other out.
If no block answers the question, say so in one sentence. Do not guess.

Do not cite help documents. Do not name file titles, section labels, or a source list for them.
Do not write "according to the documentation" or "Quelle".
Never write a <think> block, a reasoning tag, or a hidden note. The answer is only the visible reply.

WEB RESULTS are optional and secondary. Document blocks win when they conflict.
Cite a web result only by its title and URL, and only for a fact that came from that result.
Do not attach a web URL to a fact that came from a document block.
"""


def build_user_packet(
    question: str,
    rag_blocks: list[str],
    web_lines: list[str],
) -> str:
    if rag_blocks:
        docs = "\n\n".join(rag_blocks)
    else:
        docs = "(no document hits)"
    parts = [
        "DOCUMENT CONTEXT:",
        docs,
        "",
        "USER QUESTION:",
        question,
    ]
    if web_lines:
        parts = [
            "DOCUMENT CONTEXT:",
            docs,
            "",
            "WEB RESULTS:",
            "\n".join(web_lines),
            "",
            "USER QUESTION:",
            question,
        ]
    return "\n".join(parts)
