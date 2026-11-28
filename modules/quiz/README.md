# homepi-quiz

Quizrunden für einen Abend: **Jeder** kann eine Runde starten und leiten,
die Mitspieler antworten mit dem Handy, beides **ohne Konto**. Eine
Anzeigetafel zeigt Frage, Countdown und Rangliste am Beamer. Ein Konto
braucht nur, wer Fragenkataloge pflegt.

Nachgebaut aus dem eigenen Projekt Battle.Net (`D:\DevLibrary\Battle.Net`),
mit einem bewussten Unterschied: Dort kam man allein über den Namen zurück
in die Runde, und damit konnte jeder unter jedem Namen weiterspielen. Hier
gehört ein Name dem Gerät, das ihn gewählt hat.

**Für Agenten: [AGENTS.md](AGENTS.md)**

## Bereiche

| Bereich        | Adresse                          | Konto                |
| -------------- | -------------------------------- | -------------------- |
| Mitspielen     | `/modul/quiz/spielen?code=…`     | nein                 |
| Leiten         | `/modul/quiz/leiten`             | nein                 |
| Anzeigetafel   | `/modul/quiz/tafel?code=…`       | nein - nicht im Menü, das Dashboard öffnet sie |
| Kataloge       | `/modul/quiz/kataloge`           | `quiz` ab `leser`    |

Fragen schreiben und Kataloge freigeben braucht `nutzer`, einen Katalog
löschen `verwalter`:

```bash
homepi benutzer recht <name> quiz nutzer
```

## Leiten ohne Konto

- **Starten:** Unter „Leiten“ einen **freigegebenen** Katalog wählen oder ein
  eigenes Quiz hochladen (Battle.Net-ZIP oder hier gesichertes ZIP). Ein
  eigenes Quiz gehört nur dieser Runde und taucht unter „Kataloge“ nicht auf.
- **Moderatorcode:** Nach dem Start steht er genau einmal da, mit QR-Code
  (`/modul/quiz/leiten?zugang=…`). Damit übernimmt jedes Gerät die Leitung.
  Gespeichert wird nur sein SHA-256; das Gerät, das ihn eingelöst hat, merkt
  sich die Leitung in einem Cookie je Runde. Wer ihn verloren hat, stellt im
  Dashboard einen neuen aus - der alte gilt dann nicht mehr.
- **Freigabe:** Wer `nutzer` hat, gibt im Katalog „Für alle frei“. Ohne
  Freigabe kann ein Gast den Katalog nicht starten und nicht einmal sehen.
- **Aufräumen:** Runden ohne Konto verschwinden **48 Stunden nach der letzten
  Aktivität**, samt eigenem Quiz. Geprüft wird beim Laden der Startseite und
  beim Starten - einen Zeitplaner braucht es dafür nicht.
- **Grenzen:** höchstens 40 offene Runden ohne Konto, ein eigenes Quiz
  höchstens 20 MB.

Mit Konto (`nutzer`) leitet man jede Runde auch ohne Code; ein `leser` darf
zusehen.

## Dashboard

Die Leitung ist ein Dashboard in Bildschirmhöhe, ohne Seitenscrollen: links
die Fragen, in der Mitte die Bühne mit **der einen** nächsten Handlung
(zeigen, sperren, auflösen, nächste Frage), rechts die Spieler. Was nicht
dauernd zu sehen sein muss, liegt hinter einem Symbol in der Kopfleiste und
öffnet sich als Dialog: QR-Code zum Mitspielen, Anzeigetafel, Teams,
Beitritt, Auswertung, Moderatorcode, Beenden. Ein Klick auf einen Spieler
öffnet Punktkorrektur, Wiederkehrcode und Entfernen.

## Fragetypen

Alle aus Battle.Net, jeweils mit eigener Eingabe am Handy - die acht aus der
Spezifikation und die zwei, die der Battle.Net-Editor zusätzlich kannte:

| Typ           | Spieler                       | Bewertung                                        |
| ------------- | ----------------------------- | ------------------------------------------------ |
| Freitext      | Textfeld                      | gleich einer Lösung, ohne Groß/klein             |
| Zahl          | Zahlfeld                      | innerhalb der Toleranz                           |
| Schätzfrage   | Schieberegler                 | wer am nächsten liegt (bei Gleichstand alle)     |
| Auswahl       | eine oder mehrere Optionen    | +1 je richtige, −1 je falsche, nie unter 0       |
| Buzzer        | großer Knopf                  | Leitung: richtig, oder falsch und der Nächste    |
| Bildfrage     | Bild + Textfeld               | wie Freitext, ohne Lösung von Hand               |
| Bild antippen | Tipp ins Bild                 | innerhalb eines Zielkreises                      |
| Sortieren     | Liste mit ↑/↓                 | anteilig nach richtigen Plätzen                  |
| Zuordnen      | je Zeile eine Auswahl         | anteilig nach richtigen Paaren                   |
| Bildauswahl   | Bilder als Antworten          | wie Auswahl                                      |

