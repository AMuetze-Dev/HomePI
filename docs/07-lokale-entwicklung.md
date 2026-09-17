# 07 — Lokale Entwicklung auf Windows

Der Pi ist noch nicht da. Entwickelt und getestet wird deshalb vollständig in
Docker auf dem Windows-Rechner — mit derselben Software, die später auf dem Pi
läuft, nur ohne Traefik, TLS und Pi-hole. Die gehören zum Pi und würden lokal
nur Zertifikatswarnungen erzeugen.

## Start

```bash
make dev
```

| | Adresse |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:18000 (`/docs` für Swagger) |
| Postgres | localhost:15432, `app` / `app`, Datenbanken `app` und `test` |

**Warum diese Ports:** 3000, 5432 und 8000 sind auf diesem Rechner schon belegt.
Über `DEV_WEB_PORT`, `DEV_API_PORT` und `DEV_DB_PORT` lassen sie sich ändern.

```bash
make dev-logs     # folgen
make dev-ps       # Zustand
make dev-stop     # stoppen, Daten bleiben
make dev-reset    # stoppen und Datenbank wegwerfen
```

### Einmalig: ein Konto

Eine frische Umgebung hat keinen Verwalter. `http://localhost:5173` zeigt dann
die **Einrichtungsmaske**. Sie verlangt das Einrichtungstoken, das beim Start
im Log steht:

```bash
docker compose -f compose.dev.yml logs gateway | grep -A3 "keinen Verwalter"
```

Auf der Kommandozeile geht dasselbe:

```bash
export DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/app'
cd packages/homepi-core
uv run homepi benutzer anlegen aaron --artefakt verwaltung --rolle verwalter
uv run homepi benutzer liste
```

Weitere Rechte — etwa `geraete` — vergibst du danach in der Oberfläche unter
*Verwaltung* oder mit `homepi benutzer recht aaron geraete verwalter`.

`make dev-reset` wirft die Datenbank weg — danach ist auch das Konto weg.

Das Passwort wird abgefragt, nie als Argument übergeben; in einem Skript geht
`--passwort-stdin`. Wer welches Artefakt sehen darf, steht in
[11-anmeldung.md](11-anmeldung.md).

## Was lokal anders ist als auf dem Pi

| | lokal | Pi |
|---|---|---|
| Plattform | amd64, nativ | arm64 |
| Reverse Proxy | Vite-Proxy `/api` | Traefik mit TLS |
| Zertifikate | keine, alles HTTP | Wildcard von Let's Encrypt |
| Schema | `DB_SCHEMA_ANLEGEN=true` beim Start | `false`, Migration |
| Logformat | lesbarer Text | JSON |
| Worker | 1, mit `--reload` | 1, ohne Reload |

Der Vite-Proxy leitet `/api/...` an das Gateway weiter. Dadurch spricht der
Browser nur mit einer Adresse und es gibt lokal **kein CORS** — dieselbe Rolle,
die auf dem Pi Traefik übernimmt.

Wenn das Gateway gerade neu startet, antwortet der Proxy mit `problem+json` und
Status 503, also im selben Format wie das Backend. So sieht man lokal genau die
Meldung, die die Oberfläche später auch zeigen würde.

## Hot Reload

Beides funktioniert durch den Windows-Bind-Mount, aber nur mit Polling:
Docker Desktop reicht keine inotify-Ereignisse vom Host durch.

- **Backend:** `WATCHFILES_FORCE_POLLING=true` im Dockerfile.dev. Beobachtet
  werden `services/gateway/src`, `packages/homepi-core/src` **und** `modules/` —
  eine Änderung am Basispaket oder an einem Artefakt lädt den Server also
  genauso neu. Gemessen: rund 6 Sekunden.
- **Frontend:** `server.watch.usePolling` in `vite.config.ts`. HMR greift sofort.

Ohne diese beiden Einstellungen merkt keines der Werkzeuge, dass du etwas
geändert hast — und man sucht den Fehler an der völlig falschen Stelle.

### Ein Konto zum Durchklicken

Seit jedes Artefakt ein Recht verlangt, sieht ein frisches Konto **nichts** —
die Übersicht ist leer, und die Adresse von Hand einzutippen hilft nicht. Wer
die Oberfläche prüfen will, müsste also nach jedem Zurücksetzen erst ein Konto
anlegen und dann für jedes Artefakt einzeln ein Recht vergeben.

```bash
make dev-testkonto                 # Konto "tester", Verwalter auf allem
make dev-testkonto N=klick R=leser # anderer Name, andere Rolle
```

