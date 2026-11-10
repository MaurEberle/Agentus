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

---

## 5. Detailanalyse Orchestrator

Dateien: `run/orchestrator_loop.py` (äußere Schleife), `run/orchestrator_decide.py` (ein Modellaufruf und eine Entscheidung), `run/orchestrate.py` (Prompt und Parser), `run/dispatch.py` (Agent-Aufruf), `run/memory.py` (Laufgedächtnis), `run/limits.py`.

### 5.1 Ablauf

1. **Start:** `run_harness` wartet auf die erste Nutzernachricht, dann folgt `_run_orchestrator`.
2. **Jede Runde:**
   - Der System-Prompt wird jedes Mal aus `orchestrator_instructions` neu gebaut: Nutzer-Prompt, Protokoll, Roster mit maximal 400 Zeichen Agent-Anweisung, Tool-Block.
   - `RunMemory.orchestrator_messages` baut die Nachrichten jedes Mal **komplett neu**, und zwar in dieser Reihenfolge: alle `turns` (Nutzer, Gesprochenes, Notizen), Statuszeilen aller Agent-Aufrufe, das letzte Volltext-Ergebnis je Agent, Kurzzeilen zu eigenen Tools, Takeover-Hinweis, Anomalie.
3. **Entscheidung (`_orchestrator_action`):**
   - Das LLM wird gestreamt aufgerufen. Bei Tool-Calls werden die Tools ausgeführt und das Modell erneut aufgerufen, solange es Tools aufruft.
   - Danach parst `parse_orchestrator_action` die Antwort der Reihe nach: JSON, Salvage-Regex, Prosa „call X …“, Markup-Tags, sonst wird sie zu `reply`.
   - Kaputte Antworten, unbekannte Agenten und unbekannte Quellen werden bis zu 2-mal repariert.
4. **Aktionen:**
   - `think`/`defer`: wird geloggt, dann folgt die nächste Runde.
   - `ask`: Frage in den Chat, dann blockiert `_queue_get` bis zur Antwort.
   - `call`: `dispatch._orchestrator_call`, das Ergebnis landet als `AgentRecord` im Gedächtnis.
   - `reply`: Text in den Chat, `spoke=True`. Ein weiteres `reply` wird danach zu `think` umgewandelt.
   - `finish`: Endknoten auf done, Lauf erfolgreich.
5. **Limits:**
   - 24 gezählte Agent-Calls
   - 64 Thinks in Folge, 5 Kurz-Thinks
   - 2 Repairs
   - 5+2 fehlgeschlagene Orchestrator-Tools
   - Takeover nach 3 Datei-Fehlversuchen

### 5.2 Schwachstellen

