"""What the orchestrator and each agent are allowed to see during one run.

The object lives only for that run. It stores each agent's own text and file list,
then builds a fresh message list for every call. Full texts stay out of the
orchestrator transcript. A tool agent receives the writer's source, not its own
earlier prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.run.limits import AGENT_TURN_TOKEN_BUDGET
from app.runtime.completions import estimate_token_count
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import ToolCall

_PREVIEW_CHARS = 180
_LEDGER_SHOWN = 8
_LEDGER_KEPT = 24


@dataclass(frozen=True)
class FileFact:
    label: str
    ok: bool
    path: str = ""
    size: int | None = None


@dataclass
class AgentNote:
    agent_id: str
    name: str
    has_tools: bool
    text: str = ""
    ledger: list[FileFact] = field(default_factory=list)


class RunBriefing:
    def __init__(self) -> None:
        self.notes: dict[str, AgentNote] = {}
        self.source_id: str | None = None
        self.open_tool_agent = ""
        self.dialogue: list[LlmMessage] = []

    def add_user(self, text: str) -> None:
        cleaned = text.strip()
        if cleaned:
            self.dialogue.append(LlmMessage(role="user", content=cleaned))

    def add_assistant(self, text: str) -> None:
        cleaned = text.strip()
        if cleaned:
            self.dialogue.append(LlmMessage(role="assistant", content=cleaned))

    def record(
        self,
        *,
        agent_id: str,
        name: str,
        has_tools: bool,
        text: str,
        files: list[FileFact],
    ) -> None:
        note = self.notes.get(agent_id)
        if note is None:
            note = AgentNote(agent_id=agent_id, name=name, has_tools=has_tools)
            self.notes[agent_id] = note
        note.name = name or agent_id
        note.has_tools = has_tools
        if has_tools:
            note.ledger.extend(files)
            if len(note.ledger) > _LEDGER_KEPT:
                note.ledger = note.ledger[-_LEDGER_KEPT:]
            note.text = ""
            if _tool_succeeded(note.ledger):
                if self.open_tool_agent == agent_id:
                    self.open_tool_agent = ""
            else:
                self.open_tool_agent = agent_id
            return
        cleaned = text.strip()
        if cleaned:
            note.text = cleaned
            self.source_id = agent_id

    def overview(self) -> str:
        if not self.notes:
            return "No agent has run yet."
        return "\n".join(_card(note, self.open_tool_agent) for note in self.notes.values())

    def orchestrator_messages(self, system: str) -> list[LlmMessage]:
        body = system.rstrip() + "\n\nOverview:\n" + self.overview()
        return [LlmMessage(role="system", content=body), *self.dialogue]

    def agent_task(self, agent_id: str, task: str, *, has_tools: bool) -> str:
        parts = [task.strip() or " "]
        note = self.notes.get(agent_id)
        if has_tools:
            if note and note.ledger:
                parts.append("Files already written in this run:\n" + _ledger_text(note.ledger))
            source = self._source(agent_id)
            if source is not None:
                parts.append(
                    f"Source from {source.name}. Use this text. Do not replace it with a new story:\n{source.text}"
                )
        elif note and note.text:
            parts.append("Your earlier result:\n" + note.text)
        return "\n\n".join(parts)

    def _source(self, agent_id: str) -> AgentNote | None:
        if not self.source_id or self.source_id == agent_id:
            return None
        source = self.notes.get(self.source_id)
        if source is None or not source.text.strip():
            return None
        return source


def file_fact(name: str, args: dict[str, object], result: object, *, ok: bool) -> FileFact:
    action = str(args.get("action") or "").strip().lower()
    label = f"{name} {action}".strip()
    body: dict[str, object] = {}
    if isinstance(result, dict):
        nested = result.get("result")
        if isinstance(nested, dict):
            body = nested
    path = str(body.get("path") or args.get("path") or "").strip()
    size = body.get("bytes")
    return FileFact(label=label, ok=ok, path=path, size=size if isinstance(size, int) else None)


def turn_over_budget(messages: list[LlmMessage]) -> bool:
    parts: list[str] = []
    for message in messages:
        if message.content:
            parts.append(message.content)
        for call in message.tool_calls or []:
            parts.append(_call_text(call))
    return estimate_token_count("\n".join(parts)) > AGENT_TURN_TOKEN_BUDGET


def _call_text(call: ToolCall) -> str:
    return f"{call.name} {call.arguments or ''}"


def _card(note: AgentNote, open_tool_agent: str) -> str:
    if note.has_tools:
        lines = [f"{note.name} ({note.agent_id}): tool agent."]
        if note.ledger:
            lines.extend(_ledger_lines(note.ledger))
        else:
            lines.append("Tools: no calls.")
        if open_tool_agent == note.agent_id:
            lines.append("Last call did not finish the tool work.")
        return "\n".join(lines)
    title = next((line.strip() for line in note.text.splitlines() if line.strip()), "(empty)")
    title = title[:80]
    opening = " ".join(note.text.split())[:_PREVIEW_CHARS]
    return f"{note.name} ({note.agent_id}): {len(note.text)} characters. {title}\nOpening: {opening}"


_CHANGES = frozenset({"write", "delete"})


def _tool_succeeded(ledger: list[FileFact]) -> bool:
    return any(item.ok and _action(item) in _CHANGES for item in ledger)


def _action(item: FileFact) -> str:
    parts = item.label.split()
    return parts[-1] if parts else ""


def _ledger_text(ledger: list[FileFact]) -> str:
    return "\n".join(_ledger_lines(ledger))


def _ledger_lines(ledger: list[FileFact]) -> list[str]:
    lines: list[str] = []
    for fact in ledger[-_LEDGER_SHOWN:]:
        status = "ok" if fact.ok else "failed"
        extra = f" {fact.path}" if fact.path else ""
        if fact.size is not None:
            extra += f" ({fact.size} bytes)"
        lines.append(f"- {fact.label}: {status}{extra}")
    return lines
