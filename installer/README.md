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

## Uninstall

Default: Anwendungsdaten behalten. Silent-Uninstall behält Daten. Ollama und WebView2 werden nicht entfernt.

## Checkliste (manuell, Windows-VM)

1. Clean Win11 ohne Ollama, WebView2 wenn möglich entfernt/fehlend → Setup mit Defaults → Fenster öffnet, keine Konsole.
2. Ollama schon installiert → Setup skip, kein zweites Ollama.
3. Upgrade gleiche Major → Daten bleiben, Version neu.
4. Uninstall Daten behalten → YAML/SQLite noch da; Programs weg.
5. `/S` ohne Modelle → App da, Hilfe-Chat darf am fehlenden Tag scheitern.
6. Portable-Zip + vorhandenes Ollama → `source=portable`.
7. Zweiter Start → eine Instanz (Mutex).
8. Close App → Ollama lebt.
