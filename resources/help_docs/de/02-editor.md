# Editor und Bibliothek

Der Editor unter **Netzwerk** bearbeitet **ein** Graph-Dokument. Die **Verwaltung** ist die Bibliothek: Liste, Import, Löschen, aktiv setzen. Den Canvas gibt es nur im Editor, nicht in Verwaltung, Monitoring oder Historie.

## Zwei Orte

| Ort | URL-Sinn | Typische Aktionen |
|-----|----------|-------------------|
| Editor | Neu oder ein geladenes Netz | Zeichnen, Inspector, Speichern, Laden-Dialog, Duplizieren, Export des offenen Graphen |
| Verwaltung | alle Netze | Suche, Tags (eigene Spalte, höchstens zwei Zeilen, „…“ zeigt beim Überfahren alle), Details rechts mit Art, Status samt Fehlern, Tags, Geändert und Zuletzt verwendet, Art des Netzes (Orchestrator oder linear, Umschalter „Orchestrator – Alle – Linear“), als aktiv setzen, Import/Export mehrerer Dateien, Löschen |

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
| Werkzeug | `tool` | First-Party: HTTP, Websuche, Datum/Zeit, Rechner, Dateizugriff. Ausgang **Werkzeug**. |
| MCP | `mcp` | Ein in den **Einstellungen** angelegter und **aktiver** Server. Ausgang **Werkzeug**, wie ein Werkzeug-Knoten. |
| Wissen | `knowledge` | Ordner mit Dateien für das Netz. Ausgang **Wissen**, nur zum Agent-Anschluss Wissen. |
| Router | `router` | Schickt die Nachricht an genau einen Ausgang. Zweige prüfen der Reihe nach: enthält, beginnt mit, erste Zeile, regulärer Ausdruck. Der Standard fängt den Rest. Hinter dem Orchestrator führen die Ausgänge nur zu Enden. |
| Ende | `end` | Abschluss. **Mindestens eines.** |

## Verbindungen

Nur passende Anschlüsse:

- Nachricht zu Nachricht (Chat → Agent oder Chat → Orchestrator, Agent → Ende, Agent → Router, Router-Zweige → …). Der Orchestrator schickt Nachricht nur an Ende oder Router.
- Kanal zu Kanal (Orchestrator → Agent). Ein Anschluss pro Agent. Die Antwort kommt im Lauf zurück, ohne zweite Kante.
- LLM-Ausgang an Agent **LLM** oder Orchestrator **LLM** — jeder Agent und der Orchestrator brauchen **genau eine** solche Kante
- Werkzeug-Ausgang an Agent oder Orchestrator **Werkzeug** (mehrere erlaubt). Ein Werkzeug- oder MCP-Knoten darf an beide.
- Wissen-Ausgang nur an Agent **Wissen**
- Zyklen sind verboten (gerichteter Graph ohne Schleife)

Ungültiges Ziehen wird abgewiesen.

## Inspector

Kein Knoten gewählt: Name, Beschreibung, Tags, Statistik, Validierungsliste des **offenen** Netzes. Tags sind Chips; Enter, Komma oder Plus übernimmt einen Tag, das Kreuz entfernt ihn. Die Verwaltung filtert nach denselben Tags.

Knoten gewählt:

