# 12 — Artefakte testen

Wie ein Artefakt geprüft wird, von der reinen Funktion bis zum Klick im
Browser. Was hier steht, gilt für jedes Artefakt gleich — die Vorlage aus
`homepi new` bringt es fertig verdrahtet mit.

Der rote Faden: **jede Ebene beweist genau das, was die darunter nicht kann.**
Wer alles auf einer Ebene prüft, bekommt entweder langsame Tests oder
nichtssagende.

## Fünf Ebenen

| Ebene | Wo | Marker | Beweist | Dauer |
|---|---|---|---|---|
| Unit | `modules/<name>/tests/unit/` | — | die Entscheidungen in `dienst.py` | Millisekunden |
| Integration | `modules/<name>/tests/integration/` | `integration` | Router und `speicher.py` gegen echtes Postgres | Sekunden |
| Komponente | `services/web/src/module/<name>/*.test.tsx` | — | jede Ansicht für sich, Backend ersetzt | Millisekunden |
| Rauchtest | `services/gateway/tests/smoke/` | `smoke` | eine **laufende** Instanz antwortet | Sekunden |
| Oberfläche | `services/web/e2e/` | — | der Weg durch die Anwendung, echter Browser | Minuten |

Die ersten drei gehören dem Artefakt und wachsen mit ihm. Die beiden letzten
gehören der Installation: sie liegen **einmal** beim Gateway beziehungsweise
beim Frontend und prüfen alles, was gerade geladen ist. Ein neues Artefakt
schreibt dort in der Regel nichts dazu — es taucht von selbst auf.

Unit-Tests laufen immer. Integration und Rauchtest sind standardmäßig
abgewählt (`addopts = "-m 'not integration and not smoke'"`) — sonst würde ein
Lauf ohne Datenbank scheitern und man gewöhnt sich an rote Läufe.

```bash
make test-modul N=messwerte   # beide Hälften eines Artefakts, vollständig
make tdd-api P=modules/messwerte
make tdd-web N=messwerte
make e2e                      # Oberfläche, eigene Umgebung
make smoke                    # gegen die laufende Umgebung
```

## Die Trennlinie zwischen Unit und Integration

**Alles, was entscheidet, gehört in `dienst.py` und bleibt rein.** Kein
`await`, keine Datenbank, keine Fixtures. Dort entsteht der Großteil der
Tests, und dort kostet ein Test nichts.

> Fängt ein Test in `dienst.py` an, eine Datenbank zu brauchen, ist nicht der
> Test falsch — die Logik steht an der falschen Stelle.

Router und `speicher.py` gehen den umgekehrten Weg: sie bestehen fast nur aus
Datenbankzugriff. Gegen eine nachgebaute Sitzung würde man dort vor allem den
Nachbau testen. Deshalb sind sie als `integration` markiert und laufen gegen
echtes Postgres.

## Die Testdatenbank

Zwei Schutzschichten, beide aus einem Unfall entstanden.

**Erstens: nicht irgendeine Datenbank.** Integrationstests rufen `drop_all`
auf. Zeigte die Umgebung dabei auf die Arbeitsdatenbank, wäre ein Testlauf der
Verlust aller Konten. Deshalb entscheidet nicht die Umgebung allein:

```python
from homepi_core.testing.datenbank import datenbank_fuer_tests

DATENBANK = datenbank_fuer_tests()
```

Sie nimmt `HOMEPI_TEST_DATABASE_URL`, sonst `DATABASE_URL`, sonst die
Voreinstellung — und **bricht ab**, wenn dabei etwas anderes als eine Datenbank
namens `test` oder `<name>_test` herauskommt.

```bash
HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
  uv run pytest -m 'not smoke'
```

`HOMEPI_TEST_DATABASE_URL` und nicht `DATABASE_URL`: so kann daneben die
Arbeitsdatenbank gesetzt sein, ohne dass ein Testlauf sie trifft.

