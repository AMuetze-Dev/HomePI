from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

#: Es wird nie verbunden. Die Unit-Tests pruefen die Verdrahtung des Gateways,
#: nicht die Datenbank - aber ohne DATABASE_URL laesst sich das Gateway gar
#: nicht mehr bauen, seit die Artefakte eine Anmeldung voraussetzen.
TOTE_DB = "postgresql+asyncpg://app:app@127.0.0.1:59999/nix"


@pytest.fixture(autouse=True, scope="session")
def _tote_datenbank() -> AsyncIterator[None]:
    """Sonst haengt das Ergebnis davon ab, ob in der Shell gerade ein
    DATABASE_URL gesetzt ist - und der Test faellt mal so, mal so aus."""
    import os

    gemerkt = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TOTE_DB
    yield
    if gemerkt is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = gemerkt


def _gateway_app(_tote_datenbank: None):
    # Erst hier importieren: das Modul baut die App beim Import, und das soll
    # nach dem Setzen von DATABASE_URL passieren.
    from homepi_gateway.main import app as gateway_app

    return gateway_app


@pytest.fixture
async def client(_tote_datenbank: None) -> AsyncIterator[AsyncClient]:
    """Gegen das echte Gateway samt entdeckter Module - ohne Anmeldung.

    Dass die Module tatsaechlich gefunden werden, ist genau das, was hier
    geprueft werden soll; mit einer nachgebauten Liste waere der Test wertlos.
    """
    # raise_app_exceptions=False: ohne Datenbank wirft der Endpunkt, und genau
    # dieser Fall soll als HTTP-Antwort sichtbar sein statt den Test mit einem
    # Stacktrace abzubrechen.
    transport = ASGITransport(app=_gateway_app(_tote_datenbank), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def angemeldet(_tote_datenbank: None) -> AsyncIterator[AsyncClient]:
    """Wie ``client``, aber mit Rechten fuer jedes entdeckte Artefakt.

    Die Anmeldung wird ersetzt statt nachgebaut: eine echte braeuchte eine
    Datenbank, und die prueft der Integrationstest.
    """
    from homepi_core.auth.deps import hole_benutzer, hole_benutzer_optional
    from homepi_core.auth.dienst import Rolle
    from homepi_core.auth.modelle import Benutzer, Recht

    app = _gateway_app(_tote_datenbank)
    register = app.state.homepi.module
    kennung = uuid.uuid4()
    benutzer = Benutzer(
        id=kennung,
        name="pruefer",
        anzeigename="Prüfer",
        passwort_hash="egal",
        aktiv=True,
        rechte=[
            Recht(benutzer_id=kennung, artefakt=artefakt, rolle=Rolle.VERWALTER.value)
            for artefakt in register.ids + [d.id for d in register.defekte]
        ],
    )
    app.dependency_overrides[hole_benutzer] = lambda: benutzer
    app.dependency_overrides[hole_benutzer_optional] = lambda: benutzer

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
