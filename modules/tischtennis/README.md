# homepi-tischtennis

Ein Tischtennisturnier unter Kollegen: Teilnehmer eintragen, Spielplan
auswürfeln, Ergebnisse erfassen — und eine Ansicht, die jeder mit dem Link
aufrufen kann, ohne ein Konto zu haben.

Artefakt im HomePI-Gateway. Grundgerüst kommt aus `homepi-core`:
Einstellungen, Logging, `/health`, `/info`, Fehlerformat, Anfrage-Kennung.

**Für Agenten: [AGENTS.md](AGENTS.md)** — dort steht, wie hier gearbeitet wird.

## Was es kann

| | |
|---|---|
| **Turnier** | Ein Bereich für alles: Namen eintragen, auswürfeln, Ergebnisse werten |
| **Auswürfeln** | Vorschau zuerst, beliebig oft neu, erst dann festschreiben. Die **Saat** wird gespeichert: mit ihr entsteht dasselbe Los wieder |
| **Drei Modi** | Gruppen + KO, reines KO, Schweizer System — der Zeitplan entscheidet, nicht die Software |
| **Ergebnis** | Ein Tippen auf den Namen des Siegers. Mehr wird nicht eingetragen |
| **Gleichstand** | Punktgleiche an der Grenze spielen gegeneinander — das Entscheidungsspiel steht von selbst im Plan |
| **Dashboard** | Ohne Anmeldung: wer an welchem Tisch spielt, wer als nächstes dran ist, und der Plan als Bild mit Gruppen und KO-Raster |
| **Glocke** | Wer seinen Namen antippt, wird benachrichtigt, sobald das Spiel vor seinem beginnt |

## Die Entscheidungen, die man kennen sollte

**Das Artefakt ist öffentlich.** Es ist das einzige im Haus. Der Grund ist die
Dashboard-Ansicht: zwanzig Kollegen sollen zusehen können, ohne dass jemand
zwanzig Konten anlegt. Lesen darf deshalb jeder, auch unangemeldet, und die
Kachel erscheint bei jedem Besucher.

**Schreiben bleibt angemeldet.** Ein offener Würfelknopf hieße: ein Kollege
lädt die Seite neu, drückt daneben, und der Spielplan ist ein anderer. Weil
bei einem öffentlichen Artefakt die Prüfung nicht mehr am Router hängt, trägt
jeder schreibende Endpunkt sein eigenes `erfordert` — und ein Test geht alle
Routen durch und verlangt das. Siehe
[`../../docs/11-anmeldung.md`](../../docs/11-anmeldung.md).

**Die Vorschau speichert nichts.** Erst würfeln, ansehen, nochmal würfeln,
dann übernehmen. Andersherum müsste jedes Verwerfen den halben Spielplan
wieder aufräumen — und ein Fehler dabei wäre ein Turnier mit Spielen aus zwei
verschiedenen Losen.

**Ein Ergebnis ist ein Sieger und sonst nichts.** Keine Sätze, keine Bälle,
keine Differenzen. Wer nebenbei ein Turnier führt, tippt einen Namen an und
nicht sechs Zahlen. Die Einstellung „Gewinnsätze“ steht in keinem Datensatz —
sie sagt nur den Spielern am Tisch, worauf sie spielen, und darf deshalb
abends noch gekürzt werden.

**Was dabei verloren geht, entscheidet ein Spiel.** Ohne Satzdifferenz gibt es
keinen Rechenweg, der Punktgleiche trennt; der direkte Vergleich wäre eine
stille Entscheidung. Also teilen sich Punktgleiche in der Tabelle den Platz,
und wenn dieser Gleichstand die Grenze zum Weiterkommen kreuzt, setzt der
Dienst von selbst ein Entscheidungsspiel an — bei dreien eine kleine Runde
jeder gegen jeden. Steht der Gleichstand oberhalb der Grenze und kommen
ohnehin beide weiter, bleibt er stehen: dann entscheidet er nichts.

**Das KO-Raster steht vor dem ersten Ball.** Ein Spiel, dessen Gegner noch
nicht feststeht, verweist auf die Nummer des Spiels, dessen Sieger bei ihm
einläuft: „Sieger aus Spiel 13". Damit lässt sich der Plan ausdrucken und an
die Wand hängen, bevor gespielt wird.

**Die Glocke lebt im Gerät.** Wer sich benachrichtigen lässt, steht im
`localStorage` des Browsers und nirgends sonst. Sie wirkt, solange die Seite
offen ist; für eine Meldung bei geschlossenem Tab bräuchte es echtes
Web-Push mit Service Worker und Zertifikat.

**Die Zeiten sind Schätzungen.** Aus Tischanzahl und „Minuten je Spiel"
gerechnet und mit jedem Ergebnis neu. Verlässlich sind nur zwei Dinge: ein
laufendes Spiel belegt seinen Tisch, und keine erwartete Zeit liegt in der
Vergangenheit.

## Entwickeln

```bash
make dev                  # Umgebung hoch (Frontend 5173, API 18000)
uv sync
uv run ptw . --now        # Unit-Tests im Watch-Modus, ohne Datenbank
```

Integrationstests brauchen die laufende Datenbank:

```bash
HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m 'not smoke'
```

Zum Durchklicken braucht es ein Recht auf diesem Artefakt:

```bash
homepi benutzer recht <name> tischtennis verwalter
```

## Ausrollen

```bash
homepi deploy -s tischtennis
```

Danach erscheint die Kachel auf der Startseite — ohne Frontend-Änderung.
