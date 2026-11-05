# homepi-haushaltsbuch

Konten, Fixkosten und Rücklagen — für einen Haushalt mit zwei Geldbeuteln.

Artefakt im HomePI-Gateway. Grundgeruest kommt aus `homepi-core`:
Einstellungen, Logging, `/health`, `/info`, Fehlerformat, Anfrage-Kennung.

**Fuer Agenten: [AGENTS.md](AGENTS.md)** — dort steht, wie hier gearbeitet wird.

---

## Was es loest

Ein gemeinsames Konto, von dem die gemeinsamen Kosten abgehen, und zwei
Gehaltskonten, von denen beide ihren Anteil einzahlen. Dazu Kosten, die nicht
monatlich kommen: die Kfz-Versicherung wird einmal im Januar abgebucht, also
liegt jeden Monat ein Zwoelftel auf dem Sparkonto bereit.

Dieses Artefakt rechnet das aus. Es ist ein **Plan**, keine Buchhaltung: es
kennt keine Kontostaende und keine einzelnen Umsaetze. Es beantwortet eine
Frage — *wer zahlt diesen Monat wie viel wohin ein, und was muss zurueckgelegt
sein?*

## Die fuenf Begriffe

| | |
|---|---|
| **Person** | Wer am Haushalt beteiligt ist. Nicht derselbe wie ein HomePI-Benutzer: ein Haushalt laesst sich sonst nicht fuehren, solange nicht beide ein Konto auf dem Pi haben |
| **Konto** | Wo Geld liegt. Ohne Inhaber ist es gemeinschaftlich — und nur dort gibt es etwas aufzuteilen. Die Art (`verteiler`, `verbrauch`, `sparen`, `ruecklage`) sagt, wozu es da ist |
| **Kategorie** | Fasst Posten zusammen. `zaehlt_als_sparen` trennt Ruecklage und Anlage vom Verbrauch — davon haengt die Sparquote ab |
| **Posten** | Eine wiederkehrende Buchung. `betrag` ist immer das, was die **Bank abbucht**; die Monatsrate wird gerechnet, nie gespeichert |
| **Anteil** | Wie viel eines gemeinsamen Postens auf eine Person entfaellt — als Gewicht (1:2), nicht als Prozent |

## Drei Entscheidungen, die nicht offensichtlich sind

**Gewichte statt Prozent.** „1:2" bleibt richtig, wenn sich der Betrag aendert;
„33,3 % / 66,7 %" nicht, und die Summe muss nirgends 100 ergeben.

**Die Monatsrate wird aufgerundet.** 169 Euro im Jahr sind 14,0833 im Monat.
Kaufmaennisch gerundet legt man zwoelfmal 14,08 zurueck und hat 168,96 — vier
Cent zu wenig, genau in dem Monat, in dem die Bank zugreift. Lieber zwoelf
Cent zu viel auf dem Sparkonto.

**Ein Betrag wird nach der Methode des groessten Restes geteilt.** Naiv
gerundet fehlen bei 1133,47 im Verhaeltnis 1:2 drei Cent im Monat —
unauffaellig genug, um ein Jahr lang niemandem aufzufallen, und teuer genug,
um dann niemanden zu finden. `dienst.aufteilen` rechnet in ganzen Cent, und
die Teile ergeben wieder genau den Betrag.

## Die vier Flaechen

| | |
|---|---|
| **Monatsplan** | Je Person eine Bilanz: Einkommen, feste Kosten, Sparen, was uebrig bleibt. Dazu was die Bank in diesem Monat abbucht und wie viel Ruecklage bereitliegen muss |
| **Geldfluss** | Ein Sankey von den Einnahmen ueber die Konten und Kategorien zu den einzelnen Posten. Die Ansicht fuer jemanden, der dieses Artefakt nicht kennt |
| **Posten** | Alles anlegen, pausieren, entfernen. Ein Posten wird pausiert und nicht geloescht, wenn er nur gerade nicht laeuft |
| **Konten & Personen** | Stammdaten, mit einem Knopf fuer die ueblichen Kategorien |

Das Sankey ist von Hand gezeichnet (`sankey.ts`). Welcher Knoten in welcher
Spalte steht, rechnet das **Backend** (`dienst.flussbild`) — wie weit rechts
etwas steht, ist eine Aussage ueber den Haushalt und keine ueber Pixel. Die
Oberflaeche macht daraus nur Baender. `d3-sankey` waeren 40 kB fuer hundert
Zeilen Rechnung.

## Rechte

`Rolle.LESER` sieht alles und aendert nichts, `Rolle.VERWALTER` darf schreiben.
Das ist kein Beiwerk: so kann die zweite Person im Haushalt den Geldfluss
ansehen, ohne dass ihr versehentlich eine Miete verrutscht.

```bash
homepi benutzer recht <name> haushaltsbuch leser
```

## Was bewusst fehlt

| | |
|---|---|
| Kontostaende und Umsaetze | Das waere eine Buchhaltung. Hier steht der Plan; was tatsaechlich gebucht wurde, sagt die Bank |
| Umbuchungen als Posten | Dass vom Verteilerkonto aufs Verbrauchskonto umgebucht wird, folgt aus den Ausgaben dort — es noch einmal einzutragen hiesse, zwei Zahlen fuer denselben Sachverhalt zu pflegen |
| Woechentliche Intervalle | Eine Ruecklage rechnet in Monaten. Ein woechentlicher Posten ist hier ein monatlicher mit anderem Betrag |

---

## Entwickeln

```bash
make dev                  # Umgebung hoch (Frontend 5173, API 18000)
uv sync
uv run ptw . --now        # Unit-Tests im Watch-Modus
```

Integrationstests brauchen die laufende Datenbank:

```bash
HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m 'not smoke'
```

## Ausrollen

```bash
homepi deploy -s haushaltsbuch
```

Danach erscheint die Kachel auf der Startseite - ohne Frontend-Aenderung.
