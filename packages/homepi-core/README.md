# homepi-core

Grundgerüst für HomePI-Microservices. Jeder Service erbt davon Konfiguration,
Logging, `/health`, `/info`, einheitliches Fehlerformat, Anfrage-Kennung und
den Deploy-Weg — statt das in jedem Projekt neu zu schreiben.

## Installation

Innerhalb dieses Repos:

```toml
[project]
dependencies = ["homepi-core"]

[tool.uv.sources]
homepi-core = { path = "../../packages/homepi-core", editable = true }
```

In einem anderen Repo:

```toml
[project]
dependencies = ["homepi-core"]

[tool.uv.sources]
homepi-core = { git = "https://github.com/AMuetze-Dev/HomePI.git", subdirectory = "packages/homepi-core", tag = "v0.2.0" }
```

Immer auf einen **Tag** pinnen, nie auf einen Branch: sonst ändert sich das
Verhalten deiner Services, ohne dass du etwas getan hast.

## Ein Service in zwölf Zeilen

```python
from homepi_core import ServiceSettings, create_service


class Settings(ServiceSettings):
    service_name: str = "geraete"
    service_version: str = "0.1.0"


settings = Settings()
app = create_service(settings)


@app.get("/geraete")
async def liste() -> list[str]:
    return ["lampe", "heizung"]
```

Was `create_service` mitbringt, ohne dass du etwas dafür tust:

| | |
|---|---|
| `GET /health` | führt alle Sonden nebenläufig aus, 200 oder 503 |
| `GET /info` | Name, Version, Umgebung, Abhängigkeiten |
| Logging | JSON in Produktion, lesbarer Text lokal |
| `X-Request-ID` | übernommen oder erzeugt, in jeder Logzeile |
| Zugriffslog | eine Zeile pro Anfrage mit Dauer, Healthchecks ausgenommen |
| Fehlerformat | RFC 9457 `problem+json` für alle Fehler |
| Datenbank | angelegt und als Sonde registriert, wenn `DATABASE_URL` gesetzt ist |
| Cache | dasselbe für `REDIS_URL`, aber nicht essenziell |
| Herunterfahren | Verbindungen werden sauber geschlossen |

## CLI

```bash
homepi doctor            # Voraussetzungen prüfen
homepi info              # welches Projekt erkannt wurde
homepi new geraete       # neuen Service anlegen
homepi deploy            # über die Pipeline auf den Pi
homepi deploy --dry-run  # nur zeigen, was passieren würde
```

`homepi deploy` baut nichts lokal. Es stößt `images.yml` an, wartet auf den
arm64-Build, stößt dann `deploy.yml` an und wartet erneut. Es gibt damit keinen
Weg, ungetesteten Code am CI-Lauf vorbei auf den Pi zu bekommen.
