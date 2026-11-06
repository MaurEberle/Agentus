# Agentus Network – Lösungsanalyse

Stand: 2026-11-06, Branch `fix/general_v4` (inkl. uncommitted Änderungen in `frontend/src/modules/models/HubPane.tsx` und `store.ts`).
Die Analyse hat den Code nur gelesen, nichts wurde geändert. Pfade beziehen sich auf `backend/app/` bzw. `frontend/src/`, wenn nicht anders angegeben.

---

## 0. Qualitätsstatus (selbst ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| `pytest` (Backend) | **729 bestanden, 4 fehlgeschlagen**; im ersten Lauf 5 fehlgeschlagen, ein Test ist also flaky |
| `tsc --noEmit` | sauber |
| `eslint .` | **2 Fehler, 22 Warnungen** |

Fehlgeschlagene Tests:
- `tests/db/test_bootstrap.py::test_no_sqlite_outside_db`: `app/llm/blobs.py` importiert `sqlite3`, obwohl die Architekturregel SQLite nur in `app/db` erlaubt.
- `tests/runtime/test_router.py::test_model_stats_ollama`: `AttributeError: '_Profile' object has no attribute 'projector_bytes'` in `http/routers/runtime.py:115`. Das ist ein **echter Laufzeitfehler**, `/runtime/model-stats` antwortet mit 500.
- `tests/help/test_retrieve.py::test_retrieve_filters_by_locale`: liefert `de-guide` statt `fr-guide`, der Sprachfilter bzw. Fallback stimmt nicht.
- `tests/mcp/test_sessions.py::test_postgres_app_db_no_spawn`: wirft `AppError: mcp.unavailable`.
- `tests/help/test_pipeline.py::test_abort_done_partial`: flaky, liefert zeitweise `500`.

ESLint-Fehler:
- `components/ModelCombobox.tsx:137`: „Hook bedingt aufgerufen“. Fehlalarm, weil die Prop `useValueLabel` heißt; Umbenennen genügt.
- `i18n/languages.ts:28`: unbenutzter Parameter `_value`.

---

## 1. Gesamtarchitektur

```
WebView2-Fenster (pywebview) ──HTTP──► FastAPI 127.0.0.1:8765 (/api + SPA-Static)
                                          │
              ein Windows-Prozess ────────┼── SQLite (4 Stores), keyring-Vault
                                          ├── Run-Harness (Thread), SSE
                                          ├── MCP-Supervisor (stdio/HTTP-Subprozesse)
                                          └── Hilfe-Chat (RAG)
Ollama / llama-server (eigene Prozesse) ◄── Completions / Embeddings
Cloud-Provider: OpenAI, Anthropic, Gemini, xAI, openai_compat
```

Auslieferung: PyInstaller-onedir (`packaging/agentus_network.spec`), NSIS-Per-User-Setup (`installer/Agentus-Network.nsi`) mit WebView2- und Ollama-Bootstrap, außerdem ein Portable-ZIP. Gebaut wird über `scripts/build-windows.ps1`.

### 1.1 Backend (Python 3.12, FastAPI)

**Start** (`main.py`):
1. stdio absichern und Host/Port prüfen (nur Loopback erlaubt).
2. `_bootstrap()`, darin `db.init()`: Config-YAML lesen, `open_all()` mit Migrationen ausführen, verwaiste Läufe abbrechen, Credential-Migration, `atexit` registrieren.
3. Hilfe-Seed kopieren, Download-Worker starten, MCP-Hooks einrichten, optional Ollama starten.
4. Prod-Modus: `host/window.run_host` übernimmt mit Single-Instance-Mutex, Uvicorn im Daemon-Thread, Health-Wait und WebView-Fenster samt `js_api` und Navigation-Guard.
5. Mit `DEV`/`NO_HOST` läuft nur `uvicorn.run`.

**Schichten:**
- `http/`: App-Factory, CORS, Fehler-Mapping auf `{messageKey, message?}`, SPA-Mount, SSE. 14 Router unter `/api`, alle Handler synchron und damit im Threadpool.
- Services:
  - `settings/`, `networks/` (CRUD, Import/Export, Validierung)
  - `prompts/`
  - `llm/` (Hub, Downloads, Pull, Blobs)
  - `runtime/` (Completions, Embeddings, Ollama-Daemon, eigener llama-server-Runner, VRAM-Schätzung)
