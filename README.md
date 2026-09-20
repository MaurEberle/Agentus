# Agentus Network

Lokale Desktop-App, mit der sich **Agentennetze** aus LLMs, Tools und Wissen auf dem eigenen PC bauen, starten und auswerten lassen. Oberfläche, HTTP-API, Persistenz, Hilfe-Chat, MCP-Supervisor und Netz-Laufzeit laufen in **einem** Windows-Prozess. Die UI kommt über Loopback in einem **WebView2**-Fenster.


Version: `0.1.0` (eine Quelle: `backend/pyproject.toml`).

## Was die App kann

| Bereich | Route | Rolle |
|---------|--------|--------|
| Dashboard | `/dashboard` (auch `/`) | Setup-Karten, Status, letzte Läufe |
| Editor | `/network`, `/network/:id` | Graph (Knoten, Kanten, Validierung) |
| Netze | `/networks` | Bibliothek, Import/Export — kein zweiter Canvas |
| Monitoring | `/monitoring` | Live-Lauf, Log, optional Lauf-Chat |
| Historie | `/history`, `/history/:runId` | Archiv und Statistik |
| Einstellungen | `/settings` | Runtime, Zugänge, Hilfe-Chat, MCP, Datenort, About |

Der **Hilfe-Chatbot** (FAB unten rechts) beantwortet Fragen zur App und zum Graphen.

Sprachen: Deutsch (Default), Englisch und Spanisch.

## Voraussetzungen

**Endnutzer (Setup-EXE)**

- Windows 10/11 **x64**
- Kein Admin für den Normalpfad
- Internet beim ersten Setup, falls Ollama fehlt (Download der offiziellen `OllamaSetup.exe`)

**Entwicklung**

