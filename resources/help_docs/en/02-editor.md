# Editor and library

The editor under **Network** edits **one** graph document. The **library** is the catalogue: list, import, delete, set active. The canvas exists only in the editor, not in the library, monitoring, or history.

## Two places

| Place | Role | Typical actions |
|-------|------|-----------------|
| Editor | New or one loaded network | Draw, inspector, save, load dialog, duplicate, export the open graph |
| Library | all networks | Search, tags, set active, import/export several files, delete |

**Set active** and **Delete** belong in the library (or quick select for active). The editor load dialog opens **one** network and never deletes.

## Editor chrome

Top **ribbon**: New, Save, Save as, Load, Duplicate, Export, Validate, Undo/Redo, View (fit, grid, snap, minimap), To library.

Middle: **palette** (left), **canvas**, **inspector** (right). On narrow screens, palette and inspector are sheets.

Drag nodes from the palette. Cards stay compact; forms live in the inspector. Multi-select with Shift or marquee. Delete removes the selection. Undo: Ctrl+Z.

While **this** network is running: **read-only** banner — stop it in the header first.

## Node types

| Label | Type | Job |
|-------|------|-----|
| Chat | `chat_input` | Run conversation. **At most one.** Output **message**. With an orchestrator it stays open for follow-ups. |
| Orchestrator | `orchestrator` | Voice of the run chat. Inputs **message** and **LLM**. One **channel** output per agent. **Message** only to **end** (or a router). **At most one.** |
| LLM | `llm` | Provider (Ollama, xAI, OpenAI, Claude, Gemini, OpenAI-compatible), model, credential for cloud, temperature, token limit. Output **llm**. |
| Agent | `agent` | System prompt. Inputs message, llm, tool, knowledge, optional **channel**. Outputs message and handoff. The channel comes only from the orchestrator. Without it the agent runs once along the message. |
| Tool | `tool` | First-party: HTTP, web search, date/time, calculator — or **MCP**. Output **tool**. |
| Knowledge | `knowledge` | Folder of files for the network. Output **knowledge**, only to the agent knowledge port. |
| Router | `router` | Branches the message by conditions (first line / named branches) plus a default output. |
| End | `end` | Finish. **At least one.** |

## Connections

Only matching ports:

- Message to message (chat → agent, agent → end, agent → router, router branches → …)
- LLM output only to agent **llm** — each agent needs **exactly one** such edge
- Tool output to agent **tool** (several allowed)
- Knowledge output only to agent **knowledge**
- Cycles are forbidden (DAG)

Invalid drags are rejected.

## Inspector

No node selected: name, description, tags, stats, validation list of the **open** network.

Node selected:

- **LLM:** provider, model (list from runtime), credential for cloud, ping, advanced temperature / max tokens. Cloud without a credential is invalid.
- **Agent:** system prompt and display name only.
- **Tool:** kind. HTTP: method and URL, optional credential. Web search: a web-search credential. MCP: an enabled server from Settings; default is all tools on that server.
- **Knowledge:** source folder (folder picker), topK, score threshold, **Reindex**. The folder must sit **under the data directory**, must not be a drive root, and must not be the help corpus.
- **Chat input:** placeholder, start text, “input required”.
- **Router:** named branches (name + condition) and default.

Secrets do **not** belong in inspector text or graph export — only the choice of a credential.

## Validation

**Validate** on the ribbon checks, among other things:

- name not empty
- at most one chat input, at least one end
- each agent: exactly one LLM edge and one incoming message
- LLM: model set; cloud: credential
- tool: kind; MCP: enabled server, root path if the recipe needs it
- knowledge: path, sandbox, not the help corpus
- no dangling edges, no cycles, matching port types

Valid/invalid shows as a badge. Invalid networks can be saved but should not be started.

## Save, load, export

- **Save** (Ctrl+S): first time a name dialog, then update. URL becomes `/network/…`.
- **Save as:** new document, becomes the open one.
- **Load:** one saved network; search and sort. Bulk and delete only in the library.
- **Duplicate:** only when the document is already saved; opens the copy.
- **Export:** download of the open graph. Includes `credentialId`, never keys. Library import discards secrets that slipped into a file.

Leaving with unsaved changes: Save / Discard / Cancel.

## Library

List with search (name, description, tags), sort, filters “valid only” / “active only”. Multi-select.

Actions: New (editor), Open, Duplicate, Rename, Set tags, **Set active** (only one valid network), Delete, Import, Export.

Delete removes the workspace entry, not your knowledge source files on disk, not the help corpus, and not history runs. A **running** network is skipped. Deleting the active network clears quick select.

Import: rename or skip name collisions. Unsupported schema versions are rejected.
