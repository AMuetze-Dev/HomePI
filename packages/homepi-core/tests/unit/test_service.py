from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from homepi_core import ServiceSettings, create_service
from homepi_core.middleware import HEADER


async def test_health_ohne_abhaengigkeiten(client: AsyncClient) -> None:
    antwort = await client.get("/health")

    assert antwort.status_code == 200
    koerper = antwort.json()
    assert koerper["status"] == "ok"
    assert koerper["service"] == "test-service"
    assert koerper["version"] == "9.9.9"


async def test_info_nennt_die_abhaengigkeiten(client: AsyncClient) -> None:
    koerper = (await client.get("/info")).json()

    assert koerper["service"] == "test-service"
    assert koerper["environment"] == "entwicklung"
    assert koerper["abhaengigkeiten"] == []


async def test_request_id_wird_erzeugt(client: AsyncClient) -> None:
    antwort = await client.get("/info")

    assert antwort.headers[HEADER]


async def test_vorhandene_request_id_wird_uebernommen(client: AsyncClient) -> None:
    """Damit ein Aufruf ueber mehrere Services hinweg verfolgbar bleibt."""
    antwort = await client.get("/info", headers={HEADER: "abc123"})

    assert antwort.headers[HEADER] == "abc123"


async def test_datenbank_wird_als_sonde_registriert() -> None:
    einstellungen = ServiceSettings(
        service_name="mit-db",
        database_url="postgresql+asyncpg://app:app@127.0.0.1:59999/nix",
    )
    app = create_service(einstellungen)

    assert app.state.homepi.db is not None
    assert "database" in app.state.homepi.health.names


async def test_health_meldet_503_wenn_die_datenbank_fehlt() -> None:
    einstellungen = ServiceSettings(
        service_name="mit-db",
        database_url="postgresql+asyncpg://app:app@127.0.0.1:59999/nix",
    )
    app = create_service(einstellungen)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        antwort = await c.get("/health")

    assert antwort.status_code == 503
    assert antwort.json()["status"] == "down"


async def test_context_meldet_fehlende_datenbank_verstaendlich() -> None:
    app = create_service(ServiceSettings(service_name="ohne-db"))

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        app.state.homepi.require_db()


class TestKeinZwischenspeicher:
    """Ein Fehler, den erst ein Oberflaechentest gefunden hat: ein Recht stand
    in der Datenbank, die Oberflaeche zeigte weiter den alten Wert. Der Browser
    hatte die unveraenderte Adresse aus seinem Zwischenspeicher bedient."""

    async def test_jede_antwort_traegt_no_store(self, client: AsyncClient) -> None:
        assert (await client.get("/info")).headers["cache-control"] == "no-store"

    async def test_auch_die_fehlerantwort(self, client: AsyncClient) -> None:
        """Sonst merkt sich der Browser ein 404, das laengst keines mehr ist."""
        assert (await client.get("/gibtsnicht")).headers["cache-control"] == "no-store"

    async def test_ein_eigener_wert_bleibt_stehen(self) -> None:
        """setdefault statt setzen: ein Endpunkt, der es besser weiss, soll es
        sagen duerfen."""
        from starlette.responses import Response

        app = create_service(ServiceSettings(service_name="probe"))

        @app.get("/eigen")
        async def eigen() -> Response:
            return Response(
                "{}",
                media_type="application/json",
                headers={"Cache-Control": "max-age=60"},
            )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.get("/eigen")).headers["cache-control"] == "max-age=60"