| # | Grad | Ort | Schwachstelle und Folge |
|---|---|---|---|
| O1 | **H** | `orchestrator_loop.py` (Zweig `think`), `memory.py` | **Gedanken (`think`) werden nicht gespeichert.** Der Zweig loggt den Text nur. `orchestrator_messages` baut den Prompt aus dem Gedächtnis neu, in dem der Gedanke fehlt. Die nächste Runde bekommt so **denselben Prompt**. Die Planung geht verloren, und deterministische Modelle wiederholen denselben Gedanken bis `thinkLimit` (64 LLM-Aufrufe), dann scheitert der Lauf. Das widerspricht dem Prompt („Use think for internal planning … After think, emit call“). |
| O2 | **H** | `orchestrator_decide.py` (`kind == "reply" and block_reply`) | **Ein blockiertes `reply` wird still verworfen.** Nach einem `reply` wird jedes weitere `reply` in ein `think` umgewandelt, der Text verworfen, ohne Notiz an das Modell. Zusammen mit O1 sieht das Modell denselben Prompt und antwortet erneut. Das ergibt eine Schleife aus bis zu 64 unsichtbaren LLM-Aufrufen und dann `thinkLimit`. Typischer Auslöser: Nach einer Antwort will das Modell „Fertig!“ sagen, statt `finish` zu senden. |
| O3 | **H** | `controller.send_chat`, `orchestrator_loop.py` (`ask`) | **Nutzernachrichten außerhalb von `ask`:** Solange der Lauf aktiv ist, landet jede Nachricht in `chat_input_queue`. Der Orchestrator liest die Queue aber nur bei `ask`. Folgen: (a) Er bemerkt neue Wünsche nicht. (b) Beim nächsten `ask` liefert `_queue_get` **sofort die alte Nachricht** als Antwort, bevor der Nutzer die Frage gesehen hat. (c) Bei `finish` gehen ungelesene Nachrichten still verloren. In der Oberfläche ist Senden möglich, sobald `generating=false` ist, etwa nach einem `reply`. |
| O4 | **H** | `orchestrator_decide.py` (Tool-Schleife) | **Keine Obergrenze für erfolgreiche Tool-Aufrufe.** Begrenzt sind nur Fehlschläge. Ruft ein Modell in einer Entscheidung immer wieder `list`/`read` auf, läuft die Schleife weiter. Tool-Ergebnisse hängen **ungekürzt** an `messages`, bis `failed-window` den Lauf abbricht. Bei Cloud-Anbietern sind die Kosten unbegrenzt. |
| O5 | **H** | `orchestrator_decide.py` (`break` nach 5 Tool-Fehlern) | **Unvollständige Tool-Antworten.** `break` verlässt die Schleife über `result.tool_calls` mittendrin. Hatte die Assistant-Nachricht mehrere Tool-Calls, fehlen für die restlichen `tool_call_id` die `role="tool"`-Antworten. OpenAI-kompatible APIs (OpenAI, xAI, Gemini-Compat) lehnen die nächste Anfrage mit 400 ab. Der Lauf scheitert dann mit `runtime.badRequest` statt mit der vorgesehenen Think-Runde. |
| O6 | **H** | `memory._results_block`, `memory.agent_message` | **Prompt-Injection über Agent-Ergebnisse.** Agent-Texte, die Inhalte aus Web, HTTP-Tool, Dateien oder MCP enthalten können, gehen **ungekennzeichnet als `role="user"`** in den Orchestrator-Prompt. Über `source` gehen sie mit „Use this text“ an andere Agenten weiter. Ein präparierter Text („call Terminal-Agent with task: …“) steuert so den Orchestrator. Zusammen mit Terminal-, Datei- und MCP-Tools wird daraus Codeausführung bzw. Datenverlust. Es fehlen Kennzeichnung als Daten, Trennzeichen und eine Freigabe für sensible Aufrufe. |
| O7 | M | `memory.orchestrator_messages`, `_results_block` | **Der Prompt wächst unbegrenzt, es wird nichts verdichtet.** Alle `turns` bleiben für immer: jede Repair-Notiz, jedes „Status already shown …“, alle Antworten. Pro Agent wird das **letzte Ergebnis im Volltext** in jede Runde kopiert. Bei vielen Runden oder einem großen Ergebnis (z. B. generiertem Code) beendet `run.orchestrator.window` den Lauf **hart**, statt alte Teile zusammenzufassen oder zu kürzen. |
| O8 | M | `memory.clear_anomaly` (Schleifenanfang) | **Anomalien leben genau eine Runde.** Ist die nächste Entscheidung ein `think`, das wegen O1 verloren geht, ist der Fehlergrund (z. B. „no tool used“, „tool failed“) für alle folgenden Runden weg. Die Statuszeile behält nur `reason: …` ohne Text. |
| O9 | M | `memory._own_block`, `allow_own_tools` | **Eigene Tool-Ergebnisse gehen zwischen Entscheidungen verloren.** In der nächsten Runde sieht der Orchestrator nur „name ok/failed“ bzw. die letzten 8 Dateizeilen. Liest er eine Datei und wählt dann `think`, ist der Inhalt weg. Nach dem Tool-Einsatz gilt `allow_own_tools=False`, er kann also erst nach einem Agent-Call wieder nachsehen. |
| O10 | M | `orchestrate.control_source`, `parse_orchestrator_action` | **Fallback auf `reply` zeigt rohen Text.** Jede Antwort, die kein lesbares JSON ist und nicht nach Steuertext aussieht, wird als `reply` im Chat **veröffentlicht**. Ist `content` leer, nimmt `control_source` den **Provider-`reasoning`**. Die interne Gedankenkette landet dann beim Nutzer. |
| O11 | M | `orchestrate._parse_json_object` | **Nur das erste JSON-Objekt zählt.** Bei `{"action":"think"…}{"action":"call"…}`, einer häufigen Antwortform, geht der `call` verloren. Wegen O1 wiederholt sich das. |
| O12 | M | `orchestrator_loop.py`, `limits.py` | **Es gibt kein Gesamtbudget.** `steps` zählt nur Calls mit Ergebnis `ran`. Thinks werden bei jedem Call zurückgesetzt, `ask`-Runden und die Tool-Schleife (O4) sind unbegrenzt. Theoretisch sind 24 × (64 Thinks + 2 Repairs + n Tool-Runden) LLM-Aufrufe möglich, ohne Token- oder Kostenlimit und ohne Gesamtdauer. |
| O13 | M | `orchestrator_loop.py` (`finish`/`reply` bei Takeover) | **Takeover ist zu streng.** Jedes `reply` oder `finish` während eines Takeovers lässt den Lauf sofort scheitern, auch wenn das Modell den Nutzer nur informieren oder sauber beenden will. Zwei Versuche, den gesperrten Agenten aufzurufen, beenden den Lauf ebenfalls. |
| O14 | M | `orchestrator_decide.py` (`except` beim LLM-Aufruf) | **Ein Fehler des Orchestrator-LLM beendet den Lauf.** Nach einem Retry bei timeout/unreachable/upstream wird `raise` ausgelöst, und `run_harness` beendet den ganzen Lauf. Es gibt keinen Fallback und kein Pausieren mit Rückfrage, obwohl das Gedächtnis erhalten bleibt. Bei Agent-Fehlern ist das sauber gelöst: Anomalie, dann Weiterarbeit. |
| O15 | M | `_store_memory`, `memory.to_dict` | **Die Persistenz wird quadratisch teurer.** Nach **jeder** Entscheidung wird das komplette Gedächtnis als JSON in `runs.memory` geschrieben: alle Records mit allen Tool-Events (je bis 8000 Zeichen), `own_tools`, `windows` (wächst um einen Eintrag pro LLM-Aufruf) und `rejected`. Lange Läufe werden langsamer, und die History-DB wächst. Schreibfehler werden still verschluckt. |
| O16 | N | `orchestrate.match_agent` | **Unscharfe Agent-Zuordnung.** Sie arbeitet über `_ROLE_NOISE` und Präfixe (`_alias_hit`). Bei ähnlichen Namen kann ein falscher oder gar kein Agent getroffen werden. Das Ergebnis ist zwar auf genau einen Treffer beschränkt, aber der aufgelöste Name wird nicht geloggt. |
| O17 | N | `dispatch._orchestrator_call` | **Stille Annahmen beim Agent-Call.** Ein leerer `task` wird still durch die letzte Nutzernachricht ersetzt. Ein `None` aus `_agent_turn` ohne Stop (z. B. nach zu vielen Tool-Fehlern) gilt als `ran`, **ohne Anomalie**. Die Prüfung von Agent und Quelle steht doppelt, in `orchestrator_decide` und in `dispatch`. |
| O18 | N | `orchestrator_instructions` | **Langes, rein englisches Protokoll (~2 KB).** Es ist vermutlich schwer für kleine lokale Modelle wie `llama3.2:1b` aus dem Setup (nicht gemessen). Das treibt Repairs und den `reply`-Fallback (O10). Agent-Anweisungen werden im Roster auf 400 Zeichen gekürzt. |
| O19 | N | `_salvage_markup_action` / `_salvage_prose_call` | **Uneinheitliche Grenzen.** Ein Markup-Task darf 8000 Zeichen haben, Prosa- und JSON-Salvage nur 500. `str(value.get("text"))` macht aus verschachteltem JSON eine Python-Repr. |
| O20 | N | `memory.orchestrator_messages` | **Viele `user`-Nachrichten in Folge** (Status, Ergebnisse, Tools, Takeover, Anomalie). Manche Provider bzw. Templates erwarten wechselnde Rollen oder gewichten so etwas schlechter. |