- `db/`: eine SQLite-Connection pro Store mit eigenem Lock, WAL, explizitem `BEGIN`, lineare Migrationen in `db/migrate.py`.

| Store | Tabellen | Schema |
|---|---|---|
| settings | `app_settings`, `credentials` (nur Masken), `mcp_servers` | v1 |
| help | `help_messages`, `help_chat_rag_chunks` | v3 |
| workspace | `networks`, `network_rag_*`, `prompts`, `model_tags`, `model_downloads`, `download_gate` | v7 |
| history | `runs`, `llm_calls`, `run_logs`, `run_steps` | v3 |

**Secrets:** liegen im Windows Credential Manager (`db/vault.py`, Service `Agentus-Network`, `credential/{id}`). SQLite speichert nur Masken. Beim Export entfernt `networks/transfer.strip_secrets` die Secrets.

**Provider:** `runtime/urls.py` bestimmt Basis-URL und Header. Die Reihenfolge ist Knoten-Override, dann Settings, dann Default. Ollama läuft über das native `/api/chat`, OpenAI teilweise über `/v1/responses`, alle anderen über `/v1/chat/completions`. Gestreamt wird mit einem Idle-Watchdog statt eines festen Gesamt-Timeouts.

**Lauf** (`run/`):
- `controller.start()` lädt das aktive Netz, validiert und kompiliert den Graphen, prüft VRAM, legt den Run an, indexiert das Wissen synchron, öffnet die MCP-Sessions und startet den Thread `run_harness`.
- Zwei Varianten:
  - Kette (`_run_linear`): BFS über Router und Agenten, höchstens 32 Agent-Aufrufe.
  - Orchestrator-Schleife: pro Runde think/call/ask/reply/finish, Limits 24 Steps und 64 Thinks, mit Takeover-Logik.
- `agent_turn`: RAG-Snippets holen, Kontextfenster bilden, `complete_live` streamen (Idle-Grenze 180 s), Tool-Calls ausführen (auch aus Freitext „salvaged“).
- Events: `sse.publish` verteilt an Queues mit je 1000 Einträgen. Jedes Log-Event wird in die DB geschrieben, Steps per Upsert.
- Abbruch: `stop()` setzt `stop_event`, wartet bis zu 10 s per Join und ruft dann `finish("cancelled")`.

**Wissensindex** (`run/knowledge.py`): `rglob` über den Ordner, SHA256-Fingerprint, Chunking nach Überschriften und Fenstern (800 Zeichen, 80 Überlappung), Vektoren in SQLite, Cosinus in reinem Python.

**MCP** (`mcp/`): JSON-Rezepte, gestartet per npx, uvx oder GitHub-Binary. Pro Session ein eigener asyncio-Loop-Thread. Sessions starten lazy und werden nach 300 s Leerlauf geschlossen. Pfad-Argumente werden über `sandbox.confine_tool_arguments` auf die Wurzel begrenzt.

**Tools** (`tools/`): HTTP (eigene Redirect-Verfolgung und Blockliste), Websuche (Brave, Tavily, Exa, SearXNG), Datum/Zeit, Taschenrechner (AST-Whitelist), Dateizugriff (resolve plus `is_relative_to`). Dazu kommen **Terminal** und **Zip**, die die README nicht erwähnt.

**Hilfe-Chat** (`help/`): Index-Gate, RAG mit Sprachfilter, optional Websuche, Streaming mit Entfernen der Think-Blöcke, Persistenz. Der Reindex läuft in einem Hintergrund-Thread.

### 1.2 Frontend (Vite, React 18, TypeScript)

- **Routing:** `routes.tsx` mit `createBrowserRouter` und `AppShell`. Module kommen aus `modules/registry.ts` (Dashboard, Network-Editor, Networks, Monitoring, History, Settings, Models, Prompts, Downloads). Kein Lazy-Loading, das Bundle ist ca. 1,4 MB groß.
- **State:**
  - Zustand global für Session, Benachrichtigungen und UI-Prefs (persistiert).
  - Zustand pro Modul für Editor mit Undo/Redo, Monitoring-Live und Filter.
  - React Query für Serverdaten (`staleTime` 30 s, gezieltes Polling).
  - localStorage für Spaltenbreiten, Panes, Sprache und Theme.
