# Begriffe

Kurzes Glossar für den Hilfe-Chat und den Editor.

## Graph / Netz

Gespeichertes Dokument aus Knoten und Kanten. Du bearbeitest es im Editor, verwaltest Kopien in der Bibliothek. Das **aktive** Netz ist das in der Schnellwahl — nur das startet **Start**.

## Lauf (Run)

Eine Ausführung des aktiven Graphen. Es läuft höchstens **einer**. Start und Stopp in der Kopfzeile. Ergebnisse: läuft, Erfolg, Fehler, Abbruch, Timeout.

## Knoten und Kanten

Bausteine (Chat-Eingabe, Agent, LLM, Werkzeug, Wissen, Router, Ende) und typisierte Verbindungen. Beliebige Pfeile zwischen Kästen sind ungültig.

## Agent

Knoten mit Systemprompt. Modell, Nachricht, Werkzeuge und Wissen kommen über Anschlüsse, nicht als eingebettete Schlüssel.

## LLM-Knoten

Wählt Provider und Modell. Lokal über Ollama, sonst Cloud oder OpenAI-kompatible URL plus Zugang.

## Chat-Eingabe

Einziger Einstieg für Nutzertext im Lauf. Höchstens einer pro Netz. Der Monitoring-Chat schreibt hier hinein.

## Werkzeug

First-Party (HTTP, Websuche, Datum/Zeit, Rechner) oder MCP. Konfiguration im Inspector, Ausführung nur im Lauf.

## Wissen (Netz)

Knowledge-Knoten: Ordner **unter** dem Datenordner der App. Eigener Index, topK und Score. **Nicht** der Hilfe-Korpus. Nicht die Laufwerkswurzel.

## Hilfe-RAG

Dokumente im Hilfe-Ordner im Datenordner (Default-Anleitungen plus deine Markdown-Dateien). Nur der Hilfe-Chatbot. Nach Änderungen Index unter Einstellungen → Hilfe-Chatbot neu aufbauen.

## Credential / Zugang

Gespeicherter Schlüssel im Windows-Tresor. In Listen nur Maske. Im Graphen nur die ID/Wahl, nie das Secret. Export enthält keine Passwörter.

## MCP

Model Context Protocol: externe Tool-Server. In den Einstellungen anlegen und aktivieren, im Graphen als Werkzeug-Knoten der Art MCP verbinden. Die Hilfe verwendet MCP nicht.

## Provider

`ollama` (lokal), `xai`, `openai`, `anthropic` (Claude), `gemini` (Cloud, API-Key zuerst, dann Modellliste), `openai_compat` (eigene kompatible HTTP-API, z. B. LM Studio).

## Ollama

Separater Dienst für lokale Modelle. Die App ist der Client. Setup kann Ollama und zwei kleine Default-Modelle anlegen. Close der App lässt Ollama laufen.

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
