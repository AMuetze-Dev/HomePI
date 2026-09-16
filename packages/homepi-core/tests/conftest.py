from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from homepi_core import ServiceSettings, create_service
from homepi_core.settings import get_settings


@pytest.fixture(autouse=True)
def _settings_cache_leeren() -> AsyncIterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _umgebung_saeubern(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Rechner des Entwicklers hat moeglicherweise DATABASE_URL gesetzt.
    Ohne diese Fixture haengen die Tests davon ab, wer sie startet."""
    for name in ("DATABASE_URL", "REDIS_URL", "ENVIRONMENT", "SERVICE_NAME", "CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings() -> ServiceSettings:
    return ServiceSettings(service_name="test-service", service_version="9.9.9")


@pytest.fixture
async def client(settings: ServiceSettings) -> AsyncIterator[AsyncClient]:
    app = create_service(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
