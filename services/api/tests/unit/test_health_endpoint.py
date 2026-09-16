"""Der Endpunkt selbst. Die Datenbank wird ersetzt - das ist hier Absicht,
die echte Verbindung prueft tests/integration/test_database.py."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from homepi_api import db


@pytest.fixture
def datenbank_antwortet(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _ping() -> bool:
        return True

    monkeypatch.setattr(db, "ping", _ping)


@pytest.fixture
def datenbank_schweigt(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _ping() -> bool:
        return False

    monkeypatch.setattr(db, "ping", _ping)


async def test_health_meldet_200_wenn_alles_laeuft(
    client: AsyncClient, datenbank_antwortet: None
) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_health_meldet_503_ohne_datenbank(
    client: AsyncClient, datenbank_schweigt: None
) -> None:
    response = await client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "down"


async def test_health_nennt_die_version(client: AsyncClient, datenbank_antwortet: None) -> None:
    """Damit nach einem Deploy erkennbar ist, was tatsaechlich laeuft."""
    body = (await client.get("/health")).json()

    assert body["version"]
    assert body["checks"] == {"database": True}
