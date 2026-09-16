"""Fertige Rauchtests, die jedes HomePI-Projekt übernehmen kann.

    # tests/smoke/test_smoke.py
    from homepi_core.testing.smoke import *  # noqa: F401,F403

Damit laufen dieselben Prüfungen lokal, in der CI und gegen den Pi:

    pytest -m smoke                          # gegen das Standardziel
    HOMEPI_ZIEL=pi pytest -m smoke           # gegen den Pi
    HOMEPI_BASIS_URL=http://… pytest -m smoke

Sie prüfen, was nach jedem Deploy stimmen muss und was ein Unit-Test
grundsätzlich nicht sehen kann: dass der Prozess wirklich läuft, seine
Abhängigkeiten erreicht und alle Module geladen hat.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.smoke

ERLAUBTE_STATUS = {"ok", "degraded", "down"}


async def test_health_antwortet(smoke_client: httpx.AsyncClient) -> None:
    antwort = await smoke_client.get("/health")

    assert antwort.status_code in (200, 503), f"unerwarteter Code {antwort.status_code}"
    koerper = antwort.json()
    assert koerper["status"] in ERLAUBTE_STATUS
    assert isinstance(koerper["checks"], dict)


async def test_health_ist_gruen(smoke_client: httpx.AsyncClient) -> None:
    """Getrennt vom Formattest: so unterscheidet der Bericht 'Antwort kaputt'
    von 'Abhängigkeit weg'."""
    koerper = (await smoke_client.get("/health")).json()

    gestoert = [name for name, gesund in koerper["checks"].items() if not gesund]
    assert not gestoert, f"gestörte Abhängigkeiten: {', '.join(gestoert)}"


async def test_info_nennt_version_und_umgebung(smoke_client: httpx.AsyncClient) -> None:
    koerper = (await smoke_client.get("/info")).json()

    assert koerper["service"]
    assert koerper["version"], "ohne Version ist nach einem Deploy nicht erkennbar, was läuft"
    assert koerper["environment"]


async def test_modulmanifest_ist_vollstaendig(smoke_client: httpx.AsyncClient) -> None:
    """Überspringt sich selbst, wenn die Instanz kein Gateway ist."""
    antwort = await smoke_client.get("/module")
    if antwort.status_code == 404:
        pytest.skip("kein Gateway - dieser Dienst betreibt keine Module")

    eintraege: list[dict[str, Any]] = antwort.json()
    for eintrag in eintraege:
        for feld in ("id", "titel", "pfad", "status"):
            assert eintrag.get(feld) is not None, f"Feld '{feld}' fehlt in {eintrag}"


async def test_kein_modul_ist_defekt(smoke_client: httpx.AsyncClient) -> None:
    antwort = await smoke_client.get("/module")
    if antwort.status_code == 404:
        pytest.skip("kein Gateway")

    defekt = [e for e in antwort.json() if e.get("status") == "fehler"]
    namen = ", ".join(f"{e['id']} ({e['beschreibung']})" for e in defekt)
    assert not defekt, f"Module konnten nicht geladen werden: {namen}"


async def test_jedes_modul_ist_erreichbar(smoke_client: httpx.AsyncClient) -> None:
    """Ein Modul, das im Manifest steht, dessen Router aber nicht hängt, wäre
    sonst erst beim Klicken auf die Kachel aufgefallen."""
    antwort = await smoke_client.get("/module")
    if antwort.status_code == 404:
        pytest.skip("kein Gateway")

    for eintrag in antwort.json():
        if eintrag.get("status") != "bereit":
            continue
        pfad = eintrag["pfad"]
        code = (await smoke_client.get(pfad)).status_code
        # 404 hiesse: nichts unter diesem Praefix eingehaengt.
        # 401/403/422 sind in Ordnung - der Router ist da und antwortet.
        assert code != 404, f"Modul '{eintrag['id']}' ist im Manifest, aber {pfad} ist leer"
        assert code < 500, f"Modul '{eintrag['id']}' antwortet mit {code}"


async def test_anfragekennung_wird_zurueckgegeben(smoke_client: httpx.AsyncClient) -> None:
    """Ohne sie lässt sich ein Fehlerbericht des Benutzers nicht im Log finden."""
    antwort = await smoke_client.get("/info", headers={"X-Request-ID": "rauchtest"})

    assert antwort.headers.get("X-Request-ID") == "rauchtest"


async def test_unbekannter_pfad_liefert_problem_json(smoke_client: httpx.AsyncClient) -> None:
    antwort = await smoke_client.get("/gibt-es-nicht-4711")

    assert antwort.status_code == 404
    assert "problem+json" in antwort.headers.get("content-type", "")
    assert antwort.json()["title"]
