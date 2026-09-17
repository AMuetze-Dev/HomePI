from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from homepi_core import Base, Modul, ServiceSettings, create_service, register_aus
from homepi_core.auth import VERWALTUNG, Rolle
from homepi_core.auth import speicher as auth_speicher
from httpx import ASGITransport, AsyncClient

from homepi_verwaltung import modul as artefakt

DATENBANK = os.environ.get("DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:15432/test")

#: Nur fuer Tests. Die Konten legt die Fixture unten an.
PASSWORT = "korrekt-pferd-batterie-heftklammer"


@pytest.fixture
async def app_und_kontext():
    """Echte Datenbank, frische Tabellen.

    Die Verwaltung besteht fast nur aus Datenbankzugriff - gegen eine
    nachgebaute Sitzung wuerde man vor allem den Nachbau testen. Deshalb sind
    diese Tests als Integration markiert.
    """
    settings = ServiceSettings(
        service_name="verwaltung-test", service_version="0.0.1", database_url=DATENBANK
    )
    app = create_service(settings, module=register_aus([artefakt]), anmeldung=True)
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
        await verbindung.run_sync(Base.metadata.create_all)

    yield app, kontext
    await kontext.db.dispose()


async def _anlegen(kontext, name: str, *, verwalter: bool):
    async with kontext.db.session() as sitzung:
        benutzer = await auth_speicher.lege_benutzer_an(sitzung, name, PASSWORT, name.title())
        if verwalter:
            await auth_speicher.setze_recht(sitzung, benutzer.id, VERWALTUNG, Rolle.VERWALTER)
        return benutzer


@pytest.fixture
async def chefin(app_und_kontext):
    """Ein Konto, das die Verwaltung darf."""
    _, kontext = app_und_kontext
    return await _anlegen(kontext, "chefin", verwalter=True)


@pytest.fixture
async def gast(app_und_kontext):
    """Ein Konto ohne jedes Recht."""
    _, kontext = app_und_kontext
    return await _anlegen(kontext, "gast", verwalter=False)


@pytest.fixture
async def client(app_und_kontext, chefin) -> AsyncIterator[AsyncClient]:
    """Angemeldet als Verwalterin.

    Die Tests gehen damit denselben Weg wie ein echter Aufruf und nicht an der
    Zugriffspruefung vorbei.
    """
    app, _ = app_und_kontext
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        antwort = await c.post("/auth/anmelden", json={"name": "chefin", "passwort": PASSWORT})
        assert antwort.status_code == 200, antwort.text
        yield c


@pytest.fixture
async def anonym(app_und_kontext) -> AsyncIterator[AsyncClient]:
    app, _ = app_und_kontext
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def modul() -> Modul:
    return artefakt
