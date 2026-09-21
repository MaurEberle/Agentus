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

**Network (read-only):** the same graph, node colours by status (idle, waiting, running, done, error). Click a node to filter log/activity and open node detail (role, status, waiting on LLM/tool/input/index, last message, tokens). No editing, no second editor.

If knowledge hangs off an agent, start already shows the run while indexing: the knowledge node runs with wait reason **index**, the log names reading and embeddings, and the header and dashboard show the same name. An index that is already current is skipped and only noted as current.

**Activity:** current nodes, progress “step x of y”, tokens in/out, optional context window.

**Host resources:** CPU, RAM, GPU/VRAM of **this PC**, not only the app process. No local GPU (typical for cloud runs) is a hint, not an error.

## Run chat (monitoring)

**Chat** tab: the conversation of the running graph. Only while the run is active. Without an orchestrator the chat waits for the first line and passes it down the chain. With an orchestrator you talk only to it. Follow-ups stay open in the same run. Agent text and internal commands do not appear here.

This is **not** the help bubble. History and tools belong to the network.

## Log (monitoring)

**Log** tab: lines with level (debug, info, warn, error), node, time. Newest first. Pause stops follow-the-tail; “Jump to latest” resumes. Filters: search, minimum level, one node, errors only. Export visible lines.

Payloads and messages **mask** secrets (for example `Bearer`, key prefixes). Do not paste them unfiltered.

## History

Ribbon: refresh, delete selected runs, export logs, purge older than retention (see Settings → Data, default 90 days).

**One filter** drives everything: range (today, 7/30 days, from–to), network, model, search (run id, network, error). KPIs, “runs by day” chart, top errors, tabs History / By model / By network, and the list all use that filter.

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

Side panel or dedicated view: meta, mini graph, tabs **Log**, **Steps**, **Chat**. Steps: node, role, status, error. Chat: transcript, read-only. Export a single log.

Deleting history rows does not change saved networks.