- **API:** `api/client.ts` mit `apiFetch`, das `ApiError(status, messageKey, …)` wirft. `messageKey` wird auf i18n-Texte abgebildet. Es gibt kein `AbortSignal`.
- **Live:** `monitoring/live/sse.ts` mit einem `EventSource` auf `/run/stream`. Bei Fehlern Backoff, danach Polling-Fallback und Watchdog. Der Hilfe-Chat nutzt `fetch` mit `ReadableStream`.
- **Graph-Editor:** `@xyflow/react`. `FlowCanvas` spiegelt das Store-Dokument. `schema/ports.ts` regelt erlaubte Verbindungen, `validation/validate.ts` spiegelt die `graph.*`-Codes des Servers.
- **i18n:** de, en und es haben jeweils 1499 Keys und sind deckungsgleich.
- **UI:** Tailwind und Radix (shadcn), Lucide, Sonner.

---

## 2. Problemstellen

Schweregrad: **H** = hoch, **M** = mittel, **N** = niedrig. „(V)“ markiert eine Vermutung, die noch nicht vollständig verifiziert ist.

### 2.1 Sicherheit

| # | Grad | Ort | Problem / Szenario |
|---|---|---|---|
| S1 | **H** | `http/app.py:62-95` | **Weder Host- noch Origin-Prüfung** auf der API ohne Auth. Per DNS-Rebinding kann eine Webseite die API steuern: z. B. `POST /runtime/test-llm` mit fremder `baseUrl` und gespeicherter `credentialId` (Key-Exfiltration), Netze starten, MCP-Server mit beliebigem `command` anlegen (V: RCE). Lösung: TrustedHost-Middleware (`127.0.0.1`, `localhost`) plus Origin-Prüfung oder Session-Token. |
| S2 | **H** | `tools/terminal_tool.py:12,46` | Die Standard-Allowlist `git, python, py, dotnet` erlaubt `python -c "…"`. Damit ist das „eingeschränkte“ Terminal offen, und über Prompt-Injection (HTTP, Websuche, Dateien) wird Codeausführung möglich. |
| S3 | **H** | `tools/calculator_tool.py:132` | Nur der Exponent ist begrenzt (≤ 20). Verschachtelte Potenzen `((((((9**20)**20)**20)**20)**20)**20)` brauchen über 60 s CPU, halten den GIL und frieren das Backend ein (lokal gemessen). |
| S4 | M | `tools/http_tool.py:44-46,84,178` | SSRF: Private Netze sind bewusst erlaubt. Die eigene DNS-Prüfung und die spätere Auflösung durch httpx sind getrennt (TOCTOU), per Rebinding ist damit auch `127.0.0.1:8765` erreichbar. |
| S5 | M | Endpunkte ohne Body | CSRF: `/run/start`, `/run/stop`, `/help-chat/clear`, `/help-chat/reindex` und `/models/downloads/pause` lassen sich cross-site auslösen. Für JSON-Bodies schützt `strict_content_type`. |
| S6 | M | `tools/file_access_tool.py:52-57` | `allowWrite` und `allowDelete` sind standardmäßig `true`. Zusammen mit Prompt-Injection kann ein Agent Dateien unter der Wurzel löschen. |
| S7 | M | `tools/zip_tool.py:332` | Beim Entpacken werden Dateien ohne Rückfrage überschrieben; nach einem Fehler bleiben Reste liegen. |
| S8 | M | `mcp/sandbox.py:183-198` | Die Pfadbegrenzung kennt `paths` (`read_multiple_files`) und `repo_path` (git) nicht. |
| S9 | M | `mcp/recipes/excel.json`, `git.json` | Keine Version gepinnt, `npx -y` ohne Integritätsprüfung. Die GitHub-Binary wird nach dem Download nur noch auf „existiert und ist nicht leer“ geprüft (`mcp/github_server.py:45`). |
| S10 | M (V) | `networks/transfer.py`, `networks/service.py:235` | Die Knoten-`baseUrl` überlebt den Import. Ein präpariertes Netz plus eigener Zugang schickt den Key an eine fremde URL. |
| S11 | M | `components/MarkdownView.tsx:76` | `![](https://…)` wird automatisch geladen, bei importierten Prompts ein Tracking- bzw. Exfiltrationskanal. |
| S12 | N | `common/secrets.py:8-9`, `runtime/completions.py:430`, `http/errors.py:114` | Die Maskierung kennt keine `AIza…`- (Gemini) und `xai-…`-Keys. Provider-Fehler und Tracebacks werden unmaskiert geloggt. |
| S13 | N | `networks/service.py` (POST/PUT) | Knotendaten werden ungefiltert gespeichert. `strip_secrets` kennt `x-api-key` und `accessToken` nicht und hört ab Tiefe 8 auf. |
| S14 | N | `mcp/sessions.py:715` | `os.environ.copy()` gibt die komplette Prozessumgebung an Drittserver weiter. |
| S15 | N | `help-chat/HelpChatMessages.tsx:19`, `help-chat/markdown.tsx:18` | Quellen-URLs werden nicht auf `http(s)` geprüft. `dangerouslySetInnerHTML` ist derzeit escaped, aber fragil. |
| S16 | N | `run/orchestrate.py:342` | Tool-Ergebnisse gehen ungefiltert ans Modell zurück, und `salvage_tool_calls` macht aus Freitext echte Tool-Calls. Das verstärkt Prompt-Injection (Grundproblem von S2, S4, S6). |

