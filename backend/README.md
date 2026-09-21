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

Provider in der Oberfläche: `ollama`, `xai`, `openai`, `anthropic`, `gemini`. `openai_compat` bleibt für gespeicherte Graphen und Zugänge gültig, steht aber nicht in den Modell-Auswahlen. Embeddings: `ollama`, `openai`, `gemini`. Kein `lmstudio`.

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

`python -m app.main` bindet nur Loopback. Mit `AGENTUS_NETWORK_DEV=1` oder `AGENTUS_NETWORK_NO_HOST=1` nur API (Vite im Browser). Auf Windows ohne diese Flags: WebView2-Fenster (`window.chromeHost`). OpenAPI `/docs` nur mit DEV. `0.0.0.0` startet nicht.

Tests:

```powershell
cd backend
pytest
```

Tests nutzen `AGENTUS_NETWORK_HOME` (tmp) und `AGENTUS_NETWORK_VAULT=memory`. CI braucht kein Display und kein Ollama.

## Prod (Host + `frontend/dist`)

Dieselbe App, ein Prozess. `AGENTUS_NETWORK_DEV` / `NO_HOST` **nicht** setzen. Windows: WebView2-Fenster, SPA von Loopback (nicht `file://`). Ollama bleibt ein eigener Daemon. Ist er installiert, die URL Loopback und Port 11434 tot, startet die App ihn im Hintergrund (`ollama app.exe --hide --fast-startup`, sonst `serve`). Dieser Prozess beendet Ollama nicht. `AGENTUS_NETWORK_NO_OLLAMA=1` unterdrückt den Start.

Version = dieses `pyproject.toml`. Build (Windows x64):

```powershell
.\scripts\build-windows.ps1
.\scripts\build-windows.ps1 -SkipFrontend   # vorhandenes frontend/dist
.\scripts\build-windows.ps1 -SkipNsis       # nur Freeze + Portable-Zip
```

Artefakte in `dist/`:

| Datei | Inhalt |
|-------|--------|
| `AgentusNetwork/` | PyInstaller-onedir (`AgentusNetwork.exe`, kein Konsolenfenster) |
| `Agentus-Network-Setup-{version}-x64.exe` | NSIS Per-User-Setup |
| `Agentus-Network-Portable-{version}-x64.zip` | derselbe Freeze plus `portable.txt` neben der EXE |

Icon `resources/icons/app.ico` (PNG-Quelle `app.png`). Setup braucht NSIS 3 Unicode (`makensis`).

## Prod-Setup

Per-User, kein Admin. Ziel: `%LOCALAPPDATA%\Programs\Agentus-Network`. Daten: `%LOCALAPPDATA%\Agentus-Network` (nicht der Programs-Ordner).

- Fehlt WebView2: Evergreen-Bootstrapper silent (mitgepackt).
- Fehlt Ollama: Download der offiziellen `OllamaSetup.exe` (URL/SHA256 in `installer/vendor.lock.json`) und Inno silent. Bereits vorhanden → skip.
- Danach Start im Hintergrund (`ollama app.exe --hide --fast-startup`, sonst `ollama.exe serve`). Kein Warten auf das Ollama-Fenster. `curl.exe` prüft `127.0.0.1:11434` höchstens 15×2 s. Fehlt `curl.exe`, entfällt die Warte. Das Setup geht danach weiter.
- Modelle (GUI, Default an): `nomic-embed-text` und `llama3.2:1b`, nur wenn Ollama geantwortet hat. Fehlschlag oder Stille lässt das Setup **erfolgreich** enden. Desktop-Verknüpfung ist in der Komponentenliste aus.
- LM Studio wird nicht installiert.
- Hilfe-Markdown wird **nicht** vom Setup kopiert. `app/install_seed.py` kopiert fehlende Dateien aus `resources/help_docs/` beim App-Start und überschreibt vorhandene Dateien nicht.

Silent (keine UI, keine Modell-Pulls):

```text
Agentus-Network-Setup-0.1.0-x64.exe /S
```

Silent mit Modell-Pull (`/D=` ist bei NSIS der **Installationsort** und muss am Ende stehen):

```text
Agentus-Network-Setup-0.1.0-x64.exe /S /INSTALL_MODELS=1
Agentus-Network-Setup-0.1.0-x64.exe /S /INSTALL_MODELS=1 /D=%LOCALAPPDATA%\Programs\Agentus-Network
```

Log: `%LOCALAPPDATA%\Agentus-Network\logs\installer.log`.

## Portable

Zip entpacken, `AgentusNetwork.exe` starten. `portable.txt` neben der EXE schaltet Persistenz auf `{exe_dir}/data`. WebView2 und Ollama müssen schon existieren; das Zip enthält sie nicht. Die Datei `portable.txt` liegt **nicht** im NSIS-Payload.

## Uninstall

Apps & Features: **Agentus Network**. Entfernt Programs-Ordner, Startmenü, Desktop-Shortcut, Uninstall-Registry. Frage „Anwendungsdaten behalten?“ Default **Ja**. Silent-Uninstall `/S` behält Daten. Ollama, WebView2 und `%USERPROFILE%\.ollama` bleiben.

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
| HTTP-Vertrag v1 | `app/http/contract.py` — Pfade aus `python_backend_api.md`; Fachrouter dürfen keine Extra-`/api`-Routen erfinden |
| Vault | `app/db/vault.py` — Windows: `keyring` (Credential Manager), Target `Agentus-Network` / `credential/{id}`. Tests: `AGENTUS_NETWORK_VAULT=memory` |
| Completions / Embeddings | `app/runtime/` (Runtime-Prompt) |
| Tool-Katalog | `app/tools/catalog.py` (Tools-Prompt) |