- **LLM:** Provider, Modell (Liste von der Runtime), Zugang für Cloud, Kontextlänge nach Modellgrenzen (Slider lokal, Auswahl Cloud), CPU-Threads pro Knoten (Standard: physische Kerne), GPU-Offload pro Layer (Standard: alle Layer, bei Ladefehler Auto), geschätzter GPU-Speicher aus Kontext und Offload (letzte N Schichten auf der GPU; volle Attention über den ganzen Kontext, Sliding-Window-Schichten nur über ihr Fenster; Warnung, wenn er nicht auf die Karte passt), Ping, erweitert Temperature (0 bis 2, bei Anthropic 0 bis 1) und max. Tokens (ganze Zahl von 64 bis 262144, kleiner als der Kontext). Cloud ohne Zugang ist ungültig. Zahlenfelder übernehmen gültige Werte sofort; einen Wert außerhalb des Bereichs passen sie beim Verlassen des Felds an. Ein importiertes Netz mit ungültigen Werten zeigt einen Prüffehler und startet nicht.
- **Agent:** Systemprompt und Anzeigename. Hängt der Agent an einem Kanal, erklärt der Inspector, dass Aufträge vom Orchestrator kommen. Vor dem Ergebnis darf er intern denken; das erscheint nicht im Chat. Lokale Modelle (Ollama und eigene OpenAI-kompatible Server) bekommen ihr Denken der letzten Schritte eines Auftrags beim nächsten Schritt zurück, gekürzt auf je 1500 Zeichen, damit Schlüsse wie „dieser Befehl ist hier verboten“ nicht verloren gehen. Wie viele Schritte, stellt **Gedächtnis (Schritte)** am Agenten ein (leer: 10, 2 bis 50). Gekürzt wird gesammelt: Sind es doppelt so viele, fällt das ältere Denken auf einmal weg. Ollama kann seinen Zwischenspeicher nur weiterverwenden, wenn der Verlauf hinten wächst; Hybrid-Modelle wie Qwen 3.5/3.6 lesen nach jeder Änderung weiter vorn den ganzen Verlauf neu. Cloud-Anbieter bekommen es nicht. Wird das Kontextfenster knapp, fällt dieses Denken als Erstes weg. **Werkzeugaufrufe je Auftrag** begrenzt seine Werkzeugaufrufe (leer: 100); danach antwortet er mit dem, was er hat.
- **Werkzeug:** Art. HTTP: Methode und URL, optional Zugang. Der Zugang geht nur an die Adresse dieser URL (Schema, Host, Port); mit Zugang ist die URL Pflicht. Websuche: Zugang der Art Websuche. Dateizugriff: Wurzelordner, nicht die Laufwerkswurzel; der Agent arbeitet nur darunter, Schreiben und Löschen sind Schalter. **Suchen** findet Dateinamen mit einem Muster (`*.css`) oder mit `text` einen Text in einer Datei oder in den Dateien eines Ordners, mit Pfad, Zeilennummer und Zeile; `node_modules` und `.git` überspringt die Textsuche. Terminal (eingeschränkt): ein freigegebenes Programm mit Argumenten, ohne Shell. Was Modelle aus Gewohnheit anhängen und hier nichts ändert, nimmt das Werkzeug weg und sagt es dem Modell: `cd` in den Arbeitsordner, `2>&1` und ein angehängtes `| head -N` oder `| tail -N` (die Ausgabe wird dann auf diese Zeilen gekürzt). Andere Pipes, `&&`, `;` und Umleitungen bleiben abgelehnt. Der Prompt des Agenten nennt vorab, was statt üblicher Shell-Befehle zu nehmen ist (etwa `grep` → Dateizugriff-Suche mit Text, `cat` → Lesen, `mkdir` → Dateizugriff), nur mit den Werkzeugen, die der Agent hat. Einen abgelehnten Befehl merkt sich der Lauf: Für den Rest des Auftrags steht die Lehre beim Werkzeugergebnis, bei jedem weiteren Auftrag an diesen Agenten in diesem Lauf im Systemprompt (höchstens sechs Einträge). Befehle, die nicht von selbst enden (Server und Watch-Modi wie `npm run dev`, `npm start`, `vite`, `--watch`), laufen 15 Sekunden und werden dann beendet; der Agent bekommt, was sie bis dahin ausgegeben haben, und den Hinweis, dass es im Lauf keinen Browser gibt.
- **MCP:** aktiver Server aus **Einstellungen → MCP-Server**. Standard alle Tools dieses Servers; nach einer Probe kannst du eine Teilmenge wählen. Zugänge gehören in die Einstellungen. Der Wurzelordner für Dateisystem und Excel steht am Knoten; Git behält den Ordner in den Einstellungen.
- **Wissen:** Quellenordner (Ordnerwahl), Embedding-Provider (Ollama, OpenAI oder Gemini) und Embedding-Modell, topK (1 bis 20, leer: 4), Score-Schwelle (0 bis 1, leer: 0), **Index neu**. Der Ordner darf irgendwo liegen, nur nicht auf einer Laufwerk- oder Systemwurzel und nicht im Hilfe-Korpus. Gelesen werden Markdown, Text, PDF, Word (.docx), Excel (.xlsx), HTML, JSON, CSV und Quellcode. Bilder und alte .doc/.xls nicht. Cloud-Embeddings brauchen einen Zugang. Der Index gehört zu diesem Netz, nicht zur Hilfe.
- **Chat:** Platzhalter, Starttext, Schalter „Eingabe nötig“.
- **Orchestrator:** Systemprompt. Das Modell entscheidet zwischen Denken, Rückfrage, einem Agentenauftrag über dessen Kanal, Antwort und Abschluss. Denken erscheint nicht im Chat und zählt nicht gegen das Schrittlimit; nur Agentenaufträge zählen. Die Agenten sind die Kanäle, keine zweite Liste. Angeschlossene Werkzeuge ruft er selbst auf: Dateien lesen jederzeit, höchstens 15 Aufrufe je Entscheidung (einstellbar) und vor dem ersten Agentenauftrag höchstens zehn insgesamt. Will er danach weiterlesen, bekommt er dafür die nächste Entscheidung; liest er nur Bekanntes erneut, gilt das als Stillstand. Dateien ändern, Terminal und alle übrigen Werkzeuge erst nach einem gescheiterten Agentenaufruf oder in einer Übernahme. Sein Prompt sagt, was er erreicht: welche Werkzeuge angeschlossen sind, wofür sie da sind und ob sie gerade offen sind oder erst nach einem gescheiterten Agentenaufruf. Ohne eigene Werkzeuge steht dort, dass er keine Dateien lesen kann und Prüfungen einem Agenten gibt. Die Agentenliste nennt die Werkzeuge jedes Agenten. Regeln und Einzelheiten stehen nur bei den Werkzeugen, die gerade offen sind. Hat er Werkzeuge, kann er auch über Werkzeugaufrufe entscheiden (call_agent, ask_user, reply, finish). Derselbe Aufruf läuft in einem Schritt nur einmal; scheitert ein Werkzeug dreimal mit demselben Fehler oder wiederholt er einen Aufruf zweimal, zieht der Lauf es für diesen Schritt zurück. Nur die Rückfrage wartet auf den Nutzer; eine Antwort, in der eine Zeile mit „?“ endet, behandelt der Lauf als Rückfrage. Nach jedem Agentenauftrag sieht der Orchestrator alle bisherigen Aufrufe der Reihe nach: den Anfang des Auftrags, die geänderten Dateien, wie viel gelesen und gesucht wurde, vom neuesten Ergebnis eines Agenten den vollen Text und von dessen früheren Ergebnissen den Anfang. Passt sein Prompt nicht mehr ins Kontextfenster, kürzt der Lauf Schritt für Schritt, die ältesten Ergebnisse zuerst: erst auf ihren Anfang, dann ganz; das neueste Ergebnis zuletzt. Auftrag und geänderte Dateien jedes Aufrufs, deine Nachrichten und das Vorwissen bleiben; im Gedächtnis bleibt alles vollständig.
  - **Fehlversuche je Agent** (leer: 2): So oft in Folge darf ein Agent scheitern oder einen Dateiauftrag ohne Änderung beenden. Danach übernimmt der Orchestrator diese Aufgabe selbst.
  - **Agentenaufrufe je Lauf** (leer: 50): Jeder Auftrag an einen Agenten zählt, auch Review-Runden und Prüfaufträge. Ist die Grenze erreicht, fasst der Orchestrator im Chat zusammen, was fertig ist und was offen bleibt; danach endet der Lauf mit dem Hinweis auf das Limit.
  - **Werkzeugaufrufe je Entscheidung** (leer: 50) und **Modellaufrufe je Lauf** (leer: 1000, Orchestrator und Agenten zusammen).
  - **Lesezugriffe je Entscheidung** (leer: 15): So viele Dateien liest der Orchestrator in einer Entscheidung, solange er nur lesen darf. Will er weiterlesen, bekommt er dafür die nächste Entscheidung. Vor dem ersten Agentenauftrag gelten höchstens zehn insgesamt.
  - Trifft der Orchestrator mehrere Entscheidungen hintereinander ohne Fortschritt (kein Agentenauftrag, kein neues Werkzeugergebnis, keine neue Nachricht), erinnert ihn der Lauf nach vier. Nach acht bekommt er eine letzte Runde ohne Werkzeuge für eine Zusammenfassung im Chat; danach endet der Lauf als festgefahren.