### 2.2 Backend: Bugs, Nebenläufigkeit, Ressourcen

| # | Grad | Ort | Problem / Szenario |
|---|---|---|---|
| B1 | **H** | `run/controller.py:147,432-436,661` | **Stop/Start-Race:** `stop()` wartet nur 10 s, Tools laufen aber bis zu 60 s. `start()` prüft nicht `thread.is_alive()`. Der alte Harness schreibt über die globale `ctrl.run_id` Logs und Chat in den **neuen** Lauf und beendet ihn mit seinem `finish()`. |
| B2 | **H** | `main.py:89` gegen `host/window.py:96` | `_bootstrap()` läuft vor dem Single-Instance-Mutex. Eine zweite Instanz setzt über `abandon_orphaned_runs()` den laufenden Lauf der ersten auf `cancelled`. Mit `NO_HOST` gibt es gar keinen Schutz. |
| B3 | **H** | `mcp/sessions.py:82,96-104,550-573` | MCP-Subprozesse und Threads lecken: kein Aufräumen bei Setup-Fehler oder Timeout, kein `loop.close()`, kein try/finally nach `connect_transport`. (V) anyio-Kontexte werden in verschiedenen Tasks betreten und verlassen, npx-Prozesse überleben. |
| B4 | **H** | `http/routers/runtime.py:115` | `profile.projector_bytes` existiert nicht, der Endpunkt liefert 500 (Test rot). |
| B5 | M | `run/controller.py:597` | `abort_generation` wird gesetzt, aber im Stream nie gelesen. „Chat abbrechen“ stoppt die Generierung nicht. |
| B6 | M | `run/controller.py:220/259-262,478-482` | Start-Race: ein `stop()` während `start()` wird überschrieben. `finish()` ist check-then-act, der Teardown kann doppelt laufen. |
| B7 | M | `db/engine.py:97-160`, `db/bootstrap.py:243-270` | Connections werden außerhalb des Locks geholt, `close_all`/`open_all` sperren nicht. Ein Datenordner-Wechsel zerstört Connections anderer Threads (`ProgrammingError`). |
| B8 | M | `db/bootstrap.py:254-262` | Ein Datenordner-Wechsel mit Kopie überschreibt vorhandene DBs ohne Rückfrage. Ein `OSError` mittendrin lässt alle Stores geschlossen zurück. |
| B9 | M | `llm/downloads.py:335-338` | `_claim()` steht ohne `try`. Eine Exception beendet den Download-Worker dauerhaft. |
| B10 | M | `runtime/ollama_embed_runner.py:303-324` | Der Runner wird bei anderer Signatur auch mit `refs>0` beendet, das Lock bis zu 120 s gehalten, und es gibt keinen Shutdown-Hook. |
| B11 | M | `networks/service.py:94,119,214` | Der pydantic-`ValidationError` hat keinen Handler, ungültige Netze ergeben 500 statt 400. |
| B12 | M | `http/routers/models.py:63-69` | Ist Ollama nicht erreichbar, liefert `/models/delete` 500, ebenso `test-llm` bei `InvalidURL` oder `VaultError`. |
| B13 | M | `run/knowledge.py:133,150-162,235` | Die Indexierung liest jede Datei für den Fingerprint (bis zu dreimal) ohne Größen- oder Anzahlgrenze, im Request-Thread und ohne `stop_event`. |
| B14 | M | `run/knowledge.py:217,348` | Der Cache vergleicht nur den Modellnamen, nicht den Provider. Bei anderer Vektordimension liefert `cosine` 0, und der Fehler wird verschluckt. Ergebnis: stilles „No document context“. |
| B15 | M | `help/retrieve.py` | Der Sprachfilter bzw. Fallback liefert die falsche Sprache (Test rot). |
| B16 | N | `run/knowledge.py:158,205` | Ist eine einzige Datei gesperrt, ist der Fingerprint leer und der ganze Lauf scheitert. |
| B17 | N | `run/agent_turn.py:152-153` | `topK=0` und `scoreThreshold=0` fallen wegen `or` auf den Default. |
| B18 | N | `run/turn_runtime.py:171-192` | Bei mehreren Tool-Knoten derselben Art gewinnt immer der erste. |
| B19 | N | `run/sse.py:21-28` | Race zwischen `qsize()` und `put_nowait`. Ein Abonnent fällt still raus. |
| B20 | N | `http/routers/run.py` | (V) Der SSE-Sync-Generator belegt pro Verbindung einen Threadpool-Worker (Limit 40). |
| B21 | N | `run/turn_runtime.py:479`, Logs | Pro Token wird der volle Snapshot maskiert und verschickt. Log-Strings dürfen bis 1 MB groß sein, und beim Reconnect werden alle Logs erneut abgespielt. |
| B22 | N | `db/runs.py:583` | `list_calls` sortiert nach UUID4, die Paginierung ist zufällig. |
| B23 | N | `settings/service.py:130-160,272` | Read-modify-write ohne Lock, parallele PATCHs gehen verloren. |
| B24 | N | `help/abort.py`, `help/pipeline.py:184,204-212` | Es gibt nur ein globales Abort-Event, und abgebrochene Antworten werden als „done“ gespeichert. |
| B25 | N | `mcp/sessions.py:510` | Der Lock wird nach der Prüfung gelöst, zwei gleichzeitige Öffnungen starten zwei Prozesse. |
| B26 | N | sonstige | `wait_health` prüft fest `127.0.0.1` (bricht mit `::1`). Connection-Leck bei Migrationsfehler (`engine.py:136`). LIKE-Wildcards werden nicht escaped. `delete_networks` ist nicht atomar. `_with_query` verwirft doppelte Parameter. |

