"""Redis - optional.

Das Paket hängt nicht von ``redis`` ab; wer einen Cache braucht, installiert
``homepi-core[cache]``. Die Fehlermeldung sagt genau das, statt einen
ImportError durchzureichen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis


class CacheNichtVerfuegbar(RuntimeError):
    pass


class Cache:
    def __init__(self, url: str) -> None:
        try:
            from redis.asyncio import Redis
        except ImportError as fehler:  # pragma: no cover - hängt von der Installation ab
            raise CacheNichtVerfuegbar(
                "REDIS_URL ist gesetzt, aber das Paket 'redis' fehlt. "
                "Installiere homepi-core[cache]."
            ) from fehler

        self._client: Redis = Redis.from_url(url, decode_responses=True)

    @property
    def client(self) -> Redis:
        return self._client

    async def ping(self) -> bool:
        try:
            antwort: Any = await self._client.ping()
        except Exception:
            return False
        return bool(antwort)

    async def dispose(self) -> None:
        await self._client.aclose()
