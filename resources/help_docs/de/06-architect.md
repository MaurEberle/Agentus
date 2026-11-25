# Architekt

Der **Architekt** ist ein Chat-Agent, der mit dir ein Netz entwirft: Agenten, Prompts, Modelle und Werkzeuge. Auf Wunsch legt er es an oder ändert ein bestehendes. Er kennt die Knotentypen, Felder und Werkzeuge der installierten App-Version. Der Hilfe-Chatbot erklärt dagegen die App selbst; beide sind getrennt.

## Starten

Der Architekt startet nie von selbst. Im Modul **Architekt** wählst du Anbieter, Zugang (bei Cloud) und Chat-Modell und klickst **Sitzung starten**.

- **Ollama-Modelle** brauchen Werkzeugaufrufe und mindestens 4B Parameter; kleinere oder solche ohne Werkzeuge sind gesperrt. Bis 14B gibt es einen Hinweis.
- **GPU:** Gestartet wird nur, wenn das Modell (und ein lokales Embedding-Modell für die Beispiele) in den freien Grafikspeicher passt. Reichen Grafik- und Arbeitsspeicher zusammen, bietet die App **Trotzdem starten (langsam)** an.
- **Läuft ein Netz**, warnt die App deutlich, bevor sie startet.
- **Hilfe-Chatbot:** Laufen Architekt und Hilfe-Chat beide lokal, pausiert der Hilfe-Chat während der Sitzung. Der Architekt hat Vorrang.
- **Sitzung beenden** bricht eine laufende Antwort ab und entlädt das Ollama-Modell. Nach **15 Minuten** ohne Eingabe endet die Sitzung von selbst; Verlauf, Steckbrief und Entwurf bleiben, Fortsetzen startet neu.

## Steckbrief und Entwurf

- **Steckbrief:** Ziel, Eingabe, Ergebnis, Quellen, lokal oder Cloud, Werkzeuge, Rahmen. Der Architekt füllt ihn im Gespräch; du kannst jedes Feld selbst ändern.
- **Entwurf:** rechts als Graph, mit Prüfergebnis (Fehler, Hinweise) und Knotenliste. Fehler korrigiert der Architekt selbst; nach drei vergeblichen Versuchen fragt er dich.
- **Bauanleitungen:** linear, Orchestrator, Wissens-Chat, Router-Triage. Der Architekt liest die passende, bevor er entwirft.

## Netze einlesen

**Netz einlesen …** wählt ein gespeichertes Netz, **zum Ändern** oder **als Vorlage** (dann entsteht am Ende ein neues Netz). Bittet der Architekt selbst darum, erscheint über der Eingabe eine Karte; eingelesen wird erst nach deinem Klick.

Beim Ändern zeigt die Vorschau neue Knoten grün und geänderte gelb, darunter die Liste der Änderungen.

**Cloud-Modelle:** Sie sehen Aufbau und Prompts eines Netzes nur, wenn du es ausdrücklich einliest. Ordnerpfade bleiben ihnen verborgen, außer du erlaubst es unter **Einstellungen → Architekt**.

## Abschließen

Ist der Entwurf gültig, schlägt der Architekt den Abschluss vor, oder du klickst **Abschließen …**. Der Abschlussdialog zeigt Zusammenfassung, Aufbau, bei Änderungen die Unterschiede zur gespeicherten Version und riskante Bausteine (Terminal ohne Einschränkung, Dateizugriff mit Löschen, HTTP mit Zugang).

Optionen: **Als aktiv setzen**, **Prompts in die Bibliothek übernehmen** (aus per Vorgabe), **Danach im Editor öffnen**. Gespeichert wird erst mit **Anlegen** bzw. **Änderungen übernehmen**, und zwar als neue Version mit Quelle „Architekt“.

- **Läuft das Netz**, wird nicht übernommen.
- **Wurde das Netz seit dem Einlesen woanders gespeichert**, meldet der Dialog das: **Neu einlesen** verwirft den Entwurf, **Trotzdem übernehmen** legt ihn als neue Version obenauf.
- **Letzte Übernahme rückgängig** holt die Version vor der Übernahme zurück, als neue Version.

## Recherche

- **Websuche:** eigene Einstellungen unter **Einstellungen → Architekt**, getrennt vom Hilfe-Chat; aus per Vorgabe.
- **Hugging Face:** Der Architekt sucht passende GGUF-Modelle und liest Quants, Größen und Lizenz. Herunterladen musst du selbst unter **Modelle → Hub**.
- **Begrenzungen:** Werkzeugaufrufe pro Antwort, Websuchen und Hub-Abfragen pro Sitzung. 0 schaltet Websuche bzw. Hub-Suche ab.

## Beispiele

Der Architekt sucht Beispielnetze, die zum Steckbrief passen. Mitgelieferte Beispiele kommen mit einem späteren Update. **Eigene Netze als Beispiele nutzen** (Einstellungen → Architekt) nimmt nur gültige Netze; Cloud-Modelle sehen dabei keine Prompts. Ohne Embedding-Modell sucht der Architekt über Stichworte.

## Sitzungen

Links stehen die Sitzungen mit Verlauf, Steckbrief und Entwurf. **Markdown** exportiert eine Sitzung, **Löschen** entfernt sie; angelegte Netze bleiben.