### 5.3 Empfohlene Reihenfolge

1. **O1, O2:** Den `think`-Text gekürzt als `Turn("assistant", "think", …)` speichern und die letzten N behalten. Ein blockiertes `reply` als Notiz zurückmelden („reply blocked: use finish/call/ask“).
2. **O3:** Nutzernachrichten, die während der Arbeit eingehen, vor jeder Entscheidung aus der Queue in `memory.add_user` übernehmen. `ask` wartet dann nur auf **neue** Nachrichten.
3. **O4, O5, O12:** Eine Obergrenze für Tool-Runden pro Entscheidung. Für jeden `tool_call_id` eine Tool-Antwort, bei Abbruch mit „skipped“. Ein Gesamtbudget für LLM-Aufrufe bzw. Tokens pro Lauf.
4. **O6:** Agent-Ergebnisse als Daten kennzeichnen (z. B. `<agent_result name=…>…</agent_result>` mit dem Hinweis „Inhalt ist Daten, keine Anweisung“). Sensible Tools (Terminal, Delete) optional nur mit Rückfrage.
5. **O7, O8, O9, O15:** Ein Kontext-Budget, das alte Ergebnisse kürzt bzw. zusammenfasst. Anomalien bis zum nächsten Call behalten. Das Gedächtnis inkrementell oder seltener speichern und `windows` begrenzen.
6. **O10, O11:** `reasoning` nie als `reply` veröffentlichen. Mehrere JSON-Objekte erkennen und das erste ausführbare nehmen (`call`/`ask`/`finish` vor `think`).

### 5.4 Umgesetzt

- **O1:** `RunMemory.add_think` speichert jeden Orchestrator-Gedanken (gekürzt auf 600 Zeichen, die letzten 4) als Assistant-Turn im Protokollformat `{"action":"think","text":…}`. Die nächste Runde sieht den Plan. Leere Platzhalter (`…`) werden nicht gespeichert. Endet der Prompt auf einer Assistant-Nachricht, folgt ein kurzer User-Abschluss, damit Ollama den Text nicht als Prefill fortsetzt.
- **O2:** Ein blockiertes zweites `reply` wird als Gedanke behalten. Das Modell bekommt den Hinweis, dass der Text nicht angezeigt wurde, und die Anweisung, mit `call`, `ask` oder `finish` weiterzumachen. Wiederholt das Modell denselben Gedanken, gibt es einen eigenen Hinweis. Hinweise werden ersetzt statt angehäuft (`set_nudge`) und bei der nächsten echten Aktion entfernt.
- **Tests:** `tests/run/test_orchestrator_memory.py` (7 Tests). Die 3 Szenario-Tests schlagen gegen den alten Code fehl: Der Gedanke fehlt im Prompt, und beide Schleifen enden mit `failed`. Gesamt: 776/776 grün.
- **O3:** `_drain_user` übernimmt Chat-Nachrichten, die während der Arbeit eingehen, vor jeder Entscheidung ins Gedächtnis (Log `run.chat.user` mit `midRun`). Nach neuer Eingabe ist ein `reply` wieder erlaubt. Liegen beim `ask` schon Nachrichten vor, wird die Frage nicht gestellt; das Modell bekommt die Nachricht plus einen Hinweis mit der ungestellten Frage. Bei `finish` mit ungelesener Nachricht endet der Lauf nicht, sondern die Nachricht wird zuerst behandelt.
- **Tests O3:** 3 neue Tests in `tests/run/test_orchestrator_memory.py`, alle drei schlagen gegen den Code ohne O3 fehl. `test_orchestrator_asks_calls_and_finishes` legte die Antwort vorab in die Queue (genau das alte Fehlverhalten) und antwortet jetzt erst, wenn die Frage angezeigt wird. Gesamt: 779/779 grün.
- **Hinweis Testumgebung:** Die Harness-Tests fragen bei Ollama-Modellen echt `/api/show` ab. Läuft Ollama nicht, braucht unter Windows jeder abgewiesene Connect ca. 2 s, und viele Harness-Tests laufen in ihr 5-s-Timeout. Das widerspricht „CI braucht kein Ollama“ aus der README und sollte in `tests/run/conftest.py` gemockt werden.
- **O4 (umgesetzt, Entscheidungen vom 2026-11-07):**
  - **Schutzgrenze pro Schritt** (`run/limits.py`): Orchestrator `MAX_ORCHESTRATOR_TOOL_CALLS = 10` pro Entscheidung, Agent `MAX_AGENT_TOOL_CALLS = 50` pro Auftrag. Gezählt werden einzelne Aufrufe. Ist die Grenze erreicht, bekommt das Modell keine Tools mehr und einen Hinweis; der Lauf scheitert nicht. Nicht mehr ausgeführte Calls derselben Antwort bekommen eine Tool-Antwort `tool.stepLimit`. Beim Agenten steht in der Statuszeile an den Orchestrator „tool limit reached … may be incomplete“ (`AgentRecord.capped`). Logs: `run.orchestrator.toolCap`, `run.agent.toolCap`.
  - **Limit pro Tool-Knoten und Lauf** (`data.maxCalls`, ganze Zahl ≥ 1, fehlt = unbegrenzt = Standard). Es gilt für Tool- und MCP-Knoten und zählt alle Aufrufe, egal ob vom Orchestrator oder einem Agenten. Bei einem MCP-Knoten zählen alle Tools des Servers zusammen. Ist es erschöpft, wird der Aufruf nicht ausgeführt (`tool.limitReached`, Log `run.tool.limitReached` am Knoten), und das Tool wird danach nicht mehr angeboten. Verweigerte Aufrufe zählen **nicht** als Tool-Fehler. Zähler: `RunController.tool_calls`/`tool_refused`, Durchsetzung in `turn_runtime._dispatch_tool`.
  - **UI:** Im Inspector gibt es für Tool- und MCP-Knoten das Feld „Max. Aufrufe pro Lauf“ mit der Checkbox „Unbegrenzt“ (Standard an). Beim Abwählen ist der Startwert 10. Die Validierung (`graph.tool.maxCalls` bzw. `network.validation.toolMaxCalls`) läuft in Backend und Frontend; Texte in de, en und es.
  - **Nebenbei:** `list_logs` sortierte Logs mit gleichem Zeitstempel nach UUID, also zufällig. Jetzt nach `rowid`. Dadurch war `test_linear_truncated_tool_json…` instabil.
  - **Tests:** `tests/run/test_tool_limits.py` (6 Tests). `test_orchestrator_stops_after_two_failed_think_rounds` hebt die Schrittgrenze an, weil er 15 Aufrufe in einer Entscheidung erwartet. Gesamt: 785/785 grün.

