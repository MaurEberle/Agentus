# Dashboard

Die Startseite. Sie fasst Einrichtung, aktives Netz und letzte Läufe zusammen. Sie ist **kein** Live-Monitoring und **kein** Archiv — dafür gibt es eigene Seiten.

## Einrichtung

Die Karte **Einrichtung** erscheint, wenn etwas für den ersten Lauf fehlt, zum Beispiel:

- Ollama nicht erreichbar → Link **Runtime prüfen**
- Hilfe-Profil ohne Provider oder Modell → **Hilfe konfigurieren**
- Noch kein Netz → **Neues Netz** oder **Netz importieren**

Ist die Umgebung vollständig, bleibt die Karte aus. Fehlende optionale Modelle nach einem stillen Setup ohne Pull sind kein zweiter Assistent: Runtime-Ping oder der Hilfe-Chat zeigen den Fehler.

## Host-Ressourcen

Dieselbe Karte wie unter **Monitoring**: CPU, Arbeitsspeicher und GPU/VRAM **dieses PCs**, nicht nur der App-Prozess. Die Werte aktualisieren sich laufend, auch ohne aktiven Lauf.

## Status

Zeigt, ob der Dienst **gestoppt**, **startet**, **läuft** oder **stoppt**, plus das aktive Netz. Während der Indizierung von Wissen steht dort **Wissen wird indiziert** und der Name des Knotens. Dieselbe Zeile hängt an der Start-Schaltfläche. Bei laufendem Netz: Link **Monitoring** und optional „läuft seit …“. Ohne Schnellwahl: Hinweis und Link zur **Verwaltung**.

Start und Stopp bleiben in der **Kopfzeile**, nicht auf dieser Karte.

## Aktives Netz

Name, Knoten-/Kantenzahl, Gültig/Ungültig, wann zuletzt geändert. Aktionen: **Bearbeiten** (Editor), **Bibliothek**, **Neues Netz**.

Ungültig heißt: Validierung im Editor schlägt fehl (zum Beispiel fehlendes Modell an einem LLM-Knoten). Solche Netze solltest du nicht starten.

## Zuletzt verwendet

Kurze Liste gespeicherter Netze nach letzter Nutzung. Klick öffnet den Editor. Leer: noch keine Netze.

## Letzte Läufe

Die jüngsten Einträge aus der Historie (Erfolg, Fehler, Abbruch, Timeout, oder noch laufend). Ein laufender Eintrag führt ins **Monitoring**, abgeschlossene in die **Historie**. Ist der Historie-Store defekt, erscheint ein Hinweis mit Link **Daten**.

## Letzte 7 Tage

Kleine Statistik: Anzahl Läufe, erfolgreich, fehlgeschlagen. Link **Historie** für Filter und Diagramme. Das ist eine Kurzfassung, kein zweites Archiv.

## Umgebung

- Ollama erreichbar oder nicht, grobe Modellanzahl
- Store-Probleme (Einstellungen, Hilfe, Workspace, Historie)
- **Sparmodus**, wenn die Hilfe auf das Fallback-Modell ausgewichen ist

Links: **Daten**, Runtime.

## Schnellzugriff

**Neues Netz**, **Import** (Verwaltung), **Runtime**. Dieselben Aktionen erreichst du über Navigation und Einstellungen.
