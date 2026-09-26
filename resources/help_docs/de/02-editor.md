# Editor und Bibliothek

Der Editor unter **Netzwerk** bearbeitet **ein** Graph-Dokument. Die **Verwaltung** ist die Bibliothek: Liste, Import, Löschen, aktiv setzen. Den Canvas gibt es nur im Editor, nicht in Verwaltung, Monitoring oder Historie.

## Zwei Orte

| Ort | URL-Sinn | Typische Aktionen |
|-----|----------|-------------------|
| Editor | Neu oder ein geladenes Netz | Zeichnen, Inspector, Speichern, Laden-Dialog, Duplizieren, Export des offenen Graphen |
| Verwaltung | alle Netze | Suche, Tags, als aktiv setzen, Import/Export mehrerer Dateien, Löschen |

**Als aktiv setzen** und **Löschen** gehören in die Verwaltung (oder die Schnellwahl für aktiv). Der Laden-Dialog im Editor öffnet nur **ein** Netz und löscht nichts.

## Editor-Oberfläche

Oben das **Ribbon**: Neu, Speichern, Speichern unter, Laden, Duplizieren, Export, Validieren, Rückgängig/Wiederherstellen, Ansicht (Einpassen, Raster, Rasterfang, Minikarte), Zur Verwaltung.

Mitte: **Palette** (links), **Canvas**, **Inspector** (rechts). Auf dem Desktop lassen sich Palette und Inspector einklappen. Auf schmalen Screens sind sie Schubladen. Ein leeres Netz zeigt nur den Hinweis, den ersten Knoten aus der Palette auf die Fläche zu ziehen. Die Kanten sind geschwungene Kurven, wie in Monitoring und Historie.

Knoten per Ziehen aus der Palette. Karten bleiben kompakt; Formulare stehen im Inspector. Mehrfachauswahl mit Umschalt oder Gummiband. Entf löscht Auswahl. Rückgängig: Strg+Z.

Während **genau dieses** Netz läuft: Banner **Schreibgeschützt** — zuerst in der Kopfzeile stoppen.

## Knotenarten

| Anzeigename | Typ | Aufgabe |
|-------------|-----|---------|
| Chat | `chat_input` | Gespräch des Laufs. **Höchstens einer.** Ausgang **Nachricht**. Mit Orchestrator bleibt der Chat für Rückfragen offen. |
| Orchestrator | `orchestrator` | Stimme im Lauf-Chat. Eingänge **Nachricht**, **LLM** und **Werkzeug**. Pro Agent ein Ausgang **Kanal**. **Nachricht** nur zum **Ende** (oder Router). **Höchstens einer.** |
| LLM | `llm` | Provider (Ollama, xAI, OpenAI, Claude, Gemini, OpenAI-kompatibel), Modell, Zugang für Cloud, Temperature, Token-Limit. Ausgang **LLM**. |
| Agent | `agent` | Systemprompt. Eingänge Nachricht, LLM, Werkzeug, Wissen, optional **Kanal**. Ausgänge Nachricht und Übergabe. Der Kanal kommt nur vom Orchestrator. Ohne Kanal läuft der Agent einmal über die Nachricht. |
| Werkzeug | `tool` | First-Party: HTTP, Websuche, Datum/Zeit, Rechner, Dateizugriff — oder **MCP**. Ausgang **Werkzeug**. |
| Wissen | `knowledge` | Ordner mit Dateien für das Netz. Ausgang **Wissen**, nur zum Agent-Anschluss Wissen. |
| Router | `router` | Verzweigt die Nachricht nach Bedingungen (erste Zeile / benannte Zweige) plus Standard-Ausgang. |
| Ende | `end` | Abschluss. **Mindestens eines.** |

## Verbindungen

Nur passende Anschlüsse:

- Nachricht zu Nachricht (Chat → Agent oder Chat → Orchestrator, Agent → Ende, Agent → Router, Router-Zweige → …). Der Orchestrator schickt Nachricht nur an Ende oder Router.
- Kanal zu Kanal (Orchestrator → Agent). Ein Anschluss pro Agent. Die Antwort kommt im Lauf zurück, ohne zweite Kante.
- LLM-Ausgang an Agent **LLM** oder Orchestrator **LLM** — jeder Agent und der Orchestrator brauchen **genau eine** solche Kante
- Werkzeug-Ausgang an Agent oder Orchestrator **Werkzeug** (mehrere erlaubt). Ein Werkzeug darf an beide.
- Wissen-Ausgang nur an Agent **Wissen**
- Zyklen sind verboten (gerichteter Graph ohne Schleife)

