# Editor

Der Editor bearbeitet **ein** Graph-Dokument. Speichern schreibt in die Bibliothek.

## Knotenarten (kurz)

| Typ | Rolle |
|-----|--------|
| `chat_input` | Nutzereingabe (höchstens einer) |
| `llm` | Modell (Ollama oder Cloud) |
| `agent` | Prompt, nimmt Message/LLM/Tool/Wissen |
| `tool` | First-Party oder MCP |
| `knowledge` | Ordner unter dem Datenverzeichnis |
| `router` | Verzweigung nach erster Zeile |
| `end` | Lauf-Ende (mindestens einer) |

## Validierung

Der Graph muss ein DAG sein. Jeder Agent braucht genau eine LLM-Kante. Knowledge-Pfade dürfen nicht die Laufwerkswurzel oder den Hilfe-Korpus sein. MCP-Knoten brauchen einen **aktivierten** Server.
