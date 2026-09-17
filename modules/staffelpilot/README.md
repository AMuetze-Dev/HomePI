# homepi-staffelpilot

Spielberichte pruefen und abhaken - der Kern der Arbeit eines Staffelleiters.

Geprüfte Spielberichte kommen ueber `POST /staffelpilot/import` herein, ihre
Befunde werden entschieden, und **erst wenn zu jedem Befund eine Entscheidung
vorliegt**, laesst sich ein Bericht abhaken. Das ist die eine Zusage dieses
Artefakts: nichts uebersehen.

| Endpunkt | |
|---|---|
| `GET /` | Warteschlange, optional `?staffel_id=` |
| `GET /zusammenfassung` | die Zahlen fuer die Kachel |
| `GET/POST /staffeln`, `PATCH/DELETE /staffeln/{id}` | Staffeln verwalten |
| `POST /import` | geprueftte Berichte einspielen |
| `GET /spiele/{id}` | ein Bericht mit seinen Befunden, sortiert |
| `POST/DELETE /spiele/{id}/haken` | abhaken und wieder loesen |
| `POST /befunde/{id}/entscheidung` | `kenntnis` oder `verworfen` (mit Grund) |

## Was hier bewusst nicht liegt

Die **DFBnet-Automation**. Sie faehrt minutenlang einen echten Browser und
gehoert nach [docs/06-artefakte.md](../../docs/06-artefakte.md) in einen
eigenen Dienst - im gemeinsamen Gateway-Prozess wuerde sie jedes andere
Artefakt blockieren, und die synchrone Playwright-API laesst sich aus einer
laufenden Event-Loop ohnehin nicht aufrufen.

`POST /import` ist die Naht, an der sie spaeter ansetzt. Ebenso noch offen:
das Regelwerk (31 Regeln), Mahnungsformulare und Sportgerichtsfaelle.

Die bestehende Anwendung, aus der die Fachlichkeit stammt, liegt unter
`D:/DevLibrary/StaffelPilot` und ist von diesem Artefakt unberuehrt.

Artefakt im HomePI-Gateway. Grundgeruest kommt aus `homepi-core`:
Einstellungen, Logging, `/health`, `/info`, Fehlerformat, Anfrage-Kennung.

**Fuer Agenten: [AGENTS.md](AGENTS.md)** - dort steht, was zu tun ist.

## Entwickeln

```bash
make dev                  # Umgebung hoch (Frontend 5173, API 18000)
uv sync
uv run ptw . --now        # Unit-Tests im Watch-Modus
```

Integrationstests brauchen die laufende Datenbank:

```bash
DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m ''
```

## Ausrollen

```bash
homepi deploy -s staffelpilot
```

Danach erscheint die Kachel auf der Startseite - ohne Frontend-Aenderung.
