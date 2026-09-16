"""Rauchtests gegen eine laufende Instanz.

    docker compose -f compose.dev.yml up -d
    uv run pytest -m smoke

Gegen den Pi spaeter mit HOMEPI_ZIEL=pi - dieselben Tests, andere Basis-URL.
"""

from homepi_core.testing.smoke import *  # noqa: F403