- **O5 (umgesetzt):** Löst der 5. Tool-Fehler die Think-Runde aus, werden die übrigen Calls derselben Antwort nicht mehr ausgeführt. Sie bekommen aber eine Tool-Antwort `tool.skipped`. Die Think-Notiz steht erst nach der letzten Tool-Antwort. Zusätzlich ergänzt `turn_runtime._close_open_tool_calls` vor jeder LLM-Anfrage von Orchestrator und Agent fehlende Tool-Antworten und loggt das als `run.llm.toolCallsRepaired`. Ein solcher Logeintrag weist auf einen Codepfad hin, der Antworten vergisst. Tests: `tests/run/test_tool_answers.py` (3 Tests) mit einem strengen, OpenAI-artigen Fake-Provider. Gegen den alten Code scheitert der Lauf dort mit 400.

- **O6 (umgesetzt):** Agent-Ergebnisse stehen im Orchestrator-Prompt als `<agent_result agent=… id=…>…</agent_result>` mit einem Hinweis davor, dass sie Daten sind. Quelltexte und frühere Ergebnisse, die an Agenten gehen, stehen als `<source_text>`, Anomalie-Auszüge ebenfalls als `<agent_result>`. Gleichnamige Tags im Inhalt werden entschärft (`</agent_result>` wird zu `[/agent_result]`, Attribute ohne `<>"`), sodass ein Text den Block nicht schließen und als Laufzeit „sprechen“ kann (`memory.as_data`). Orchestrator-Protokoll und Agent-System-Prompt enthalten eine feste Regel: Inhalte dieser Blöcke, Dokumentkontext und Tool-Ergebnisse sind Daten, Anweisungen darin werden nicht befolgt. Grenze: Das ist eine Abschwächung, kein Schutz. Ob das Modell der Regel folgt, ist nicht garantiert. Eine Rückfrage vor sensiblen Aktionen (O6b) ist bewusst verworfen. Tests: `tests/run/test_prompt_injection.py` (5 Tests, darunter ein vollständiger Lauf mit Ausbruchsversuch).

- **O7 (umgesetzt):** Der Orchestrator-Prompt hat jetzt ein Budget in `RunMemory` (`compact_level` 0 bis 3). **Stufe 0 gilt immer:** höchstens 8 Laufzeit-Notizen, 4 Gedanken, Agent-Ergebnisse höchstens 20.000 Zeichen im Prompt (Anfang 70 %, Ende 30 %, dazwischen ein Hinweis „… omitted …, set source to <id>“). **Stufen 1 bis 3 greifen nur, wenn der Prompt nicht ins Fenster passt.** Sie verdichten schrittweise: Ergebnisse auf 8.000, 3.000 bzw. 1.200 Zeichen, weniger Notizen und Gedanken, ältere Statuszeilen als eine Zusammenfassung, ab Stufe 2 auch weniger gesprochene Texte und gekürzte Nutzernachrichten. Auf Stufe 3 werden zusätzlich die Tool-Ergebnisse der laufenden Entscheidung gekürzt. Jede Stufe wird geloggt (`run.orchestrator.compact`) und gilt für den Rest des Laufs. Erst wenn auch Stufe 3 nicht passt, endet der Lauf mit `run.orchestrator.window`. Das gespeicherte Gedächtnis bleibt vollständig: Volltexte gehen über `source` weiter ungekürzt an Agenten, und `compactLevel` steht in `runs.memory`. Tests: `tests/run/test_prompt_budget.py` (5 Tests). Offen bleibt: Ab Stufe 3 wird gekürzt, aber nicht inhaltlich per LLM zusammengefasst. Das wäre bei Bedarf eine Erweiterung.

