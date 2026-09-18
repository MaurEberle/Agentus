# Settings

Gear in the header. Sections: Appearance, Credentials, Runtime, Help chatbot, MCP servers, Data, About. Unsaved fields when leaving a section: Stay / Discard.

## Appearance

Light, dark, or system — applies everywhere, including the header. Language: German or English.

**Help button** shows or hides the bubble at the bottom right. **Configuration** of the chatbot stays under **Help chatbot**, even if the bubble is hidden.

## Credentials

Named secrets for cloud models, web search, and some MCP recipes. Create: name, kind, secret **once**. After that, only the **mask**. Edit can replace the secret (empty = unchanged).

Kinds include: xAI, OpenAI-compatible, web search, GitHub, Azure, GitLab, Slack, Notion, Atlassian, Linear, Postgres, token.

**Delete** is blocked while the help profile, a network (LLM/tool), or an MCP server still uses the credential. Remove the link first.

## Runtime

**Ollama base URL** (usually Ollama’s local address) and optional **OpenAI-compatible base URL**. **Ping** and the **model list** go through the app, not around the browser.

Without reachable Ollama, local LLM nodes and default help stall. You install models with Ollama itself or during setup; the app does **not** silently pull at runtime.

## Help chatbot

The only place that configures the help widget. Incomplete without chat provider and chat model.

- chat provider and chat model (default Ollama / `llama3.2:1b`)
- optional cloud credential
- **embedding provider and model** (default Ollama / `nomic-embed-text`) — **not** the chat model
- optional fallback model (default the same small chat model)
- web search on/off plus a search credential; without a credential the chat stays configured and search stays off
- ping, clear history, **rebuild index**, show onboarding again

After changing the embedding model or adding files to the help corpus: **rebuild index**. The corpus is the help-documents folder in the data directory, not network knowledge.

Help uses **no** MCP servers and **no** graph knowledge nodes.

## MCP servers

**Recipes** for external tools: GitHub, filesystem, Git, Playwright, Postgres, Slack, Notion, Office formats, and others. Recipes are not bundled binaries. Many need Node/`npx`, Docker, or `uvx` on the PC plus a credential.

Default: servers **off**. The app does not start MCP processes when you open Settings — only when a run needs a connected MCP tool node.

Create from a recipe (credential, optional root path) or as a **custom server** (command, args, or URL). Use unknown commands only if you trust them. Probe checks reachability; “runtime missing” if Node/Docker/`uvx` is absent.

Office bundles PDF and Office formats; enable single presets only if you really need them.

Delete removes the server config, not Ollama and not credentials.

## Data

Shows the **data folder** and store health: settings, help, workspace, history — no SQL browser, no secrets.

**Change folder** only when no network is starting, running, or stopping. Drive or system roots are invalid. Optionally copy contents into the new folder; the old folder stays.

**Portable** or an externally fixed folder: path is **read-only**.

**History retention:** 30 / 90 / 365 days or unlimited (default 90). The History page can purge older rows to match.

## About

UI and API version, coarse Ollama status, whether stores are reachable. No secrets, no internal file paths with a username that you would share.