- **Router:** benannte Zweige (Name + Bedingung) und Standard.

Geheimnisse gehören **nicht** in den Inspector-Text und nicht in den Graph-Export — nur die Wahl eines Zugangs.

## Validierung

**Validieren** im Ribbon prüft unter anderem:

- Name nicht leer
- höchstens ein Chat, höchstens ein Orchestrator, mindestens ein Ende
- die Ordner von Dateizugriff, Terminal und ZIP existieren; fehlt einer, startet der Lauf nicht. Verschwindet ein Ordner während des Laufs, schaltet der Lauf das Werkzeug ab
- ohne Orchestrator führt die Kette vom Start (Chat oder erster Agent) bis zu einem Ende; mit Orchestrator hat er mindestens einen Kanal zu einem Agenten
- jeder Agent: genau eine LLM-Kante. Ohne Orchestrator eine eingehende Nachricht. Mit Orchestrator genau ein Kanal und keine Nachrichten-Kette am selben Agenten
- LLM: Modell gesetzt; Cloud: Zugang
- Werkzeug: Art. MCP: aktiver Server aus den Einstellungen; Wurzelpfad wenn das Rezept ihn braucht
- Wissen: Pfad gesetzt, keine Wurzel, nicht der Hilfe-Korpus, Embedding-Zugang wenn der Provider ihn braucht
- keine hängenden Kanten, keine Zyklen, passende Anschlusstypen