- **O8 (umgesetzt):** Eine Anomalie wird nicht mehr nach jeder Entscheidung gelöscht. Sie bleibt über `think`, `reply` und `ask` hinweg im Prompt und endet erst, wenn der nächste Agent-Aufruf beginnt (`RunMemory.begin_call`). Der Protokolltext im Orchestrator-Prompt sagt jetzt „It stays until your next call.“ Die aktuelle Anomalie steht als `anomaly` in `runs.memory`. Test: `test_anomaly_survives_think_and_ends_with_next_call`; gegen das alte Verhalten fehlt die Anomalie nach dem `think`.

- **O9–O20 (Paket, umgesetzt bis auf O18):**
  - **O9:** Die letzten 3 eigenen Tool-Ergebnisse des Orchestrators bleiben im Prompt, je bis 1.500 Zeichen und als `<tool_result name=…>`-Daten (`_own_results_block`). Der Prompttext ist angepasst („your last three tool results, shortened“).
  - **O10:** Kommt eine Entscheidung nur aus dem Provider-`reasoning` (sichtbarer Inhalt leer) und ist keine Steueraktion lesbar, wird sie ein interner Gedanke und nicht im Chat veröffentlicht (`run.orchestrator.privateReasoning`). Sichtbarer Fließtext bleibt ein `reply`.
  - **O11:** Mehrere JSON-Objekte in einer Antwort werden alle gelesen. Es gewinnt das erste ausführbare (`call`/`ask`/`finish`), dann ein `reply`, sonst der erste `think` (höchstens 40 Objekte).
  - **O12:** Budget pro Lauf `MAX_RUN_LLM_CALLS = 400` Modellaufrufe (Orchestrator und Agenten zusammen). Danach endet der Lauf mit `run.llmBudget`, Fehlerklasse `budget`.
  - **O13:** Ein `reply` während eines Takeovers erreicht den Nutzer, statt den Lauf zu beenden. Das erste `finish` während eines Takeovers bekommt einen Hinweis, erst das zweite beendet den Lauf als fehlgeschlagen. Gesperrte Agent-Aufrufe sind bis `MAX_TAKEOVER_REJECTS = 3` erlaubt (vorher 2).
  - **O14:** Bleibt das Orchestrator-Modell nach dem Retry unerreichbar (`timeout`/`unreachable`/`upstream`), pausiert der Lauf: eine Chat-Meldung (`monitoring.chat.llmRetry`), Warten auf eine Nachricht, dann ein neuer Versuch mit intaktem Gedächtnis. Höchstens `MAX_LLM_PAUSES = 3` Pausen. Andere Fehler (z. B. `unauthorized`) beenden den Lauf weiterhin.
  - **O15:** In `runs.memory` werden Listen (`windows`, `ownTools`, `rejected`, Tool-Events) auf 50 Einträge und Ergebnisse auf 2.000 Zeichen begrenzt. Ist der Stand unverändert, wird nicht neu geschrieben (Fingerprint). Schreibfehler werden geloggt statt verschluckt. Das Gedächtnis während des Laufs bleibt vollständig.
  - **O16:** `run.orchestrator.action` loggt neben der aufgelösten Agent-ID auch den geschriebenen Namen (`requested`).
  - **O17:** Ein leerer Auftrag wird als `run.orchestrator.emptyTask` geloggt. Gibt ein Agent-Zug ohne Stop auf, entsteht eine Anomalie („agent stopped“).
  - **O19:** Der Markup-Salvage-Task ist auf 2.000 Zeichen begrenzt. Verschachteltes JSON in Feldern bleibt JSON statt Python-Repr.
  - **O20:** Aufeinanderfolgende User-Nachrichten im Orchestrator-Prompt werden zu einer zusammengefasst.
  - **Nebenbei:** Der Prompt versprach „call tools as often as you need“. Das ist korrigiert auf „up to ten tools per decision“ (passend zu O4).
  - **O18 (zurückgestellt):** Das Protokoll ist weiter englisch und lang. Eine Kürzung lohnt sich erst nach einer Messung mit kleinen Modellen. Ohne Messdaten wäre das Risiko für funktionierende Netze höher als der Nutzen.
  - **UI:** neue Log- und Chat-Texte in de, en und es (`runLog.run.*`, `monitoring.chat.llmRetry`).
  - **Tests:** `tests/run/test_orchestrator_package.py` (11 Tests). Angepasst wurden 4 bestehende Tests, die das alte Verhalten festschrieben (O9: Ergebnisse verborgen, O13: `reply` im Takeover verborgen, Prompttexte). Gesamt: 810/810.

---

## 6. Offene Aufgaben (Backlog)

Stand 2026-11-07. Erledigt sind: S1, S2, S3, S5, S12, B1, B2, B3, B4, B6, B9, B11, B12, B15, B22, F1, F2, F3, F6, F8, F9, F10, O1, O2, O3, O4, O5, O6, O7–O17, O19, O20, die Lint-Fehler und das Aufräumen im Installer. Einzelheiten stehen in den Abschnitten 2 und 5.