- Python **3.12**
- Node.js (Frontend)
- Optional: [Ollama](https://ollama.com) auf `http://127.0.0.1:11434`
- Windows-Installer-Build: NSIS 3 Unicode (`makensis`) plus `pip install -e ".[packaging]"` im Backend

## Schnellstart für Nutzer

### Setup (empfohlen)

1. `dist/Agentus-Network-Setup-0.1.0-x64.exe` ausführen (nach `.\scripts\build-windows.ps1`).
2. Per-User nach `%LOCALAPPDATA%\Programs\Agentus-Network`.
3. Startmenü: **Agentus Network** → `AgentusNetwork.exe`.

Das Setup installiert bei Bedarf die **WebView2**-Runtime (Evergreen-Bootstrapper, mitgepackt) und **Ollama** (Download zur Install-Zeit, SHA256 in `installer/vendor.lock.json`). Bereits vorhanden → skip. LM Studio wird nicht installiert.

Modelle (GUI, Default an): `nomic-embed-text` und `llama3.2:1b`. Ein Fehlschlag beendet das Setup trotzdem erfolgreich; die Dashboard-Setup-Karte fängt das auf.

### Silent

```text
Agentus-Network-Setup-0.1.0-x64.exe /S
Agentus-Network-Setup-0.1.0-x64.exe /S /INSTALL_MODELS=1
```

`/D=C:\pfad` setzt den **Installationsort** und muss **am Ende** der Kommandozeile stehen. `/D` ist nicht der Modell-Schalter.

Log: `%LOCALAPPDATA%\Agentus-Network\logs\installer.log`.

### Portable

`dist/Agentus-Network-Portable-0.1.0-x64.zip` entpacken und `AgentusNetwork.exe` starten. Die Datei `portable.txt` **neben** der EXE legt Daten nach `{exe_dir}/data`. WebView2 und Ollama müssen schon da sein. `portable.txt` liegt nicht im NSIS-Payload.

### Deinstallieren

Apps & Features → **Agentus Network**. Programmdateien, Shortcuts und Uninstall-Registry weg. Frage „Anwendungsdaten behalten?“ Default **Ja**. Silent-Uninstall `/S` behält Daten. **Ollama, WebView2 und `%USERPROFILE%\.ollama` bleiben.**

## Datenorte

| Pfad | Inhalt |
|------|--------|
| `%LOCALAPPDATA%\Programs\Agentus-Network\` | Programmdateien (NSIS) |
| `%LOCALAPPDATA%\Agentus-Network\config.yaml` | Zeiger (kein Secret) |
| `%LOCALAPPDATA%\Agentus-Network\data\` | vier SQLite-Stores + Hilfe-Korpus `agentus_network_rag_documents/` |
| Windows-Anmeldeinformationsverwaltung | Secrets, Target `Agentus-Network` / `credential/{id}` |

Portable: Config und `data\` neben der EXE. Hilfe-Markdown wird beim **ersten App-Start** einmal in den Korpus kopiert, wenn der Ordner leer ist — nicht vom Setup.

## Entwicklung

Zwei Terminals. Vite proxyt `/api` auf die Loopback-API.

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

UI: `http://localhost:5173`. API: `http://127.0.0.1:8765/api`. OpenAPI `/docs` nur mit `AGENTUS_NETWORK_DEV=1`.

Ohne `DEV` / `NO_HOST` auf Windows startet dasselbe Backend ein WebView2-Fenster und serviert `frontend/dist` (vorher `npm run build` im Frontend). Die API bindet nur Loopback (`127.0.0.1`, `localhost`, `::1`). `0.0.0.0` startet nicht.

Frontend-Mocks sind Default (`VITE_USE_MOCKS` alles außer `false`). Gegen die echte API: `VITE_USE_MOCKS=false`.

```powershell
cd backend
pytest
cd ..\frontend
npm run typecheck
npm run lint
```

Tests setzen `AGENTUS_NETWORK_HOME` (tmp) und `AGENTUS_NETWORK_VAULT=memory`. CI braucht kein Display und kein Ollama.

## Windows-Build (Freeze + Setup)

```powershell
.\scripts\build-windows.ps1
.\scripts\build-windows.ps1 -SkipFrontend
.\scripts\build-windows.ps1 -SkipNsis
```

Erzeugt unter `dist/`:

| Datei | Inhalt |
|-------|--------|
| `AgentusNetwork/` | PyInstaller-onedir, `AgentusNetwork.exe`, kein Konsolenfenster |
| `Agentus-Network-Setup-{version}-x64.exe` | NSIS Per-User-Setup |
| `Agentus-Network-Portable-{version}-x64.zip` | derselbe Freeze plus `portable.txt` |

Voraussetzungen: Python 3.12-venv im Backend, `frontend/dist`, NSIS 3 (`makensis` auf PATH oder unter `build/nsis/`). Vendor-Cache `installer/vendor/` nicht committen. Icon `resources/icons/app.ico` (PNG `resources/icons/app.png`).

Mehr: [`installer/README.md`](installer/README.md), Checkliste für eine frische Windows-VM dort.

## Architektur (kurz)

```
WebView2-Fenster  ──HTTP──►  FastAPI 127.0.0.1:8765
        ▲                         │
        └── dieselbe EXE ─────────┴── SQLite, Vault, Hilfe, MCP, Run
Ollama (eigener Prozess) ◄──────────── Runtime-Completions / Embeddings
```

- Ein Prozess, JSON camelCase, Fehler `{ messageKey, message? }`.
- Provider: `ollama` | `xai` | `openai_compat` — kein `lmstudio` als eigener Dienst.
- Completions nur `POST {base}/v1/chat/completions`. Kein stilles `ollama pull` zur Laufzeit.
- First-Party-Tools: HTTP, Websuche, Datum/Zeit, Taschenrechner. MCP über vendored Rezepte, Sessions lazy.
- Secrets nie in Node-Daten, Export oder Git. Listen zeigen nur Masken.

Umgebung (Prefix `AGENTUS_NETWORK_*`): Host/Port, `DEV` / `NO_HOST`, `STATIC_DIR`, `HOME`, `DATA_DIR`, `VAULT=memory` (Tests). Tabelle: [`backend/README.md`](backend/README.md).

## Repo

```
frontend/     Vite + React (Shell, Module, i18n)
backend/      Python-Paket `app` (API, Persistenz, Host)
packaging/    PyInstaller-Spec
installer/    NSIS, vendor.lock.json, Lizenz
resources/    Hilfe-Markdown (de/en), App-Icon
scripts/      build-windows.ps1
prompts/      Produkt- und Coding-Prompts (features.md, build.md)
```

Detaillierte Modul-READMEs: [`frontend/README.md`](frontend/README.md), [`backend/README.md`](backend/README.md). Die verbindliche Bau-Reihenfolge steht in `prompts/build.md`.

## Lizenz und Drittanbieter

Setup-Text: `installer/license.txt`. Ollama, WebView2, Modelle und optionale MCP-Server bleiben unter ihren eigenen Lizenzen. Optional OpenAI-kompatible Endpunkte (einschließlich LM Studio) konfigurierst du selbst unter Einstellungen; sie werden nicht mitinstalliert.
