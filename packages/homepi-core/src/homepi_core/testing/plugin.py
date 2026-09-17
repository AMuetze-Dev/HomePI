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
def testdatenbank() -> str:
    """Die URL, gegen die Integrationstests laufen duerfen.

    Sie bricht ab, wenn die Umgebung auf eine Arbeitsdatenbank zeigt -
    Integrationstests rufen drop_all auf, und das waere dort der Verlust aller
    Konten.
    """
    from .datenbank import datenbank_fuer_tests

    return datenbank_fuer_tests()


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


@pytest.fixture
async def angemeldeter_smoke_client(
    smoke_client: httpx.AsyncClient,
) -> AsyncIterator[httpx.AsyncClient]:
    """Wie ``smoke_client``, aber angemeldet.

    Seit Artefakte je Benutzer sichtbar sind, sagt ein anonymes ``GET /module``
    nichts mehr über den Zustand der Instanz: es ist berechtigterweise leer.
    Ohne Konto überspringen sich die betroffenen Tests deshalb ausdrücklich,
    statt auf einer leeren Liste stillschweigend grün zu werden.

        HOMEPI_SMOKE_BENUTZER=rauchtest HOMEPI_SMOKE_PASSWORT=… pytest -m smoke
    """
    import os

    name = os.environ.get("HOMEPI_SMOKE_BENUTZER", "").strip()
    passwort = os.environ.get("HOMEPI_SMOKE_PASSWORT", "")
    if not name or not passwort:
        pytest.skip(
            "HOMEPI_SMOKE_BENUTZER/HOMEPI_SMOKE_PASSWORT nicht gesetzt - "
            "ohne Konto sind die Artefakte erwartungsgemäß unsichtbar"
        )

    antwort = await smoke_client.post("/auth/anmelden", json={"name": name, "passwort": passwort})
    if antwort.status_code != 200:
        pytest.fail(
            f"Anmeldung als '{name}' scheiterte mit {antwort.status_code}. "
            "Konto anlegen: homepi benutzer anlegen <name> --passwort-stdin"
        )

    yield smoke_client

    await smoke_client.post("/auth/abmelden")
