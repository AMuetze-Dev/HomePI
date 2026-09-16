"""Datenbankzugriff.

Kein Modul-Singleton, sondern eine Instanz: sonst teilen sich Tests und
Anwendung dieselbe Engine und man jagt Zustand über Testgrenzen hinweg.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Kapselt Engine und Session-Factory eines Service."""

    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 5,
        echo: bool = False,
    ) -> None:
        # Der Pi hat vier Kerne. Ein großer Pool bringt nichts und belegt nur
        # Verbindungen, die andere Services und Home Assistant auch brauchen:
        # Postgres steht hier auf max_connections=100 für *alle* zusammen.
        self._engine: AsyncEngine = create_async_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            echo=echo,
        )
        self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection]:
        async with self._engine.connect() as conn:
            yield conn

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Transaktion mit Commit am Ende, Rollback bei Fehler."""
        async with self._sessionmaker() as sitzung:
            try:
                yield sitzung
                await sitzung.commit()
            except Exception:
                await sitzung.rollback()
                raise

    async def ping(self) -> bool:
        """True, wenn die Datenbank antwortet. Wirft nicht."""
        try:
            async with self.connection() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return False
        return True

    async def dispose(self) -> None:
        await self._engine.dispose()
