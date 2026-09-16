"""Die Dependencies, ueber die ein Modul an Datenbank und Einstellungen kommt.

Ein Modul kennt die Anwendung nicht, in die es eingehaengt wird - deshalb
laufen diese Zugriffe ueber den Request und nicht ueber eine globale Variable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from homepi_core import Modul, ServiceSettings, create_service, register_aus
from homepi_core.deps import DbSitzung, Einstellungen, Kontext

TOTE_DB = "postgresql+asyncpg://app:app@127.0.0.1:59999/nix"


def _modul_mit_deps() -> Modul:
    router = APIRouter()

    @router.get("/kontext")
    async def kontext(k: Kontext) -> dict[str, object]:
        return {"service": k.settings.service_name, "hat_db": k.db is not None}

    @router.get("/einstellungen")
    async def einstellungen(e: Einstellungen) -> dict[str, str]:
        return {"name": e.service_name}

    @router.get("/sitzung")
    async def sitzung(s: DbSitzung) -> dict[str, bool]:
        return {"sitzung": s is not None}

    return Modul(id="probe", titel="Probe", router=router)


async def _client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_service(
        ServiceSettings(service_name="deps-test"), module=register_aus([_modul_mit_deps()])
    )
    async for c in _client(app):
        yield c


async def test_kontext_kommt_beim_modul_an(client: AsyncClient) -> None:
    koerper = (await client.get("/probe/kontext")).json()

    assert koerper["service"] == "deps-test"
    assert koerper["hat_db"] is False


async def test_einstellungen_kommen_beim_modul_an(client: AsyncClient) -> None:
    assert (await client.get("/probe/einstellungen")).json() == {"name": "deps-test"}


async def test_ohne_datenbank_gibt_es_eine_klare_meldung(client: AsyncClient) -> None:
    """Der Endpunkt verlangt eine Sitzung, der Service hat keine Datenbank."""
    antwort = await client.get("/probe/sitzung")

    assert antwort.status_code == 500
    assert antwort.json()["title"] == "Interner Fehler"


async def test_sitzung_wird_geliefert_wenn_es_eine_datenbank_gibt() -> None:
    app = create_service(
        ServiceSettings(service_name="deps-test", database_url=TOTE_DB),
        module=register_aus([_modul_mit_deps()]),
    )
    kontext = app.state.homepi

    assert kontext.db is not None
    assert kontext.require_db() is kontext.db
    await kontext.db.dispose()


async def test_fremde_anwendung_meldet_sich_verstaendlich() -> None:
    """Wer die Dependencies in einer App ohne create_service benutzt, soll
    das erfahren - nicht ein AttributeError irgendwo tiefer."""
    fremde = FastAPI()
    fremde.include_router(_modul_mit_deps().router, prefix="/probe")

    async for client in _client(fremde):
        antwort = await client.get("/probe/kontext")
        assert antwort.status_code == 500
