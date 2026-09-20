# Dashboard

The home page. It summarises setup, the active network, and recent runs. It is **not** live monitoring and **not** the archive — those have their own pages.

## Setup

The **Setup** card appears when something is missing for a first run, for example:

- Ollama unreachable → **Check runtime**
- Help profile missing provider or model → **Configure help**
- No network yet → **New network** or **Import network**

When the environment is complete, the card stays hidden. Missing optional models after a silent install without pulls are not a second wizard: runtime ping or help chat will show the failure.

## Host resources

The same card as on **Monitoring**: CPU, RAM, and GPU/VRAM of **this PC**, not only the app process. Values refresh continuously, even when no run is active.

## Status

Shows whether the service is **stopped**, **starting**, **running**, or **stopping**, plus the active network. While running: **Monitoring** link and optional “running since …”. With empty quick select: a hint and a link to the **library**.

Start and Stop stay in the **header**, not on this card.

## Active network

Name, node/edge counts, valid/invalid, last updated. Actions: **Edit** (editor), **Library**, **New network**.

Invalid means editor validation failed (for example a missing model on an LLM node). Do not start those networks.

## Recently used

Short list of saved networks by last use. Click opens the editor. Empty: no networks yet.

## Recent runs

Newest history rows (succeeded, failed, cancelled, timeout, or still running). A running row goes to **Monitoring**, finished rows to **History**. If the history store is broken, a hint links to **Data**.

## Last 7 days

Small stats: run count, succeeded, failed. **History** link for filters and charts. This is a summary, not a second archive.

## Environment

- Ollama reachable or not, rough model count
- Store problems (settings, help, workspace, history)
- **Degraded mode** when help fell back to the spare model

Links: **Data**, Runtime.

## Quick actions

**New network**, **Import** (library), **Runtime**. The same actions exist in navigation and Settings.