Gültig/Ungültig siehst du als Badge. Ungültige Netze lassen sich speichern, aber schlecht starten.

## Speichern, Laden, Export

- **Speichern** (Strg+S): erstes Mal Namensdialog, danach Update. URL wird `/network/…`.
- **Speichern unter:** neues Dokument, wird das geöffnete.
- **Laden:** ein gespeichertes Netz; Suche und Sortierung. Bulk und Löschen nur in der Verwaltung.
- **Duplizieren:** nur bei schon gespeichertem Dokument; öffnet die Kopie.
- **Export:** Dialog, dann JSON des offenen Graphen (`schemaVersion` 1). Enthält `credentialId`, keine Schlüssel.
- **Import:** Dialog für eine JSON-Datei. Daraus wird ein neues Netz. Ein schon vergebener Name wird umbenannt oder die Datei übersprungen.

Ungespeichert verlassen: Dialog Speichern / Verwerfen / Abbrechen.

## Verwaltung (Bibliothek)

Liste mit Suche (Name, Beschreibung, Tags), Sortierung, Filter „nur gültige“ / „nur aktive“. Mehrfachauswahl.

Aktionen: Neu (Editor), Öffnen, Duplizieren, Umbenennen, Tags setzen, **Als aktiv setzen** (nur ein gültiges Netz), Löschen, Importieren, Exportieren. Tags setzen lädt die vorhandenen Tags der Auswahl als Chips.

Löschen entfernt den Workspace-Eintrag, nicht deine Knowledge-Quelldateien auf der Platte, nicht den Hilfe-Korpus und nicht die Historie-Läufe. Ein **laufendes** Netz wird übersprungen. Aktives Netz löschen leert die Schnellwahl.

Import: Dialog mit Vorschau. Gleicher Name: umbenennen oder überspringen. Andere schemaVersion wird abgelehnt. Geheimnisse werden verworfen.
