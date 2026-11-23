from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from homepi_core import Base, Modul, ServiceSettings, create_service, register_aus
from homepi_core.auth import Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.testing.datenbank import datenbank_fuer_tests
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from homepi_staffelpilot import modul as artefakt
from homepi_staffelpilot.dienst import DIENSTKONTO_VARIABLE

#: Nur eine Datenbank, die erkennbar zum Testen da ist - diese Tests
#: werfen das ganze Schema weg.
DATENBANK = datenbank_fuer_tests()

#: Nur hier, nur fuer Tests. Angelegt wird das Konto in der Fixture unten.
PASSWORT = "korrekt-pferd-batterie-heftklammer"


#: Wer hier der Pruefdienst ist -- im Betrieb sagt es die Umgebung des Gateways.
DIENSTKONTO = "pruefdienst"


@pytest.fixture
async def umgebung(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Any]:
    """Echte Datenbank, frische Tabellen, ein Dienst mit Anmeldung.

    Der Router besteht fast nur aus Datenbankzugriff - ihn gegen eine
    nachgebaute Sitzung zu testen wuerde vor allem den Nachbau testen.
    Deshalb sind die Tests damit als Integration markiert.
    """
    monkeypatch.setenv(DIENSTKONTO_VARIABLE, DIENSTKONTO)
    settings = ServiceSettings(
        service_name="staffelpilot-test", service_version="0.0.1", database_url=DATENBANK
    )
    app = create_service(settings, module=register_aus([artefakt]), anmeldung=True)
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        # Nicht `drop_all`: das kennt nur die Tabellen, die es heute gibt. Eine,
        # die ein frueherer Stand hier liegen liess, haelt mit ihrem
        # Fremdschluessel sonst jede andere fest.
        await verbindung.execute(text("DROP SCHEMA public CASCADE"))
        await verbindung.execute(text("CREATE SCHEMA public"))
        await verbindung.run_sync(Base.metadata.create_all)

    yield app

    await kontext.db.dispose()


async def _angemeldet(app: Any, name: str, anzeigename: str, rolle: Rolle) -> AsyncClient:
    async with app.state.homepi.db.session() as sitzung:
        benutzer = await auth_speicher.lege_benutzer_an(sitzung, name, PASSWORT, anzeigename)
        await auth_speicher.setze_recht(sitzung, benutzer.id, artefakt.id, rolle)

    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    antwort = await c.post("/auth/anmelden", json={"name": name, "passwort": PASSWORT})
    assert antwort.status_code == 200, antwort.text
    return c


@pytest.fixture
async def client(umgebung: Any) -> AsyncIterator[AsyncClient]:
    """Angemeldeter Staffelleiter mit Verwalterrecht.

    Angemeldet, weil das Artefakt geschuetzt ist: die Tests gehen damit durch
    denselben Weg wie ein echter Aufruf und nicht an der Pruefung vorbei.
    """
    c = await _angemeldet(umgebung, "staffelleiter", "Staffelleiter", Rolle.VERWALTER)
    yield c
    await c.aclose()


@pytest.fixture
async def zweite(umgebung: Any, client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Eine zweite Staffelleiterin, nur mit Nutzerrecht -- neben `client`."""
    c = await _angemeldet(umgebung, "erika", "Erika Muster", Rolle.NUTZER)
    yield c
    await c.aclose()


@pytest.fixture
async def verwalterin(umgebung: Any, client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Ein zweiter Mensch mit Verwalterrecht -- und trotzdem nur ein Staffelleiter."""
    c = await _angemeldet(umgebung, "vera", "Vera Verwalter", Rolle.VERWALTER)
    yield c
    await c.aclose()


@pytest.fixture
async def pruefdienst(umgebung: Any, client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Der Pruefdienst: das eine Konto, das alles erreicht."""
    c = await _angemeldet(umgebung, DIENSTKONTO, "Pruefdienst", Rolle.VERWALTER)
    yield c
    await c.aclose()


@pytest.fixture
async def leser(umgebung: Any, client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Jemand, der nur zusehen darf."""
    c = await _angemeldet(umgebung, "lena", "Lena Leser", Rolle.LESER)
    yield c
    await c.aclose()


@pytest.fixture
def modul() -> Modul:
    return artefakt