### 6.1 Entscheidungen nötig
- [ ] **B5:** „Chat abbrechen“ wirkt nicht. Soll der Lauf nach dem Abbruch auf die nächste Nachricht warten, statt zu enden?
- [ ] **S6:** Soll der Dateizugriff `allowWrite`/`allowDelete` standardmäßig auf `false` setzen? Das ändert das Verhalten bestehender Netze.

### 6.2 Orchestrator
- [x] **O5:** erledigt (siehe 5.4).
- [x] **O6:** Kennzeichnung als Daten erledigt (siehe 5.4).
- ~~**O6b:** Rückfrage vor sensiblen Tool-Aufrufen~~ - **verworfen** (Entscheidung 2026-11-07): Rückfragen würden den Workflow stören. Schutz bleibt bei Kennzeichnung (O6), Tool-Konfiguration (Allowlist, Wurzelordner, `maxCalls`) und Schutzgrenzen.
- [x] **O7:** erledigt (siehe 5.4).
- [x] **O8:** erledigt (siehe 5.4).
- [x] **O9:** erledigt (siehe 5.4).
- [x] **O10:** erledigt (siehe 5.4).
- [x] **O11:** erledigt (siehe 5.4).
- [x] **O12:** erledigt (siehe 5.4).
- [x] **O13:** erledigt (siehe 5.4).
- [x] **O14:** erledigt (siehe 5.4).
- [x] **O15:** erledigt (siehe 5.4).
- [x] **O16, O17, O19, O20:** erledigt (siehe 5.4).
- [ ] **O18:** zurückgestellt. Prompt erst nach einer Messung mit kleinen Modellen kürzen bzw. übersetzen.

### 6.3 Sicherheit
- [ ] **S4:** SSRF und DNS-Rebinding im HTTP-Tool (aufgelöste IP an den Connect binden, privat nur per Opt-in).
- [ ] **S7:** Zip-Entpacken überschreibt Dateien ohne Rückfrage.
- [ ] **S8:** MCP-Pfadbegrenzung für `paths` und `repo_path`.
- [ ] **S9:** MCP-Rezepte ohne Versionspin, GitHub-Binary nach dem Download nicht erneut prüfen.
- [ ] **S10:** Knoten-`baseUrl` aus importierten Netzen prüfen bzw. anzeigen.
- [ ] **S11:** Bilder in `MarkdownView` nicht automatisch laden.
- [ ] **S13:** `strip_secrets` mit `common/secrets` zusammenführen und Secrets schon beim Speichern filtern.
- [ ] **S14:** MCP-Prozessen nicht die komplette Umgebung (`os.environ`) mitgeben.
- [ ] **S15:** URL-Schema der Hilfe-Quellen prüfen und `dangerouslySetInnerHTML` ersetzen.

### 6.4 Backend
- [ ] **B7, B8:** Datenordner-Wechsel: Locks um den Wechsel der Connections, Kopieren ohne Überschreiben, Rollback bei `OSError`.
- [ ] **B10:** Embedding-Runner: kein Kill bei `refs>0`, kein langer Lock, Shutdown-Hook.
- [ ] **B13, B14, B16:** Wissensindex: Größen- und Anzahlgrenzen, Abbruch über `stop_event`, Provider in den Cache-Schlüssel, gesperrte Datei überspringen.
- [ ] **B17:** `topK=0` bzw. `scoreThreshold=0` zulassen.
- [ ] **B18:** Mehrere Tool-Knoten derselben Art an einem Agenten: Es gewinnt immer der erste. Dadurch greift `maxCalls` eines zweiten gleichartigen Knotens nie.
- [ ] **B19–B21:** SSE-Abonnenten-Race, SSE belegt Threadpool, Snapshot pro Token, Log-Größe.
- [ ] **B23–B26:** Settings-PATCH ohne Lock, Hilfe-Abbruch global, doppelter MCP-Start, `wait_health` mit `::1`, LIKE-Escape, `delete_networks` nicht atomar.

### 6.5 Frontend
- [ ] **F4:** Ctrl+Z in Textfeldern soll die native Undo-Funktion nutzen (Undo-Einträge im Store bündeln).
- [ ] **F5:** Eingaben während des Speicherns gehen verloren, Undo-Historie wird nach dem ersten Speichern geleert.
- [ ] **F7:** Polling löst alle 1,5 s `hydrateLastRun` aus.
- [ ] **F11:** Chat-Nachrichten eines neuen Laufs maskieren.
- [ ] **F12:** `serviceStatus` hat zwei Quellen.
- [ ] **F13:** Watchdog wird durch eigene Events „belebt“.
- [ ] **F14:** 22 Lint-Warnungen `exhaustive-deps` einzeln prüfen.
- [ ] **Performance (2.4):** Neuaufbau im Canvas, `isDirty`, Undo pro Tastendruck, Log ohne Virtualisierung, Code-Splitting.

### 6.6 Tests, Doku, Wartung
- [ ] Ollama in `tests/run/conftest.py` mocken. Ohne laufendes Ollama scheitern sonst viele Harness-Tests am 5-s-Timeout.
- [ ] Testlücken aus 2.7 schließen (Stop/Start-Race, Abbruch während der Indexierung, Zip-Überschreiben, MCP-Pfade). Es gibt noch keine Frontend-Tests.
- [ ] README angleichen (2.6): Endpunkte, Hilfesprachen, Tools Terminal/Zip, Env-Variablen, `prompts/`.
- [ ] Toten Code und Duplikate aufräumen (2.5), z. B. dreifache Secret-Masken, doppelter RAG/Cosinus, `include_all` schluckt `ImportError`.

---

## 7. Laufanalyse „Coder Architekt“ (2026-11-07)

