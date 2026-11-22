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

Middle: **palette** (left), **canvas**, **inspector** (right). On the desktop, palette and inspector can collapse. On narrow screens they are sheets. An empty network shows only a hint to drag the first node from the palette onto the canvas. Edges are curves, the same as in monitoring and history.

Drag nodes from the palette. Cards stay compact; forms live in the inspector. Multi-select with Shift or marquee. Delete removes the selection. Undo: Ctrl+Z.

While **this** network is running: **read-only** banner — stop it in the header first.

## Node types

| Label | Type | Job |
|-------|------|-----|
| Chat | `chat_input` | Run conversation. **At most one.** Output **message**. With an orchestrator it stays open for follow-ups. |
| Orchestrator | `orchestrator` | Voice of the run chat. Inputs **message**, **LLM**, and **tool**. One **channel** output per agent. **Message** only to **end** (or a router). **At most one.** |
| LLM | `llm` | Provider (Ollama, xAI, OpenAI, Claude, Gemini, OpenAI-compatible), model, credential for cloud, temperature, token limit. Output **llm**. |
| Agent | `agent` | System prompt. Inputs message, llm, tool, knowledge, optional **channel**. Outputs message and handoff. The channel comes only from the orchestrator. Without it the agent runs once along the message. |
| Tool | `tool` | First-party: HTTP, web search, date/time, calculator, file access. Output **tool**. |
| MCP | `mcp` | One server created and **enabled** in **Settings**. Output **tool**, same as a tool node. |
| Knowledge | `knowledge` | Folder of files for the network. Output **knowledge**, only to the agent knowledge port. |
| Router | `router` | Sends the message to exactly one output. Branches are checked in order: contains, starts with, first line, regular expression. Default catches the rest. After the orchestrator, outputs lead only to ends. |
| End | `end` | Finish. **At least one.** |

## Connections

Only matching ports:

- Message to message (chat → agent or chat → orchestrator, agent → end, agent → router, router branches → …). The orchestrator sends message only to end or a router.
- Channel to channel (orchestrator → agent). One port per agent. The reply comes back inside the run, without a second edge.
- LLM output to agent **llm** or orchestrator **llm** — each agent and the orchestrator need **exactly one** such edge
- Tool output to agent or orchestrator **tool** (several allowed). A tool or MCP node may connect to both.
- Knowledge output only to agent **knowledge**
- Cycles are forbidden (directed graph without a loop)

Invalid drags are rejected.

## Inspector

No node selected: name, description, tags, stats, validation list of the **open** network. Tags are chips; Enter, comma, or plus commits a tag, the cross removes it. The library filters on the same tags.

Node selected:

