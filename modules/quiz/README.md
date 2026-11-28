# homepi-quiz

Quizrunden für einen Abend: Die Leitung schreibt Fragenkataloge und steuert
die Runde, die Mitspieler antworten mit dem Handy **ohne Konto**, eine
Anzeigetafel zeigt Frage, Countdown und Rangliste am Beamer.

Nachgebaut aus dem eigenen Projekt Battle.Net (`D:\DevLibrary\Battle.Net`),
mit einem bewussten Unterschied: Dort kam man allein über den Namen zurück
in die Runde, und damit konnte jeder unter jedem Namen weiterspielen. Hier
gehört ein Name dem Gerät, das ihn gewählt hat.

**Für Agenten: [AGENTS.md](AGENTS.md)**

## Bereiche

| Bereich        | Adresse                          | Konto                |
| -------------- | -------------------------------- | -------------------- |
| Mitspielen     | `/modul/quiz/spielen?code=…`     | nein                 |
| Anzeigetafel   | `/modul/quiz/tafel?code=…`       | nein                 |
| Runden         | `/modul/quiz/runden`             | `quiz` ab `leser`    |
| Kataloge       | `/modul/quiz/kataloge`           | `quiz` ab `leser`    |

Leiten und Fragen schreiben braucht `nutzer`, einen Katalog löschen
`verwalter`:

```bash
homepi benutzer recht <name> quiz nutzer
```

## Fragetypen

Die acht aus Battle.Net, jeweils mit eigener Eingabe am Handy:

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

## Ausrollen

Neue Tabellen (`quiz_*`). Auf dem Pi nach dem Update einmal:

```bash
docker compose exec gateway homepi schema anlegen
```

## Offen

- Teams (in Battle.Net angelegt, dort ungetestet) - bewusst später.
- Import der Battle.Net-Kataloge (ZIP mit `questions.xml` und Medien).
