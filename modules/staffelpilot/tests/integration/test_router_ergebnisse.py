"""Die Ergebnisseite gegen eine echte Datenbank."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import befund, einspielen, spiel, staffel_anlegen

pytestmark = pytest.mark.integration


class TestErgebnisse:
    async def test_eine_leere_installation_zeigt_nullen(self, client: AsyncClient) -> None:
        werte = (await client.get("/staffelpilot/ergebnisse")).json()

        assert werte["befunde"] == 0
        assert werte["spiele"] == 0
        # Die drei Schweren stehen trotzdem da.
        assert len(werte["nach_schwere"]) == 3

    async def test_sie_zaehlt_ueber_alle_spiele(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(
            client,
            staffel_id,
            spiel("M-1", befunde=[befund(), befund(regel="foto", schwere="hinweis")]),
            spiel("M-2", befunde=[befund()]),
        )

        werte = (await client.get("/staffelpilot/ergebnisse")).json()

        assert werte["befunde"] == 3
        assert werte["offen"] == 3
        assert werte["spiele"] == 2

    async def test_sie_gruppiert_nach_regel(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(
            client,
            staffel_id,
            spiel(befunde=[befund(), befund(regel="foto"), befund(regel="foto2")]),
        )

        nach_regel = (await client.get("/staffelpilot/ergebnisse")).json()["nach_regel"]

        assert {p["name"] for p in nach_regel} == {"rote_karte", "foto", "foto2"}

    async def test_der_monat_kommt_aus_dem_spieltag(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(
            client,
            staffel_id,
            spiel("M-1", datum="2026-09-13", befunde=[befund()]),
            spiel("M-2", datum="2026-10-04", befunde=[befund()]),
        )

        nach_monat = (await client.get("/staffelpilot/ergebnisse")).json()["nach_monat"]

        assert [p["name"] for p in nach_monat] == ["2026-09", "2026-10"]

    async def test_entschiedenes_zaehlt_mit_aber_nicht_als_offen(self, client: AsyncClient) -> None:
        """Ein verworfener Befund ist passiert. Er verschwindet nicht aus der
        Jahresbilanz, nur weil jemand ihn entschieden hat."""
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund()]))
        b = (await client.get("/staffelpilot/befunde")).json()[0]
        await client.post(
            f"/staffelpilot/befunde/{b['id']}/entscheidung",
            json={"art": "verworfen", "grund": "kein Verstoß"},
        )

        werte = (await client.get("/staffelpilot/ergebnisse")).json()

        assert werte["befunde"] == 1
        assert werte["offen"] == 0

    async def test_nach_staffel_filtern(self, client: AsyncClient) -> None:
        erste = await staffel_anlegen(client)
        zweite = await staffel_anlegen(client, name="Stadtliga D")
        await einspielen(client, erste, spiel("M-1", befunde=[befund()]))
        await einspielen(client, zweite, spiel("M-2", befunde=[befund(), befund(regel="x")]))

        werte = (await client.get(f"/staffelpilot/ergebnisse?staffel_id={erste}")).json()

        assert werte["befunde"] == 1
        assert werte["spiele"] == 1

    async def test_abgehakte_spiele_werden_gezaehlt(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel("M-1"), spiel("M-2"))
        spiel_id = (await client.get("/staffelpilot/")).json()[0]["id"]
        await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")

        werte = (await client.get("/staffelpilot/ergebnisse")).json()

        assert werte["spiele"] == 2
        assert werte["abgehakt"] == 1

    async def test_die_route_steht_vor_der_spielkennung(self, client: AsyncClient) -> None:
        """Waere es umgekehrt, versuchte FastAPI 'ergebnisse' als UUID zu lesen."""
        assert (await client.get("/staffelpilot/ergebnisse")).status_code == 200
