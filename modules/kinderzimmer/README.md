# homepi-kinderzimmer

Spiele für die Kleinste: Figuren, Klänge, Stimmen

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
homepi deploy -s kinderzimmer
```

Danach erscheint die Kachel auf der Startseite - ohne Frontend-Aenderung.
