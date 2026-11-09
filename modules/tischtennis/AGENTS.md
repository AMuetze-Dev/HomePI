# Artefakt „tischtennis" — Auftrag für den Agenten

Dieses Artefakt ist **gefüllt und läuft**. Was es kann und warum es so
entschieden ist, steht in [README.md](README.md); dieser Text beschreibt, wie
hier gearbeitet wird und was noch aussteht.

Lies zuerst [`../../docs/06-artefakte.md`](../../docs/06-artefakte.md) — dort
steht, warum ein Artefakt ein Modul im Gateway ist und kein eigener Container —
und [`../../docs/12-testen.md`](../../docs/12-testen.md) für die Prüfebenen.

## Stand (09.11.2026)

Gebaut: Teilnehmerliste, Auslosung mit Vorschau und Saat, drei Spielmodi
(Gruppen + KO, reines KO mit Freilosen, Schweizer System), Spielplan mit
Tischen und geschätzten Zeiten, Tabellen mit geteilten Plätzen,
Entscheidungsspiele bei Gleichstand an der Grenze, ein KO-Raster, das vor dem
ersten Ball vollständig steht, und eine öffentliche Dashboard-Ansicht, die den
Plan als Bild zeigt — Gruppenkarten und Raster — mit Glocke.

Dazu seit dem zweiten Durchgang am 09.11.2026: **Doppel-KO** als zweite
Chance, **verschiebbare Spiele** für die Turnierleitung, und ein Dashboard,
das Tabelle und Raster nicht mehr beide zeigt.

**Der Umbau vom 09.11.2026 hieß Einfachheit.** Vorher bestand ein Ergebnis aus
bis zu sieben Sätzen mit Ballpunkten, und die Oberfläche hatte sechs Bereiche.
Jetzt ist ein Ergebnis ein Sieger, und es sind drei Bereiche. Was dabei
wegfiel, steht unten unter „Was bewusst nicht da ist“ — nicht aus
Sparsamkeit, sondern weil dieses Artefakt nebenbei bedient wird.

**Der zweite Durchgang hieß Ruhe.** Das Dashboard war ein Stapel aus sechs
Abschnitten; zwei davon sagten dasselbe („Als nächstes“ und die
Warteschlange am Tisch), zwei weitere waren Nachschlagewerk und standen
trotzdem offen zwischen dem, was gerade passiert, und dem Spielplan. Jetzt
sind es zwei Abschnitte und zwei Klappen. Die Gestaltung folgt derselben
Linie: Haarlinien statt Kästen, Hierarchie über Größe statt über Farbe,
Signalfarbe nur dort, wo etwas ein Signal ist.

**Eine Rechnung, die immer wieder auffällt:** 20 Teilnehmer im reinen KO
ergeben ein 32er-Raster mit 12 Freilosen und **4** Erstrundenspielen. Das ist
richtig und fühlt sich falsch an — 12 von 20 sehen in Runde 1 keinen Ball.
„Jeder spielt in Runde 1“ ist mit einem Setzraster nicht erfüllbar; die
Antwort darauf ist Gruppen + KO, nicht eine Änderung an `los.py`.

**Sechs Zusagen sind nicht verhandelbar** und gehören in jede Änderung:

1. **Jeder schreibende Endpunkt prüft selbst.** Dieses Artefakt ist
   `Zugang.OEFFENTLICH` — damit hängt die Prüfung *nicht* am Router. Der Test
   `test_jeder_schreibende_endpunkt_prueft_selbst` geht alle Routen durch und
   verlangt bei jeder nicht-GET-Route ein `erfordert`. Wird er je rot, ist das
   kein Testproblem.
2. **Ein Ergebnis ist ein Sieger.** Keine Sätze, keine Bälle, keine
   Differenzen. Wer das zurückdreht, dreht den ganzen Zuschnitt zurück: die
   zwei Knöpfe am Tisch, die geteilten Plätze und das Entscheidungsspiel
   hängen alle daran.
3. **Die Vorschau speichert nichts.** `POST …/auslosung` rechnet ein Los und
   legt es hin; erst `POST …/auswuerfeln` schreibt es. Nur deshalb darf
   „nochmal würfeln“ beliebig oft gedrückt werden.
4. **Die Glocke bleibt im Gerät.** Wer sich benachrichtigen lässt, steht im
   `localStorage` des Browsers und in keiner Tabelle.
5. **`nummer` ist unantastbar, `reihenfolge` ist beweglich.** Die Verweise des
   Rasters hängen an `nummer` — „Sieger aus Spiel 7“ darf nicht etwas anderes
   bedeuten, nur weil jemand keine Zeit hatte. Verschoben wird deshalb
   ausschließlich `reihenfolge`, und `speicher.spiele()` sortiert danach.
