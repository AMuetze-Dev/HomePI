from __future__ import annotations

from homepi_core.cache import Cache


async def test_ping_meldet_false_statt_zu_werfen() -> None:
    """Wie bei der Datenbank: ein Healthcheck darf nicht explodieren."""
    cache = Cache("redis://127.0.0.1:59998/0")
    try:
        assert await cache.ping() is False
    finally:
        await cache.dispose()


async def test_client_ist_erreichbar() -> None:
    cache = Cache("redis://127.0.0.1:59998/0")
    try:
        assert cache.client is not None
    finally:
        await cache.dispose()
