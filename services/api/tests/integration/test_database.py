"""Laeuft nur mit echter Datenbank:  pytest -m integration

Lokal:  make up-data   (oder ein beliebiger Postgres auf 127.0.0.1:5432)
CI:     Service-Container, DATABASE_URL kommt aus der Umgebung
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from homepi_api import db

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _use_test_database(monkeypatch: pytest.MonkeyPatch, database_url: str):
    """Die Engine ist ein Modul-Singleton - vor und nach jedem Test wegwerfen,
    sonst haengt der naechste Test an der Verbindung des vorigen."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    await db.dispose_engine()
    yield
    await db.dispose_engine()


async def test_ping_findet_die_datenbank() -> None:
    assert await db.ping() is True


async def test_ping_meldet_false_statt_zu_werfen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Healthcheck, der eine Exception wirft, ist kein Healthcheck."""
    from homepi_api.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://nobody:wrong@127.0.0.1:59999/nope")
    get_settings.cache_clear()
    await db.dispose_engine()

    assert await db.ping() is False


async def test_verbindung_kann_lesen() -> None:
    async with db.connection() as conn:
        result = await conn.execute(text("SELECT 42 AS antwort"))
        assert result.scalar_one() == 42
