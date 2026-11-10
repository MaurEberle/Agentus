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
# O12: model calls per run (orchestrator and agents together). Then the run fails as run.llmBudget.
MAX_RUN_LLM_CALLS = 400
# O14: times one run may pause for an unreachable orchestrator model before it fails.
MAX_LLM_PAUSES = 3
# O13: calls to the closed takeover agent before the run fails.
MAX_TAKEOVER_REJECTS = 3
# Tool calls the orchestrator may make in one decision. Then tools are withheld and it must decide.
MAX_ORCHESTRATOR_TOOL_CALLS = 10
# Tool calls one agent may make for one task. Then it must answer with what it has.
MAX_AGENT_TOOL_CALLS = 50
# Consecutive failed orchestrator tool calls. A success resets the count.
MAX_ORCHESTRATOR_FAILED_TOOLS = 5
# Failed think rounds after a five-fail streak. Two in a row stop the run.
MAX_ORCHESTRATOR_FAILED_THINKS = 2
# File attempts without a write, edit, or delete before the orchestrator takes the task.
DEFAULT_AGENT_MISS_LIMIT = 3
MAX_AGENT_MISS_LIMIT = 8
# Consecutive think turns during takeover. The next one ends the run.
MAX_TAKEOVER_THINKS = 2
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
