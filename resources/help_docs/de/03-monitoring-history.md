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

Leerzustand: **Kein Lauf** — Starte über die Kopfzeile. Zeigt das aktive Netz oder den Hinweis, dass die Schnellwahl leer ist. Getrennt / Fehler / Startet / Stoppt haben eigene Texte. Letzte Werte können ausgegraut bleiben, bis die Verbindung steht.

## Während eines Laufs

Kopfbereich: Lauf-ID, Startzeit, Dauer, grober Schritt, aktive LLMs (lokal vs. Cloud).

**Netz (nur Lesen):** derselbe Graph, Knotenfarben nach Status (Leerlauf, wartend, läuft, fertig, Fehler). Klick auf einen Knoten filtert Log/Aktivität und öffnet das Knotendetail (Rolle, Status, wartet auf LLM/Werkzeug/Eingabe, letzte Meldung, Token). Kein Bearbeiten, kein zweiter Editor.

**Aktivität:** aktuelle Knoten, Fortschritt „Schritt x von y“, Token ein/aus, optional Kontextfenster.

**Host-Ressourcen:** CPU, RAM, GPU/VRAM **dieses PCs**, nicht nur der App. Ohne lokale GPU (typisch bei Cloud-Läufen) erscheint ein Hinweis, kein Fehler.

## Netz-Chat (Monitoring)

Tab **Chat**: Nachrichten an die **Chat-Eingabe** des laufenden Graphen. Nur aktiv, solange der Lauf läuft. „Eingabe nötig“ am Chat-Knoten: der Graph wartet auf die erste Zeile.

Das ist **nicht** die Hilfe-Sprechblase. Verlauf und Tools sind die des Netzes.

## Log (Monitoring)

Tab **Log**: Zeilen mit Level (Debug, Info, Warnung, Fehler), Knoten, Zeit. Neueste oben. Pause hält das Nachziehen; „Zu neuesten“ springt wieder ans Ende. Filter: Suche, Level ab, ein Knoten, nur Fehler. Export der sichtbaren Zeilen.

Payloads und Meldungen **maskieren** Geheimnisse (zum Beispiel `Bearer`, Schlüsselpräfixe). Nicht ungefiltert weitergeben.

## Historie

Ribbon: Aktualisieren, Löschen ausgewählter Läufe, Logs exportieren, alte Einträge nach Aufbewahrung bereinigen (siehe Einstellungen → Daten, Default 90 Tage).

**Ein Filter** steuert alles: Zeitraum (Heute, 7/30 Tage, von–bis), Netz, Modell, Suche (Lauf-ID, Netz, Fehler). KPIs, Diagramm „Läufe nach Tag“, häufigste Fehler, Tabs Historie / Pro Modell / Pro Netz und die Liste verwenden denselben Filter.

## Ergebnisse eines Laufs

| Ergebnis | Bedeutung |
|----------|-----------|
| Läuft | noch aktiv — in der Historie nur als Link |
| Erfolg | normal beendet |
| Fehler | Schritt oder Dienst fehlgeschlagen |
| Abbruch | Stopp in der Kopfzeile oder Fenster zu |
| Timeout | Zeitüberschreitung |

**Abbruch ist nicht Fehler.** Timeouts und Abbrüche zählen in den KPIs getrennt (Fußzeile bei „Fehler“).

## Lauf-Detail

Rechte Seite oder eigene Ansicht: Meta, Mini-Graph, Tabs **Log**, **Schritte**, **Chat**. Schritte: Knoten, Rolle, Status, Fehler. Chat: Transkript, read-only. Einzelnes Log exportieren.

Löschen von Historieneinträgen ändert die gespeicherten Netze nicht.
