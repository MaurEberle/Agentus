# Agentus Network — quick start

Agentus Network is a **local** desktop app: agent networks run on this PC. The UI is served by the same process over loopback, not Chrome and not `file://`.

## Create a network

1. Open **Networks** or **New** in the editor.
2. Connect at least `chat_input` → `agent` ← `llm` → `end`.
3. Save. The active network is the session network (header / dashboard).

## Start and stop

**Start** in the header runs **one** job of the **active** network. A second start is blocked until stop. Stop cancels the run; **Ollama stays** a separate daemon and is not killed.

## Help FAB is not network chat

The bubble at the bottom-right is the **help chatbot** (docs + optional web search). Monitoring chat is the **run chat** (`chat_input`). They do not share history or tools.

## Ollama and cloud

Local: Ollama at `http://127.0.0.1:11434`. Cloud: credentials under **Settings → Credentials**. Secrets live in the OS vault; lists show a mask only.
