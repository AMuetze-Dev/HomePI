"""Datenbankzugriff. Nur hier faellt echtes I/O an."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from .config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url,
            # Der Pi hat vier Kerne; ein grosser Pool bringt nichts und
            # belegt nur Verbindungen, die Home Assistant auch braucht.
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
        )
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


@asynccontextmanager
async def connection() -> AsyncIterator[AsyncConnection]:
    async with get_engine().connect() as conn:
        yield conn


async def ping() -> bool:
    """True, wenn die Datenbank antwortet. Wirft nicht."""
    try:
        async with connection() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # der Grund landet im Healthcheck, nicht hier
        return False
    return True
