# Terms

Short glossary for help chat and the editor.

## Graph / network

A saved document of nodes and edges. You edit it in the editor and manage copies in the library. The **active** network is the one in quick select — **Start** runs only that.

## Run

One execution of the active graph. At most **one** at a time. Start and Stop in the header. Outcomes: running, succeeded, failed, cancelled, timeout.

## Nodes and edges

Building blocks (chat, orchestrator, agent, LLM, tool, knowledge, router, end) and typed connections. Arbitrary box-to-box arrows are invalid.

## Agent

Node with a system prompt. Model, message, tools, and knowledge arrive through ports. Without an orchestrator the message starts it, and message or handoff passes the answer on. With an orchestrator it hangs on its own channel: one task in, one result back.

## LLM node

Chooses provider and model. Local via Ollama, otherwise cloud plus a credential.

## Chat

The only entry for user text in a run. At most one per network. Monitoring chat writes here. With an orchestrator the conversation stays open across several messages.

## Orchestrator

A node with its own LLM. It is the only voice in the run chat, asks follow-ups, and calls connected agents one at a time through a channel each. At most one. Chat connects only to it. Its message output goes to end or a router. You do not see agent text or internal commands as chat bubbles. The app attaches the latest result to the next task. An agent is either on the channel or on the message chain. Tools may connect to its tool port. It calls them itself.

## Tool

First-party (HTTP, web search, date/time, calculator, file access) or MCP. File access stays inside a root folder, not a drive root. Configured in the inspector, executed only during a run.

## Knowledge (network)

Knowledge node: a folder of text for the network. It may sit anywhere except a drive or system root and the help corpus. Its own embedding model, index, topK, and score. **Not** the help corpus. At start you see the indexing; an index that is already current is skipped.

## Help RAG

Documents in the help folder inside the data directory (default guides plus your markdown). Help chatbot only. After changes, rebuild the index under Settings → Help chatbot.

## Credential

A stored secret in the Windows vault. Lists show a mask. The graph stores only the id/choice, never the secret. Export contains no passwords.

## MCP

Model Context Protocol: external tool servers. Create and enable them in Settings, connect them in the graph as a tool node of kind MCP. Help does not use MCP.

## Provider

In the picker: `ollama` (local), `xai`, `openai`, `anthropic` (Claude), `gemini` (cloud: credential first, then the model list). Embeddings: Ollama, OpenAI, Gemini. `openai_compat` stays valid for older graphs and credentials, but it is no longer in the model picker.

## Ollama

A separate service for local models. The app is the client. If it is installed, the address is local, and the port is down, the app starts it and does not stop it. Setup can install Ollama, wait briefly, and pull two small default models when it answers.

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
