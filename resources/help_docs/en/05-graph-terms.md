# Terms

Short glossary for help chat and the editor.

## Graph / network

A saved document of nodes and edges. You edit it in the editor and manage copies in the library. The **active** network is the one in quick select — **Start** runs only that.

## Run

One execution of the active graph. At most **one** at a time. Start and Stop in the header. Outcomes: running, succeeded, failed, cancelled, timeout.

## Nodes and edges

Building blocks (chat input, agent, LLM, tool, knowledge, router, end) and typed connections. Arbitrary box-to-box arrows are invalid.

## Agent

Node with a system prompt. Model, message, tools, and knowledge arrive through ports, not as embedded keys.

## LLM node

Chooses provider and model. Local via Ollama, otherwise cloud or an OpenAI-compatible URL plus a credential.

## Chat input

The only entry for user text in a run. At most one per network. Monitoring chat writes here.

## Tool

First-party (HTTP, web search, date/time, calculator) or MCP. Configured in the inspector, executed only during a run.

## Knowledge (network)

Knowledge node: a folder **under** the app data directory. Its own index, topK, and score. **Not** the help corpus. Not a drive root.

## Help RAG

Documents in the help folder inside the data directory (default guides plus your markdown). Help chatbot only. After changes, rebuild the index under Settings → Help chatbot.

## Credential

A stored secret in the Windows vault. Lists show a mask. The graph stores only the id/choice, never the secret. Export contains no passwords.

## MCP

Model Context Protocol: external tool servers. Create and enable them in Settings, connect them in the graph as a tool node of kind MCP. Help does not use MCP.

## Provider

`ollama` (local), `xai` (cloud), `openai_compat` (compatible HTTP API). No separate “LM Studio” switch — you can register LM Studio as OpenAI-compatible.

## Ollama

A separate service for local models. The app is the client. Setup can install Ollama and two small default models. Closing the app leaves Ollama running.

## Dashboard, monitoring, history

Dashboard = overview and setup. Monitoring = live. History = archive. Not the same page three times.

## Valid / invalid

Graph validation. Invalid networks can be saved but should not be started. Only a valid network can be set active.

## Quick select

Header control for the active network. Same as “Set active” in the library.

## Degraded mode

Help falls back to the spare model when the main model does not work. The dashboard can show this under Environment.

## Portable

`portable.txt` beside the EXE: data next to the app. Installed copy: data in the app data folder, programs elsewhere.
