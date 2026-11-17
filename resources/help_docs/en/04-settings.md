# Settings

Gear in the header. Sections: Appearance, Credentials, Runtime, Help chatbot, MCP servers, Data, About. Unsaved fields when leaving a section: Stay / Discard. Saving settings does not create a notification; a save error does.

## Appearance

Light, dark, or system — applies everywhere, including the header. **Language** is a dropdown with a flag: Deutsch, English, Español. The name in parentheses is the translation in the current UI language.

**Help button** shows or hides the bubble at the bottom right. **Configuration** of the chatbot stays under **Help chatbot**, even if the bubble is hidden.

## Credentials

Named secrets for cloud models, web search, and some MCP recipes. Create: name, kind, secret **once**. After that, only the **mask**. Edit can replace the secret (empty = unchanged).

Kinds include: xAI, OpenAI, Claude, Gemini, OpenAI-compatible, web search, GitHub, Azure, GitLab, Slack, Notion, Atlassian, Linear, Postgres, token.

**Delete** is blocked while the help profile, a network (LLM/tool), or an MCP server still uses the credential. Remove the link first.

## Runtime

**Ollama runtime:** In the **Own runtime** mode (default) the app copies the installed Ollama into its folder and starts the copy on its own port (usually 11435) with the same model folder. The card shows state, version, port and the version of the installed Ollama. The Ollama app downloads updates as usual. When the installed version is newer, Agentus says so in a notification and in the card. **Switch and restart** copies the new version, starts it once as a test, closes Agentus and opens it again. If the new version does not start afterwards, the app goes back to the old one. This is not possible while a run or a model download is active. If the app finds no installed Ollama or the copy does not start, it uses the address below. In the **External Ollama** mode the app only uses the address. A mode change applies after a restart.

**Ollama base URL** (the address of an external Ollama, otherwise the fallback). **Ping** and the **model list** go through the app. The list splits into **Normal models** and **Embedding models**. A model counts as an embedding when its name contains `embed`. An empty group shows **None**.

Without reachable Ollama, local LLM nodes and default help stall. You install models with Ollama itself or during setup; the app does **not** silently pull at runtime. An OpenAI-compatible base URL is no longer offered here.

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

**Change folder** only when no network is starting, running, or stopping. Drive or system roots are invalid. Optionally copy contents into the new folder; the old folder stays. If the target already holds data, the app does not copy over it and says so. If the switch fails, the previous folder stays active.

**Portable** or an externally fixed folder: path is **read-only**.

**History retention:** 30 / 90 / 365 days or unlimited (default 90). The History page can purge older rows to match.

## About

UI and API version, coarse Ollama status, whether stores are reachable. No secrets, no internal file paths with a username that you would share.
