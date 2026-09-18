# Agentus Network — Kurzanleitung

Agentus Network ist eine **lokale** Desktop-App: Netze aus Agenten, LLM-Knoten und Werkzeugen laufen auf diesem PC. Die Oberfläche kommt aus demselben Prozess (Loopback), nicht aus Chrome und nicht als `file://`.

## Ein Netz anlegen

1. **Netze** öffnen oder den Editor über **Neu**.
2. Mindestens `chat_input` → `agent` ← `llm` → `end` verbinden.
3. Speichern. Das aktive Netz steht in der Sitzung (Header / Dashboard).

## Start und Stopp

**Start** im Header startet **einen** Lauf des **aktiven** Netzes. Ein zweiter Start ist blockiert, bis Stopp. Stopp bricht den Lauf ab; **Ollama bleibt** ein eigener Dienst und wird nicht beendet.

## Hilfe-FAB ist nicht der Netz-Chat

Das Sprechblasen-Symbol unten rechts ist der **Hilfe-Chatbot** (Doku + optionale Websuche). Der Chat im Monitoring ist der **Lauf-Chat** des Graphen (`chat_input`). Beide teilen sich weder Verlauf noch Tools.

## Ollama und Cloud

Lokal: Ollama auf `http://127.0.0.1:11434`. Cloud: Zugänge (xAI, OpenAI-kompatibel) unter **Einstellungen → Zugänge**. Secrets liegen im Windows-Tresor, Listen zeigen nur eine Maske.
