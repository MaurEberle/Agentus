# Einstellungen

Zahnrad in der Kopfzeile. Abschnitte links: Darstellung, Zugänge, Runtime, Hilfe-Chatbot, MCP-Server, Daten, Über. Ungespeicherte Felder beim Wechsel: Dialog Bleiben / Verwerfen. Speichern in den Einstellungen erzeugt keine Benachrichtigung; ein Fehler beim Speichern schon.

## Darstellung

Hell, Dunkel oder System — gilt für die ganze App inklusive Kopfzeile. **Sprache** ist ein Dropdown mit Flagge: Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية. Der Name in Klammern ist die Übersetzung in der aktuell gewählten Sprache.

Schalter **Hilfe-Schaltfläche**: blendet die Sprechblase unten rechts ein oder aus. Die **Konfiguration** des Chatbots bleibt unter **Hilfe-Chatbot**, auch wenn die Blase aus ist.

## Zugänge

Benannte Geheimnisse für Cloud-Modelle, Websuche und manche MCP-Rezepte. Anlegen: Name, Art, Secret **einmal**. Danach nur noch die **Maske**. Bearbeiten kann das Secret ersetzen (leer = unverändert).

Arten unter anderem: xAI, OpenAI, Claude, Gemini, OpenAI-kompatibel, Websuche, GitHub, Azure, GitLab, Slack, Notion, Atlassian, Linear, Postgres, Token.

**Löschen** ist gesperrt, solange Hilfe-Profil, ein Netz (LLM/Tool) oder ein MCP-Server den Zugang nutzt. Zuerst die Zuordnung entfernen.

## Runtime

**Ollama-Basis-URL** (üblich die lokale Adresse von Ollama). **Verbindung prüfen** und die **Modellliste** laufen über die App. Die Liste teilt sich in **Normale Modelle** und **Embedding-Modelle**. Ein Modell gilt als Embedding, wenn der Name `embed` enthält. Eine leere Gruppe zeigt **Keine**.

Ist die Adresse lokal und Ollama installiert, aber aus, startet die App den Dienst beim Öffnen und beendet ihn nicht. Ohne erreichbares Ollama bleiben lokale LLM-Knoten und die Standard-Hilfe stehen. Modelle installierst du mit Ollama selbst oder beim Setup; die App **pullt** zur Laufzeit nicht still. Eine OpenAI-kompatible Basis-URL wird hier nicht mehr angeboten.

## Hilfe-Chatbot

Einzige Stelle für das Hilfe-Widget. Unvollständig ohne Chat-Provider und Chat-Modell.

- Chat-Provider und Chat-Modell (Default Ollama / `llama3.2:1b`)
- optional Cloud-Zugang
- **Embedding-Provider und -Modell** (Default Ollama / `nomic-embed-text`) — das ist **nicht** das Chat-Modell
- optionales Spar-Modell (Fallback, Default dasselbe kleine Chat-Modell)
- Websuche an/aus plus Such-Zugang; ohne Zugang bleibt der Chat konfiguriert, die Suche ist aus
- Verbindung prüfen, Verlauf löschen, **Index neu aufbauen**, Onboarding erneut zeigen

Nach Wechsel des Embedding-Modells oder nach neuen Dateien im Hilfe-Korpus: **Index neu aufbauen**. Der Lauf geht weiter, auch wenn du die Einstellungen verlässt. Ein zweiter Klick startet keinen zweiten Index. Der Korpus ist der Ordner für Hilfe-Dokumente im Datenordner, nicht das Netz-Wissen. Es gelten dieselben Dateitypen wie beim Knowledge-Knoten. Neue mitgelieferte Anleitungen überschreiben Dateien, die schon dort liegen, nicht von selbst.

Die Hilfe antwortet in der Oberflächensprache. Kann das Modell die Sprache nicht, antwortet es auf Englisch. Sie nennt keine Dokumenttitel aus den Anleitungen. Nur eine Websuche zeigt Quellen, und zwar Titel und Adresse. Interne Denkblöcke des Modells erscheinen nicht. Die Hilfe nutzt **keine** MCP-Server und **kein** Knowledge der Graphen.

## MCP-Server

Vorlagen (**Rezepte**) für externe Tools. Rezepte sind keine mitgelieferten Programme. Viele brauchen Node/`npx`, Docker oder `uvx` auf dem PC plus einen **Zugang**.

Standard: Server **inaktiv**. Die App startet MCP-Prozesse nicht beim Öffnen, sondern wenn ein Lauf einen verbundenen **MCP-Knoten** braucht.

**Einrichten:** Rezept wählen, Zugänge der passenden Art zuordnen. Dateisystem und Excel aktivierst du ohne Ordner; den Ordner setzt du am MCP-Knoten im Editor. Git braucht den Wurzelordner hier. Speichern legt den Server an und aktiviert ihn. **Probe** spricht `tools/list`. „Runtime fehlt“, wenn Node/Docker/`uvx` nicht da ist.

Was welches Rezept braucht:

| Rezept | Zugang | Sonst |
|--------|--------|--------|
| GitHub | PAT, Art **GitHub** | lokal `npx` |
| GitLab | PAT, Art **GitLab** | lokal `npx` |
| Azure | Token/PAT, Art **Azure** | lokal `npx` |
| Slack | Bot-Token, Art **Slack** | lokal `npx` |
| Notion | Integration-Token, Art **Notion** | lokal `npx` |
| Atlassian | Cloud-Token, Art **Atlassian** | remote |
| Linear | API-Key, Art **Linear** | remote HTTP |
| Context7 | API-Key, Art **Token** | remote HTTP |
| Sentry | Auth-Token, Art **Token** | lokal `npx` |
| Postgres | Verbindungszeichenfolge, Art **Postgres** (nicht die App-SQLite) | lokal `npx` |
| Dateisystem, Excel | keiner | Wurzelordner **am MCP-Knoten** im Editor; lokal `npx` |
| Git | keiner | **Wurzelordner** in den Einstellungen; lokal `uvx` |
| Fetch | keiner | lokal `uvx` |
| Playwright | keiner | lokal `npx` plus Browser |

Zugänge legst du unter **Zugänge** an, nicht im Rezept-Dialog. Ohne passenden Zugang bleibt der Server ungültig.

Oder **eigener Server** (Befehl, Argumente oder URL). Unbekannte Befehle nur verwenden, wenn du ihnen vertraust.

Löschen entfernt die Server-Konfiguration, nicht Ollama und nicht Zugänge. Im Netz verbindest du den Server über den Palette-Knoten **MCP**, nicht über die Werkzeug-Art.

## Daten

Zeigt den **Datenordner** und den Zustand der Stores: Einstellungen, Hilfe, Workspace, Historie — ohne SQL-Ansicht und ohne Secrets.

Ordner **wechseln** nur, wenn kein Netz startet, läuft oder stoppt. Laufwerks- oder Systemwurzeln sind ungültig. Optional Inhalt in den neuen Ordner kopieren; der alte Ordner bleibt liegen.

**Portabel** oder ein von außen vorgegebener Ordner: Pfad **schreibgeschützt**.

**Aufbewahrung der Historie:** 30 / 90 / 365 Tage oder unbegrenzt (Default 90). Die Historie-Seite kann ältere Einträge passend bereinigen.

## Über

UI- und API-Version, grober Ollama-Status, ob Stores erreichbar sind. Keine Geheimnisse, keine internen Dateipfade mit Benutzername in der Fläche, die du teilen würdest.