Jede Frage kann zusätzlich ein Bild und einen **Ton** tragen. Den Ton spielt
die Leitung oder die Anzeigetafel ab, nicht das Handy.

`punkte` einer Frage ist immer die Höchstzahl. Jede Bewertung lässt sich
danach von Hand ändern, dazu kommen Korrekturen ±1 je Spieler.

## Spieler ohne Konto

- **Beitritt** mit Rundencode und Namen. Der Name ist je Runde **einmal**
  vergeben, verglichen nach NFKC + `casefold`: `ANNA`, `anna` und `Ａｎｎａ`
  sind derselbe. Unsichtbare Zeichen (Kategorie C, etwa Nullbreite) werden
  abgelehnt, sonst ließe sich ein Doppelgänger bauen. Die Datenbank sichert
  das mit einer Eindeutigkeit, nicht eine Vorabprüfung.
- **Token**: 256 Bit aus `secrets`, als `httponly`-Cookie
  `homepi_quiz_<CODE>` (`SameSite=Lax`, `secure` in Produktion, zwei Tage).
  In der Datenbank steht nur der SHA-256, wie bei den Sitzungen in
  homepi-core.
- **Gerät verloren**: Die Leitung stellt einen Wiederkehrcode aus (acht
  Zeichen, 15 Minuten, einmal). Mit Namen und Code bekommt der Spieler ein
  neues Token; das alte ist damit wertlos. Über den Namen allein kommt
  niemand hinein.
- **Was öffentlich ist**: Stand der Runde mit Name und Punkten je Platz, die
  Frage erst nach dem Zeigen, die Lösung erst nach dem Auflösen, das Bild erst
  mit der Frage. Kataloge sind nie öffentlich - dort stehen die Lösungen.
- Die Sortier-Elemente haben Kennungen, die ihren Platz nicht verraten; die
  Mischung ist je Frage fest, damit die Liste beim Abruf nicht springt.

## Teams

Die Leitung legt je Runde Teams an. Ab dann wählt jeder neue Spieler beim
Beitritt eines; vor dem Start darf er selbst wechseln, danach setzt nur die
Leitung um. Ein Team zählt die **Summe** seiner Mitglieder, und beim Buzzer
drückt jedes Team einmal. Ohne Teams spielt jeder für sich.

## Beitritt schließen

Ein Code am Beamer ist von jedem abfotografierbar, und die Seite ist aus dem
Internet erreichbar. Deshalb kann die Leitung den Beitritt schließen - dann
kommt nur noch zurück, wer einen Wiederkehrcode hat.

## Import, Export, Auswertung

- **Battle.Net übernehmen:** Unter „Kataloge“ ein gespeichertes Battle.Net-Quiz
  hochladen (das ZIP aus `backend/data/quizzes/` mit `quiz.json`, Bilder und
  Ton als Data-URL). Was nicht passt, steht danach als Hinweis im Katalog.
  Bilder von **fremden Adressen werden nicht geholt** - der Pi greift nicht auf
  Zuruf einer Datei ins Internet. Das XML-Format der Spezifikation gab es nur
  als Beispieldatei und wird nicht übernommen.
- **Sichern:** „Als ZIP sichern“ schreibt `katalog.json` plus `medien/`. Dasselbe
  ZIP lässt sich wieder übernehmen, ohne Verlust.
- **Auswertung:** In der Runde je gespielter Frage, wer was geantwortet hat,
  dazu das Ergebnis als CSV (Semikolon, BOM - öffnet in Excel richtig).
  Spielernamen, die mit `=`, `+`, `@` oder `-` beginnen, werden dort als Text
  geschrieben und nicht als Formel.

## Live

Kein WebSocket: Handy, Tafel und Leitung fragen alle anderthalb Sekunden nach,
wie die Tischtennis-Tafel. Die Frist rechnet mit der Uhr des Servers (`jetzt`
in jeder Antwort), die Buzzer-Reihenfolge ist die Reihenfolge des Eintreffens
(Sequenz in der Datenbank), nicht die Uhr des Handys.

## Entwickeln

```bash
make dev N=quiz
cd modules/quiz && uv run ptw . --now
HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
  uv run pytest -m 'not smoke' --cov
```

## Prüfen

Neben Unit- und Integrationstests eine eigene Oberflächenreise
(`services/web/e2e/quiz.spec.ts`, in `make e2e` und der CI-Matrix):
Einrichtung, Recht, Battle.Net-Import, Spieler ohne Konto in eigenem
Browser-Kontext, Namensschutz, Antwort, Auflösung, Podest, 375 px.

## Ausrollen

Tabellen `quiz_*`. Seit Teams und Medien zusätzlich eine Spalte an einer
schon laufenden Tabelle - auf dem Pi **in dieser Reihenfolge**:

```bash
docker exec -i postgres psql -U app -d app -v ON_ERROR_STOP=1 \
  -f - < scripts/migrationen/2026-11-28-quiz-beitritt-offen.sql
docker compose exec gateway homepi schema anlegen
```
