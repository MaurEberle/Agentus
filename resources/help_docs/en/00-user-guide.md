# Agentus Network — quick start

Agentus Network is a **local desktop app**. You build networks of agents, language models, and tools on this PC, start **one** run, and watch it live. The UI belongs to the app (its own window), not Chrome and not a `file://` page.

Ollama is a **separate service**. Closing or uninstalling Agentus Network does not stop Ollama and does not delete models.

## Window and navigation

Left (on a phone: burger menu):

- **Dashboard** — home, setup, active network, recent runs
- **Network** — editor (one graph)
- **Library** — all saved networks
- **Monitoring** — live run
- **History** — finished runs and stats

**Settings** live in the header (gear), not in the left nav.

The header also has **Start** / **Stop**, **quick select** for the active network, the bell (notifications), light/dark/system, language (German/English), and window buttons (minimize, maximize, close).

Drag the logo or empty header to move the window. Start, Stop, quick select, and the buttons on the right are not drag areas.

## First hour

1. Ollama must be running (the installer can set it up and pull the small models `nomic-embed-text` and `llama3.2:1b`).
2. Under **Settings → Runtime**, ping the connection; the model list should not be empty.
3. Under **Settings → Help chatbot**, set provider and chat model (default: Ollama + `llama3.2:1b`). Embeddings stay a **different** model (`nomic-embed-text`).
4. In the **library** or editor, create a network, save it, and set it **active** in quick select.
5. **Start** in the header. Watch the run under **Monitoring**.

The dashboard shows missing steps as setup cards.

## A minimal network

In the editor (**Network**) you need at least:

1. **Chat input** (`chat_input`) — at most one
2. **Agent** — system prompt
3. **LLM** — provider and model
4. **End** (`end`) — at least one

Connections (typed ports, not arbitrary arrows):

- Chat input **message** → agent **message**
- LLM **llm** → agent **llm**
- Agent **message** → end

Optional: **tool** to the agent **tool** port, **knowledge** to **knowledge**. Save. In the **library**, **Set active** if quick select does not have it yet.

## Start and stop

**Start** runs **one** job of the **active** network (quick select). A second network never runs in parallel. A second Start is rejected until **Stop**.

**Stop** cancels the run (outcome **cancelled**, not **failed**). Ollama stays up.

With no active network, nothing starts. Fix an invalid network (validation errors, missing model) in the editor before starting.

While the active network is running, **that** document is read-only in the editor. You can still view other networks; deleting the running network in the library is blocked.

Closing the window ends the run and the app. Ollama keeps running.

## Help chatbot is not network chat

Bottom right: the bubble is **in-app help** (this guide, graph terms, optional web search). Onboarding explains that the first time you open it.

In **Monitoring**, the **Chat** tab is **run chat** for the graph (chat-input node). It talks to the agent network.

The two share **no** history, tools, or credentials. Help does **not** use MCP servers.

## Ollama and cloud

- **Local:** Ollama, configured as Runtime in Settings. List and ping models there. The app does **not** silently pull models at runtime.
- **Cloud:** credentials under **Settings → Credentials** (xAI, OpenAI-compatible, web search, …). Lists show a **mask** only, never the secret. LLM nodes and help refer to the credential by name, not with the key in the graph.

OpenAI-compatible (for example a local server) needs the base URL under **Runtime** and often a credential.

## One instance

A second launch brings the existing window to the front. It does not start a second backend or a second run.

## Portable vs installed

The installed app stores data under the local app folder **Agentus-Network**, not next to Program Files. The portable build (`portable.txt` beside the EXE) stores data **next to the EXE**. For portable, you must already have WebView2 and Ollama.
