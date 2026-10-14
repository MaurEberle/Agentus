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
# Failed tool calls in one agent invocation. Successful calls are unbounded.
MAX_FAILED_TOOL_CALLS = 10
# Same truncated tool-call JSON from llama-server. Then it counts as one failed tool.
MAX_TOOL_JSON_ATTEMPTS = 3
# Orchestrator checks files; it does not spend the run on tools instead of agents.
MAX_ORCHESTRATOR_TOOL_ROUNDS = 2
# Extra attempts after an unreadable orchestrator decision. Not part of the step cap.
MAX_CONTROL_REPAIRS = 2
# One same-prompt retry when the model died before any tool succeeded.
MAX_SAME_RETRIES = 1
# Idle gap between stream chunks (or first byte). Not a total run duration.
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
