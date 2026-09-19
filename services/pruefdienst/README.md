# homepi-pruefdienst

Liest DFBnet und spielt in das Artefakt `staffelpilot` ein.

**Eigener Container und kein Artefakt im Gateway.** Er fährt minutenlang einen
echten Browser; im gemeinsamen Prozess würde er jedes andere Artefakt
blockieren, und die synchrone Playwright-API lässt sich aus einer laufenden
Event-Loop ohnehin nicht aufrufen. Das steht so auch in
[docs/06-artefakte.md](../../docs/06-artefakte.md).

## Wie er arbeitet

Er hält **nichts** fest. Sein Gedächtnis ist der Auftrag im Artefakt — stirbt
der Container mitten im Lauf, steht dort, wie weit er kam, und der nächste
Start findet ihn wieder. Genau dafür ist ein Auftrag ein Datensatz und kein
Thread.

```
Oberfläche          Artefakt                      Prüfdienst
────────────────────────────────────────────────────────────────────
"Prüflauf"  ──────► POST /auftraege
                    (angefordert)   ◄──────────── GET /auftraege/offen
                    POST /zugang/abholen ◄──────── holt die Zugangsdaten
                                                   meldet sich bei DFBnet an
                    …/fortschritt   ◄──────────── Schritt, Zahlen, Protokoll
                    POST /import    ◄──────────── die gelesenen Spiele
                    …/abschluss     ◄──────────── fertig oder gescheitert
Prüflauf-Tafel ◄─── GET /auftraege/offen
```

Er meldet sich am Gateway an wie jeder andere Benutzer — kein eigener
Schlüssel, kein Sonderweg. So steht in jedem Zugriffsprotokoll, wer gearbeitet
hat, und ein Konto, das abhandenkommt, lässt sich sperren wie jedes andere.

## Einrichten

Der Container läuft in der Entwicklungsumgebung mit. Was ihm fehlt, ist ein
Konto:

```bash
make dev
make dev-pruefdienst
```

Nur `verwalter` für **staffelpilot**, nicht für `verwaltung`: Letzteres wäre
ein Administrator, und dann gälte die Installation als eingerichtet — die
Wache der Oberflächentests bricht dort ab.

`--passwort-stdin` und nicht `--startpasswort`: ein Dienst kann kein Passwort
wechseln.

Ohne Konto **stürzt er nicht ab**, sondern sagt einmal, was fehlt, und wartet.
Ein Container in einer Neustartschleife füllt das Protokoll mit Abstürzen und
verdeckt genau den Satz, auf den es ankommt.

Danach in der Oberfläche unter **DFBnet-Zugang** die Anmeldedaten hinterlegen.
Ohne sie bricht jeder Lauf mit einer klaren Meldung ab.

## Was er liest

| `PRUEFDIENST_LESER` | |
|---|---|
| `demo` *(Voreinstellung)* | **Beispieldaten.** Klopft nirgends an, erfindet zu jeder Staffel drei Spiele, vier Mannschaften (davon eine SG) und zwei Befunde am ersten Spiel |
| `dfbnet` | ein echter Browser, echte Anmeldung |

Wer nichts sagt, bekommt den, der nirgends anklopft. Ein Dienst, der beim
ersten Start ungefragt einen Browser nach DFBnet schickt, ist eine Überraschung
zu viel.

Die Beispieldaten sagen, dass sie welche sind: jede Spielkennung fängt mit
`DEMO-` an, und in jedem Befundtext steht „(Beispieldaten)". Wer das in der
Oberfläche sieht, weiß, dass niemand bei DFBnet war.

## Zusehen

Im Container gibt es keinen Bildschirm. Wer dem Prüflauf bei der Arbeit
zusehen will, lässt ihn auf dem eigenen Rechner laufen:

```bash
make pruefdienst-zusehen            # Beispieldaten, kein Browser
make pruefdienst-zusehen L=dfbnet   # echter, sichtbarer Browser
```

Der Container wird dafür angehalten: es gibt genau eine DFBnet-Sitzung, und
zwei Dienste würden sich um jeden Auftrag streiten.

Ohne sichtbaren Browser steht der Fortschritt in der Oberfläche unter
**Prüflauf** — Schritt, Balken und Protokoll, im Drei-Sekunden-Takt.

## Was er **nicht** tut

**Er trägt nichts in DFBnet ein**, solange nicht *beide* Schalter an sind:

| | |
|---|---|
| in der Oberfläche | Prüflauf → „Übertragung freigeben" |
| in der Umgebung | `PRUEFDIENST_DARF_SCHREIBEN=1` |

Eine Prüferfreigabe ist eine Handlung, die ein Verein sieht. Sie soll nicht
passieren, weil ein Container gestartet wurde.

## Der Stand, ehrlich