Lauf `0fe6a4cd…` lief mit dem Build vom 2026-11-07 (inkl. O1–O20):
- **Laufzeit:** 13:07 bis 18:25 Uhr, also 5 h 17 min.
- **Ergebnis:** `succeeded`, 32 Dateien im Projektordner `hello-world-10-languages`.
- **Modellaufrufe:** 377, davon Orchestrator „Chef Coder“ (Qwen 35B MoE) 185, Senior (LFM2.5 24B) 102, Junior (Qwen 14B) 90.
- **Tool-Aufrufe:** 260, davon Orchestrator 82, Senior 96, Junior 82; 20 fehlgeschlagen.

**Was gut funktioniert hat:**
- Die O4-Schrittgrenze hat den Orchestrator 8-mal gestoppt.
- Der Retry nach dem Verbindungsabbruch hat geklappt.
- Es mussten keine fehlenden Tool-Antworten ergänzt werden (O5).
- Es war keine Verdichtung nötig (O7, Prompt höchstens ca. 17.700 Tokens).

| # | Grad | Befund |
|---|---|---|
| R1 | **H** | **Ausufernde Generierung ohne Obergrenze: 72 % der Laufzeit.** Zwei einzelne Modellaufrufe dauerten 64 min (Junior: 123.102 Ausgabe-Tokens reines Reasoning, `finish_reason=length`, kein sichtbares Ergebnis) und 165 min (Senior, danach `WinError 10053` „Verbindung abgebrochen“, gespeichert als `runtime.timeout`). Die LLM-Knoten haben kein `maxTokens`, Ollama generiert also bis zum Kontextende (131k bzw. 88k). Der Idle-Watchdog greift nicht, weil laufend Tokens kommen. Danach liefen beide Agenten problemlos weiter (Retry 7 s). |
| R2 | **H** | **Der Orchestrator macht die Arbeit der Agenten selbst.** Noch vor dem ersten Agent-Aufruf versuchte er, `package.json` und Ordner selbst zu schreiben. Insgesamt kamen 82 Datei-Tool-Aufrufe (Lesen, Schreiben, Editieren) von ihm. Er verbrauchte 49 % aller Modellaufrufe und stieß 8-mal an die 10er-Grenze. Der Prompt sagt „Use tools to check files … Do not use tools instead of calling an agent“, durchgesetzt wird das nicht. Ursache: Der eine Dateizugriffs-Knoten hängt an allen vier Knoten und erlaubt allen alle Aktionen. |
| R3 | M | **Tool-Markup landet im Chat und erzeugt leere Gedanken.** 4 von 7 Orchestrator-Antworten im Chat enthalten rohes `<tool_call><function=file_access>…`. 19 von 82 Gedanken bestehen nur aus Tool-Markup. Grund: Nach eigener Tool-Nutzung bzw. der Grenze bekommt der Orchestrator keine Tools angeboten, schreibt den Aufruf aber als Text. `salvage_tool_calls` greift nur bei angebotenen Tools, also wird der Text veröffentlicht bzw. als `think` gezählt. |
| R4 | M | **Budget fast erschöpft:** 377 von 400 Modellaufrufen. Ein etwas längerer Lauf wäre nach über 5 Stunden mit `run.llmBudget` gescheitert. Mit R1/R2 behoben wären es deutlich weniger Aufrufe. Alternativ das Budget pro Netz einstellbar machen. |
| R5 | N | **Pfadfehler:** 11-mal `tools.fileAccess.notFound`, weil Modelle `src/…` ohne Projektordner schreiben, die Wurzel aber der übergeordnete Ordner ist. Das ist eine Netz-Konfiguration (Wurzel auf den Projektordner setzen oder im Prompt nennen), kein Code-Fehler. |
| R6 | N | **Fortschrittsmeldungen im Chat listen auch Lesezugriffe** („Senior is done. Files: . list, … read“). Sie sollten nur geänderte Dateien nennen (`dispatch._publish_progress`). |
| R7 | N | **`runs.models` ohne Orchestrator-Modell:** Die Historie zeigt nur 2 von 3 Modellen, weil `controller.start` nur Agent-Modelle sammelt. |
| R8 | N | **Irreführende Einordnung:** Ein fehlgeschlagener Aufruf wird ohne Tokens gespeichert. Ein Verbindungsabbruch nach 165 min erscheint als `runtime.timeout`. |

### 7.1 Backlog aus der Laufanalyse
- [x] **R1:** umgesetzt. Ist `maxTokens` leer, setzt die Laufzeit für Ollama automatisch `num_predict` = Kontext/4 (4.096 bis 16.384), höchstens aber den Platz, den der Prompt im Fenster lässt (mind. 1.024). Die vom Nutzer gesetzte Kontextlänge bleibt unverändert, und die Fensterwahl sieht die automatische Grenze nicht. Ein eigenes `maxTokens` gilt immer, Cloud-Anbieter behalten ihren Standard. Zusätzlich eine Zeitgrenze von 20 min pro Aufruf (`runtime.generationLimit`): Beim Agenten wird daraus eine Anomalie ohne Retry, der Orchestrator bekommt einen kurzen zweiten Versuch. Wird eine Antwort abgeschnitten, kommt nur noch ein Auszug von 2.000 Zeichen zurück in den Verlauf (vorher das volle Reasoning), dazu der Hinweis „act now“. Der Watchdog-Abbruch meldet „no progress for 180 s after N min“ (Teil von R8). `run.llm.start` loggt `maxTokens`/`maxTokensAuto`. Im Inspector zeigt das leere Feld „Max. Tokens“ als Platzhalter, was gilt (z. B. „leer = automatisch 16.384“). Tests: `tests/run/test_output_limits.py` (8, darunter ein echter Stream-Server).
- [x] **R2:** erledigt durch den Merge von `fix/backend_testing`: Der Orchestrator bekommt Tools nur nach einem Agent-Fehler oder im Takeover (siehe Abschnitt 8).
- [ ] **R3:** Tool-Markup in Antworten erkennen, nicht veröffentlichen und dem Modell zurückmelden, dass in diesem Schritt keine Tools verfügbar sind.
- [ ] **R4:** Budget pro Netz einstellbar machen (Standard 400), nach R1/R2 neu bewerten.
- [ ] **R6:** Fortschrittsmeldung nur mit geänderten Dateien.
- [ ] **R7:** Orchestrator-Modell in `runs.models` aufnehmen.
- [ ] **R8:** Verbindungsabbruch (`ReadError`) als `runtime.unreachable` einordnen und Tokens auch bei Fehlschlag speichern.