**Zweitens: nicht dieselbe wie beim letzten Mal.** Die geprüfte Datenbank ist
nur die *Vorlage*. Beim Start legt das pytest-Plugin daneben eine eigene an
und stellt die Umgebung darauf um; am Ende wird sie weggeworfen und die
vorherige wieder eingestellt. Im Kopf des Laufs steht, welche es ist:

```
Testdatenbank: messwerte_test (neu angelegt, wird am Ende weggeworfen)
```

Nach einem **roten** Lauf bleibt sie stehen, damit man hineinsehen kann — der
nächste Lauf legt sie ohnehin neu an, es häuft sich also nichts an. Details in
[07-lokale-entwicklung.md](07-lokale-entwicklung.md).

## Angemeldet testen

Jedes Artefakt ist `Zugang.GESCHUETZT`. Ein Test, der die Prüfung umgeht, prüft
den Weg nicht, den ein echter Aufruf nimmt. Die `conftest.py` der Vorlage meldet
sich deshalb wirklich an:

```python
app = create_service(settings, module=register_aus([artefakt]), anmeldung=True)

async with kontext.db.session() as sitzung:
    benutzer = await auth_speicher.lege_benutzer_an(sitzung, "pruefer", PASSWORT, "Prüfer")
    await auth_speicher.setze_recht(sitzung, benutzer.id, artefakt.id, Rolle.VERWALTER)

await c.post("/auth/anmelden", json={"name": "pruefer", "passwort": PASSWORT})
```

Ein Artefakt mit `Zugang.OEFFENTLICH` lässt den Anmeldeteil weg — aber dann
gehört ein Test dazu, der festhält, dass es **absichtlich** öffentlich ist.

## Was jedes Artefakt mitbringen muss

`tests/unit/test_anmeldung.py` aus der Vorlage prüft die Verdrahtung. Diese
fünf Punkte fallen sonst erst im Betrieb auf, und dann als fehlende Kachel:

1. **Der Entry Point zeigt auf dieses Modul.** Ein Tippfehler in der
   `pyproject.toml` bleibt sonst unsichtbar.
2. **Der Zugang ist bewusst gesetzt.** Wäre das Artefakt versehentlich
   öffentlich, sähe es jeder Besucher.
3. **`GET /<artefakt>/` antwortet.** Daran erkennt der Rauchtest, dass ein
   Modul aus dem Manifest wirklich eingehängt ist. Ein `404` hier hieße: im
   Manifest genannt, aber nirgends angeschlossen — genau das ist schon
   passiert. Das ist der einzige Berührungspunkt zwischen einem Artefakt und
   den Rauchtests, und er kostet einen Endpunkt.
4. **Jeder Endpunkt hat ein `summary=`.** Ohne bleibt er in der generischen
   Ansicht namenlos.
5. **Das Manifest hat die Felder der Kachel** (`status`, `pfad`).

## Oberfläche: Komponenten und Weg

**Komponententests** prüfen jede Ansicht für sich, mit ersetztem Backend
(`vi.spyOn(api, …)`). Zugriff über Rollen und sichtbaren Text, nie über
CSS-Klassen:

```tsx
expect(await screen.findByRole("heading", { name: "Messwerte" })).toBeInTheDocument();
```

**Oberflächentests** (`services/web/e2e/`) prüfen den Weg, den ein Mensch
nimmt — anmelden, Konto anlegen, Startpasswort weitergeben, erzwungener
Wechsel. Genau dort war der Fehler, den kein Komponententest sehen konnte.

Sie brauchen eine eigene Umgebung mit eigener Datenbank:

```bash
make e2e     # Umgebung hoch, Tests, Umgebung samt Datenbank weg
```

Bevor der erste Test etwas anfasst, fragt eine Wache nach, ob diese
Installation schon einen Verwalter hat. Wenn ja, bricht der Lauf ab, statt in
fremden Konten zu wüten.