6. **Tabelle oder Raster, nie beides.** Solange die Gruppen laufen, sagt die
   Tabelle, wer weiterkommt. Steht das Raster, ist sie Vergangenheit und
   verschwindet — `PlanGrafik` entscheidet das an einer Stelle.

## Was bewusst nicht da ist

| | |
|---|---|
| **Ein zweiter Durchgang im Verliererzweig** | Steht es im Kreis, bleibt es stehen |
| **Satz- und Ballergebnisse** | Eingetragen wird der Sieger. `best_of` steht in keinem Datensatz und sagt allein den Spielern, wie lange sie spielen — deshalb ist es auch mitten im Turnier noch änderbar |
| **Direkter Vergleich als Rangregel** | Punktgleiche teilen sich den Platz. Kreuzt der Gleichstand die Grenze zum Weiterkommen, wird gespielt statt gerechnet |
| **Ein Bereich je Tätigkeit** | Teilnehmer, Auswürfeln und Spielplan sind einer. Drei Reiter waren richtig, solange ein Ergebnis aus sechs Zahlen bestand |

Offen, in der Reihenfolge, in der es sich lohnt:

| | |
|---|---|
| **Echtes Web-Push** | Die Glocke wirkt nur, solange die Seite offen ist. Für eine Meldung bei geschlossenem Tab braucht es einen Service Worker, VAPID-Schlüssel im Gateway und ein gültiges Zertifikat auf dem Pi |
| **Platz 3** | Nach dem Halbfinale gibt es kein Spiel um den dritten Platz. Das Raster kann es, der Dienst setzt es nicht an |
| **Bracket reset im Doppel-KO** | Gewinnt im Endspiel der aus dem Verliererzweig, ist er Sieger — obwohl der andere erst eine Niederlage hat. Streng genommen fehlt ein zweites Endspiel. Ein Turnier, dessen Ende „vielleicht noch ein Spiel“ ist, lässt sich nebenbei nicht führen |
| **Spiel an eine Zielstelle ziehen** | Verschoben wird um einen Platz. Wer jemanden deutlich später spielen lassen will, drückt mehrmals — und sieht dazwischen, was es mit dem Plan macht |
| **Doppel** | Alles ist auf Einzel gebaut: ein Teilnehmer ist eine Person. Doppel wären ein Teilnehmer aus zwei Namen — am Datenmodell eine Zeile, an der Oberfläche mehr |
| **Gleichstand im Kreis** | Spielen drei das Entscheidungsspiel und gewinnt jeder einmal, steht der Gleichstand wieder. Ein zweiter Durchgang brächte dasselbe, deshalb bleibt er dann stehen — `speicher._schon_entschieden` |
| **Migrationen** | `homepi schema` legt nur an. Eine neue Spalte in einer bestehenden Tabelle hält das Gateway auf `unhealthy` an |

---

## 1. Was bereits funktioniert

Nicht neu bauen, nicht umbauen:

| | |
|---|---|
| Anmeldung | Entry Point `homepi.module` in `pyproject.toml` → Gateway findet das Modul beim Start |
| Routing | Router hängt unter `/tischtennis`; Traefik leitet `api.<domain>/tischtennis` dorthin. **`GET /tischtennis/` muss antworten** - daran erkennt der Rauchtest, dass das Modul wirklich eingehängt ist |
| Kachel | Startseite liest `GET /module` und zeigt „Tischtennisturnier" — **auch ohne Anmeldung**, weil das Artefakt öffentlich ist |
| Zugriff | `zugang=Zugang.OEFFENTLICH` in `__init__.py`. Lesen darf jeder, Schreiben braucht `erfordert("tischtennis", …)` an jedem einzelnen Endpunkt — siehe Zusage 1 oben und [`../../docs/11-anmeldung.md`](../../docs/11-anmeldung.md) |
| Health | `/health` und `/info` kommen aus `homepi-core` |
| Fehlerformat | Jeder Fehler wird RFC 9457 `problem+json`. Eigene Fehler erben von `ServiceError` |
| Logging | JSON in Produktion, Text lokal, `X-Request-ID` in jeder Zeile |
| DB-Sitzung | `DbSitzung` aus `homepi_core.deps` — eine Transaktion je Anfrage. Committet **vor** der Antwort; nie selbst committen |
| Testen | fünf Ebenen, Testdatenbank, bekannte Fallen: `docs/12-testen.md` |
| Tabellen | erben von `homepi_core.Base`; das Gateway legt sie beim Start an |

**Du schreibst nie selbst:** FastAPI-App, CORS, Middleware, Health-Endpunkt,
Datenbank-Engine, Logging-Konfiguration, Dockerfile, Compose-Fragment.

---

## 2. Dateien und ihre Rolle

