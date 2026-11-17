MAX_AGENT_INVOCATIONS = 32
# Agent dispatches (call). think / reply / ask / repair do not count.
MAX_ORCHESTRATOR_STEPS = 24
# Consecutive think turns without call/ask/finish. Runaway guard, not a work budget.
MAX_ORCHESTRATOR_THINKS = 64
# Consecutive think turns in one agent invocation without a tool call or result.
MAX_AGENT_THINKS = 128
# Consecutive 0- or 1-token think turns on agent or orchestrator.
MAX_SHORT_THINKS = 5
# After a successful write/delete, a think this small is the result, not another round.
MAX_CLOSING_THINK_TOKENS = 16
# Consecutive empty replies after a successful write or delete.
# Each one asks the model to continue. The last one ends the run as incomplete.
MAX_EMPTY_STOPS = 5
# Consecutive failed tool calls in one agent invocation. A success resets the count.
MAX_FAILED_TOOL_CALLS = 10
# Same truncated tool-call JSON from llama-server. Then it counts as one failed tool.
MAX_TOOL_JSON_ATTEMPTS = 3
# R1: output per model call when the LLM node has no maxTokens (Ollama only).
# Context / 4, at least 4096, at most 16384, and never more than the room the prompt leaves.
AUTO_OUTPUT_MIN = 4096
AUTO_OUTPUT_MAX = 16384
AUTO_OUTPUT_ROOM_MIN = 1024
# R1: wall-clock limit for one model call, on top of the idle watchdog.
MAX_CALL_SECONDS = 1200.0
# Text-only review: retries of an agent with tools that again answer with text only.
# Then the orchestrator takes the step over.
MAX_TEXT_RETRIES = 2
# Takeovers that cannot happen (orchestrator lacks the tools) before the run fails.
MAX_TAKEOVER_UNAVAILABLE = 3
# O12: model calls per run (orchestrator and agents together). Then the run fails as run.llmBudget.
# The orchestrator node can set its own value (maxLlmCalls).
MAX_RUN_LLM_CALLS = 1000
# O14: times one run may pause for an unreachable orchestrator model before it fails.
MAX_LLM_PAUSES = 3
# O13: calls to the closed takeover agent before the run fails.
MAX_TAKEOVER_REJECTS = 3
# Tool calls the orchestrator may make in one decision. Then tools are withheld and it must decide.
# Node setting maxToolCalls on the orchestrator overrides it.
MAX_ORCHESTRATOR_TOOL_CALLS = 50
# Tool calls one agent may make for one task. Then it must answer with what it has.
# Node setting maxToolCalls on the agent overrides it.
MAX_AGENT_TOOL_CALLS = 100
# Bounds for the node settings above.
NODE_TOOL_CALLS_MIN = 1
NODE_TOOL_CALLS_MAX = 1000
NODE_LLM_CALLS_MIN = 10
NODE_LLM_CALLS_MAX = 10000
# Consecutive failed orchestrator tool calls. A success resets the count.
MAX_ORCHESTRATOR_FAILED_TOOLS = 5
# Failed think rounds after a five-fail streak. Two in a row stop the run.
MAX_ORCHESTRATOR_FAILED_THINKS = 2
# Failed calls in a row, or file attempts without a write, edit, or delete, before the
# orchestrator takes the task over. Orchestrator node setting agentMissLimit.
DEFAULT_AGENT_MISS_LIMIT = 2
MAX_AGENT_MISS_LIMIT = 8
# Consecutive think turns during takeover. The next one ends the run.
MAX_TAKEOVER_THINKS = 2
# Orchestrator decisions without progress (think, reply, refused or unreadable output).
# Progress is an agent call, an answered question, an own tool call or a new user message.
# At the first value the orchestrator is told to act; at the second the run fails as stuck.
IDLE_NUDGE_DECISIONS = 4
MAX_IDLE_DECISIONS = 8
# Unreadable decisions in a row that the runtime turned into a think after a reply.
MAX_UNREADABLE_STREAK = 2
# Own tool calls of the orchestrator before its first agent call (looking around).
# Then its tools are withheld until it has called an agent.
MAX_ORIENTATION_CALLS = 10
# The same error from the same tool in a row withdraws that tool for the rest of the decision.
MAX_SAME_TOOL_ERRORS = 3
# Repeats of an own tool call with the same arguments in one decision. They do not run;
# the second repeat withdraws the tool for the rest of the decision.
MAX_REPEATED_CALLS = 2
# Own tool calls per decision while the orchestrator may only read (no failure yet).
# MAX_ORCHESTRATOR_TOOL_CALLS applies after a failure or in a takeover. Raise when runs are steadier.
MAX_READ_DECISION_CALLS = 10
# Extra attempts after an unreadable orchestrator decision. Not part of the step cap.
MAX_CONTROL_REPAIRS = 2
# One same-prompt retry when the model died before any tool succeeded.
MAX_SAME_RETRIES = 1
# Silence with neither a stream chunk nor runner token progress.
# A live generation keeps the request open. Not a cap on the answer length.
STREAM_IDLE_TIMEOUT_SEC = 180.0
RESOURCES_INTERVAL_SEC = 1.5
SSE_QUEUE_MAX = 1000
# Visible agent text after list/read/stat/mkdir is the result at this length.
SUBSTANTIAL_RESULT_CHARS = 400
# Per-string cap for run log payloads. Payloads stay valid JSON; the UI clips previews.
LOG_PAYLOAD_MAX = 1_000_000
# Snapshot lastMessage cap. Activity/log lists clip further in the UI.
LAST_MESSAGE_MAX = 8000
KNOWLEDGE_CHUNK_CHARS = 800
DEFAULT_TOP_K = 4
DEFAULT_SCORE_MIN = 0.0
DEFAULT_EMBED_MODEL = "nomic-embed-text"
