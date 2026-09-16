from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from homepi_core import ServiceError, ServiceSettings, create_service
from homepi_core.errors import PROBLEM_JSON


class GeraetUnbekannt(ServiceError):
    status = 404
    title = "Gerät unbekannt"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_service(ServiceSettings(service_name="fehler-test"))

    @app.get("/fachlich")
    async def fachlich() -> None:
        raise GeraetUnbekannt("Gerät 42 existiert nicht", geraet_id=42)

    @app.get("/http")
    async def http() -> None:
        raise HTTPException(status_code=403, detail="Nicht erlaubt")

    @app.get("/kaputt")
    async def kaputt() -> None:
        raise RuntimeError("Passwort im Klartext: geheim123")

    @app.get("/zahl/{wert}")
    async def zahl(wert: int) -> int:
        return wert

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_fachlicher_fehler_wird_zu_problem_json(client: AsyncClient) -> None:
    antwort = await client.get("/fachlich")

    assert antwort.status_code == 404
    assert antwort.headers["content-type"].startswith(PROBLEM_JSON)
    koerper = antwort.json()
    assert koerper["title"] == "Gerät unbekannt"
    assert koerper["detail"] == "Gerät 42 existiert nicht"
    assert koerper["instance"] == "/fachlich"
    assert koerper["geraet_id"] == 42


async def test_http_fehler_bekommt_dasselbe_format(client: AsyncClient) -> None:
    koerper = (await client.get("/http")).json()

    assert koerper["status"] == 403
    assert koerper["title"] == "Nicht erlaubt"


async def test_validierungsfehler_nennt_das_feld(client: AsyncClient) -> None:
    antwort = await client.get("/zahl/keine-zahl")

    assert antwort.status_code == 422
    assert antwort.json()["fehler"][0]["feld"].endswith("wert")


async def test_unerwarteter_fehler_verraet_nichts(client: AsyncClient) -> None:
    """Der Stacktrace gehoert ins Log, nicht in die Antwort."""
    antwort = await client.get("/kaputt")

    assert antwort.status_code == 500
    rohtext = antwort.text
    assert "geheim123" not in rohtext
    assert "Traceback" not in rohtext
    assert antwort.json()["title"] == "Interner Fehler"


async def test_jede_fehlerantwort_traegt_die_request_id(client: AsyncClient) -> None:
    koerper = (await client.get("/fachlich", headers={"X-Request-ID": "xyz"})).json()

    assert koerper["request_id"] == "xyz"


async def test_unbekannter_pfad_liefert_problem_json(client: AsyncClient) -> None:
    """Fuer nicht gefundene Routen wirft Starlette seine eigene HTTPException.
    Ein Handler, der nur auf FastAPIs Variante haengt, verpasst genau die -
    also ausgerechnet den haeufigsten Fehlerfall."""
    antwort = await client.get("/diesen-pfad-gibt-es-nicht")

    assert antwort.status_code == 404
    assert antwort.headers["content-type"].startswith(PROBLEM_JSON)
    assert antwort.json()["title"]