### 2.3 Frontend: Bugs

| # | Grad | Ort | Problem / Szenario |
|---|---|---|---|
| F1 | **H** | uncommitted Diff: `downloads/DownloadsHeader.tsx:29`, `models/ModelsModule.tsx:481` | Beide invalidieren `['models','hub','files']`, die Hub-Daten liegen aber jetzt im Zustand-Store. Nach einem Download oder Löschen bleibt „Installieren“ stehen, doppelte Downloads werden möglich. |
| F2 | M | uncommitted Diff: `models/HubPane.tsx:557/562` | `filesError` wird beim Modellwechsel nicht zurückgesetzt, beim Laden von B steht noch der Fehler von A. |
| F3 | **H** | `network/NetworkModule.tsx:279-309` | `readOnly` wird nur für Ctrl+S geprüft. Bei laufendem Netz verändern Entf, Ctrl+D/V, Pfeiltasten und Undo das Dokument trotzdem. |
| F4 | M | `network/NetworkModule.tsx:279` | Ctrl+Z wird vor der Prüfung „tippt der Nutzer gerade?“ abgefangen. Im Textfeld greift damit die Store-Undo statt der nativen Textfeld-Undo. |
| F5 | M | `network/NetworkModule.tsx:330,334,196` | `markSaved` überschreibt Eingaben, die während des Speicherns gemacht wurden. Nach dem ersten Speichern wird die Undo-Historie geleert. |
| F6 | **H** | `monitoring/live/sse.ts:126-134` | Nach drei Verbindungsfehlern wird nur noch gepollt und SSE nie wieder versucht. Nach einem Backend-Neustart kommen bis zum Neuladen keine Log- und Chat-Events mehr an. |
| F7 | M | `monitoring/store.ts:266`, `sse.ts:91` | Im Polling-Modus löst `service: stopped` alle 1,5 s `hydrateLastRun` aus, also 3 Requests. |
| F8 | M | `monitoring/live/adapter.ts:46-48` | Scheitert das Senden im Chat, bleibt `chatGenerating` auf `true`, und der Text ist schon gelöscht. |
| F9 | M | `components/help-chat/api.ts:38` | Ein Stream-Ende ohne `done`/`error` lässt den Hilfe-Chat dauerhaft im Zustand „generiert“. |
| F10 | M | `downloads/DownloadsHeader.tsx:27` | Beim ersten Download einer Sitzung wird nichts invalidiert. |
| F11 | M | `monitoring/store.ts:344` | Chat-Nachrichten eines neuen Laufs werden ohne `maskText` übernommen. |
| F12 | M (V) | `api/session.ts:204` und `monitoring/store.ts` | `serviceStatus` hat zwei Quellen. Eine verspätete Session-Antwort kann einen neueren SSE-Status überschreiben. |
| F13 | N | `sse.ts:62` | Der Watchdog wird durch selbst erzeugte Events „belebt“. |
| F14 | N | `Inspector.tsx:370,1199`, `PromptPickDialog.tsx`, `NetworksModule.tsx:95`, `PromptsModule.tsx:232`, `McpSection.tsx:103` | `exhaustive-deps`-Warnungen; einzeln prüfen, ob dort veraltete Werte (stale closures) entstehen. |

