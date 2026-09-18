# Agentus Network — Python-Prozess

Ein Prozess: HTTP-API, Persistenz, Hilfe, MCP-Supervisor, Netz-Laufzeit, optional WebView2. Frontend-Adapter sprechen nur `http://127.0.0.1:8765/api`. JSON camelCase, Fehler `{ messageKey, message? }`.

Dieses Paket ist der Rahmen (`python_backend.md`). Fachmodule hängen Code in `app/` ein; Shared-Hilfen liegen nur in `app/common/`.

## Stack

- Python 3.12+
- FastAPI + Uvicorn (ASGI)
- Pydantic v2
- ein `httpx`-Client (`app.common.http.client`)
- vier SQLite-Dateien (`settings`, `help`, `workspace`, `history`), Secrets nur im Tresor
- pytest

Provider: `ollama` | `xai` | `openai_compat` — kein `lmstudio`.

## Layout

```
backend/
  app/
    main.py          # python -m app.main
    common/          # types, secrets, http — keine Fachlogik
    http/            # Factory, Fehler, Router (HTTP-Prompt)
    db/              # Stores (Persistenz-Prompt)
    settings/
    runtime/
    tools/
    mcp/
    help/
    run/
    host/
  tests/
```

## Dev (API ohne Fenster, Vite im Browser)

Zwei Terminals. Vite proxyt `/api` auf `127.0.0.1:8765`.

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:AGENTUS_NETWORK_DEV = "1"
$env:AGENTUS_NETWORK_NO_HOST = "1"
python -m app.main
```

```powershell
cd frontend
npm i
npm run dev
```

UI: `http://localhost:5173`. API: `http://127.0.0.1:8765/api`.

`python -m app.main` bindet nur Loopback und serviert `GET /api/health`. OpenAPI `/docs` nur mit `AGENTUS_NETWORK_DEV=1`. `0.0.0.0` startet nicht.

Tests:

```powershell
cd backend
pytest
```

Tests nutzen `AGENTUS_NETWORK_HOME` (tmp) und `AGENTUS_NETWORK_VAULT=memory`. CI braucht kein Display und kein Ollama.

## Prod (Host + `frontend/dist`)

Dieselbe App, ein Prozess. `AGENTUS_NETWORK_DEV` / `NO_HOST` **nicht** setzen. Windows: WebView2-Fenster, SPA von Loopback (nicht `file://`). Ollama bleibt ein eigener Daemon; dieser Prozess beendet Ollama nicht.

Installer (PyInstaller onedir + NSIS) kommt nach Host + `frontend/dist`. Version = dieses `pyproject.toml`.

## Umgebung

Prefix überall `AGENTUS_NETWORK_*`.

| Variable | Default | Bedeutung |
|----------|---------|-----------|
| `AGENTUS_NETWORK_API_HOST` | `127.0.0.1` | Bind. Nur Loopback (`127.0.0.1`, `localhost`, `::1`). `0.0.0.0` startet nicht. |
| `AGENTUS_NETWORK_API_PORT` | `8765` | Port 1–65535 |
| `AGENTUS_NETWORK_DEV` | unset | `1`/`true`: kein Host-Fenster, CORS für Vite `:5173`, OpenAPI `/docs` |
| `AGENTUS_NETWORK_NO_HOST` | unset | `1`/`true`: nur API, auch ohne DEV |
| `AGENTUS_NETWORK_STATIC_DIR` | unset | Ordner mit `frontend/dist`; sonst `../frontend/dist` relativ zu `backend/` |
| `AGENTUS_NETWORK_API_VERSION` | Paketversion / `0.1.0` | `GET /api/about` → `apiVersion` |
| `AGENTUS_NETWORK_HOME` | `%LOCALAPPDATA%\Agentus-Network` | Wurzel für YAML/Daten (Tests) |
| `AGENTUS_NETWORK_DATA_DIR` | unset | Override Datenordner; Wechsel über API dann read-only |
| `AGENTUS_NETWORK_VAULT` | OS | `memory` = In-Memory-Tresor (Tests) |
| `AGENTUS_NETWORK_CORS_ORIGINS` | unset | Zusätzliche Loopback-Origins, kommagetrennt |

Listen in v1 nicht auf `0.0.0.0`. Kein Auth, kein TLS.

## Shared Code

Ein Konzept einmal. Fachmodule importieren, klonen nicht.

| Thema | Stelle |
|--------|--------|
| Provider-/Store-Literals | `app/common/types.py` |
| Secret-Maskierung | `app/common/secrets.py` (`mask_text`, `mask_obj`) |
| `httpx.Client` | `app/common/http.py` `client()` |
| `messageKey`-Fehler | `app/http/errors.py` (`AppError`) |
| Vault | `app/db/vault.py` — Windows: `keyring` (Credential Manager), Target `Agentus-Network` / `credential/{id}`. Tests: `AGENTUS_NETWORK_VAULT=memory` |
| Completions / Embeddings | `app/runtime/` (Runtime-Prompt) |
| Tool-Katalog | `app/tools/catalog.py` (Tools-Prompt) |
