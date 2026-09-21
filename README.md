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

Der **Hilfe-Chatbot** (FAB unten rechts) beantwortet Fragen zur App in der gewählten Oberflächensprache. Quellen nennt er nur bei der Websuche (Titel und Adresse), nicht für die eingebauten Anleitungen.

Ein Netz ist entweder eine **Kette** (Chat → Agent → Ende, optional Router, Werkzeug, Wissen) oder hat **einen** Orchestrator. Der Orchestrator ist die einzige Stimme im Lauf-Chat. Er ruft angeschlossene Agenten nacheinander über je einen Kanal auf. Deren Texte erscheinen nicht als eigene Chatblasen. Ohne Orchestrator läuft jeder Agent einmal über Nachricht und Übergabe.

Wissen darf auf einen beliebigen Ordner zeigen, außer auf eine Laufwerk- oder Systemwurzel und auf den Hilfe-Korpus. Hängt Wissen an einem Agenten, bleibt der Start in „startet“, bis der Index fertig oder als aktuell erkannt ist. Monitoring, Kopfzeile und Dashboard nennen den Knoten.

Sprachen der Oberfläche und der Hilfe: Deutsch (Default), English, Español, Français, Türkçe, Português, 中文, 日本語, العربية.

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

Das Setup installiert bei Bedarf die **WebView2**-Runtime (Evergreen-Bootstrapper, mitgepackt) und **Ollama** (Download der offiziellen `OllamaSetup.exe` zur Install-Zeit, SHA256 in `installer/vendor.lock.json`). Bereits vorhanden → skip. LM Studio wird nicht installiert.

Ist Ollama schon da oder gerade installiert, startet das Setup ihn **im Hintergrund** (`ollama app.exe --hide --fast-startup`, sonst `ollama.exe serve` über `start`). Es wartet nicht auf das Ollama-Fenster. Mit `curl.exe` prüft es `http://127.0.0.1:11434/` (`--ipv4`, Connect-Timeout 1 s, gesamt 2 s), höchstens 15-mal mit 2 s Pause. Fehlt `curl.exe`, entfällt die Warte. Danach geht das Setup weiter, auch wenn der Port noch nicht antwortet.

Modelle (in der Komponentenliste an): `nomic-embed-text` und `llama3.2:1b`, **nur** wenn diese Prüfung Ollama erreicht hat. Ein fehlgeschlagener `ollama pull` beendet das Setup trotzdem erfolgreich; die Dashboard-Setup-Karte zeigt den Runtime-Status. Die Desktop-Verknüpfung ist in der Komponentenliste aus, das Startmenü an.

Die App selbst startet einen lokalen Ollama ebenfalls, wenn die Runtime-Adresse Loopback ist und Port 11434 nicht antwortet. Sie beendet ihn beim Schließen nie. `AGENTUS_NETWORK_NO_OLLAMA=1` unterdrückt diesen Start.

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

Portable: Config und `data\` neben der EXE. Hilfe-Markdown liegt als Quelle unter `resources/help_docs/` (neun Sprachen). Beim App-Start kopiert der Seed **fehlende** Dateien nach `agentus_network_rag_documents/`. Vorhandene Dateien werden nicht überschrieben. Das Setup kopiert den Korpus nicht. Der Hilfe-Chat liest den Index, nicht die Markdown-Dateien direkt: neue Texte gelten erst nach **Index neu aufbauen** unter Einstellungen → Hilfe-Chatbot.

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

Das Frontend spricht die Python-API (`/api`, Proxy in Vite). Backend mit `AGENTUS_NETWORK_DEV=1` und `AGENTUS_NETWORK_NO_HOST=1` parallel zum Vite-Dev-Server starten.

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
- Provider in der Oberfläche: `ollama`, `xai`, `openai`, `anthropic`, `gemini`. `openai_compat` bleibt für gespeicherte Graphen und Zugänge gültig, steht aber nicht in den Modell-Auswahlen. Embeddings: `ollama`, `openai`, `gemini`. Kein `lmstudio` als eigener Dienst.
- Completions nur `POST {base}/v1/chat/completions`, gestreamt. Ein Lauf bricht ab, wenn eine Weile keine Tokens mehr kommen, nicht nach einer festen Gesamtdauer. Kein stilles `ollama pull` zur Laufzeit.
- First-Party-Tools: HTTP, Websuche, Datum/Zeit, Taschenrechner, Dateizugriff. MCP über vendored Rezepte, Sessions lazy.
- Secrets nie in Node-Daten, Export oder Git. Listen zeigen nur Masken.

Umgebung (Prefix `AGENTUS_NETWORK_*`): Host/Port, `DEV` / `NO_HOST`, `STATIC_DIR`, `HOME`, `DATA_DIR`, `VAULT=memory` (Tests). Tabelle: [`backend/README.md`](backend/README.md).

## Repo

```
frontend/     Vite + React (Shell, Module, i18n)
backend/      Python-Paket `app` (API, Persistenz, Host)
packaging/    PyInstaller-Spec
installer/    NSIS, vendor.lock.json, Lizenz
resources/    Hilfe-Markdown (de, en, es, fr, tr, pt, zh, ja, ar), App-Icon
scripts/      build-windows.ps1
prompts/      Produkt- und Coding-Prompts (features.md, build.md)
```

Detaillierte Modul-READMEs: [`frontend/README.md`](frontend/README.md), [`backend/README.md`](backend/README.md). Die verbindliche Bau-Reihenfolge steht in `prompts/build.md`.

## Lizenz und Drittanbieter

Setup-Text: `installer/license.txt`. Ollama, WebView2, Modelle und optionale MCP-Server bleiben unter ihren eigenen Lizenzen. Optional OpenAI-kompatible Endpunkte (einschließlich LM Studio) konfigurierst du selbst unter Einstellungen; sie werden nicht mitinstalliert.