```
==> Testkonto 'tester' anlegen
    verwalter auf: geraete, staffelpilot, verwaltung
    + 'tester' kann sich anmelden.
==> Passwort
    nur-zum-durchklicken-im-eigenen-netz
```

Die Rechte kommen aus derselben Entdeckung wie im Gateway — ein neu
dazugekommenes Artefakt ist nach einem erneuten Aufruf dabei. Der Befehl ist
wiederholbar: gibt es das Konto schon, werden Passwort, Sperre und Rechte neu
gesetzt, statt zu scheitern.

Das Passwort ist **fest und steht im Quelltext**. Das ist kein Versehen: man
meldet sich damit zwanzigmal am Tag an, und ein erzeugtes müsste man zwanzigmal
nachschlagen. Deshalb hängt am Befehl ein Riegel, und der ist zu, solange
nicht ausdrücklich etwas anderes dasteht:

```
FEHLER: 'testkonto' legt ein Konto mit Rechten auf JEDEM Artefakt an und gibt
sein Passwort aus.
Das geht nur mit ENVIRONMENT=entwicklung (hier: nicht gesetzt).
Sonst: homepi benutzer anlegen <name> --startpasswort
```

Gelesen wird `ENVIRONMENT` direkt, nicht über die Einstellungen — sonst würde
ein unbeteiligter Konfigurationsfehler den Riegel mit einem Stacktrace
überspringen, statt ihn zufallen zu lassen.

## Tests

```bash
make test           # alles, was die CI auch prüft
make test-python    # die drei Python-Projekte
make test-web       # Frontend
make smoke          # gegen die laufende Dev-Umgebung
make tdd-web        # vitest im Watch-Modus
make tdd-api P=modules/geraete
```

### Die Testdatenbank ist nicht die Arbeitsdatenbank

Integrationstests rufen `drop_all` auf. Zeigt `DATABASE_URL` gerade auf die
Arbeitsdatenbank — und auf einem Entwicklungsrechner tut sie das die meiste
Zeit —, dann löscht ein Testlauf die Konten, an denen man eben noch gearbeitet
hat. Genau das ist einmal passiert.

Deshalb entscheidet nicht mehr die Umgebung allein:

```python
from homepi_core.testing.datenbank import datenbank_fuer_tests

DATENBANK = datenbank_fuer_tests()
```

Sie nimmt `HOMEPI_TEST_DATABASE_URL`, sonst `DATABASE_URL`, sonst die
Voreinstellung — und **bricht ab**, wenn dabei etwas anderes als eine
Datenbank namens `test` oder `<name>_test` herauskommt:

```
'app' sieht nicht nach einer Testdatenbank aus.
Integrationstests rufen drop_all auf - gegen die Arbeitsdatenbank wäre das
der Verlust aller Konten.
```

### Jeder Lauf bekommt eine frische Datenbank

Die geprüfte Datenbank ist nur die **Vorlage**. Beim Start legt das
pytest-Plugin daneben eine eigene an und stellt die Umgebung darauf um; am
Ende wird sie weggeworfen und die vorherige wieder eingestellt. Im Kopf des
Laufs steht, welche es ist:

```
Testdatenbank: homepi_core_test (neu angelegt, wird am Ende weggeworfen)
```

Der Name kommt vom Projekt (`homepi-core` → `homepi_core_test`), ist also
wiederfindbar. Zwei Folgen, beide beabsichtigt:

- **Kein Lauf sieht, was der vorige hinterlassen hat.** Ein Test, der nur
  wegen eines Restes grün ist, ist schlimmer als ein roter.
- **Nach einem roten Lauf bleibt sie stehen**, damit man hineinsehen kann.
  Der nächste Lauf legt sie ohnehin neu an — es häuft sich nichts an.

```bash
psql "postgresql://app:app@127.0.0.1:15432/homepi_core_test"

# Bei der Vorlage bleiben, statt je Lauf eine eigene anzulegen:
HOMEPI_TEST_DATENBANK_JE_LAUF=0 uv run pytest -m integration
```

Lässt sich keine anlegen — etwa weil gerade keine Postgres läuft —, sagt der
Lauf das als Warnung und benutzt die vorgegebene. Unit-Tests brauchen ohnehin
keine, und `pytest -m smoke` fasst gar keine an: dort gehört die Datenbank der
laufenden Instanz.

### Die Oberflächentests bekommen eine ganze Umgebung

Sie gehen noch einen Schritt weiter: mit `make e2e` eine **eigene Umgebung**
mit eigener Datenbank, eigenen Ports und eigenem Projektnamen. Sie legen
Konten an, ändern Rechte und werfen am Ende alles weg.

