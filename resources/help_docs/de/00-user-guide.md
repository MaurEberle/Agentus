# Agentus Network — Kurzanleitung

Agentus Network ist eine **lokale Desktop-App**. Du baust auf diesem PC Netze aus Agenten, Sprachmodellen und Werkzeugen, startest **einen** Lauf und siehst ihn live. Die Oberfläche gehört zur App selbst (eigenes Fenster), nicht zu Chrome und nicht zu einer `file://`-Seite.

Ollama ist ein **eigener Dienst** neben der App. Schließen oder Deinstallieren von Agentus Network beendet Ollama nicht und löscht keine Modelle.

## Fenster und Navigation

Links (auf dem Telefon: Burger-Menü):

- **Dashboard** — Startseite, Einrichtung, aktives Netz, letzte Läufe
- **Netzwerk** — Editor (ein Graph)
- **Verwaltung** — Bibliothek aller gespeicherten Netze
- **Monitoring** — Live-Lauf
- **Historie** — abgeschlossene Läufe und Statistik

**Einstellungen** sitzen in der Kopfzeile (Zahnrad), nicht in der linken Navigation.

In der Kopfzeile außerdem: **Start** / **Stopp**, **Schnellwahl** des aktiven Netzes, Glocke (Benachrichtigungen), Hell/Dunkel/System, Sprache (Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية), Fensterknöpfe (Minimieren, Maximieren, Schließen).

Ziehen am Logo oder an leerem Header-Bereich verschiebt das Fenster. Start, Stopp, Schnellwahl und die Knöpfe rechts sind keine Ziehflächen.

## Erster Durchgang

1. Ollama muss laufen (Installer kann ihn anlegen und die kleinen Modelle `nomic-embed-text` und `llama3.2:1b` holen).
2. Unter **Einstellungen → Runtime** Verbindung prüfen; die Modellliste darf nicht leer sein.
3. Unter **Einstellungen → Hilfe-Chatbot** Provider und Chat-Modell setzen (Default: Ollama + `llama3.2:1b`). Embeddings bleiben ein **anderes** Modell (`nomic-embed-text`).
4. In der **Verwaltung** oder im Editor ein Netz anlegen, speichern, in der Schnellwahl **als aktiv** setzen.
5. **Start** in der Kopfzeile. Den Lauf siehst du unter **Monitoring**.

Das Dashboard zeigt fehlende Schritte als Einrichtungs-Karten.

## Ein minimales Netz

Im Editor (**Netzwerk**) mindestens:

1. **Chat-Eingabe** (`chat_input`) — höchstens eine
2. **Agent** — Systemprompt
3. **LLM** — Provider und Modell
4. **Ende** (`end`) — mindestens eines

Verbindungen (typisierte Anschlüsse, keine beliebigen Pfeile):

- Chat-Eingabe **Nachricht** → Agent **Nachricht**
- LLM **LLM** → Agent **LLM**
- Agent **Nachricht** → Ende

Optional: **Werkzeug** an den Agent-Anschluss **Werkzeug**, **Wissen** an **Wissen**. Speichern. In der **Verwaltung** „Als aktiv setzen“, wenn die Schnellwahl es noch nicht ist.

## Start und Stopp

**Start** startet **einen** Lauf des **aktiven** Netzes (Schnellwahl). Es läuft nie ein zweites Netz parallel. Ein zweiter Start wird abgelehnt, bis **Stopp**.

**Stopp** bricht den Lauf ab (Ergebnis **Abbruch**, nicht **Fehler**). Ollama bleibt an.

Ohne aktives Netz startet nichts. Ein ungültiges Netz (Validierungsfehler, fehlendes Modell) solltest du vor dem Start im Editor prüfen.

Während das aktive Netz läuft, ist **dieses** Dokument im Editor schreibgeschützt. Andere Netze kannst du weiter ansehen; Löschen des laufenden Netzes in der Verwaltung ist gesperrt.

Schließen des Fensters beendet den Lauf und die App. Ollama lebt weiter.

## Hilfe-Chatbot ist nicht der Netz-Chat

Unten rechts: Sprechblase = **Hilfe zur App** (diese Anleitung, Graph-Begriffe, optionale Websuche). Onboarding erklärt das beim ersten Öffnen.

Im **Monitoring** der Tab **Chat** = **Lauf-Chat** des Graphen (Knoten Chat-Eingabe). Er spricht mit dem Agentennetz.

Die beiden teilen **keinen** Verlauf, keine Tools und keine Zugänge. Die Hilfe nutzt **keine** MCP-Server.

## Ollama und Cloud

- **Lokal:** Ollama, in den Einstellungen als Runtime. Modelle listest und prüfst du dort. Die App lädt zur Laufzeit **keine** Modelle still nach.
- **Cloud:** Zugänge unter **Einstellungen → Zugänge** (xAI, OpenAI-kompatibel, Websuche, …). Listen zeigen nur eine **Maske**, nie das Geheimnis. LLM-Knoten und die Hilfe verweisen auf den Zugang per Name, nicht mit dem Schlüssel im Graphen.

OpenAI-kompatibel (zum Beispiel ein lokaler Server) braucht die Basis-URL unter **Runtime** und oft einen Zugang.

## Eine Instanz

Ein zweiter Start holt das vorhandene Fenster nach vorn. Es startet kein zweites Backend und kein zweiter Lauf.

## Portable und installiert

Die installierte App legt Daten unter dem lokalen App-Ordner **Agentus-Network** ab, nicht neben dem Programmordner. Die Portable-Variante (Datei `portable.txt` neben der EXE) legt Daten **neben der EXE** ab. WebView2 und Ollama musst du bei Portable selbst mitbringen.
