"""Start und Herunterfahren. Ohne diese Tests merkt niemand, dass Verbindungen
beim Beenden offen bleiben - bis Postgres irgendwann keine mehr vergibt."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from homepi_core import ServiceContext, ServiceSettings, create_service

TOTE_DB = "postgresql+asyncpg://app:app@127.0.0.1:59999/nix"


async def test_lifespan_laeuft_durch() -> None:
    app = create_service(ServiceSettings(service_name="x"))

    async with app.router.lifespan_context(app):
        pass


async def test_datenbank_wird_beim_herunterfahren_geschlossen() -> None:
    app = create_service(ServiceSettings(service_name="x", database_url=TOTE_DB))
    engine = app.state.homepi.db.engine

    async with app.router.lifespan_context(app):
        pass

    # Eine entsorgte Engine legt einen frischen Pool an - der alte ist weg.
    assert engine.pool.checkedout() == 0


async def test_on_startup_wird_vorher_und_nachher_ausgefuehrt() -> None:
    verlauf: list[str] = []

    async def start(kontext: ServiceContext) -> AsyncIterator[None]:
        verlauf.append(f"start:{kontext.settings.service_name}")
        yield
        verlauf.append("ende")

    app = create_service(ServiceSettings(service_name="mit-hook"), on_startup=start)

    async with app.router.lifespan_context(app):
        verlauf.append("laeuft")

    assert verlauf == ["start:mit-hook", "laeuft", "ende"]


async def test_on_startup_ohne_abschluss_ist_erlaubt() -> None:
    """Ein Hook, der nach dem yield nichts mehr tut, darf einfach enden."""

    async def start(_: ServiceContext) -> AsyncIterator[None]:
        yield

    app = create_service(ServiceSettings(service_name="x"), on_startup=start)

    async with app.router.lifespan_context(app):
        pass


async def test_fehlender_cache_meldet_sich_verstaendlich() -> None:
    app = create_service(ServiceSettings(service_name="x"))

    with pytest.raises(RuntimeError, match="REDIS_URL"):
        app.state.homepi.require_cache()
