from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from homepi_core import Base, Modul, ServiceSettings, create_service, register_aus
from httpx import ASGITransport, AsyncClient

from homepi_geraete import modul as geraete_modul

DATENBANK = os.environ.get("DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:15432/test")


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Echte Datenbank, frische Tabellen.

    Der Router besteht fast nur aus Datenbankzugriff - ihn gegen eine
    nachgebaute Sitzung zu testen wuerde vor allem den Nachbau testen.
    Deshalb sind diese Tests als Integration markiert.
    """
    settings = ServiceSettings(
        service_name="geraete-test", service_version="0.0.1", database_url=DATENBANK
    )
    app = create_service(settings, module=register_aus([geraete_modul]))
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
        await verbindung.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await kontext.db.dispose()


@pytest.fixture
def modul() -> Modul:
    return geraete_modul