- **LLM:** provider, model (list from runtime), credential for cloud, context length from model limits (slider locally, dropdown in the cloud), CPU threads per node (default: physical cores), GPU offload one step per layer (default: all layers, Auto if loading fails), estimated GPU memory from context and offload (last N layers on the GPU; full attention over the whole context, sliding-window layers only for their window; warning if it does not fit the card), ping, advanced temperature (0 to 2, for Anthropic 0 to 1) and max tokens (a whole number from 64 to 262144, below the context). Cloud without a credential is invalid. Number fields take valid values at once; a value outside the range is adjusted when you leave the field. An imported network with invalid values shows a validation error and does not start.
- **Agent:** system prompt and display name. If the agent is on a channel, the inspector explains that tasks come from the orchestrator. It may think internally before writing or calling a tool; think is not shown in the chat. Local models (Ollama and your own OpenAI-compatible servers) get their thinking of the last steps of a task back at the next step, clipped to 1500 characters each, so conclusions such as “this command is not allowed here” are not lost. How many steps is set by **Memory (steps)** on the agent (empty: 10, 2 to 50). It is cut in one go: at twice as many, the older thinking goes at once. Ollama can reuse its cache only when the transcript grows at the end; hybrid models such as Qwen 3.5/3.6 read the whole transcript again after any change further up. Cloud providers do not get it. When the context window gets tight, this thinking goes first. **Tool calls per task** limits its tool calls (empty: 100); after that it answers with what it has.
- **Tool:** kind. HTTP: method and URL, optional credential. The credential is only sent to the address of that URL (scheme, host, port); with a credential the URL is required. Web search: a web-search credential. File access: a root folder, not a drive root; the agent works only under it, and write and delete are switches. **Search** finds file names with a pattern (`*.css`), or with `text` a text inside a file or the files of a folder, with path, line number and line; the text search skips `node_modules` and `.git`. Terminal (restricted): one allowed program with its arguments, no shell. What models add out of habit and what changes nothing here is taken off, and the model is told: `cd` into the working folder, `2>&1` and a trailing `| head -N` or `| tail -N` (the output is then cut to those lines). Other pipes, `&&`, `;` and redirects are still rejected. The agent's prompt says up front what to use instead of common shell commands (for example `grep` → file access search with text, `cat` → read, `mkdir` → file access), naming only tools the agent has. The run remembers a rejected command: for the rest of the task the lesson comes with the tool result, and for every later task to that agent in this run it stands in the system prompt (at most six entries). Commands that do not end on their own (servers and watch modes such as `npm run dev`, `npm start`, `vite`, `--watch`) run for 15 seconds and are then stopped; the agent gets what they printed until then and the note that there is no browser in the run.
- **MCP:** an enabled server from **Settings → MCP servers**. Default is all tools on that server; after a probe you can pick a subset. Credentials belong in Settings. The root folder for Filesystem and Excel is on the node; Git keeps its folder in Settings.
- **Knowledge:** source folder (folder picker), embedding provider (Ollama, OpenAI, or Gemini) and embedding model, topK (1 to 20, empty: 4), score threshold (0 to 1, empty: 0), **Reindex**. The folder may sit anywhere except a drive or system root and the help corpus. Indexed types: Markdown, text, PDF, Word (.docx), Excel (.xlsx), HTML, JSON, CSV, and source code. Images and legacy .doc/.xls are skipped. Cloud embeddings need a credential. The index belongs to this network, not to help.
- **Chat:** placeholder, start text, “input required”.
- **Orchestrator:** system prompt. The model chooses think, a follow-up, one agent task on that agent’s channel, a reply, or finish. Think is not shown in the chat and does not count against the step limit; only agent calls count. The agents are the channels, not a second list. It calls connected tools itself: reading files at any time, at most 15 calls per decision (adjustable) and at most ten in total before the first agent call. If it wants to read on after that, it gets the next decision for it; reading only what it already read counts as no progress. Changing files, the terminal and all other tools only after an agent call failed or during a takeover. Its prompt says what it can reach: which tools are connected, what they are for, and whether they are open now or only after an agent call failed. Without tools of its own it says that it cannot read files and gives checks to an agent. The agent list names the tools of each agent. Rules and details appear only for the tools open at that moment. With tools it can also decide through tool calls (call_agent, ask_user, reply, finish). The same call runs only once per step; a tool that fails three times with the same error, or whose call is repeated twice, is withdrawn for that step. Only a follow-up question waits for you; a reply with a line ending in “?” is handled as a follow-up question. After each agent task the orchestrator sees all calls so far in order: the start of the task, the changed files, how much was read and searched, the full text of each agent's latest result and the start of its earlier results. If its prompt no longer fits the context window, the run shortens it step by step, oldest results first: first to their start, then entirely; the newest result last. The task and changed files of every call, your messages and the background stay; the run memory keeps everything in full.
  - **Misses per agent** (empty: 2): how often in a row an agent may fail or finish a file task without a change. The orchestrator then does that task itself.
  - **Agent calls per run** (empty: 50): every task to an agent counts, review rounds and checks included. At the limit the orchestrator sums up in the chat what is done and what is still open; then the run ends with a note about the limit.
  - **Tool calls per decision** (empty: 50) and **Model calls per run** (empty: 1000, orchestrator and agents together).
  - **Reads per decision** (empty: 15): how many files the orchestrator reads in one decision while it may only read. If it wants to read on, it gets the next decision for it. Before the first agent call at most ten in total apply.
  - If the orchestrator makes several decisions in a row without progress (no agent call, no new tool result, no new message), the run reminds it after four. After eight it gets one last turn without tools for a summary in the chat; then the run ends as stuck.
- **Router:** named branches (name + condition) and default.

Secrets do **not** belong in inspector text or graph export — only the choice of a credential.

## Validation

**Validate** on the ribbon checks, among other things:

- name not empty
- at most one chat, at most one orchestrator, at least one end
- the folders of file access, terminal and zip exist; if one is missing, the run does not start. If a folder disappears during a run, the run switches that tool off
- without an orchestrator, the chain leads from its start (chat or first agent) to an end; with one, it has a channel to at least one agent
- each agent: exactly one LLM edge. Without an orchestrator, one incoming message. With an orchestrator, exactly one channel and no message chain on the same agent
- LLM: model set; cloud: credential
- tool: kind. MCP: an enabled server from Settings; root path if the recipe needs it; file access: a folder that is not a drive root
- knowledge: path set, not a root, not the help corpus, embedding credential when the provider needs one
- no dangling edges, no cycles, matching port types

Valid/invalid shows as a badge. Invalid networks can be saved but should not be started.

## Save, load, export

- **Save** (Ctrl+S): first time a name dialog, then update. URL becomes `/network/…`.
- **Save as:** new document, becomes the open one.
- **Load:** one saved network; search and sort. Bulk and delete only in the library.
- **Duplicate:** only when the document is already saved; opens the copy.
- **Export:** dialog, then JSON of the open graph (`schemaVersion` 1). Includes `credentialId`, never keys.
- **Import:** dialog for a JSON file. It becomes a new network. A name already in use is renamed, or the file is skipped.

Leaving with unsaved changes: Save / Discard / Cancel.

## Library

List with search (name, description, tags), sort, filters “valid only” / “active only”. Multi-select.

Actions: New (editor), Open, Duplicate, Rename, Set tags, **Set active** (only one valid network), Delete, Import, Export. Set tags opens the existing tags of the selection as chips.

Delete removes the workspace entry, not your knowledge source files on disk, not the help corpus, and not history runs. A **running** network is skipped. Deleting the active network clears quick select.

Import: dialog with a preview. Same name: rename or skip. Another schemaVersion is rejected. Secrets are discarded.
