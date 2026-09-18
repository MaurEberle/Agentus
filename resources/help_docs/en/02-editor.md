# Editor

The editor edits **one** graph document. Save writes to the library.

## Node types (short)

| Type | Role |
|------|------|
| `chat_input` | User input (at most one) |
| `llm` | Model (Ollama or cloud) |
| `agent` | Prompt; takes message/LLM/tool/knowledge |
| `tool` | First-party or MCP |
| `knowledge` | Folder under the data directory |
| `router` | Branch on the first line |
| `end` | Run end (at least one) |

## Validation

The graph must be a DAG. Each agent needs exactly one LLM edge. Knowledge paths must not be a drive root or the help corpus. MCP nodes need an **enabled** server.
