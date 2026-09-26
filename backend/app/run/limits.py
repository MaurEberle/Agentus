MAX_AGENT_INVOCATIONS = 32
MAX_ORCHESTRATOR_STEPS = 24
MAX_TOOL_ROUNDS = 8
# Estimated prompt size at which a tool-using agent stops and returns its file list.
# The next call starts clean instead of rereading the previous tool arguments.
AGENT_TURN_TOKEN_BUDGET = 6000
# Idle gap between stream chunks (or first byte). Not a total run duration.
STREAM_IDLE_TIMEOUT_SEC = 180.0
RESOURCES_INTERVAL_SEC = 1.5
SSE_QUEUE_MAX = 1000
LOG_PAYLOAD_MAX = 8000
KNOWLEDGE_CHUNK_CHARS = 800
DEFAULT_TOP_K = 4
DEFAULT_SCORE_MIN = 0.0
DEFAULT_EMBED_MODEL = "nomic-embed-text"
