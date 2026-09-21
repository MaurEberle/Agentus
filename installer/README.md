# Agentus Network — Windows-Installer

PyInstaller onedir + NSIS 3 Unicode, Per-User, kein Admin. Version kommt aus `backend/pyproject.toml`.

Build:

```powershell
.\scripts\build-windows.ps1
```

Vendor-Dateien (nicht committen): `installer/vendor/` laut `vendor.lock.json`. WebView2-Bootstrapper wird ins Setup gepackt. `OllamaSetup.exe` (~1,4 GB) wird **zur Install-Zeit** geladen und gehasht, nicht ins Repo.

`resources/icons/app.ico` ist das App-Icon (Quelle `resources/icons/app.png`).

## Silent

```text
Agentus-Network-Setup-0.1.0-x64.exe /S
Agentus-Network-Setup-0.1.0-x64.exe /S /INSTALL_MODELS=1
```

`/D=C:\pfad` setzt den Installationsort und muss **am Ende** der Kommandozeile stehen. `/D` ist nicht der Modell-Schalter.

Komponenten: Anwendung und Startmenü fest, WebView2 und Ollama „falls fehlend“, Standardmodelle an, Desktop-Verknüpfung aus. Silent ohne `/INSTALL_MODELS=1` zieht keine Modelle.

## Ollama im Setup

Fehlt Ollama, lädt das Setup die offizielle `OllamaSetup.exe` (URL und SHA256 in `vendor.lock.json`) und startet sie silent. Danach, oder wenn Ollama schon da ist:

1. Start **asynchron** mit NSIS `Exec`, nicht `nsExec`. Zuerst `%LOCALAPPDATA%\Programs\Ollama\ollama app.exe --hide --fast-startup`, sonst derselbe Name unter `%LOCALAPPDATA%\Ollama`, sonst `ollama.exe serve` über `cmd /c start`. `nsExec` auf die GUI würde das Setup blockieren.
2. Prüfung mit `%SystemRoot%\System32\curl.exe -s -o NUL --ipv4 --connect-timeout 1 --max-time 2 --noproxy 127.0.0.1 http://127.0.0.1:11434/`. Höchstens 15 Versuche, dazwischen 2 s. Fehlt `curl.exe`, wird nicht gewartet.
3. Antwortet der Port nicht, geht das Setup mit Erfolg weiter. `nomic-embed-text` und `llama3.2:1b` werden nur gezogen, wenn die Prüfung erfolgreich war. Ein fehlgeschlagener Pull bricht das Setup nicht ab.

Die App startet einen lokalen Ollama beim Öffnen ebenfalls, wenn die Runtime-Adresse Loopback ist und Port 11434 tot ist, und beendet ihn nie.

## Uninstall

Default: Anwendungsdaten behalten. Silent-Uninstall behält Daten. Ollama und WebView2 werden nicht entfernt.

## Checkliste (manuell, Windows-VM)

1. Clean Win11 ohne Ollama, WebView2 wenn möglich entfernt/fehlend → Setup mit Defaults → Fenster öffnet, keine Konsole.
2. Ollama schon installiert → Setup skip, kein zweites Ollama.
3. Upgrade gleiche Major → Daten bleiben, Version neu.
4. Uninstall Daten behalten → YAML/SQLite noch da; Programs weg.
5. `/S` ohne Modelle → App da, keine Pulls. Hilfe-Chat darf am fehlenden Tag scheitern.
6. Ollama installiert, Port tot → Setup startet ihn im Hintergrund, wartet höchstens etwa eine halbe Minute, zieht Modelle nur bei Antwort, endet sonst trotzdem erfolgreich.
7. Portable-Zip + vorhandenes Ollama → `source=portable`.
8. Zweiter Start → eine Instanz (Mutex).
9. Close App → Ollama lebt.
