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

Mitte: **Palette** (links), **Canvas**, **Inspector** (rechts). Auf schmalen Screens sind Palette und Inspector Schubladen.

Knoten per Ziehen aus der Palette. Karten bleiben kompakt; Formulare stehen im Inspector. Mehrfachauswahl mit Umschalt oder Gummiband. Entf löscht Auswahl. Rückgängig: Strg+Z.

Während **genau dieses** Netz läuft: Banner **Schreibgeschützt** — zuerst in der Kopfzeile stoppen.

## Knotenarten

| Anzeigename | Typ | Aufgabe |
|-------------|-----|---------|
| Chat-Eingabe | `chat_input` | Starttext und Nutzereingabe. **Höchstens eine.** Ausgang **Nachricht**. |
| LLM | `llm` | Provider (Ollama, xAI, OpenAI-kompatibel), Modell, optional Zugang, Temperature, Token-Limit. Ausgang **LLM**. |
| Agent | `agent` | Systemprompt. Eingänge Nachricht, LLM, Werkzeug, Wissen. Ausgang Nachricht, optional Übergabe. LLM, Tools und Wissen kommen **nur über Kanten**, nicht als geheime Felder. |
| Werkzeug | `tool` | First-Party: HTTP, Websuche, Datum/Zeit, Rechner — oder **MCP**. Ausgang **Werkzeug**. |
| Wissen | `knowledge` | Ordner mit Dateien für das Netz. Ausgang **Wissen**, nur zum Agent-Anschluss Wissen. |
| Router | `router` | Verzweigt die Nachricht nach Bedingungen (erste Zeile / benannte Zweige) plus Standard-Ausgang. |
| Ende | `end` | Abschluss. **Mindestens eines.** |

## Verbindungen

Nur passende Anschlüsse:

- Nachricht zu Nachricht (Chat → Agent, Agent → Ende, Agent → Router, Router-Zweige → …)
- LLM-Ausgang nur an Agent **LLM** — jeder Agent braucht **genau eine** solche Kante
- Werkzeug-Ausgang an Agent **Werkzeug** (mehrere erlaubt)
- Wissen-Ausgang nur an Agent **Wissen**
- Zyklen sind verboten (gerichteter Graph ohne Schleife)

Ungültiges Ziehen wird abgewiesen.

## Inspector

Kein Knoten gewählt: Name, Beschreibung, Tags, Statistik, Validierungsliste des **offenen** Netzes.

Knoten gewählt:

- **LLM:** Provider, Modell (Liste von der Runtime), Zugang für Cloud, Ping, erweitert Temperature / max. Tokens. Cloud ohne Zugang ist ungültig.
- **Agent:** nur Systemprompt und Anzeigename.
- **Werkzeug:** Art. HTTP: Methode und URL, optional Zugang. Websuche: Zugang der Art Websuche. MCP: aktivierter Server aus den Einstellungen; Standard alle Tools dieses Servers.
- **Wissen:** Quellenordner (Ordnerwahl), topK, Score-Schwelle, **Index neu**. Der Ordner muss **unter dem Datenordner** liegen, darf nicht die Laufwerkswurzel sein und nicht der Hilfe-Korpus.
- **Chat-Eingabe:** Platzhalter, Starttext, Schalter „Eingabe nötig“.
- **Router:** benannte Zweige (Name + Bedingung) und Standard.

Geheimnisse gehören **nicht** in den Inspector-Text und nicht in den Graph-Export — nur die Wahl eines Zugangs.

## Validierung

**Validieren** im Ribbon prüft unter anderem:

- Name nicht leer
- höchstens eine Chat-Eingabe, mindestens ein Ende
- jeder Agent: genau eine LLM-Kante und eine eingehende Nachricht
- LLM: Modell gesetzt; Cloud: Zugang
- Werkzeug: Art; MCP: aktiver Server, Wurzelpfad wenn das Rezept ihn braucht
- Wissen: Pfad, Sandbox, nicht Hilfe-Korpus
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