```
modules/tischtennis/
  src/homepi_tischtennis/
    __init__.py    Anmeldung: modul = Modul(id=..., titel=..., router=...)
    schemas.py     Pydantic: was rein- und rausgeht
    modelle.py     Turnier, Gruppe, Teilnehmer, Spiel
    dienst.py      REINE Regeln: Tabelle, Gleichstand, Zeitplan, Zustaende
    los.py         REIN: Gruppen, Spielfolge, KO-Raster, Schweizer Paarung
    speicher.py    DB-Zugriff - kein einziges if einer Fachregel
    router.py      HTTP: übersetzt Anfrage ↔ Fachlichkeit, sonst nichts
  tests/
    unit/          test_dienst.py, test_los.py, test_anmeldung.py - ohne DB
    integration/   Marker `integration`, braucht Postgres

services/web/src/module/tischtennis/
  api.ts                  typisierter Zugriff auf das Backend
  TischtennisSeite.tsx    Verteiler auf die drei Bereiche
  DashboardTafel.tsx      die öffentliche Ansicht, fragt im Takt nach
  PlanGrafik.tsx          Gruppenkarten und Raster - der Plan als Bild
  Raster.tsx              das KO-Raster, eine Spalte je Runde
  TurnierTafel.tsx        Teilnehmer, Auswürfeln und Spielplan in einem
  EinstellungenTafel.tsx  Regeln des Turniers, Anlegen und Beenden
  glocke.ts               localStorage, Ton, Vibration, Benachrichtigung
  zeit.ts                 Uhrzeit, Dauer, „läuft seit"
  testdaten.ts            Vorlagen für die Tests, an einer Stelle
  TischtennisSeite.module.css   eine Datei für alle Tafeln
```

### Die Trennung ist nicht verhandelbar

`dienst.py` und `los.py` enthalten die Entscheidungen und sind rein.
`speicher.py` macht I/O und entscheidet nichts — es ruft die reinen
Funktionen auf, statt deren Regeln nachzubauen. `router.py` übersetzt.

Der Grund ist messbar: die 104 Unit-Tests laufen in 0,3 Sekunden, und nur
deshalb benutzt man die rot-grün-Schleife wirklich. Sobald eine
Fallunterscheidung in `speicher.py` oder `router.py` rutscht, braucht ihr Test
eine Datenbank — und ab da wird nicht mehr getestet, sondern geklickt.

### Wo welche Regel steht

| Frage | Ort |
|---|---|
| Darf dieser Sieger eingetragen werden? | `dienst.pruefe_sieger` |
| Wer steht auf welchem Platz? | `dienst.tabelle` — Punktgleiche teilen ihn |
| Muss noch gespielt werden? | `dienst.gleichstand_an_der_grenze` |
| Wer spielt das Entscheidungsspiel? | `dienst.entscheidungsspiele`, angesetzt in `speicher._entscheidungen_ansetzen` |
| Wann wird welcher Tisch frei? | `dienst.planen` |
| Wer ist „gleich dran"? | `dienst.planen`, Feld `gleich_dran` |
| Was kommt nach der Gruppenphase? | `dienst.naechster_schritt` |
| Wer kommt gegen wen im Raster? | `los.ko_setzliste` und `los.ko_raster` |
| Wer bekommt ein Freilos? | `los.ko_raster` (die Gesetzten) bzw. `los.schweizer_paarung` |

---

## 3. Ablauf

### 3.1 Vertrag zuerst

`schemas.py`. Was geht rein, was kommt raus, welche Werte sind zulässig.
Pydantic-Validierung wird automatisch zu `422` mit Feldnamen.

### 3.2 Fachlogik testgetrieben

1. Test in `tests/unit/test_dienst.py` oder `test_los.py` schreiben und
   **scheitern sehen**
2. einfachste Änderung, die ihn grün macht
3. aufräumen, Tests bleiben unverändert

```bash
make dev N=tischtennis              # Gateway lädt nur dieses Artefakt
cd modules/tischtennis && uv run ptw . --now
```

Für die Oberfläche in einem zweiten Fenster:

```bash
make tdd-web N=tischtennis
```

### 3.3 Persistenz

Tabellen in `modelle.py` (erben von `Base`), Zugriff in `speicher.py`.
Integrationstests gegen eine Testdatenbank:

```bash
make dev
cd modules/tischtennis
HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m 'not smoke'
```

Niemals gegen `app`: die Tests legen Tabellen an und löschen sie wieder.

### 3.4 Endpunkte

`router.py`. Regeln:

- **jeder nicht-GET-Endpunkt braucht `dependencies=[MITSCHREIBEN]` oder
  `[EINRICHTEN]`** — das ist die Besonderheit dieses Artefakts
- `summary=` bei jedem Endpunkt — die generische Ansicht im Frontend zeigt ihn
- feste Pfade **vor** parametrisierte, sonst liest FastAPI `/dashboard`
  als UUID und antwortet `422`
