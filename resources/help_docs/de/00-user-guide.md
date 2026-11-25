# Agentus Network — Kurzanleitung

Agentus Network ist eine **lokale Desktop-App**. Du baust auf diesem PC Netze aus Agenten, Sprachmodellen und Werkzeugen, startest **einen** Lauf und siehst ihn live. Die Oberfläche gehört zur App selbst (eigenes Fenster), nicht zu Chrome und nicht zu einer `file://`-Seite.

Agentus startet eine **eigene Kopie** von Ollama auf eigenem Port, mit demselben Modellordner wie das installierte Ollama. Die Kopie endet mit der App. Das installierte Ollama und seine Modelle bleiben unberührt, auch beim Deinstallieren. Aktualisiert sich die Ollama-App, läuft Agentus weiter: Die App meldet die neuere Version und übernimmt sie auf Knopfdruck; dafür startet sie neu. Im Betrieb **Externes Ollama** nutzt die App die Adresse aus den Einstellungen; ist sie lokal und der Dienst aus, startet die App ein installiertes Ollama wie früher.

## Fenster und Navigation

Links (auf dem Telefon: Burger-Menü):

- **Dashboard** — Startseite, Einrichtung, aktives Netz, letzte Läufe
- **Netzwerk** — Editor (ein Graph)
- **Verwaltung** — Bibliothek aller gespeicherten Netze
- **Architekt** — entwirft mit dir ein Netz und legt es auf Wunsch an
- **Monitoring** — Live-Lauf
- **Historie** — abgeschlossene Läufe und Statistik

**Einstellungen** sitzen in der Kopfzeile (Zahnrad), nicht in der linken Navigation.

In der Kopfzeile außerdem: **Start** / **Stopp**, **Schnellwahl** des aktiven Netzes, Glocke (Benachrichtigungen), Hell/Dunkel/System, Sprache (Deutsch, English, Español), Fensterknöpfe (Minimieren, Maximieren, Schließen).

Ziehen am Logo oder an leerem Header-Bereich verschiebt das Fenster. Start, Stopp, Schnellwahl und die Knöpfe rechts sind keine Ziehflächen.

## Erster Durchgang

1. Ollama muss installiert sein. Beim ersten Start kopiert die App es einmalig in ihren Ordner (je nach Grafikkarte etwa 130 MB bis 1,2 GB) und startet die Kopie selbst. Das Setup kann Ollama anlegen, ihn kurz im Hintergrund starten und die kleinen Modelle `nomic-embed-text` und `llama3.2:1b` holen — nur, wenn Ollama antwortet. Ein stilles Setup ohne Modell-Schalter lädt keine Modelle. Ein fehlgeschlagener Download beendet das Setup trotzdem erfolgreich.
2. Unter **Einstellungen → Runtime** Verbindung prüfen; die Modellliste darf nicht leer sein.
3. Unter **Einstellungen → Hilfe-Chatbot** Provider und Chat-Modell setzen (Default: Ollama + `llama3.2:1b`). Embeddings bleiben ein **anderes** Modell (`nomic-embed-text`).
4. In der **Verwaltung** oder im Editor ein Netz anlegen, speichern, in der Schnellwahl **als aktiv** setzen.
5. **Start** in der Kopfzeile. Den Lauf siehst du unter **Monitoring**.

Das Dashboard zeigt fehlende Schritte als Einrichtungs-Karten.

## Ein minimales Netz

Im Editor (**Netzwerk**) mindestens:

1. **Chat** (`chat_input`) — höchstens einer
2. **Agent** — Systemprompt
3. **LLM** — Provider und Modell
4. **Ende** (`end`) — mindestens eines

Verbindungen (typisierte Anschlüsse, keine beliebigen Pfeile):

- Chat **Nachricht** → Agent **Nachricht**
- LLM **LLM** → Agent **LLM**
- Agent **Nachricht** → Ende

