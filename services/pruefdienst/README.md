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

```bash
# Ein Konto mit "verwalter" für staffelpilot. --passwort-stdin, nicht
# --startpasswort: ein Dienst kann kein Passwort wechseln.
printf '%s' "$PW" | docker compose -f compose.dev.yml exec -T \
  -w /app/services/gateway gateway uv run homepi benutzer anlegen \
  pruefdienst --artefakt staffelpilot --rolle verwalter --passwort-stdin

PRUEFDIENST_PASSWORT="$PW" docker compose -f compose.dev.yml \
  --profile pruefdienst up -d --build pruefdienst
```

Danach in der Oberfläche unter **DFBnet-Zugang** die Anmeldedaten hinterlegen.
Ohne sie bricht jeder Lauf mit einer klaren Meldung ab.

## Was er liest

| `PRUEFDIENST_LESER` | |
|---|---|
| `demo` *(Voreinstellung)* | klopft nirgends an, gibt zurück, was ihm mitgegeben wurde. Damit lässt sich die ganze Kette ansehen, bevor je ein Passwort im Spiel war |
| `dfbnet` | ein echter Browser, echte Anmeldung |

Wer nichts sagt, bekommt den, der nirgends anklopft. Ein Dienst, der beim
ersten Start ungefragt einen Browser nach DFBnet schickt, ist eine Überraschung
zu viel.

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
| Regelprüfung (die 31 Regeln) | **fehlt**. Eingespielte Spiele haben `befunde: []` — der Bericht ist da, geprüft ist er nicht |
| Meldung einer Staffel holen (Initialisierung) | **fehlt**. Der Leser gibt eine leere Liste zurück, und die überschreibt im Artefakt nichts |
| Eintragen in DFBnet (Prüferfreigabe, Fallanlage) | **fehlt**. Vorgemerktes bleibt stehen, statt still auf „fertig" zu springen |

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
  dienst.py     REINE Entscheidungen - Zeile zerlegen, Fortschritt, Wartezeit
  gateway.py    HTTP zum Artefakt
  leser.py      das Protokoll, und ein Leser ohne DFBnet
  dfbnet.py     der echte Browser
  schleife.py   der Ablauf
  __main__.py   Umgebung, Signale, Schleife
```

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