- Fehler über eigene `ServiceError`-Klassen, nie `HTTPException`
- Rückgabetypen annotieren, sonst fehlt das OpenAPI-Schema

### 3.5 Oberfläche

`api.ts` erweitern, dann die Tafel. Zugriff in Tests über Rollen und
sichtbaren Text, nie über CSS-Klassen. Nur Tokens aus
`src/styles/tokens.css` — kein fester Farbwert, keine feste Pixelzahl.
Bausteine aus `src/ui`: `Knopf`, `Karte`, `Feld`, `Etikett`, `Hinweis`,
`Leerzustand`, `Platzhalter`.

Zwei Dinge sind hier eigen:

- Die Dashboard-Tafel holt ihre Daten **selbst** und in einem Abruf. Ein
  Besucher ohne Konto soll nicht auf Spielplan, Tabellen und Teilnehmerliste
  warten, die er nicht sieht.
- Bereiche, für die das Recht fehlt, zeigen einen Hinweis und keinen Fehler.
  Die Navigationsleiste ist zur Build-Zeit fest (`src/module/register.ts`) und
  kennt den Benutzer nicht.

Details: [`../../docs/08-design.md`](../../docs/08-design.md).

---

## 4. Abnahmekriterien

Fertig ist eine Änderung, wenn **alles** davon zutrifft:

```bash
# Backend
cd modules/tischtennis
uv run ruff format --check . && uv run ruff check . && uv run mypy
HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m 'not smoke'

# Frontend
cd services/web
npx prettier --check src && npx eslint . && npm run typecheck && npm run test:coverage

# Zusammenspiel
make dev && make smoke
```

Kürzer, solange du nur an diesem Artefakt arbeitest:

```bash
make test-modul N=tischtennis
```

| Kriterium | Schwelle |
|---|---|
| Coverage Backend | ≥ 85 % |
| Coverage Frontend | ≥ 85 % Zeilen, ≥ 80 % Zweige |
| `mypy --strict` | keine Fehler |
| `GET /module` ohne Cookie | enthält `tischtennis` — dieses Artefakt ist öffentlich |
| `GET /tischtennis/dashboard` ohne Cookie | 200 |
| `POST /tischtennis/turnier` ohne Cookie | 401, mit Konto ohne Recht 403 |
| Rauchtests | grün |

Zusätzlich, was kein Werkzeug prüft:

- [ ] Jeder Ladezustand hat einen Platzhalter, keinen Layoutsprung
- [ ] Der Erstzustand erklärt, was als Nächstes zu tun ist
- [ ] Fehlermeldungen des Backends erreichen den Benutzer wörtlich, nicht als
      „Fehler 409"
- [ ] Ein fehlgeschlagenes Formular behält seine Eingabe
- [ ] Bei 375 px Breite ist alles erreichbar, ohne horizontal zu scrollen
- [ ] Das laufende Spiel ist auf dem Dashboard aus zwei Metern lesbar
- [ ] Ein abgerissener Abruf tauscht die stehende Anzeige **nicht** gegen eine
      Fehlerseite — im Saal ist das WLAN mal weg

---

## 5. Ausrollen

```bash
git commit && git push          # CI prüft
homepi deploy -s tischtennis    # Pipeline baut arm64, Pi zieht
```

Die Kachel erscheint danach von selbst — bei jedem, auch ohne Konto. Wer
Ergebnisse eintragen soll, braucht ein Recht:

```bash
homepi benutzer recht <name> tischtennis nutzer      # Ergebnisse, Teilnehmer
homepi benutzer recht <name> tischtennis verwalter   # auswürfeln, Einstellungen
```

---

## 6. Häufige Fehler

| Symptom | Ursache |
|---|---|
| Kachel fehlt | Entry Point in `pyproject.toml` falsch, oder Modul nicht als Abhängigkeit im Gateway — `uv sync` im Gateway vergessen? |
| `status: "fehler"` im Manifest | Import wirft. Grund steht in der Kachel und im Log |
| `422` statt Treffer | parametrisierte Route steht vor der festen |
| `RuntimeError: keine DATABASE_URL` | Unit-Test benutzt `DbSitzung`; das gehört in `tests/integration/` |
| Leere Tabelle nach Neustart | `DB_SCHEMA_ANLEGEN=false`. Lokal `true`, in Produktion braucht es eine Migration |
| Endpunkt fehlt in generischer Ansicht | `summary=` oder Rückgabetyp fehlt |
| Coverage von `speicher.py` wirkt absurd niedrig | `concurrency = ["greenlet", "thread"]` fehlt in `pyproject.toml` — SQLAlchemys asyncio-Schicht setzt Koroutinen in einem Greenlet fort, und coverage verliert dort die Spur |
| „Es sind noch Spiele offen" beim Ansetzen | genau so gemeint: ohne vollständige Tabelle gibt es keine Setzliste |
