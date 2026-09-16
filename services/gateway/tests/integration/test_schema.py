"""Der Startvorgang gegen eine echte Datenbank.

DB_SCHEMA_ANLEGEN ist ein Startwerkzeug, kein Migrationssystem - aber es muss
tun, was es verspricht, sonst steht nach dem ersten Deploy ein Gateway ohne
Tabellen da.
"""

from __future__ import annotations

import os

import pytest
from homepi_core import Base
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration

URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:15432/test")


@pytest.fixture
async def leere_datenbank():
    engine = create_async_engine(URL)
    async with engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    yield
    engine = create_async_engine(URL)
    async with engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _app_starten(monkeypatch: pytest.MonkeyPatch, *, anlegen: bool):
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("SERVICE_NAME", "gateway")
    monkeypatch.setenv("DB_SCHEMA_ANLEGEN", "true" if anlegen else "false")

    # Nach dem Setzen der Umgebung importieren: main.py baut die App beim Import.
    import importlib

    import homepi_gateway.main as hauptmodul

    modul = importlib.reload(hauptmodul)
    return modul.app


async def _tabellen() -> list[str]:
    engine = create_async_engine(URL)
    try:
        async with engine.connect() as verbindung:
            return await verbindung.run_sync(lambda s: inspect(s).get_table_names())
    finally:
        await engine.dispose()


async def test_schema_wird_beim_start_angelegt(
    monkeypatch: pytest.MonkeyPatch, leere_datenbank: None
) -> None:
    app = await _app_starten(monkeypatch, anlegen=True)

    async with app.router.lifespan_context(app):
        pass

    # Die Tabelle des geraete-Moduls muss dabei sein: alle Module erben von
    # derselben Base, deshalb genuegt dem Gateway ein Durchgang.
    assert "geraete" in await _tabellen()


async def test_ohne_schalter_wird_nichts_angelegt(
    monkeypatch: pytest.MonkeyPatch, leere_datenbank: None
) -> None:
    """In Produktion steht der Schalter auf false - ein Schema aendert man
    mit einer Migration, nicht beim Start."""
    app = await _app_starten(monkeypatch, anlegen=False)

    async with app.router.lifespan_context(app):
        pass

    assert "geraete" not in await _tabellen()


async def test_zweiter_start_ist_unschaedlich(
    monkeypatch: pytest.MonkeyPatch, leere_datenbank: None
) -> None:
    """create_all legt nur Fehlendes an - ein Neustart darf nicht scheitern."""
    app = await _app_starten(monkeypatch, anlegen=True)

    async with app.router.lifespan_context(app):
        pass
    async with app.router.lifespan_context(app):
        pass

    assert "geraete" in await _tabellen()


async def test_gateway_arbeitet_nach_dem_start(
    monkeypatch: pytest.MonkeyPatch, leere_datenbank: None
) -> None:
    from httpx import ASGITransport, AsyncClient

    app = await _app_starten(monkeypatch, anlegen=True)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            gesundheit = await client.get("/health")
            geraete = await client.get("/geraete/")

    assert gesundheit.status_code == 200
    assert gesundheit.json()["checks"]["database"] is True
    assert geraete.status_code == 200
    assert geraete.json() == []

    # Eine leere Datenbank ist etwas anderes als eine fehlende Tabelle.
    async with create_async_engine(URL).connect() as verbindung:
        assert (await verbindung.execute(text("SELECT count(*) FROM geraete"))).scalar() == 0
