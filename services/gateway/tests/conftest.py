from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True, scope="session")
def _ohne_datenbank() -> AsyncIterator[None]:
    """Die Unit-Tests pruefen die Verdrahtung, nicht die Datenbank.

    Ohne dieses Leeren haengt das Ergebnis davon ab, ob in der Shell gerade
    ein DATABASE_URL gesetzt ist - und der Test faellt mal so, mal so aus.
    """
    import os

    gemerkt = os.environ.pop("DATABASE_URL", None)
    yield
    if gemerkt is not None:
        os.environ["DATABASE_URL"] = gemerkt


@pytest.fixture
async def client(_ohne_datenbank: None) -> AsyncIterator[AsyncClient]:
    """Gegen das echte Gateway samt entdeckter Module - ohne Datenbank.

    Dass die Module tatsaechlich gefunden werden, ist genau das, was hier
    geprueft werden soll; mit einer nachgebauten Liste waere der Test wertlos.
    """
    # Erst hier importieren: das Modul baut die App beim Import, und das
    # soll nach dem Leeren von DATABASE_URL passieren.
    from homepi_gateway.main import app as gateway_app

    # raise_app_exceptions=False: ohne Datenbank wirft der Endpunkt, und genau
    # dieser Fall soll als HTTP-Antwort sichtbar sein statt den Test mit einem
    # Stacktrace abzubrechen.
    transport = ASGITransport(app=gateway_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
