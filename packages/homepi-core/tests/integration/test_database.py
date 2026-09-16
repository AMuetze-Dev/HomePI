"""Laeuft nur mit echter Datenbank:  pytest -m integration"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from homepi_core.db import Database

pytestmark = pytest.mark.integration

URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:15432/test")


@pytest.fixture
async def db():
    datenbank = Database(URL)
    yield datenbank
    await datenbank.dispose()


async def test_ping_findet_die_datenbank(db: Database) -> None:
    assert await db.ping() is True


async def test_ping_meldet_false_statt_zu_werfen() -> None:
    datenbank = Database("postgresql+asyncpg://nobody:wrong@127.0.0.1:59999/nope")
    try:
        assert await datenbank.ping() is False
    finally:
        await datenbank.dispose()


async def test_verbindung_kann_lesen(db: Database) -> None:
    async with db.connection() as conn:
        assert (await conn.execute(text("SELECT 42"))).scalar_one() == 42


async def test_session_macht_rollback_bei_fehler(db: Database) -> None:
    with pytest.raises(RuntimeError):
        async with db.session() as sitzung:
            await sitzung.execute(text("SELECT 1"))
            raise RuntimeError("Abbruch")
