# Monitoring and history

**Monitoring** = now, one run. **History** = archive and stats. History is **not** a second dashboard and **not** a live tail. Start and Stop stay in the **header**.

## Live vs archive

| | Monitoring | History |
|---|------------|---------|
| When | service starting, running, or stopping | after the run ends (and a link while it still runs) |
| Graph | mini graph, read-only, node status | stored snapshot, no live updates |
| Log | stream, newest first, can pause | frozen lines, filterable |
| Chat | run chat, only while running | stored transcript, not continued |

A still-running history row is only a jump to monitoring (“View live”).

## Monitoring with no run

With no active run the page shows the **last saved run** for reading (graph, activity, log, chat). A note says nothing is live. The page is fully empty only when no run has been saved: **No run**, plus the active network or a hint that quick select is empty. Disconnected / error / starting / stopping have their own copy. While knowledge is indexing, the starting hint switches to that node’s name. Last values may stay greyed out until the connection is back.

## During a run

Header: run id, start time, duration, rough step, active LLMs (local vs cloud).

**Network (read-only):** the same graph, node colours by status (idle, waiting, running, done, error). Click a node to filter log/activity and open node detail (role, status, waiting on LLM/tool/input/index/thinking, last message, tokens). No editing, no second editor.

If knowledge hangs off an agent, start already shows the run while indexing: the knowledge node runs with wait reason **index**, the log names reading and embeddings, and the header and dashboard show the same name. An index that is already current is skipped and only noted as current.

**Activity:** At the top the live values: tokens per second of the model that is writing; how full its context window is (bar, yellow from 75 %, red from 90 %); output tokens of the whole run. Below, in one line, who is at work, and the full task of the working agent, ready to copy. When the run waits for you, a highlighted line says so.

Chat and log sit above the network and activity. The three cards keep their height when the window grows; drag the edges between them to resize. The sizes you set are kept after you close the app.

**Host resources:** CPU, RAM, GPU/VRAM of **this PC**, not only the app process. No local GPU (typical for cloud runs) is a hint, not an error.

## Run chat (monitoring)

**Chat** tab (opens when a run starts, if the graph has a chat input): the conversation of the running graph. Only while the run is active. Without an orchestrator the chat waits for the first line and passes it down the chain. With an orchestrator you talk only to it. Before the first message you can pick an earlier run of this network under **Continue from an earlier run** (time, outcome, start of the request). Before its first decision the orchestrator then reads that run's record: requests, agent calls, how it ended, changed files and, if that run itself continued from an earlier one, its background. From it the orchestrator writes itself a background of at most 3000 characters; it appears in the chat. It describes only the earlier run as it ended; your new message is not part of it, and what the agents report in the new run counts as newer. Only the orchestrator gets it and passes on to the agents what they need. If the analysis fails, it gets the shortened record. The run waits only on a follow-up question. Agent text and internal commands do not appear here. A follow-up question shows in the notification bell and the header; the taskbar icon flashes while the window is in the background. **Stop generating** ends the answer in progress. With an orchestrator the run stays open and waits for your next message; in a chain without one the run ends as cancelled.

This is **not** the help bubble. History and tools belong to the network.

## Log (monitoring)

**Log** tab: one line per event as a sentence, newest first. In front: time, icon (decision, agent, tool, model, limit) and status (✓ succeeded, ✗ failed, ⚠ warning); the duration is on the right. Examples: “Senior: reads src/App.tsx · 41 lines”, “Senior: runs: npm run build · exit code 1: …”, “Chief: calls Senior: fix RTL”. Pause stops follow-the-tail; “Jump to latest” resumes.

**View:**

- **Important** (default): orchestrator decisions, tasks, results, limits, warnings and errors.
- **All**: also every tool and model call.
- **Debug**: also debug lines, for example model starts.

**Groups:** Every agent task is a group. Its header names agent, task and result (tool calls, changed files, duration); the arrow shows the lines below. A running task is expanded.

**Filters:** Search finds the shown text, task, result, path and command. The node filter also shows tool and model calls this agent made. Plus “errors only”.

**Detail:** click a line. Tools show path or command, result, error and the hint for the model; agents show task and result; model calls show tokens, duration, answer and reasoning. The raw data (JSON) can be expanded.

**Summary:** At the end of a run a card at the top shows outcome, duration, agent calls per agent (with the highest share of the context window), model calls and tokens, tool calls, changed files and limits reached.

**Context:** The closing line of each agent task names the largest request against the window (for example “largest request 30,896 of 202,752 tokens (15 %)”) and how often it was compacted. If the model reports clearly fewer input tokens than in the step before within one task without compaction, or far fewer than estimated at the window edge, the log warns: **conversation probably cut**. The model is then likely missing the start of the conversation; usually the window on the LLM node is too small.

**Export:** “Export as text” saves the shown lines as Markdown, “JSON” as JSON Lines. File contents are clipped to 2 KB in the log, model answers to 8 KB.

Payloads and messages **mask** secrets (for example `Bearer`, key prefixes). Do not paste them unfiltered.

## History

Ribbon: refresh, delete selected runs, export logs, purge older than retention (see Settings → Data, default 90 days; with “Unlimited” the button is hidden).

**One filter** drives everything: range (today, 7/30 days, from–to), network, model, search (run id, network, error). KPIs, “runs by day” chart, top errors, tabs History / By model / By network, and the list all use that filter.

**Top errors** shows each kind of error of the failed runs as a tile: the more often, the larger, coloured by error class (orchestrator, LLM, tool, timeout …). Large tiles also name share, nodes and the last time; on small ones the tooltip says so. A click filters KPIs, chart and list to that kind of error; a second click or the ✕ in the head lifts the filter. The tiles stay in place meanwhile.

The chart and error list, and the run list and detail, can be resized by dragging the edges, same as in Monitoring. The sizes you set are kept after you close the app.

## Run outcomes

| Outcome | Meaning |
|---------|---------|
| Running | still active — in history only as a link |
| Succeeded | finished normally |
| Failed | a step or the service failed |
| Cancelled | Stop in the header, window closed, or app exit (including after a crash, on the next start) |
| Timeout | deadline exceeded |

**Cancelled is not failed.** Timeouts and cancellations are counted separately in KPIs (footnote on “Failed”).

## Run detail

Side panel or dedicated view: meta, mini graph, tabs **Log**, **Steps**, **Chat**. The log looks like the one in monitoring: views, groups, summary, export as text. Older runs carry less detail (no task, no caller). Steps: node, role, status, error. Chat: transcript, read-only. Export a single log.

Deleting history rows does not change saved networks.
