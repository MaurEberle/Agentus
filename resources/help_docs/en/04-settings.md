# Settings

Gear in the header. Sections: Appearance, Credentials, Runtime, Help chatbot, MCP servers, Data, About. Unsaved fields when leaving a section: Stay / Discard. Saving settings does not create a notification; a save error does.

## Appearance

Light, dark, or system — applies everywhere, including the header. **Language** is a dropdown with a flag: Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية. The name in parentheses is the translation in the current UI language.

**Help button** shows or hides the bubble at the bottom right. **Configuration** of the chatbot stays under **Help chatbot**, even if the bubble is hidden.

## Credentials

Named secrets for cloud models, web search, and some MCP recipes. Create: name, kind, secret **once**. After that, only the **mask**. Edit can replace the secret (empty = unchanged).

Kinds include: xAI, OpenAI, Claude, Gemini, OpenAI-compatible, web search, GitHub, Azure, GitLab, Slack, Notion, Atlassian, Linear, Postgres, token.

**Delete** is blocked while the help profile, a network (LLM/tool), or an MCP server still uses the credential. Remove the link first.

## Runtime

**Ollama base URL** (usually Ollama’s local address). **Ping** and the **model list** go through the app. The list splits into **Normal models** and **Embedding models**. A model counts as an embedding when its name contains `embed`. An empty group shows **None**.

If the address is local and Ollama is installed but down, the app starts the service when the window opens and does not stop it. Without reachable Ollama, local LLM nodes and default help stall. You install models with Ollama itself or during setup; the app does **not** silently pull at runtime. An OpenAI-compatible base URL is no longer offered here.

## Help chatbot

The only place that configures the help widget. Incomplete without chat provider and chat model.

- chat provider and chat model (default Ollama / `llama3.2:1b`)
- optional cloud credential
- **embedding provider and model** (default Ollama / `nomic-embed-text`) — **not** the chat model
- optional fallback model (default the same small chat model)
- web search on/off plus a search credential; without a credential the chat stays configured and search stays off
- ping, clear history, **rebuild index**, show onboarding again

After changing the embedding model or adding files to the help corpus: **rebuild index**. The job keeps running if you leave Settings. A second click does not start a second index. The corpus is the help-documents folder in the data directory, not network knowledge. The same file types as the knowledge node apply. New bundled guides do not overwrite files that are already there.

Help answers in the UI language. If the model cannot use that language, it answers in English. It does not name document titles from the guides. Only a web search shows sources, as title and address. Internal thinking blocks from the model are hidden. Help uses **no** MCP servers and **no** graph knowledge nodes.

## MCP servers

**Recipes** for external tools. Recipes are not bundled binaries. Many need Node/`npx`, Docker, or `uvx` on the PC plus a **credential**.

Default: servers **off**. The app does not start MCP processes when you open Settings — only when a run needs a connected **MCP node**.

**Set up:** pick a recipe and assign credentials of the matching kind. Filesystem and Excel enable without a folder; you set the folder on the MCP node in the editor. Git still needs the root folder here. Saving creates and enables the server. **Probe** calls `tools/list`. “Runtime missing” if Node/Docker/`uvx` is absent.

What each recipe needs:

| Recipe | Credential | Other |
|--------|------------|--------|
| GitHub | PAT, kind **GitHub** | official server, downloaded on first use |
| GitLab | PAT, kind **GitLab** | local `npx` |
| Azure | token/PAT, kind **Azure** | local `npx` |
| Slack | bot token, kind **Slack** | local `npx` |
| Notion | integration token, kind **Notion** | local `npx` |
| Atlassian | Cloud token, kind **Atlassian** | remote |
| Linear | API key, kind **Linear** | remote HTTP |
| Context7 | API key, kind **Token** | remote HTTP |
| Sentry | auth token, kind **Token** | local `npx` |
| Postgres | connection string, kind **Postgres** (not the app SQLite) | local `npx` |
| Filesystem, Excel | none | root folder **on the MCP node** in the editor; local `npx` |
| Git | none | **root folder** in Settings; local `uvx` |
| Fetch | none | local `uvx` |
| Playwright | none | local `npx`; Playwright also needs a browser |

Create credentials under **Credentials**, not in the recipe dialog. Without a matching credential the server stays invalid.

Or a **custom server** (command, args, or URL). Use unknown commands only if you trust them.

Delete removes the server config, not Ollama and not credentials. In the network you attach the server with the palette node **MCP**, not a tool kind.

## Data

Shows the **data folder** and store health: settings, help, workspace, history — no SQL browser, no secrets.

**Change folder** only when no network is starting, running, or stopping. Drive or system roots are invalid. Optionally copy contents into the new folder; the old folder stays.

**Portable** or an externally fixed folder: path is **read-only**.

**History retention:** 30 / 90 / 365 days or unlimited (default 90). The History page can purge older rows to match.

## About

UI and API version, coarse Ollama status, whether stores are reachable. No secrets, no internal file paths with a username that you would share.