Optional **Orchestrator**: Chat nur an den Orchestrator, LLM an den Orchestrator, pro Agent ein **Kanal** vom Orchestrator an den Kanal des Agenten, **Nachricht** vom Orchestrator an **Ende**. Er ist die einzige Stimme im Lauf-Chat, stellt Rückfragen und ruft die Agenten nacheinander auf. Agententexte und interne Aufträge erscheinen nicht als Chatblasen. Den letzten Agententext hängt die App an den nächsten Auftrag, du musst ihn nicht in den Chat kopieren. Der Chat bleibt offen, bis er den Lauf beendet. Ohne Orchestrator bleibt jeder Agent eine eigene Kette über Nachricht und Übergabe. Ein Agent hängt entweder am Kanal oder an der Kette, nie an beidem.

Optional: **Werkzeug** oder **MCP** an den Anschluss **Werkzeug** von Agent oder Orchestrator, **Wissen** an **Wissen**. MCP-Server zuerst unter Einstellungen einrichten. Speichern. In der **Verwaltung** „Als aktiv setzen“, wenn die Schnellwahl es noch nicht ist.

## Start und Stopp

**Start** startet **einen** Lauf des **aktiven** Netzes (Schnellwahl). Es läuft nie ein zweites Netz parallel. Ein zweiter Start wird abgelehnt, bis **Stopp**.

**Stopp** bricht den Lauf ab (Ergebnis **Abbruch**, nicht **Fehler**). Ollama bleibt an.

Die Glocke meldet Start und Stopp nur bei Erfolg oder Misserfolg. Endet ein Lauf von selbst, kommt eine Meldung zu Erfolg, Fehler oder Abbruch.

Ohne aktives Netz startet nichts. Ein ungültiges Netz (Validierungsfehler, fehlendes Modell) solltest du vor dem Start im Editor prüfen.

Während das aktive Netz läuft, ist **dieses** Dokument im Editor schreibgeschützt. Andere Netze kannst du weiter ansehen; Löschen des laufenden Netzes in der Verwaltung ist gesperrt.

Schließen des Fensters beendet den Lauf, die App und ihre Ollama-Kopie. Das installierte Ollama lebt weiter.

## Hilfe-Chatbot ist nicht der Netz-Chat

Unten rechts: Sprechblase = **Hilfe zur App** (diese Anleitung, Graph-Begriffe, optionale Websuche). Onboarding erklärt das beim ersten Öffnen. Die Hilfe kennt die letzten drei Fragen samt Antworten; eine Rückfrage wie „und wie geht das?“ bezieht sich darauf. Löschst du den Hilfe-Verlauf in den Einstellungen, beginnt sie neu.

Im **Monitoring** der Tab **Chat** = **Lauf-Chat** des Graphen (Knoten Chat). Ohne Orchestrator ist das die Eingabe an die Agenten. Mit Orchestrator ist es das Gespräch: er kann nachfragen, bevor er Agenten aufruft.

Die beiden teilen **keinen** Verlauf, keine Tools und keine Zugänge. Die Hilfe nutzt **keine** MCP-Server.

## Ollama und Cloud

- **Lokal:** Ollama, in den Einstellungen als Runtime. Modelle listest und prüfst du dort. Die App lädt zur Laufzeit **keine** Modelle still nach.
- **Cloud:** Zugänge unter **Einstellungen → Zugänge** (xAI, OpenAI, Claude, Gemini, Websuche, …). Im LLM-Knoten wählst du Ollama, xAI, OpenAI, Claude oder Gemini. Cloud ohne passenden Zugang ist ungültig. Listen zeigen nur eine **Maske**, nie das Geheimnis. LLM-Knoten und die Hilfe verweisen auf den Zugang per Name, nicht mit dem Schlüssel im Graphen.

Eine eigene OpenAI-kompatible Basis-URL steht in Runtime nicht mehr zur Auswahl. Bestehende Zugänge dieser Art bleiben unter Zugänge sichtbar.

## Eine Instanz

Ein zweiter Start holt das vorhandene Fenster nach vorn. Es startet kein zweites Backend und kein zweiter Lauf.

## Portable und installiert

Die installierte App legt Daten unter dem lokalen App-Ordner **Agentus-Network** ab, nicht neben dem Programmordner. Die Portable-Variante (Datei `portable.txt` neben der EXE) legt Daten **neben der EXE** ab. WebView2 und Ollama musst du bei Portable selbst mitbringen.