### 2.4 Performance (Frontend)

- `network/canvas/FlowCanvas.tsx:89-131`: Jeder Tastendruck baut alle Node-`data` neu auf, damit rendern alle `NetworkNode` neu. Bei den Kanten kommt `nodes.find` pro Kante hinzu (O(E·N)).
- `NetworkModule.tsx:167`: `isDirty()` ruft zweimal `JSON.stringify` über das ganze Dokument auf, bei jeder Store-Änderung.
- `network/store.ts:169`: ein Undo-Eintrag mit tiefer Kopie pro Tastendruck, ohne Bündelung.
- `monitoring/log/LogPanel.tsx:209`: bis zu 2000 Zeilen ohne Virtualisierung; pro Event eine Array-Kopie und eine lineare Duplikatsuche.
- `validateDocument` läuft doppelt (`NetworkModule.tsx:172`, `FlowCanvas.tsx:62`).
- Kein Code-Splitting, das Bundle ist ca. 1,4 MB groß.

### 2.5 Wartbarkeit, toter Code, Duplikation

- Sehr große Dateien: `Inspector.tsx` (2155 Zeilen), `NetworkModule.tsx` (761), `PromptsModule.tsx` (730).
- Toter Code bzw. No-ops:
  - `_vram_start` gibt immer `False` zurück (`run/controller.py:189,266`).
  - `set_help_degraded(True)` wird nie aufgerufen.
  - `RunController.reset()` und `stop_resources()` werden nicht genutzt.
  - `run/validate.py:162` enthält `if False`.
  - `ApiModel.model_config` wird in `create_app` neu gesetzt, ohne Rebuild; das ist wirkungslos.
  - `persist_status` enthält einen doppelten oder unerreichbaren Zweig.
  - `languageDirection` ist ein Platzhalter.
