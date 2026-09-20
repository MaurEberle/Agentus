# Einstellungen

Zahnrad in der Kopfzeile. Abschnitte links: Darstellung, Zugänge, Runtime, Hilfe-Chatbot, MCP-Server, Daten, Über. Ungespeicherte Felder beim Wechsel: Dialog Bleiben / Verwerfen.

## Darstellung

Hell, Dunkel oder System — gilt für die ganze App inklusive Kopfzeile. **Sprache** ist ein Dropdown mit Flagge: Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية. Der Name in Klammern ist die Übersetzung in der aktuell gewählten Sprache.

Schalter **Hilfe-Schaltfläche**: blendet die Sprechblase unten rechts ein oder aus. Die **Konfiguration** des Chatbots bleibt unter **Hilfe-Chatbot**, auch wenn die Blase aus ist.

## Zugänge

Benannte Geheimnisse für Cloud-Modelle, Websuche und manche MCP-Rezepte. Anlegen: Name, Art, Secret **einmal**. Danach nur noch die **Maske**. Bearbeiten kann das Secret ersetzen (leer = unverändert).

Arten unter anderem: xAI, OpenAI-kompatibel, Websuche, GitHub, Azure, GitLab, Slack, Notion, Atlassian, Linear, Postgres, Token.

**Löschen** ist gesperrt, solange Hilfe-Profil, ein Netz (LLM/Tool) oder ein MCP-Server den Zugang nutzt. Zuerst die Zuordnung entfernen.

## Runtime

**Ollama-Basis-URL** (üblich die lokale Adresse von Ollama) und optional **OpenAI-kompatible Basis-URL**. **Verbindung prüfen** und die **Modellliste** laufen über die App, nicht am Browser vorbei.

Ohne erreichbares Ollama bleiben lokale LLM-Knoten und die Standard-Hilfe stehen. Modelle installierst du mit Ollama selbst oder beim Setup; die App **pullt** zur Laufzeit nicht still.

## Hilfe-Chatbot

Einzige Stelle für das Hilfe-Widget. Unvollständig ohne Chat-Provider und Chat-Modell.

- Chat-Provider und Chat-Modell (Default Ollama / `llama3.2:1b`)
- optional Cloud-Zugang
- **Embedding-Provider und -Modell** (Default Ollama / `nomic-embed-text`) — das ist **nicht** das Chat-Modell
- optionales Spar-Modell (Fallback, Default dasselbe kleine Chat-Modell)
- Websuche an/aus plus Such-Zugang; ohne Zugang bleibt der Chat konfiguriert, die Suche ist aus
- Verbindung prüfen, Verlauf löschen, **Index neu aufbauen**, Onboarding erneut zeigen

Nach Wechsel des Embedding-Modells oder nach neuen Dateien im Hilfe-Korpus: **Index neu aufbauen**. Der Korpus ist der Ordner für Hilfe-Dokumente im Datenordner, nicht das Netz-Wissen.

Die Hilfe nutzt **keine** MCP-Server und **kein** Knowledge der Graphen.

## MCP-Server

Vorlagen (**Rezepte**) für externe Tools: GitHub, Dateisystem, Git, Playwright, Postgres, Slack, Notion, Office-Formate und andere. Rezepte sind keine mitgelieferten Programme. Viele brauchen Node/`npx`, Docker oder `uvx` auf dem PC plus einen Zugang.

Standard: Server **inaktiv**. Die App startet MCP-Prozesse nicht beim Öffnen, sondern wenn ein Lauf einen verbundenen MCP-Werkzeugknoten braucht.

Anlegen aus einem Rezept (Zugang, optionaler Wurzelpfad) oder als **eigener Server** (Befehl, Argumente oder URL). Unbekannte Befehle nur verwenden, wenn du ihnen vertraust. Probe prüft Erreichbarkeit; „Runtime fehlt“, wenn Node/Docker/`uvx` nicht da ist.

Office bündelt PDF und Office-Formate; Einzel-Presets nur extra aktivieren, wenn du sie wirklich brauchst.

Löschen entfernt die Server-Konfiguration, nicht Ollama und nicht Zugänge.

## Daten

Zeigt den **Datenordner** und den Zustand der Stores: Einstellungen, Hilfe, Workspace, Historie — ohne SQL-Ansicht und ohne Secrets.

Ordner **wechseln** nur, wenn kein Netz startet, läuft oder stoppt. Laufwerks- oder Systemwurzeln sind ungültig. Optional Inhalt in den neuen Ordner kopieren; der alte Ordner bleibt liegen.

**Portabel** oder ein von außen vorgegebener Ordner: Pfad **schreibgeschützt**.

**Aufbewahrung der Historie:** 30 / 90 / 365 Tage oder unbegrenzt (Default 90). Die Historie-Seite kann ältere Einträge passend bereinigen.

## Über

UI- und API-Version, grober Ollama-Status, ob Stores erreichbar sind. Keine Geheimnisse, keine internen Dateipfade mit Benutzername in der Fläche, die du teilen würdest.
