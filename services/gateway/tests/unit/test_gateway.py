"""Das Gateway selbst: findet es die Artefakte und haengt es sie richtig ein?"""

from __future__ import annotations

from httpx import AsyncClient


async def test_geraete_modul_wird_gefunden(angemeldet: AsyncClient) -> None:
    """Der Entry Point ist die einzige Verdrahtung zwischen Artefakt und
    Gateway - ein Tippfehler dort faellt sonst erst im Betrieb auf."""
    eintraege = (await angemeldet.get("/module")).json()

    nach_id = {e["id"]: e for e in eintraege}
    assert "geraete" in nach_id
    assert nach_id["geraete"]["pfad"] == "/geraete"
    assert nach_id["geraete"]["status"] == "bereit"


async def test_kein_modul_ist_defekt(angemeldet: AsyncClient) -> None:
    defekt = [e for e in (await angemeldet.get("/module")).json() if e["status"] == "fehler"]

    assert not defekt, f"Module konnten nicht geladen werden: {defekt}"


async def test_ohne_anmeldung_ist_nichts_zu_sehen(client: AsyncClient) -> None:
    """Auf diesem Gateway ist kein Artefakt oeffentlich. Ein Besucher ohne
    Konto soll nicht erfahren, was hier laeuft."""
    assert (await client.get("/module")).json() == []


async def test_info_nennt_nur_die_anzahl(client: AsyncClient) -> None:
    """/info braucht keine Anmeldung - die Namen der Artefakte gehen nur den
    etwas an, der sie sehen darf."""
    koerper = (await client.get("/info")).json()

    assert koerper["service"] == "gateway"
    assert koerper["module"] >= 1


async def test_router_haengt_unter_dem_praefix(angemeldet: AsyncClient) -> None:
    """Ohne Datenbank antwortet der Endpunkt mit 500 - aber eben nicht mit 404.
    Dass die Route existiert, ist hier die Frage; ob sie Daten liefert, prueft
    der Integrationstest des Moduls."""
    antwort = await angemeldet.get("/geraete/")

    assert antwort.status_code == 500
    assert antwort.status_code != 404


async def test_ohne_recht_kommt_niemand_an_die_geraete(client: AsyncClient) -> None:
    """Die Pruefung haengt am ganzen Router. Sie gilt damit auch fuer Endpunkte,
    die es heute noch gar nicht gibt."""
    antwort = await client.get("/geraete/")

    assert antwort.status_code == 401
    assert "problem+json" in antwort.headers["content-type"]


async def test_openapi_beschreibt_die_modulpfade(client: AsyncClient) -> None:
    """Die generische Ansicht im Frontend liest genau dieses Schema. In
    Produktion ist es zu - siehe homepi_core."""
    pfade = (await client.get("/openapi.json")).json()["paths"]

    assert any(p.startswith("/geraete") for p in pfade)


async def test_die_anmeldung_ist_erreichbar(client: AsyncClient) -> None:
    """Ohne diesen Endpunkt kaeme niemand an die geschuetzten Artefakte."""
    antwort = await client.post("/auth/anmelden", json={"name": "x", "passwort": "y"})

    # Ohne Datenbank scheitert der Aufruf - aber die Route ist da.
    assert antwort.status_code != 404


async def test_unbekannter_pfad_liefert_problem_json(client: AsyncClient) -> None:
    antwort = await client.get("/gibtsnicht")

    assert antwort.status_code == 404
    assert "problem+json" in antwort.headers["content-type"]