- Duplikation:
  - Masken- und Secret-Key-Logik gibt es dreifach mit unterschiedlichen Schlüssel-Sets (`common/secrets.py`, `networks/transfer.py`, `settings/service.py`).
  - RAG-Abfrage und Cosinus gibt es doppelt (`run/knowledge.py:321`, `help/retrieve.py:75`).
  - `_flag` und `env_flag` sind doppelt.
  - localStorage-Helfer stecken in mehreren Modulen.
- `http/routers/__init__.py:30` (`include_all`) schluckt jeden `ImportError`. Ein kaputtes Import deaktiviert einen Router still, die Folge sind 404.
- `get_recipe` liest bei jedem Aufruf alle Rezept-JSONs neu.
- Das uncommitted Diff legt Serverdaten in Zustand statt in React Query und widerspricht damit der Konvention in `frontend/README.md`.

### 2.6 Doku gegen Code

- Laut README läuft alles über „nur `/v1/chat/completions`“. Tatsächlich nutzt Ollama `/api/chat` und OpenAI zum Teil `/v1/responses`.
- Die README nennt neun Hilfesprachen; vorhanden sind nur de, en und es.
- Die README führt `prompts/` im Repo-Baum auf, das Verzeichnis ist aber per `.gitignore` ausgeschlossen. Die Repo-README verweist trotzdem auf `prompts/build.md` als verbindlich.
- Laut README gibt es einen gemeinsamen httpx-Client. Tatsächlich entsteht pro Aufruf ein neuer Client ohne Connection-Reuse.
- Die Tools Terminal und Zip sind nicht dokumentiert.
- `AGENTUS_NETWORK_NO_OLLAMA` und `AGENTUS_NETWORK_HELP_DOCS` fehlen in der Env-Tabelle.

### 2.7 Testlücken

- Die echte `_SdkSession` wird nie getestet (`connect_transport` ist immer gemockt), damit gibt es auch keinen Test auf Prozess-Lecks.
- Keine Tests für Stop/Start-Races, Stop bei langlaufendem Tool, `abort_chat` oder Abbruch während der Indexierung.
- Keine Tests für verschachtelte Potenzen, DNS-Rebinding, die Terminal-Standard-Allowlist, Zip-Überschreiben, Provider-Wechsel im Wissensindex oder die Lücken in der MCP-Pfadbegrenzung.
- Es gibt keine Frontend-Tests (weder Unit noch E2E).

---

## 3. Empfohlene Reihenfolge

1. **Sicherheit, kleine Fixes mit großer Wirkung:**
   - S1: TrustedHost-/Origin-Middleware oder Session-Token einbauen.
   - S2: Standard-Allowlist des Terminals leeren bzw. `python` entfernen.
   - S3: die Basis bzw. die Ergebnisgröße beim Potenzieren begrenzen.
   - S6: `allowWrite`/`allowDelete` standardmäßig auf `false`.
2. **Rote Tests reparieren:** B4 (`projector_bytes`), B15 (Sprachfilter), `llm/blobs.py` in `db/` verschieben, MCP-Postgres-Test, flaky Abort-Test.
3. **Uncommitted Diff vor dem Commit korrigieren:** F1, F2.
4. **Laufzeit stabil machen:** B1/B6 (Thread-Lebenszyklus, `run_id` pro Harness statt global), B2 (Mutex vor dem Bootstrap), B3 (try/finally beim MCP-Aufbau), B5 (`abort_generation` auswerten).
5. **Frontend:** F3/F4 (readOnly, Undo im Textfeld), F6 (SSE-Reconnect), F8/F9 (hängende Generating-Zustände).
6. **Danach:** Performance im Editor, Aufräumen von Duplikation und totem Code, Doku angleichen, Testlücken schließen.

---

## 4. Umgesetzt (2026-11-06, uncommitted)

