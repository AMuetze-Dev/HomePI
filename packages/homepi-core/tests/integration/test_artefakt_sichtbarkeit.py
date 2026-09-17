"""Artefakt-Sichtbarkeit gegen eine echte Datenbank.

Der ganze Weg, den ein Besucher nimmt: anmelden, Cookie bekommen, Manifest
holen, ein fremdes Artefakt aufrufen. Die Einzelteile prüfen die Unit-Tests;
hier geht es darum, dass die Kette hält.

Der Fall aus der Praxis: ein Staffelleiter benutzt StaffelPilot. Von den
Geräten im Haus soll er nicht einmal erfahren, dass es sie gibt.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from homepi_core import (
    Base,
    Modul,
    Modulregister,
    ServiceSettings,
    Zugang,
    create_service,
    register_aus,
)
from homepi_core.auth import Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.modules import DefektesModul

pytestmark = pytest.mark.integration

URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:15432/test")
PASSWORT = "korrekt-pferd-batterie-heftklammer"


def _modul(kennung: str, zugang: Zugang) -> Modul:
    router = APIRouter()

    @router.get("/", summary=f"Wurzel von {kennung}")
    async def wurzel() -> dict[str, str]:
        return {"modul": kennung}

    return Modul(id=kennung, titel=kennung.title(), router=router, zugang=zugang)


def _register() -> Modulregister:
    register = register_aus(
        [
            _modul("start", Zugang.OEFFENTLICH),
            _modul("geraete", Zugang.GESCHUETZT),
            _modul("staffelpilot", Zugang.GESCHUETZT),
        ]
    )
    register.defekte.append(DefektesModul(id="kaputt", grund="ImportError: kein pandas"))
    return register


@pytest.fixture
async def app_und_kontext():
    app = create_service(
        ServiceSettings(service_name="sichtbarkeit-test", database_url=URL),
        module=_register(),
        anmeldung=True,
    )
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
        await verbindung.run_sync(Base.metadata.create_all)

    yield app, kontext
    await kontext.db.dispose()


@pytest.fixture
async def client(app_und_kontext) -> AsyncIterator[AsyncClient]:
    app, _ = app_und_kontext
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def staffelleiter(app_und_kontext):
    """Jemand, der StaffelPilot benutzt - und sonst nichts."""
    _, kontext = app_und_kontext
    async with kontext.db.session() as sitzung:
        benutzer = await auth_speicher.lege_benutzer_an(
            sitzung, "leiter", PASSWORT, "Staffelleiter"
        )
        await auth_speicher.setze_recht(sitzung, benutzer.id, "staffelpilot", Rolle.VERWALTER)
        return benutzer


async def _anmelden(client: AsyncClient, name: str) -> None:
    antwort = await client.post("/auth/anmelden", json={"name": name, "passwort": PASSWORT})
    assert antwort.status_code == 200


def _ids(antwort: object) -> set[str]:
    assert isinstance(antwort, list)
    return {str(eintrag["id"]) for eintrag in antwort}


# --- Ohne Anmeldung --------------------------------------------------------


async def test_ein_besucher_sieht_nur_das_oeffentliche(client: AsyncClient) -> None:
    assert _ids((await client.get("/module")).json()) == {"start"}


async def test_ein_besucher_kommt_an_das_oeffentliche_artefakt(client: AsyncClient) -> None:
    assert (await client.get("/start/")).json() == {"modul": "start"}


async def test_ein_besucher_wird_am_geschuetzten_artefakt_abgewiesen(client: AsyncClient) -> None:
    assert (await client.get("/geraete/")).status_code == 401


async def test_ein_defektes_artefakt_bleibt_unbeteiligten_verborgen(client: AsyncClient) -> None:
    assert "kaputt" not in _ids((await client.get("/module")).json())


# --- Angemeldet ------------------------------------------------------------


async def test_ein_staffelleiter_erfaehrt_nichts_von_den_geraeten(
    client: AsyncClient, staffelleiter
) -> None:
    """Der Kern der Sache. Nicht 'gesperrt', sondern nicht vorhanden."""
    await _anmelden(client, "leiter")

    sichtbar = _ids((await client.get("/module")).json())

    assert sichtbar == {"start", "staffelpilot"}


async def test_sein_eigenes_artefakt_ist_erreichbar(client: AsyncClient, staffelleiter) -> None:
    await _anmelden(client, "leiter")

    assert (await client.get("/staffelpilot/")).json() == {"modul": "staffelpilot"}


async def test_ein_fremdes_artefakt_bleibt_zu(client: AsyncClient, staffelleiter) -> None:
    await _anmelden(client, "leiter")

    antwort = await client.get("/geraete/")

    assert antwort.status_code == 403
    assert antwort.json()["artefakt"] == "geraete"


async def test_nach_dem_abmelden_ist_wieder_alles_zu(client: AsyncClient, staffelleiter) -> None:
    await _anmelden(client, "leiter")
    await client.post("/auth/abmelden")

    assert _ids((await client.get("/module")).json()) == {"start"}
    assert (await client.get("/staffelpilot/")).status_code == 401


async def test_ein_entzogenes_recht_wirkt_sofort(
    client: AsyncClient, staffelleiter, app_und_kontext
) -> None:
    """Ohne diese Eigenschaft bliebe ein entzogenes Recht bis zum Ablauf der
    Sitzung wirkungslos - bis zu vierzehn Tage."""
    _, kontext = app_und_kontext
    await _anmelden(client, "leiter")

    async with kontext.db.session() as sitzung:
        await auth_speicher.entziehe_recht(sitzung, staffelleiter.id, "staffelpilot")

    assert (await client.get("/staffelpilot/")).status_code == 403
    assert _ids((await client.get("/module")).json()) == {"start"}


async def test_ein_abgelaufenes_cookie_gilt_wie_kein_cookie(client: AsyncClient) -> None:
    """Das Manifest darf daran nicht scheitern - sonst sähe ein Besucher mit
    altem Cookie einen Fehler statt der öffentlichen Seite."""
    client.cookies.set("homepi_sitzung", "gibt-es-nicht")

    antwort = await client.get("/module")

    assert antwort.status_code == 200
    assert _ids(antwort.json()) == {"start"}