---

## 8. Merge `fix/backend_testing` → `fix/orchestrator_v2` (2026-11-10)

**Übernommen wie geliefert:**
- `capabilities.py`: Tool-Inventar im Prompt von Orchestrator und Agenten.
- Kontextverdichtung für Agenten (`compact.py`).
- Orchestrator-Parser `_utterance`.
- Schärfere Prompttexte.
- Excel-MCP legt eine fehlende Arbeitsmappe an.
- Frontend: Chat kopieren, Tag-Suche, Scroll-Fix.

**Konflikte aufgelöst:**
- `dispatch.py`: `generationLimit` und Freigabe der Tools.
- `orchestrate.py`: deren Tool-Text plus „up to ten tools“; die Auswertung mehrerer JSON-Objekte (O11) mit `_field` (O19) und `_utterance` kombiniert.
- Tests: beide Seiten zusammengeführt.

**Angepasst:**
- **Der Orchestrator bekommt Tools nur nach einem Agent-Fehler** (aus dem Zweig). Damit ist **R2** erledigt. Der Abbruchpfad „agent stopped“ (O17) gibt Tools jetzt ebenfalls frei.
- **Zusammenfassungs-Aufruf in `compact.py`:** zählt zum Laufbudget (O12), hat die 20-min-Grenze (R1), steht in der Historie (`insert_call`) und im Log (`run.llm.start`, `waitReason: compact`).
- **Abgeschnittene Antworten:**
  - Der Entwurf wird verworfen (Ansatz aus dem Zweig). Mein R1-Kürzen war tot und ist entfernt.
  - Der Hinweis ist neutral formuliert („output or context limit … act now“).
  - Zwei Abbrüche in Folge ergeben die Anomalie `output limit` (`run.agent.outputLimit`) statt fälschlich „prompt does not fit“.
- **Excel:**
  - Eine nicht leere Datei, die keine Arbeitsmappe ist, wird vor dem Ersetzen als `*.xlsx.bak` gesichert.
  - Nur absolute, also bereits begrenzte Pfade werden angefasst.
  - Fehler beim Anlegen werden geloggt und nicht weitergeworfen.

**Neu: Prüfung reiner Textantworten (Variante C, Entscheidung 2026-11-10):**
- **Textantworten erlaubt:** Agenten mit Tools dürfen mit reinem Text antworten („Tools are optional“, die Anomalie „no tool used“ entfällt). Die Statuszeile an den Orchestrator sagt dann „text only … Check the text against its task“ (`AgentRecord.text_only`, Log `run.agent.textOnly`).
- **Wiederholung:** Passt der Text nicht zur Aufgabe, ruft der Orchestrator denselben Agenten mit `"retry": true` erneut auf. Nur so ein Aufruf zählt. Neue Aufgaben an denselben Agenten (z. B. einen planenden Architekten) zählen nicht. Ein `retry` ohne vorherige reine Textantwort wird ignoriert (`run.orchestrator.retryIgnored`).
- **Übernahme:** Liefern **2** Wiederholungen erneut nur Text (`MAX_TEXT_RETRIES`, Log `run.orchestrator.textRetry`), übernimmt der Orchestrator. Takeover-Art `tools`: Er bekommt seine Tools, der Agent ist gesperrt, und ein erfolgreicher eigener Tool-Aufruf beendet die Übernahme. Liefert eine Wiederholung Tool-Nutzung, startet die Zählung neu.
- **Übernahme nicht möglich** (Orchestrator ohne passende Tools, gilt für Datei- und Tool-Übernahmen): Statt sofort abzubrechen, gibt es eine Anomalie mit dem Hinweis „call another agent, ask the user, or finish and say what is missing“ (`run.orchestrator.takeoverUnavailable`). Höchstens **3**-mal pro Lauf (`MAX_TAKEOVER_UNAVAILABLE`), beim 4. Mal endet der Lauf mit `run.orchestrator.takeoverNoTool`.

**Tests:**
- Neu: `tests/run/test_text_review.py` (10 Tests).
- Angepasst wurden Tests, die das alte Verhalten festschrieben: Orchestrator-Tools ab Start, Hinweistext bei abgeschnittenem JSON, Fehlergrund nach zwei Abbrüchen.
- Gesamt: 840/840 grün, Typecheck sauber, ESLint 0 Fehler.

**Backlog:** R2 erledigt. R5 ist durch `capabilities.py` (Wurzel und Pfadregeln im Prompt) teilweise abgedeckt; der Pfad-Hinweis bei `notFound` bleibt offen. R3, R4, R6, R7 und der Token-Teil von R8 bleiben offen.
