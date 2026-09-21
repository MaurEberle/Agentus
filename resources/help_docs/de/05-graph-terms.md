# Begriffe

Kurzes Glossar für den Hilfe-Chat und den Editor.

## Graph / Netz

Gespeichertes Dokument aus Knoten und Kanten. Du bearbeitest es im Editor, verwaltest Kopien in der Bibliothek. Das **aktive** Netz ist das in der Schnellwahl — nur das startet **Start**.

## Lauf (Run)

Eine Ausführung des aktiven Graphen. Es läuft höchstens **einer**. Start und Stopp in der Kopfzeile. Ergebnisse: läuft, Erfolg, Fehler, Abbruch, Timeout.

## Knoten und Kanten

Bausteine (Chat, Orchestrator, Agent, LLM, Werkzeug, Wissen, Router, Ende) und typisierte Verbindungen. Beliebige Pfeile zwischen Kästen sind ungültig.

## Agent

Knoten mit Systemprompt. Modell, Nachricht, Werkzeuge und Wissen kommen über Anschlüsse. Ohne Orchestrator startet ihn die Nachricht, und Nachricht oder Übergabe geben die Antwort weiter. Mit Orchestrator hängt er an einem eigenen Kanal: ein Auftrag hinein, ein Ergebnis zurück.

## LLM-Knoten

Wählt Provider und Modell. Lokal über Ollama, sonst Cloud oder OpenAI-kompatible URL plus Zugang.

## Chat

Einziger Einstieg für Nutzertext im Lauf. Höchstens einer pro Netz. Der Monitoring-Chat schreibt hier hinein. Mit Orchestrator bleibt das Gespräch über mehrere Nachrichten offen.

## Orchestrator

Knoten mit eigenem LLM. Er ist die einzige Stimme im Lauf-Chat, stellt Rückfragen und ruft die angeschlossenen Agenten einzeln über je einen Kanal auf. Höchstens einer. Der Chat verbindet sich nur mit ihm. Sein Nachrichtenausgang geht an Ende oder an einen Router. Agententexte und interne Aufträge siehst du nicht als Chatblasen. Die App hängt das letzte Ergebnis an den nächsten Auftrag. Ein Agent ist entweder am Kanal oder in der Nachrichtenkette.

## Werkzeug

First-Party (HTTP, Websuche, Datum/Zeit, Rechner, Dateizugriff) oder MCP. Dateizugriff bleibt in einem Wurzelordner, nicht auf der Laufwerkswurzel. Konfiguration im Inspector, Ausführung nur im Lauf.

## Wissen (Netz)

Knowledge-Knoten: ein Ordner mit Texten für das Netz. Er darf irgendwo liegen, nur nicht auf einer Laufwerk- oder Systemwurzel und nicht im Hilfe-Korpus. Eigenes Embedding-Modell, eigener Index, topK und Score. Beim Start siehst du die Indizierung. Ein schon aktueller Index wird übersprungen.

## Hilfe-RAG

Dokumente im Hilfe-Ordner im Datenordner (Default-Anleitungen plus deine Markdown-Dateien). Nur der Hilfe-Chatbot. Nach Änderungen Index unter Einstellungen → Hilfe-Chatbot neu aufbauen.

## Credential / Zugang

Gespeicherter Schlüssel im Windows-Tresor. In Listen nur Maske. Im Graphen nur die ID/Wahl, nie das Secret. Export enthält keine Passwörter.

## MCP

Model Context Protocol: externe Tool-Server. In den Einstellungen anlegen und aktivieren, im Graphen als Werkzeug-Knoten der Art MCP verbinden. Die Hilfe verwendet MCP nicht.

## Provider

In der Auswahl: `ollama` (lokal), `xai`, `openai`, `anthropic` (Claude), `gemini` (Cloud, Zugang zuerst, dann Modellliste). Embeddings: Ollama, OpenAI, Gemini. `openai_compat` bleibt für ältere Graphen und Zugänge gültig, steht aber nicht mehr in der Modell-Auswahl.

## Ollama

Separater Dienst für lokale Modelle. Die App ist der Client. Ist er installiert, die Adresse lokal und der Port zu, startet die App ihn und beendet ihn nicht. Das Setup kann Ollama anlegen, kurz auf ihn warten und zwei kleine Default-Modelle laden, wenn er antwortet.

## Dashboard, Monitoring, Historie

Dashboard = Überblick und Einrichtung. Monitoring = Live. Historie = Archiv. Nicht dieselbe Seite dreimal.

## Gültig / Ungültig

Validierung des Graphen. Ungültig speicherbar, aber zum Start ungeeignet. Nur ein gültiges Netz lässt sich als aktiv setzen.

## Schnellwahl

Kopfzeilen-Auswahl des aktiven Netzes. Entspricht „Als aktiv setzen“ in der Verwaltung.

## Sparmodus

Hilfe weicht auf das Fallback-Modell aus, wenn das Hauptmodell nicht trägt. Das Dashboard kann das unter Umgebung anzeigen.

## Portable

`portable.txt` neben der EXE: Daten neben der Anwendung. Installierte Kopie: Daten im App-Datenordner, Programme extra.
