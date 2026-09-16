"""pytest-Plugin. Wird über den Entry Point ``pytest11`` automatisch geladen,
sobald ``homepi-core[test]`` installiert ist - kein ``pytest_plugins`` nötig.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import httpx

    from .ziel import Ziel

# Absichtlich KEIN Import auf Modulebene ausser pytest: dieses Modul wird
# ueber den pytest11-Entry-Point beim Start JEDES Projekts geladen, das
# homepi-core[test] installiert hat. Httpx und die Zielaufloesung kommen erst,
# wenn eine Fixture sie wirklich braucht.


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "smoke: spricht mit einer laufenden Instanz (HOMEPI_ZIEL / HOMEPI_BASIS_URL)",
    )


@pytest.fixture(scope="session")
def ziel() -> Ziel:
    from .ziel import ziel_aus_umgebung

    return ziel_aus_umgebung()


@pytest.fixture
async def smoke_client(ziel: Ziel) -> AsyncIterator[httpx.AsyncClient]:
    """Client gegen das konfigurierte Ziel.

    Läuft dort nichts, scheitert der Test mit einer Meldung, die den Grund
    nennt - nicht mit einem nackten ConnectError, den man erst zuordnen muss.
    """
    import httpx

    async with httpx.AsyncClient(
        base_url=ziel.basis_url,
        timeout=ziel.timeout,
        verify=ziel.tls_pruefen,
        follow_redirects=True,
    ) as client:
        try:
            await client.get("/health")
        except httpx.ConnectError as problem:
            pytest.fail(
                f"Ziel '{ziel.name}' ({ziel.basis_url}) ist nicht erreichbar: {problem}\n"
                "Lokal starten:  uv run uvicorn <modul>:app\n"
                "Anderes Ziel:   HOMEPI_ZIEL=pi pytest -m smoke"
            )
        yield client
