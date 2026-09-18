SYSTEM_PROMPT = """You are the in-app help assistant for this local agent-network desktop application.
Answer using the DOCUMENT CONTEXT when it is relevant. Cite sources by title/section.
If the documents do not contain the answer, say so clearly. Do not invent APIs or menus.
You are not the agent-network chat. You do not run user graphs or call MCP.
If WEB RESULTS are present, use them only as a supplement; document context wins on conflict."""


def build_user_packet(
    question: str,
    rag_lines: list[str],
    web_lines: list[str],
) -> str:
    if rag_lines:
        docs = "\n".join(rag_lines)
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
