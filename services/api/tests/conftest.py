from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from homepi_api.config import get_settings
from homepi_api.main import create_app


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> AsyncIterator[None]:
    """get_settings ist gecacht - sonst leckt Konfiguration zwischen Tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP-Client gegen die App, ohne echten Server und ohne freien Port."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def database_url() -> str:
    """Von der CI gesetzt; lokal der Postgres aus dem data-Stack."""
    return os.environ.get("DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:5432/app")