Ungültiges Ziehen wird abgewiesen.

## Inspector

Kein Knoten gewählt: Name, Beschreibung, Tags, Statistik, Validierungsliste des **offenen** Netzes.

Knoten gewählt:

- **LLM:** Provider, Modell (Liste von der Runtime), Zugang für Cloud, Ping, erweitert Temperature / max. Tokens. Cloud ohne Zugang ist ungültig.
- **Agent:** Systemprompt und Anzeigename. Hängt der Agent an einem Kanal, erklärt der Inspector, dass Aufträge vom Orchestrator kommen.
- **Werkzeug:** Art. HTTP: Methode und URL, optional Zugang. Websuche: Zugang der Art Websuche. Dateizugriff: Wurzelordner, nicht die Laufwerkswurzel; der Agent arbeitet nur darunter, Schreiben und Löschen sind Schalter. MCP: aktivierter Server aus den Einstellungen; Standard alle Tools dieses Servers.
- **Wissen:** Quellenordner (Ordnerwahl), Embedding-Provider (Ollama, OpenAI oder Gemini) und Embedding-Modell, topK, Score-Schwelle, **Index neu**. Der Ordner darf irgendwo liegen, nur nicht auf einer Laufwerk- oder Systemwurzel und nicht im Hilfe-Korpus. Cloud-Embeddings brauchen einen Zugang. Der Index gehört zu diesem Netz, nicht zur Hilfe.
- **Chat:** Platzhalter, Starttext, Schalter „Eingabe nötig“.
- **Orchestrator:** Systemprompt. Das Modell entscheidet zwischen Rückfrage, einem Agentenauftrag über dessen Kanal, Antwort und Abschluss. Die Agenten sind die Kanäle, keine zweite Liste. Angeschlossene Werkzeuge ruft er selbst auf. Nur die Rückfrage wartet auf den Nutzer.
- **Router:** benannte Zweige (Name + Bedingung) und Standard.

Geheimnisse gehören **nicht** in den Inspector-Text und nicht in den Graph-Export — nur die Wahl eines Zugangs.

## Validierung

**Validieren** im Ribbon prüft unter anderem:

- Name nicht leer
- höchstens ein Chat, höchstens ein Orchestrator, mindestens ein Ende
- jeder Agent: genau eine LLM-Kante. Ohne Orchestrator eine eingehende Nachricht. Mit Orchestrator genau ein Kanal und keine Nachrichten-Kette am selben Agenten
- LLM: Modell gesetzt; Cloud: Zugang
- Werkzeug: Art; MCP: aktiver Server, Wurzelpfad wenn das Rezept ihn braucht
- Wissen: Pfad gesetzt, keine Wurzel, nicht der Hilfe-Korpus, Embedding-Zugang wenn der Provider ihn braucht
- keine hängenden Kanten, keine Zyklen, passende Anschlusstypen

Gültig/Ungültig siehst du als Badge. Ungültige Netze lassen sich speichern, aber schlecht starten.

## Speichern, Laden, Export

- **Speichern** (Strg+S): erstes Mal Namensdialog, danach Update. URL wird `/network/…`.
- **Speichern unter:** neues Dokument, wird das geöffnete.
- **Laden:** ein gespeichertes Netz; Suche und Sortierung. Bulk und Löschen nur in der Verwaltung.
- **Duplizieren:** nur bei schon gespeichertem Dokument; öffnet die Kopie.
- **Export:** Download des offenen Graphen. Enthält `credentialId`, keine Schlüssel. Import in der Verwaltung verwirft mitgeschickte Geheimnisse.

Ungespeichert verlassen: Dialog Speichern / Verwerfen / Abbrechen.

## Verwaltung (Bibliothek)

Liste mit Suche (Name, Beschreibung, Tags), Sortierung, Filter „nur gültige“ / „nur aktive“. Mehrfachauswahl.

Aktionen: Neu (Editor), Öffnen, Duplizieren, Umbenennen, Tags setzen, **Als aktiv setzen** (nur ein gültiges Netz), Löschen, Importieren, Exportieren.

Löschen entfernt den Workspace-Eintrag, nicht deine Knowledge-Quelldateien auf der Platte, nicht den Hilfe-Korpus und nicht die Historie-Läufe. Ein **laufendes** Netz wird übersprungen. Aktives Netz löschen leert die Schnellwahl.

Import: Dateien mit Namenskollision umbenennen oder überspringen. Nicht unterstützte Schema-Versionen werden abgelehnt.
