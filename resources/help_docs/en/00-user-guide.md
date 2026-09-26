# Agentus Network — quick start

Agentus Network is a **local desktop app**. You build networks of agents, language models, and tools on this PC, start **one** run, and watch it live. The UI belongs to the app (its own window), not Chrome and not a `file://` page.

Ollama is a **separate service**. Closing or uninstalling Agentus Network does not stop Ollama and does not delete models. If Ollama is installed on this PC, the address in Settings is local, and the service is down, the app starts it when the window opens.

## Window and navigation

Left (on a phone: burger menu):

- **Dashboard** — home, setup, active network, recent runs
- **Network** — editor (one graph)
- **Library** — all saved networks
- **Monitoring** — live run
- **History** — finished runs and stats

**Settings** live in the header (gear), not in the left nav.

The header also has **Start** / **Stop**, **quick select** for the active network, the bell (notifications), light/dark/system, language (Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية), and window buttons (minimize, maximize, close).

Drag the logo or empty header to move the window. Start, Stop, quick select, and the buttons on the right are not drag areas.

## First hour

1. Ollama must be reachable. The app starts a local service itself when it is installed but down. Setup can install Ollama, start it briefly in the background, and pull the small models `nomic-embed-text` and `llama3.2:1b` — only if Ollama answers. A silent setup without the model switch pulls nothing. A failed download still finishes setup successfully.
2. Under **Settings → Runtime**, ping the connection; the model list should not be empty.
3. Under **Settings → Help chatbot**, set provider and chat model (default: Ollama + `llama3.2:1b`). Embeddings stay a **different** model (`nomic-embed-text`).
4. In the **library** or editor, create a network, save it, and set it **active** in quick select.
5. **Start** in the header. Watch the run under **Monitoring**.

The dashboard shows missing steps as setup cards.

## A minimal network

In the editor (**Network**) you need at least:

1. **Chat** (`chat_input`) — at most one
2. **Agent** — system prompt
3. **LLM** — provider and model
4. **End** (`end`) — at least one

Connections (typed ports, not arbitrary arrows):

- Chat **message** → agent **message**
- LLM **llm** → agent **llm**
- Agent **message** → end

Optional **orchestrator**: chat only to the orchestrator, an LLM to the orchestrator, one **channel** from the orchestrator to each agent’s channel, and **message** from the orchestrator to **end**. It is the only voice in the run chat, asks follow-ups, and calls agents one at a time. Agent text and internal commands do not appear as chat bubbles. Each agent keeps its own text. A tool agent receives the writer's source and the list of files it already wrote. The orchestrator sees only a short overview of that. If an agent has a tool and does not call it, or the call fails, the task stays open. A success message about that work does not appear in the chat. The chat stays open until the orchestrator finishes the run. Without an orchestrator each agent stays its own chain through message and handoff. An agent is either on a channel or on the chain, never both.

Optional: **tool** on the agent **tool** port, **knowledge** on **knowledge**. Save. In the **library**, **Set active** if quick select does not have it yet.

## Start and stop

**Start** runs **one** job of the **active** network (quick select). A second network never runs in parallel. A second Start is rejected until **Stop**.

**Stop** cancels the run (outcome **cancelled**, not **failed**). Ollama stays up.

With no active network, nothing starts. Fix an invalid network (validation errors, missing model) in the editor before starting.

While the active network is running, **that** document is read-only in the editor. You can still view other networks; deleting the running network in the library is blocked.

Closing the window ends the run and the app. Ollama keeps running.

## Help chatbot is not network chat

Bottom right: the bubble is **in-app help** (this guide, graph terms, optional web search). Onboarding explains that the first time you open it.

In **Monitoring**, the **Chat** tab is **run chat** for the graph (Chat node). Without an orchestrator it is the input to the agents. With an orchestrator it is the conversation: it can ask you before it calls agents.

The two share **no** history, tools, or credentials. Help does **not** use MCP servers.

## Ollama and cloud

- **Local:** Ollama, configured as Runtime in Settings. List and ping models there. The app does **not** silently pull models at runtime.
- **Cloud:** credentials under **Settings → Credentials** (xAI, OpenAI, Claude, Gemini, web search, …). On an LLM node you choose Ollama, xAI, OpenAI, Claude, or Gemini. Cloud without a matching credential is invalid. Lists show a **mask** only, never the secret. LLM nodes and help refer to the credential by name, not with the key in the graph.

An OpenAI-compatible base URL is no longer offered under Runtime. Existing credentials of that kind stay visible under Credentials.

## One instance

A second launch brings the existing window to the front. It does not start a second backend or a second run.

## Portable vs installed

The installed app stores data under the local app folder **Agentus-Network**, not next to Program Files. The portable build (`portable.txt` beside the EXE) stores data **next to the EXE**. For portable, you must already have WebView2 and Ollama.