```bash
make e2e          # Umgebung hoch, Tests, Umgebung samt Datenbank weg
```

Bevor der erste Test etwas anfasst, fragt er nach: hat diese Installation
schon einen Verwalter? Wenn ja, bricht der Lauf ab, statt in fremden Konten
zu wüten:

```
http://127.0.0.1:5173 hat bereits einen Verwalter — hier arbeitet also jemand.
Diese Tests legen Konten an und vergeben Rechte; sie laufen nur gegen eine
frische Installation mit eigener Datenbank:
  make e2e
```

Vier Arten, bewusst getrennt:

| | wo | wann |
|---|---|---|
| Unit | `tests/unit/` | bei jeder Änderung, Millisekunden |
| Integration | `tests/integration/`, Marker `integration` | mit laufender Datenbank |
| Rauchtest | `tests/smoke/`, Marker `smoke` | gegen eine laufende Instanz |
| Oberfläche | `services/web/e2e/` | gegen eine eigene, frische Umgebung |

Die Oberflächentests melden sich an wie ein Mensch: Ersteinrichtung mit Token,
Konto anlegen, Startpasswort weitergeben, erstes Anmelden, erzwungener
Wechsel. Was sie sehen, sehen die Komponententests nicht — die prüfen jede
Ansicht für sich, mit ersetztem Backend. Der Weg dazwischen ist das, was
kaputtgeht.

Die Rauchtests werten `GET /module` aus. Ohne Konto ist die Liste
berechtigterweise leer, und die betroffenen Tests überspringen sich:

```bash
HOMEPI_SMOKE_BENUTZER=aaron HOMEPI_SMOKE_PASSWORT=… make smoke
```

Unit-Tests laufen immer. Integration und Rauchtest sind standardmäßig
abgewählt — sonst würde ein Testlauf ohne Datenbank scheitern und man gewöhnt
sich an rote Läufe.

**Die Integrationstests benutzen niemals `app`.** Sie legen Tabellen an und
löschen sie wieder; liefen sie auf der Arbeitsdatenbank, wären deren Daten
nach jedem Testlauf weg.

Die Rauchtests sind dieselben, die später gegen den Pi laufen. Was sich
unterscheidet, ist die Basis-URL aus `homepi.toml`:

```bash
make smoke                              # [ziele.standard] -> localhost:18000
HOMEPI_ZIEL=pi pytest -m smoke          # -> der Pi
```

## Ein neues Artefakt

```bash
homepi new messwerte          # legt modules/... bzw. services/... an
```

Als **Modul** (Standard, ein Prozess für alle Artefakte):

1. Paket unter `modules/<name>/` mit einem `APIRouter`
2. Entry Point in der `pyproject.toml`:
   ```toml
   [project.entry-points."homepi.module"]
   messwerte = "homepi_messwerte:modul"
   ```
3. Als Abhängigkeit in `services/gateway/pyproject.toml` eintragen
4. `make dev` neu bauen — die Kachel erscheint von selbst auf der Startseite

Schritt 4 braucht **keine** Frontend-Änderung. Eine eigene Oberfläche ist
optional; ohne sie zeigt die generische Ansicht die Endpunkte aus dem
OpenAPI-Schema. Wer mehr will, trägt eine Komponente in
`services/web/src/module/register.ts` ein.

Begründung für Modul statt eigenem Container: [06-artefakte.md](06-artefakte.md).

## Fallstricke, die hier schon zugeschlagen haben

**`exec: uvicorn: not found` im Produktions-Image.** Die venv wurde unter
`/app/services/gateway/.venv` gebaut und nach `/app/.venv` kopiert — die
Shebangs der Skripte zeigten danach ins Leere. Lösung: `UV_PROJECT_ENVIRONMENT`
setzt den Zielpfad direkt. Die CI startet das Image jetzt testweise, weil ein
Image, das baut, aber nicht startet, kein gebautes Image ist.

**node_modules vom Host.** Im Dev-Container liegt ein anonymes Volume auf
`/app/node_modules`. Ohne das überdeckt das Windows-`node_modules` das im Image
installierte, und esbuild findet seine Linux-Binärdatei nicht.

**CRLF.** `.gitattributes` erzwingt LF. Ohne das startet auf dem Pi kein
einziges Shell-Skript (`bad interpreter: /bin/bash^M`).

**Port 8000 ist belegt.** Auf diesem Rechner lauscht dort bereits etwas anderes.
Deshalb 18000 — und deshalb prüft man das besser vorher, statt sich zu wundern,
warum `curl` eine fremde Antwort liefert.
