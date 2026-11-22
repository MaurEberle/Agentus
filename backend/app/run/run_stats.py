"""Tally of one run, built from the log lines it writes (B7: ``run.summary``).

``emit_log`` hands every line to ``RunStats.observe``. The summary therefore counts
exactly what the log shows: agent calls from ``run.agent.done``, model calls from
``run.llm.done``, tool calls from ``run.tool.call``, limits from their warning keys.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

# Warnings and errors that mean a limit or guard stopped something.
LIMIT_KEYS = frozenset(
    {
        "run.agent.emptyStops",
        "run.agent.outputLimit",
        "run.agent.thinkLimit",
        "run.agent.thinkLoop",
        "run.agent.toolCap",
        "run.agent.toolFailures",
        "run.agent.window",
        "run.llm.contextCut",
        "run.llmBudget",
        "run.orchestrator.orientationCap",
        "run.orchestrator.stepClose",
        "run.orchestrator.stuckClose",
        "run.orchestrator.stuck",
        "run.orchestrator.thinkLimit",
        "run.orchestrator.thinkLoop",
        "run.orchestrator.toolCap",
        "run.orchestrator.toolFailures",
        "run.orchestrator.toolWithdrawn",
        "run.orchestrator.window",
        "run.stepLimit",
        "run.tool.disabled",
        "run.tool.limitReached",
        "runtime.generationLimit",
    }
)
MAX_SUMMARY_FILES = 50


@dataclass
class _AgentTally:
    name: str
    calls: int = 0
    failed: int = 0
    duration_ms: int = 0
    tools: int = 0
    # Highest share of the context window one call of this agent used, in percent.
    context_share: float = 0.0


@dataclass
class RunStats:
    started: float = field(default_factory=time.monotonic)
    agents: dict[str, _AgentTally] = field(default_factory=dict)
    llm_calls: int = 0
    llm_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tool_ok: int = 0
    tool_failed: int = 0
    tools: dict[str, int] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    limits: dict[str, int] = field(default_factory=dict)
    warnings: int = 0
    errors: int = 0

    def observe(self, level: str, message: str, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        if level == "warn":
            self.warnings += 1
        elif level == "error":
            self.errors += 1
        if message in LIMIT_KEYS:
            self.limits[message] = self.limits.get(message, 0) + 1
        if message == "run.tool.call":
            self._tool(data)
        elif message == "run.llm.done":
            self.llm_calls += 1
            self.llm_ms += _int(data.get("durationMs"))
            self.tokens_in += _int(data.get("tokensIn"))
            self.tokens_out += _int(data.get("tokensOut"))
        elif message == "run.agent.done":
            self._agent(data)

    def _tool(self, data: dict) -> None:
        if data.get("ok") is False:
            self.tool_failed += 1
        else:
            self.tool_ok += 1
        name = str(data.get("name") or "")
        if name:
            self.tools[name] = self.tools.get(name, 0) + 1
        changed = data.get("changed")
        if isinstance(changed, str) and changed and changed not in self.files:
            self.files.append(changed)

    def _agent(self, data: dict) -> None:
        key = str(data.get("agentId") or data.get("agentName") or "")
        if not key:
            return
        tally = self.agents.get(key)
        if tally is None:
            tally = _AgentTally(name=str(data.get("agentName") or key))
            self.agents[key] = tally
        tally.calls += 1
        if data.get("outcome") in {"anomaly", "stopped"}:
            tally.failed += 1
        tally.duration_ms += _int(data.get("durationMs"))
        tally.tools += _int(data.get("tools"))
        share = data.get("contextShare")
        if isinstance(share, (int, float)) and not isinstance(share, bool):
            tally.context_share = max(tally.context_share, float(share))

    def summary(self, outcome: str, error: str | None = None) -> dict:
        body: dict = {
            "outcome": outcome,
            "durationMs": int((time.monotonic() - self.started) * 1000),
            "agentCalls": sum(item.calls for item in self.agents.values()),
            "agents": [
                {
                    "id": key,
                    "name": item.name,
                    "calls": item.calls,
                    "failed": item.failed,
                    "durationMs": item.duration_ms,
                    "tools": item.tools,
                    **({"contextShare": item.context_share} if item.context_share else {}),
                }
                for key, item in self.agents.items()
            ],
            "llmCalls": self.llm_calls,
            "llmMs": self.llm_ms,
            "tokensIn": self.tokens_in,
            "tokensOut": self.tokens_out,
            "toolCalls": self.tool_ok + self.tool_failed,
            "toolsOk": self.tool_ok,
            "toolsFailed": self.tool_failed,
            "tools": dict(sorted(self.tools.items(), key=lambda item: -item[1])),
            "files": self.files[:MAX_SUMMARY_FILES],
            "filesCount": len(self.files),
            "limits": dict(self.limits),
            "warnings": self.warnings,
            "errors": self.errors,
        }
        if error:
            body["error"] = error[:300]
        return body


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0
