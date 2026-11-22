# Monitoring und Historie

**Monitoring** = jetzt, ein Lauf. **Historie** = Archiv und Statistik. Die Historie ist **kein** zweites Dashboard und **kein** Live-Log. Start und Stopp bleiben in der **Kopfzeile**.

## Live vs. Archiv

| | Monitoring | Historie |
|---|------------|----------|
| Wann | Dienst startet, läuft oder stoppt | nach Ende des Laufs (und Link, solange er noch läuft) |
| Graph | Mini-Graph, nur Lesen, Knotenstatus | gespeicherter Stand, keine Live-Aktualisierung |
| Log | Strom, neueste oben, Pause möglich | festgehaltene Zeilen, filterbar |
| Chat | Lauf-Chat, nur während des Laufs | gespeichertes Transkript, nicht weiterschreiben |

Ein noch laufender Historieneintrag ist nur ein Sprung ins Monitoring („Live ansehen“).

## Monitoring ohne Lauf

Ohne aktiven Lauf zeigt die Seite den **letzten gespeicherten Lauf** zum Ansehen (Graph, Aktivität, Log, Chat). Ein Hinweis sagt, dass nichts live ist. Ganz leer ist die Seite nur, wenn noch kein Lauf gespeichert ist: **Kein Lauf**, plus das aktive Netz oder der Hinweis, dass die Schnellwahl leer ist. Getrennt / Fehler / Startet / Stoppt haben eigene Texte. Während der Indizierung wechselt der Start-Hinweis auf den Namen des Wissensknotens. Letzte Werte können ausgegraut bleiben, bis die Verbindung steht.

## Während eines Laufs

Kopfbereich: Lauf-ID, Startzeit, Dauer, grober Schritt, aktive LLMs (lokal vs. Cloud).

**Netz (nur Lesen):** derselbe Graph, Knotenfarben nach Status (Leerlauf, wartend, läuft, fertig, Fehler). Klick auf einen Knoten filtert Log/Aktivität und öffnet das Knotendetail (Rolle, Status, wartet auf LLM/Werkzeug/Eingabe/Index/Denken, letzte Meldung, Token). Kein Bearbeiten, kein zweiter Editor.

Hängt Wissen an einem Agenten, zeigt der Start den Lauf schon während der Indizierung: der Wissensknoten läuft mit Wartegrund **Index**, das Log nennt Lesen und Embeddings, die Kopfzeile und das Dashboard denselben Namen. Ein bereits aktueller Index wird übersprungen und nur kurz als aktuell gemeldet.

**Aktivität:** Oben die Live-Werte: Token pro Sekunde des Modells, das gerade schreibt; wie voll sein Kontextfenster ist (Balken, gelb ab 75 %, rot ab 90 %); Ausgabe-Token des ganzen Laufs. Darunter in einer Zeile, wer gerade arbeitet, und der Auftrag des arbeitenden Agenten in voller Länge, zum Kopieren. Wartet der Lauf auf dich, steht das hervorgehoben darüber.

Chat und Log stehen über Netz und Aktivität. Die drei Karten behalten ihre Höhe, wenn das Fenster größer wird; am Rand dazwischen lässt sich die Größe ziehen. Die eingestellten Größen bleiben nach dem Schließen der App erhalten.

**Host-Ressourcen:** CPU, RAM, GPU/VRAM **dieses PCs**, nicht nur der App. Ohne lokale GPU (typisch bei Cloud-Läufen) erscheint ein Hinweis, kein Fehler.

## Netz-Chat (Monitoring)

Tab **Chat** (beim Start eines Laufs, wenn der Graph einen Chat-Eingang hat): Gespräch des laufenden Graphen. Nur aktiv, solange der Lauf läuft. Ohne Orchestrator wartet der Chat auf die erste Zeile und gibt sie an die Kette. Mit Orchestrator sprichst du nur mit ihm. Vor der ersten Nachricht kannst du dort unter **An Vorlauf anknüpfen** einen früheren Lauf dieses Netzes wählen (Zeit, Ergebnis, Anfang des Auftrags). Vor seiner ersten Entscheidung liest der Orchestrator dann dessen Bericht: Aufträge, Agentenaufrufe, Ende, geänderte Dateien und, falls jener Lauf selbst an einen früheren anknüpfte, dessen Vorwissen. Daraus schreibt er sich ein Vorwissen von höchstens 3000 Zeichen; es erscheint im Chat. Es beschreibt nur den früheren Lauf, wie er endete; deine neue Nachricht fließt nicht ein, und was die Agenten im neuen Lauf berichten, gilt als neuer. Nur der Orchestrator bekommt es, den Agenten gibt er weiter, was sie brauchen. Scheitert die Auswertung, bekommt er den gekürzten Bericht. Der Lauf wartet nur bei einer Rückfrage. Agententexte und interne Aufträge siehst du hier nicht. Bei einer Rückfrage erscheinen ein Hinweis in der Glocke und in der Kopfzeile; das Taskleisten-Symbol blinkt, wenn das Fenster im Hintergrund liegt. **Generierung stoppen** bricht die laufende Antwort ab. Mit Orchestrator bleibt der Lauf offen und wartet auf deine nächste Nachricht; in einer Kette ohne Orchestrator endet der Lauf als Abbruch.

Das ist **nicht** die Hilfe-Sprechblase. Verlauf und Tools sind die des Netzes.

## Log (Monitoring)