Ein neues Artefakt gehört **nicht** automatisch in `weg.spec.ts`. Dort steht
der Weg durch die Anwendung, nicht jede Ansicht. Nimm es auf, wenn es den Weg
verändert — etwa weil es einen eigenen Einstieg oder einen neuen Zustand
mitbringt.

## Durchklicken von Hand

Seit jedes Artefakt ein Recht verlangt, sieht ein frisches Konto **nichts**.
Für das Prüfen im Browser gibt es deshalb ein Konto mit Rechten auf allem,
was geladen ist:

```bash
make dev-testkonto        # Konto "tester", Verwalter auf jedem Artefakt
```

Der Befehl ist wiederholbar und bricht ohne `ENVIRONMENT=entwicklung` ab.

## Schwellen

Die Coverage-Schwelle steht in der `pyproject.toml` des Artefakts
(`[tool.coverage.report] fail_under`), nicht in der CI — so gilt sie auch
lokal und muss beim Anlegen nirgends nachgetragen werden. Für das Frontend
stehen die Schwellen in `vite.config.ts`.

**Die CI findet neue Module von selbst.** Ihre Matrix wird aus `packages/*`,
`modules/*` und `services/gateway` erzeugt, nicht aufgezählt. Ein Artefakt, an
dessen Eintrag niemand gedacht hat, wäre sonst ungeprüft.

## Fallen, die schon einmal Zeit gekostet haben

**Der Browser hat einen Zwischenspeicher.** Ein Recht stand in der Datenbank,
die Oberfläche zeigte den alten Wert — ein Komponententest bewies, dass die
Komponente richtig neu lädt. Die alten Daten kamen aus dem Cache. Jede Antwort
trägt seitdem `Cache-Control: no-store`. Wer eine eigene Antwort baut, lässt
den Header dran.

**Die Datenbanksitzung committet vor der Antwort.** `DbSitzung` ist mit
`scope="function"` verdrahtet; ohne das liefe der Commit hinter dem Statuscode
her. Nie selbst committen, und die Sitzung nicht selbst aufbauen.

**Die URL der Testdatenbank ist eine Modulkonstante.** Sie steht schon beim
Einlesen der Testdatei fest, lange vor der ersten Fixture — deshalb legt das
Plugin die Datenbank in `pytest_configure` an und nicht in einer Fixture.

**Reihenfolge beim Ersetzen.** `mitAnmeldung` setzt eigene Vorgaben für
`holeIch`; ein vorher gesetzter Spy wird davon überschrieben. Nach dem
Rendern ersetzen, nicht davor.

**`-m ''` hebt den Standardfilter auf.** `-m 'not smoke'` ist der übliche
Lauf: Postgres ist da, eine laufende Instanz nicht.

**Ein Test, der nichts findet, ist kein grüner Test.** Seit Artefakte je
Benutzer sichtbar sind, ist ein anonymes `GET /module` berechtigterweise leer.
Die Rauchtests überspringen sich deshalb ausdrücklich ohne Konto, statt auf
einer leeren Liste still grün zu werden.

## Abnahme

```bash
cd modules/messwerte
uv run ruff format --check . && uv run ruff check . && uv run mypy
HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
  uv run pytest -m 'not smoke' --cov

cd ../../services/web
npx prettier --check src && npx eslint . && npm run typecheck && npm run test:coverage

make dev && make smoke
make e2e
```

Kürzer, wenn es nur um das eine Artefakt geht:

```bash
make test-modul N=messwerte
```

## Weiter

- [09-artefakt-bauen.md](09-artefakt-bauen.md) — der Weg vom leeren
  Verzeichnis bis zur Kachel
- [07-lokale-entwicklung.md](07-lokale-entwicklung.md) — Umgebung,
  Testdatenbank, `make e2e`
- [11-anmeldung.md](11-anmeldung.md) — warum jeder Test sich anmeldet
- [08-design.md](08-design.md) — worüber Komponententests zugreifen dürfen