| | |
|---|---|
| Anfordern, anmelden, Fortschritt, Abschluss, Fehlerbehandlung | **geprüft** — gegen ein nachgebautes Gateway und den Demo-Leser |
| Anmelden bei DFBnet, Trefferliste lesen | gebaut, **nicht gegen das echte DFBnet geprüft** |
| Spielbericht aus HTML lesen | **geprüft** — gegen echtes, aufgezeichnetes DFBnet-HTML (`tests/aufnahmen/`): Kopfdaten, Karten, Tore, Wechsel, Bestätigungen, Vorkommnisse |
| Aufstellung aus der Schnittstelle | die **Übersetzung** ist geprüft (`aufstellung.py`, 100 %). Der Abruf selbst fehlt noch |
| Regelprüfung (die 31 Regeln) | **fehlt**. Eingespielte Spiele haben `befunde: []` — der Bericht ist da, geprüft ist er nicht |
| Meldung einer Staffel holen (Initialisierung) | **fehlt** — im DFBnet-Leser. Er gibt eine leere Liste zurück, und die überschreibt im Artefakt nichts; der Auftrag meldet dann, dass nichts kam, statt einen Erfolg |
| Eintragen in DFBnet (Prüferfreigabe, Fallanlage) | **fehlt**. Mit `PRUEFDIENST_LESER=dfbnet` bleibt Vorgemerktes stehen, statt still auf „fertig" zu springen |
| Eintragen **simuliert** | mit den Beispieldaten wird jede Übertragung als erledigt gemeldet — mit dem Vermerk „Simuliert — es war kein Browser bei DFBnet" an der Zeile. Nur so lässt sich der Weg bis zum Freigeben einmal durchklicken |

Was fehlt, liegt fertig in der alten Anwendung unter
`D:/DevLibrary/StaffelPilot/src/automation/` und `src/rules/` — rund 5000
beziehungsweise mehrere tausend Zeilen, über eine Saison gewachsen. Das wird
übernommen und nicht neu geschrieben.

> Von diesem Rechner aus gibt es keine DFBnet-Zugangsdaten, und ein Probelauf
> gegen das Livesystem ist eine Handlung, die ein Verband sieht. Der erste
> echte Lauf ist der Beweis, nicht diese Datei.

## Aufbau

```
src/homepi_pruefdienst/
  dienst.py       REINE Entscheidungen - Zeile zerlegen, Fortschritt, Wartezeit
  bericht.py      Spielbericht aus HTML (uebernommen, woertlich)
  aufstellung.py  Aufstellung aus der DFBnet-Schnittstelle (uebernommen)
  gateway.py      HTTP zum Artefakt
  leser.py        das Protokoll, und ein Leser ohne DFBnet
  dfbnet.py       der echte Browser
  schleife.py     der Ablauf
  __main__.py     Umgebung, Signale, Schleife
```

### Was übernommen ist und warum

`bericht.py` und `aufstellung.py` sind **wörtlich** aus
`D:/DevLibrary/StaffelPilot/src/automation/` übernommen. Sie sind dort über
eine Saison an echten Seiten gewachsen und haben zwei Fehler gefunden, die 630
andere Tests nicht sahen. Sie neu zu schreiben hieße, dieselben Fehler noch
einmal zu machen.

Deshalb sind sie auch von `ruff` und `mypy` ausgenommen: sie nach unserem
Geschmack umzuformen hieße, jede Zeile anzufassen, die sich bewährt hat — und
der Vergleich mit dem Original wäre danach keiner mehr. Gehalten werden sie
durch die Golden-Tests.

**Aus dem HTML kommt keine Aufstellung.** Die Seite nennt die beiden
Mannschaftsnamen und sonst nichts; Spieler, Geburtsdaten, Spielrecht und Fotos
kommen aus der Aufstellungsschnittstelle. Ein eigener Test hält das fest —
sonst sähe der leere Kader aus wie ein Extraktor, der aufgehört hat zu
arbeiten.

Das Zerlegen einer Tabellenzeile steht in `dienst.py` und nicht in
`dfbnet.py` — es ist die Stelle, die kaputtgeht, wenn DFBnet eine Spalte
verschiebt, und dort ist sie in Millisekunden prüfbar. Beide Anordnungen, die
DFBnet bisher hatte, haben einen Test.

## Entwickeln

```bash
cd services/pruefdienst
uv sync
uv run ruff format --check . && uv run ruff check . && uv run mypy
uv run pytest --cov
```

`dfbnet.py` und `__main__.py` sind von der Abdeckung ausgenommen: das eine
braucht einen Browser, das andere einen Prozess. Eine Zahl, die so tut, wäre
schlimmer als die ehrliche Lücke.

`bericht.py` ebenfalls, aus einem anderen Grund: er ist durch die Golden-Tests
gehalten und kommt dabei auf **70 %**. Was fehlt, sind Zweige für
Auszeichnungsvarianten, von denen hier keine Aufnahme existiert — sie mit
selbst erfundenem HTML anzufahren hieße, die eigene Erfindung zu prüfen und
nicht DFBnet. Die Schwelle von 90 % gilt damit für das, was wir selbst
geschrieben haben.

### Der ganze Weg

`services/web/e2e/staffelpilot.spec.ts` geht ihn durch — Ersteinrichtung,
Recht vergeben, Staffel anlegen, Zugang hinterlegen, Saisondaten holen,
Prüflauf, Befund entscheiden, abhaken, freigeben. Gegen einen echten
Container, eine echte Datenbank und diesen Dienst:

```bash
make e2e
```

Beide Reisen dort brauchen eine **frische** Installation — die eine richtet
ein, die andere prüft, dass die Einrichtung noch offen ist. Sie bekommen
deshalb je einen eigenen Durchgang.
