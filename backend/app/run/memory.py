"""Run memory for the orchestrator path. Stored course, not the prompt."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.help.visible import strip_think
from app.run.orchestrate import match_agent
from app.runtime.models import ChatMessage as LlmMessage

_ANOMALY_TEXT_CAP = 400
_FILES_SHOWN = 8
_FILES_KEPT = 48


@dataclass
class FileFact:
    tool: str
    action: str
    path: str
    ok: bool
    size: int | None = None


@dataclass
class ToolEvent:
    name: str
    arguments: str
    ok: bool
    result: str


@dataclass
class AgentRecord:
    agent_id: str
    name: str
    task: str
    has_tools: bool
    text: str = ""
    tools: list[ToolEvent] = field(default_factory=list)
    files: list[FileFact] = field(default_factory=list)
    finished: bool = False
    error: str = ""
    saw_tokens: bool = False
    tool_ok: bool = False


@dataclass
class Turn:
    role: str
    kind: str
    text: str


@dataclass
class Rejected:
    reason: str
    body: str


@dataclass
class SourceChoice:
    text: str = ""
    ambiguous: list[str] = field(default_factory=list)
    missing: str = ""
    auto: bool = False


class RunMemory:
    def __init__(self) -> None:
        self.turns: list[Turn] = []
        self.records: list[AgentRecord] = []
        self.own_tools: list[ToolEvent] = []
        self.own_files: list[FileFact] = []
        self.allow_own_tools = True
        self.finish_warned = False
        self.rejected: list[Rejected] = []
        self.windows: list[dict[str, object]] = []
        self.raised: dict[str, int] = {}
        self.arch: dict[str, int | None] = {}
        self.thinking: dict[str, bool] = {}
        self.loaded: dict[str, int | None] = {}
        self._anomaly: str | None = None

    def add_user(self, text: str) -> None:
        cleaned = (text or "").strip()
        if cleaned:
            self.turns.append(Turn("user", "user", cleaned))

    def add_spoken(self, kind: str, text: str) -> None:
        cleaned = (text or "").strip()
        if cleaned:
            self.turns.append(Turn("assistant", kind, cleaned))

    def add_note(self, text: str) -> None:
        cleaned = (text or "").strip()
        if cleaned:
            self.turns.append(Turn("user", "note", cleaned))

    def reject(self, body: str, reason: str) -> None:
        self.rejected.append(Rejected(reason=reason, body=body or ""))

    def last_user(self) -> str:
        for turn in reversed(self.turns):
            if turn.kind == "user":
                return turn.text
        return ""

    def begin_call(self, agent_id: str, name: str, task: str, has_tools: bool) -> AgentRecord:
        record = AgentRecord(agent_id=agent_id, name=name, task=task, has_tools=has_tools)
        self.records.append(record)
        return record

    def resolve_source(self, token: str, roster: list[tuple[str, str]]) -> SourceChoice:
        writers = self._writers()
        raw = (token or "").strip()
        if raw:
            agent_id = match_agent(raw, roster)
            if agent_id is None:
                return SourceChoice(missing=raw)
            text = self._text_of(agent_id)
            if not text:
                return SourceChoice(missing=raw)
            return SourceChoice(text=text)
        if len(writers) == 1:
            return SourceChoice(text=writers[0][2], auto=True)
        if len(writers) > 1:
            return SourceChoice(ambiguous=[item[0] for item in writers])
        return SourceChoice()

    def agent_message(self, agent_id: str, task: str, has_tools: bool, source_text: str) -> str:
        parts = [(task or "").strip() or " "]
        own = "" if has_tools else self._text_of(agent_id)
        if has_tools:
            files = self._files_of(agent_id)
            if files:
                parts.append("Files already written in this run:\n" + _file_block(files))
        elif own:
            parts.append("Your earlier result:\n" + own)
        if source_text and source_text != own:
            parts.append(
                "Source text. Use this text. Do not replace it with a new one:\n" + source_text
            )
        return "\n\n".join(parts)

    def continuation_message(self, agent_id: str, task: str, has_tools: bool, source_text: str) -> str:
        base = self.agent_message(agent_id, task, has_tools, source_text)
        return (
            base
            + "\n\nThese actions already succeeded. Do not repeat them.\n"
            + _file_block(self._files_of(agent_id))
        )

    def orchestrator_messages(self, system: str) -> list[LlmMessage]:
        messages = [LlmMessage(role="system", content=system)]
        for turn in self.turns:
            role = "assistant" if turn.role == "assistant" else "user"
            messages.append(LlmMessage(role=role, content=turn.text))
        if self.records:
            messages.append(LlmMessage(role="user", content="\n".join(self._status(rec) for rec in self.records)))
        results = self._results_block()
        if results:
            messages.append(LlmMessage(role="user", content=results))
        own = self._own_block()
        if own:
            messages.append(LlmMessage(role="user", content="Your tools:\n" + own))
        if self._anomaly:
            messages.append(LlmMessage(role="user", content=self._anomaly))
        return messages

    def set_anomaly(self, record: AgentRecord) -> None:
        lines = [
            f"Anomaly for {record.name} ({record.agent_id}).",
            f"task: {record.task}",
            f"reason: {record.error or 'error'}",
        ]
        block = _file_block(record.files)
        lines.append(block if block else "files: none")
        if _anomaly_needs_text(record):
            lines.append("text:\n" + record.text[:_ANOMALY_TEXT_CAP])
        self._anomaly = "\n".join(lines)

    def clear_anomaly(self) -> None:
        self._anomaly = None

    def note_own_tool(self, event: ToolEvent, fact: FileFact | None) -> None:
        self.own_tools.append(event)
        if fact is not None and len(self.own_files) < _FILES_KEPT:
            self.own_files.append(fact)

    def note_window(self, model: str, *, context_max: int | None, need: int) -> None:
        self.windows.append({"model": model, "contextMax": context_max, "need": need})

    def prompt_text(self, system: str) -> str:
        return "\n".join(message.content or "" for message in self.orchestrator_messages(system))

    def exposes_rejected(self, system: str) -> bool:
        blob = self.prompt_text(system)
        return any(item.body and item.body in blob for item in self.rejected)

    def to_dict(self) -> dict[str, object]:
        return {
            "turns": [{"role": turn.role, "kind": turn.kind, "text": turn.text} for turn in self.turns],
            "calls": [
                {
                    "agentId": rec.agent_id,
                    "name": rec.name,
                    "task": rec.task,
                    "hasTools": rec.has_tools,
                    "text": rec.text,
                    "finished": rec.finished,
                    "error": rec.error,
                    "files": [
                        {
                            "tool": fact.tool,
                            "action": fact.action,
                            "path": fact.path,
                            "ok": fact.ok,
                            "size": fact.size,
                        }
                        for fact in rec.files
                    ],
                    "tools": [
                        {
                            "name": event.name,
                            "arguments": event.arguments,
                            "ok": event.ok,
                            "result": event.result,
                        }
                        for event in rec.tools
                    ],
                }
                for rec in self.records
            ],
            "ownFiles": [
                {
                    "tool": fact.tool,
                    "action": fact.action,
                    "path": fact.path,
                    "ok": fact.ok,
                    "size": fact.size,
                }
                for fact in self.own_files
            ],
            "ownTools": [
                {
                    "name": event.name,
                    "arguments": event.arguments,
                    "ok": event.ok,
                    "result": event.result,
                }
                for event in self.own_tools
            ],
            "rejected": [{"reason": item.reason, "body": item.body} for item in self.rejected],
            "windows": list(self.windows),
            "raised": dict(self.raised),
        }

    def _writers(self) -> list[tuple[str, str, str]]:
        found: dict[str, tuple[str, str, str]] = {}
        for rec in self.records:
            if rec.finished and rec.text:
                found[rec.agent_id] = (rec.agent_id, rec.name, rec.text)
        return list(found.values())

    def _text_of(self, agent_id: str) -> str:
        text = ""
        for rec in self.records:
            if rec.agent_id == agent_id and rec.text:
                text = rec.text
        return text

    def _files_of(self, agent_id: str) -> list[FileFact]:
        files: list[FileFact] = []
        for rec in self.records:
            if rec.agent_id == agent_id:
                files.extend(rec.files)
        return files[-_FILES_KEPT:]

    def _own_block(self) -> str:
        lines = _file_block(self.own_files).splitlines() if self.own_files else []
        for event in self.own_tools:
            if event.name == "file_access":
                continue
            lines.append(f"{event.name} {'ok' if event.ok else 'failed'}")
        return "\n".join(lines[-_FILES_SHOWN:])

    def _last_result(self) -> str:
        return self._results_block()

    def _results_block(self) -> str:
        latest: dict[str, AgentRecord] = {}
        order: list[str] = []
        for rec in self.records:
            if rec.finished and rec.text:
                if rec.agent_id not in latest:
                    order.append(rec.agent_id)
                latest[rec.agent_id] = rec
        parts: list[str] = []
        for agent_id in order:
            rec = latest[agent_id]
            parts.append(f"Result from {rec.name} ({rec.agent_id}):\n{rec.text}")
        return "\n\n".join(parts)

    def _status(self, rec: AgentRecord) -> str:
        state = "finished" if rec.finished and not rec.error else "not finished"
        line = f"Agent {rec.name} ({rec.agent_id}) {state}. characters: {len(rec.text)}."
        block = _file_block(rec.files)
        if block:
            line = f"{line}\n{block}"
        if rec.error:
            line = f"{line}\nreason: {rec.error}"
        return line


def record_tool(record: AgentRecord, event: ToolEvent, fact: FileFact | None) -> None:
    record.tools.append(event)
    if event.ok:
        record.tool_ok = True
    if fact is None:
        return
    if len(record.files) < _FILES_KEPT:
        record.files.append(fact)


def reused_file_result(record: AgentRecord, action: str, path: str) -> dict | None:
    """A continuation does not write a path that already succeeded in this call."""
    for fact in record.files:
        if fact.ok and fact.action == action and fact.path == path and path:
            body: dict[str, object] = {"path": path, "reused": True}
            if fact.size is not None:
                body["bytes"] = fact.size
            return {"ok": True, "result": body}
    return None


_MCP_FILE_ACTIONS = {
    "write_file": "write",
    "edit_file": "write",
    "create_or_update_file": "write",
    "push_files": "write",
    "create_directory": "mkdir",
    "read_file": "read",
    "read_text_file": "read",
    "read_media_file": "read",
    "read_multiple_files": "read",
    "get_file_contents": "read",
    "list_directory": "list",
    "list_directory_with_sizes": "list",
    "directory_tree": "list",
    "search_files": "list",
    "get_file_info": "stat",
    "list_allowed_directories": "list",
}


def _leaf_tool(name: str) -> str:
    raw = name or ""
    if raw.startswith("mcp__") and "__" in raw[5:]:
        return raw.rsplit("__", 1)[-1]
    return raw


def _fact_path(args: dict, result: object) -> str:
    path = str(args.get("path") or args.get("destination") or "")
    if not path:
        paths = args.get("paths")
        if isinstance(paths, list) and paths:
            path = str(paths[0] or "")
    if not path:
        files = args.get("files")
        if isinstance(files, list) and files and isinstance(files[0], dict):
            path = str(files[0].get("path") or "")
    if not path and isinstance(result, dict):
        inner = result.get("result") if isinstance(result.get("result"), dict) else result
        if isinstance(inner, dict) and inner.get("path"):
            path = str(inner.get("path"))
    return path


def _fact_size(result: object) -> int | None:
    if not isinstance(result, dict):
        return None
    inner = result.get("result") if isinstance(result.get("result"), dict) else result
    if not isinstance(inner, dict):
        return None
    raw_size = inner.get("bytes", inner.get("size"))
    return raw_size if isinstance(raw_size, int) else None


def file_fact(name: str, args: dict, result: object, *, ok: bool) -> FileFact | None:
    leaf = _leaf_tool(name)
    if leaf == "file_access":
        action = str(args.get("action") or "").strip().lower()
        path = str(args.get("path") or "")
        size = _fact_size(result)
        if isinstance(result, dict):
            inner = result.get("result") if isinstance(result.get("result"), dict) else result
            if isinstance(inner, dict) and inner.get("path"):
                path = str(inner.get("path"))
        return FileFact(tool=leaf, action=action, path=path, ok=ok, size=size)
    action = _MCP_FILE_ACTIONS.get(leaf)
    if action is None:
        return None
    return FileFact(tool=leaf, action=action, path=_fact_path(args, result), ok=ok, size=_fact_size(result))


def visible_text(raw: str) -> str:
    return strip_think(raw or "").strip()


def _file_block(files: list[FileFact]) -> str:
    lines: list[str] = []
    for fact in files[-_FILES_SHOWN:]:
        flag = "ok" if fact.ok else "failed"
        size = f" {fact.size}" if fact.size is not None else ""
        lines.append(f"{fact.path} {fact.action} {flag}{size}".rstrip())
    return "\n".join(lines)


def _anomaly_needs_text(record: AgentRecord) -> bool:
    if record.error == "no tool used" and record.text:
        return True
    if record.error != "tool failed" or not record.text:
        return False
    failed = [fact for fact in record.files if not fact.ok]
    return bool(failed) and all(not fact.path for fact in failed)