Tab **Log**: eine Zeile pro Ereignis als Satz, neueste oben. Vorn stehen Zeit, Symbol (Entscheidung, Agent, Werkzeug, Modell, Grenze) und Status (✓ erfolgreich, ✗ fehlgeschlagen, ⚠ Warnung), rechts die Dauer. Beispiele: „Senior: liest src/App.tsx · 41 Zeilen“, „Senior: führt aus: npm run build · Exit-Code 1: …“, „Chef: ruft Senior: RTL korrigieren“. Pause hält das Nachziehen; „Zu neuesten“ springt wieder ans Ende.

**Ansicht:**

- **Wichtig** (Standard): Entscheidungen des Orchestrators, Aufträge, Ergebnisse, Grenzen, Warnungen und Fehler.
- **Alles**: zusätzlich jeder Werkzeug- und Modellaufruf.
- **Debug**: zusätzlich Debug-Zeilen, zum Beispiel Modellstarts.

**Gruppen:** Jeder Agentenauftrag ist eine Gruppe. Die Kopfzeile nennt Agent, Auftrag und Ergebnis (Werkzeugaufrufe, geänderte Dateien, Dauer); ein Klick auf den Pfeil zeigt die Zeilen darunter. Ein laufender Auftrag ist aufgeklappt.

**Filter:** Die Suche findet den angezeigten Text, Auftrag, Ergebnis, Pfad und Befehl. Der Knotenfilter zeigt auch Werkzeug- und Modellaufrufe, die dieser Agent gemacht hat. Dazu „nur Fehler“.

**Detail:** Klick auf eine Zeile. Werkzeuge zeigen Pfad oder Befehl, Ergebnis, Fehler und den Hinweis an das Modell; Agenten Auftrag und Ergebnis; Modellaufrufe Token, Dauer, Antwort und Denktext. Die Rohdaten (JSON) sind aufklappbar.

**Zusammenfassung:** Am Ende eines Laufs steht oben eine Karte: Ausgang, Dauer, Agentenaufrufe je Agent (mit dem höchsten Anteil am Kontextfenster), Modellaufrufe und Token, Werkzeugaufrufe, geänderte Dateien, erreichte Grenzen.

**Kontext:** Die Abschlusszeile jedes Agentenauftrags nennt die größte Anfrage im Verhältnis zum Fenster (etwa „größte Anfrage 30.896 von 202.752 Token (15 %)“) und wie oft verdichtet wurde. Meldet das Modell innerhalb eines Auftrags ohne Verdichtung deutlich weniger Eingabe-Tokens als im Schritt davor, oder am Fensterrand viel weniger als geschätzt, warnt das Log: **Verlauf vermutlich abgeschnitten**. Dann fehlt dem Modell wahrscheinlich der Anfang des Verlaufs; meist ist das Fenster am LLM-Knoten zu klein.

**Export:** „Als Text exportieren“ speichert die angezeigten Zeilen als Markdown, „JSON“ als JSON Lines. Dateiinhalte stehen im Log nur gekürzt (2 KB), Modellantworten bis 8 KB.

Payloads und Meldungen **maskieren** Geheimnisse (zum Beispiel `Bearer`, Schlüsselpräfixe). Nicht ungefiltert weitergeben.

## Historie

Ribbon: Aktualisieren, Löschen ausgewählter Läufe, Logs exportieren, alte Einträge nach Aufbewahrung bereinigen (siehe Einstellungen → Daten, Default 90 Tage; bei „Unbegrenzt“ gibt es den Knopf nicht).

**Ein Filter** steuert alles: Zeitraum (Heute, 7/30 Tage, von–bis), Netz, Modell, Suche (Lauf-ID, Netz, Fehler). KPIs, Diagramm „Läufe nach Tag“, häufigste Fehler, Tabs Historie / Pro Modell / Pro Netz und die Liste verwenden denselben Filter.

**Häufigste Fehler** zeigt jede Fehlerart der fehlgeschlagenen Läufe als Fläche: je häufiger, desto größer, die Farbe nach Fehlerklasse (Orchestrator, LLM, Werkzeug, Timeout …). Große Flächen nennen auch Anteil, Knoten und das letzte Auftreten; bei kleinen steht das im Tooltip. Ein Klick filtert Kennzahlen, Diagramm und Liste auf diese Fehlerart; ein zweiter Klick oder das ✕ im Kopf hebt den Filter auf. Die Flächen bleiben dabei stehen.

Diagramm und Fehlerliste sowie Lauf-Liste und Detail lassen sich wie im Monitoring am Rand ziehen. Die eingestellten Größen bleiben nach dem Schließen der App erhalten.

## Ergebnisse eines Laufs

| Ergebnis | Bedeutung |
|----------|-----------|
| Läuft | noch aktiv — in der Historie nur als Link |
| Erfolg | normal beendet |
| Fehler | Schritt oder Dienst fehlgeschlagen |
| Abbruch | Stopp in der Kopfzeile, Fenster zu, oder App-Ende (auch nach Absturz beim nächsten Start) |
| Timeout | Zeitüberschreitung |

**Abbruch ist nicht Fehler.** Timeouts und Abbrüche zählen in den KPIs getrennt (Fußzeile bei „Fehler“).

## Lauf-Detail

Rechte Seite oder eigene Ansicht: Meta, Mini-Graph, Tabs **Log**, **Schritte**, **Chat**. Das Log sieht aus wie im Monitoring: Ansichten, Gruppen, Zusammenfassung, Export als Text. Ältere Läufe haben weniger Angaben (kein Auftrag, kein Aufrufer). Schritte: Knoten, Rolle, Status, Fehler. Chat: Transkript, read-only. Einzelnes Log exportieren.

Löschen von Historieneinträgen ändert die gespeicherten Netze nicht.
