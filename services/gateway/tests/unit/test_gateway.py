"""Das Gateway selbst: findet es die Artefakte und haengt es sie richtig ein?"""

from __future__ import annotations

from httpx import AsyncClient


async def test_geraete_modul_wird_gefunden(client: AsyncClient) -> None:
    """Der Entry Point ist die einzige Verdrahtung zwischen Artefakt und
    Gateway - ein Tippfehler dort faellt sonst erst im Betrieb auf."""
    eintraege = (await client.get("/module")).json()

    nach_id = {e["id"]: e for e in eintraege}
    assert "geraete" in nach_id
    assert nach_id["geraete"]["pfad"] == "/geraete"
    assert nach_id["geraete"]["status"] == "bereit"


async def test_kein_modul_ist_defekt(client: AsyncClient) -> None:
    defekt = [e for e in (await client.get("/module")).json() if e["status"] == "fehler"]

    assert not defekt, f"Module konnten nicht geladen werden: {defekt}"


async def test_info_nennt_die_module(client: AsyncClient) -> None:
    koerper = (await client.get("/info")).json()

    assert koerper["service"] == "gateway"
    assert "geraete" in koerper["module"]


async def test_router_haengt_unter_dem_praefix(client: AsyncClient) -> None:
    """Ohne Datenbank antwortet der Endpunkt mit 500 - aber eben nicht mit 404.
    Dass die Route existiert, ist hier die Frage; ob sie Daten liefert, prueft
    der Integrationstest des Moduls."""
    antwort = await client.get("/geraete/")

    assert antwort.status_code == 500
    assert antwort.status_code != 404


async def test_openapi_beschreibt_die_modulpfade(client: AsyncClient) -> None:
    """Die generische Ansicht im Frontend liest genau dieses Schema."""
    pfade = (await client.get("/openapi.json")).json()["paths"]

    assert any(p.startswith("/geraete") for p in pfade)


async def test_unbekannter_pfad_liefert_problem_json(client: AsyncClient) -> None:
    antwort = await client.get("/gibtsnicht")

    assert antwort.status_code == 404
    assert "problem+json" in antwort.headers["content-type"]
