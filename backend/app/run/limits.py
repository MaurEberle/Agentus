MAX_AGENT_INVOCATIONS = 32
MAX_ORCHESTRATOR_STEPS = 24
MAX_TOOL_ROUNDS = 8
# Extra attempts after an unreadable orchestrator decision. Not part of the step cap.
MAX_CONTROL_REPAIRS = 2
# One same-prompt retry when the model died before any tool succeeded.
MAX_SAME_RETRIES = 1
# Idle gap between stream chunks (or first byte). Not a total run duration.
STREAM_IDLE_TIMEOUT_SEC = 180.0
RESOURCES_INTERVAL_SEC = 1.5
SSE_QUEUE_MAX = 1000
LOG_PAYLOAD_MAX = 8000
KNOWLEDGE_CHUNK_CHARS = 800
DEFAULT_TOP_K = 4
DEFAULT_SCORE_MIN = 0.0
DEFAULT_EMBED_MODEL = "nomic-embed-text"