| Punkt | Änderung |
|---|---|
| S1, S5 | Neue Middleware `backend/app/http/guard.py`: Fremde `Host`- und `Origin`-Header bekommen 403 (`http.forbiddenHost`/`http.forbiddenOrigin`). Die Test-Clients nutzen `base_url="http://127.0.0.1"`. |
| S2 | Ohne Programmliste erlaubt das Terminal standardmäßig nur noch `git` (Backend und Inspector). Code direkt in der Kommandozeile (`python -c`, `git -c`/`--config-env`, `node -e`) wird mit `tools.terminal.inlineCode` blockiert. |
| S3 | Ganzzahlen sind im Rechner auf 1100 Bit begrenzt, verschachtelte Potenzen werden sofort abgewiesen. |
| B1, B6 | `start()` lehnt ab, solange der alte Harness-Thread noch lebt. Kommt ein Stop während des Starts, wird der Lauf sauber als `cancelled` beendet statt überschrieben. |
| B2 | Mutex und Port-Prüfung laufen vor `db.init()`. Eine zweite Instanz bricht so keine laufenden Läufe mehr ab. |
| B4 | `projector_bytes` wird tolerant gelesen. |
| Tests | `sqlite3` liegt jetzt in `app/db/ollama_settings.py`. Die veralteten Tests (Locale `fr`, Postgres-Rezept) sind angepasst, der instabile Abbruch-Test ist korrigiert. |
| F1, F2, F10 | Hub-Dateien werden über `filesNonce`/`invalidateHubFiles()` aktualisiert. Ein neu gewähltes Modell setzt den alten Fehler zurück, und der erste Download einer Sitzung aktualisiert die Listen. |
| F3 | Im Lesemodus sind Tastenkürzel zum Bearbeiten (Entf, Ctrl+D/V/Z, Pfeile) gesperrt. |
| F6 | SSE versucht im Polling-Modus weiter, sich neu zu verbinden, und beendet das Polling, sobald die Verbindung steht. |
| Lint | Prop `useValueLabel` heißt jetzt `customValueLabel`, `languageDirection()` hat keinen Parameter mehr. |

Ergebnis: `pytest` 763/763 grün, `tsc` sauber, ESLint 0 Fehler (22 Warnungen, unverändert).

### 4.1 Zweite Runde (Fehlerbehandlung)

| Punkt | Änderung |
|---|---|
| B11, B12 | Zentrale Handler in `http/errors.py`: pydantic `ValidationError` ergibt 400 `http.validation`. `RuntimeApiError` und httpx-Transportfehler ergeben 502 `runtime.unreachable`/`runtime.upstream` bzw. 504 `runtime.timeout`, `httpx.InvalidURL` ergibt 400 `runtime.invalidUrl`. Keine 500er mehr bei ungültigen Netzen oder nicht erreichbarem Ollama. Den doppelten bzw. unerreichbaren Zweig in `persist_status` habe ich entfernt. |
| B3 | Die MCP-`_SdkSession` betritt und verlässt ihre Kontexte jetzt in **einem** Task (`_lifecycle` mit `AsyncExitStack`). Ein fehlgeschlagener Start räumt Loop-Thread und Kindprozess auf, `close()` schließt den Loop. `_run` bricht Coroutinen nach einem Timeout ab, und `open()` schließt die Session, wenn `list_tools` oder das Speichern scheitert. Der neue Test `tests/mcp/test_sdk_session.py` nutzt einen echten stdio-Server. Gegen den alten Code schlägt er fehl, weil der Loop-Thread leckt. |
| B9 | Der Download-Worker überlebt Store-Fehler (Backoff 2 s) und Fehler beim Abschließen eines Downloads. |
| S12 | `mask_text` maskiert zusätzlich Gemini- (`AIza…`), xAI- (`xai-…`) und GitHub-Tokens. Als geheime Schlüssel gelten jetzt auch `x-api-key`, `accessToken`, `refresh_token` und `client_secret`. |
| B22 | `list_calls` sortiert nach `rowid` (Einfügereihenfolge) statt nach UUID. |
| F8 | Scheitert das Senden im Lauf-Chat, wird `chatGenerating` zurückgesetzt und der Text ins Eingabefeld zurückgeschrieben. |
| F9 | Endet der Hilfe-Chat-Stream ohne `done`/`error`, wird ein Fehler gemeldet, statt dass die Anzeige endlos lädt. |
| Build | `build-windows.ps1` nutzt fest `%SystemRoot%\System32\tar.exe`. Aus Git Bash wurde sonst GNU-tar gefunden, und das Portable-ZIP schlug fehl. |

Ergebnis: `pytest` 769/769, `tsc` sauber, ESLint 0 Fehler.
