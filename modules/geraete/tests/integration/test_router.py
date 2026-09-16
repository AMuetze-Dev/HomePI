"""Der Router gegen eine echte Datenbank.

Als Integration markiert, weil er fast nur aus Datenbankzugriff besteht: gegen
eine nachgebaute Sitzung wuerde man vor allem den Nachbau testen.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def anlegen(client: AsyncClient, **rest: object) -> dict:
    daten = {"name": "Stehlampe", "raum": "Wohnzimmer", **rest}
    antwort = await client.post("/geraete/", json=daten)
    assert antwort.status_code == 201, antwort.text
    return antwort.json()


class TestAnlegen:
    async def test_legt_an_und_gibt_zurueck(self, client: AsyncClient) -> None:
        geraet = await anlegen(client)

        assert geraet["name"] == "Stehlampe"
        assert geraet["eingeschaltet"] is False
        assert geraet["id"]

    async def test_doppelter_name_wird_abgelehnt(self, client: AsyncClient) -> None:
        await anlegen(client)

        antwort = await client.post("/geraete/", json={"name": "Stehlampe", "raum": "Küche"})

        assert antwort.status_code == 409
        assert "problem+json" in antwort.headers["content-type"]
        assert "existiert bereits" in antwort.json()["detail"]

    async def test_ungueltige_daten_nennen_das_feld(self, client: AsyncClient) -> None:
        antwort = await client.post("/geraete/", json={"name": "", "raum": "Küche"})

        assert antwort.status_code == 422
        assert any("name" in f["feld"] for f in antwort.json()["fehler"])


class TestLesen:
    async def test_leere_liste(self, client: AsyncClient) -> None:
        assert (await client.get("/geraete/")).json() == []

    async def test_liste_ist_nach_raum_und_name_sortiert(self, client: AsyncClient) -> None:
        await anlegen(client, name="B", raum="Küche")
        await anlegen(client, name="A", raum="Küche")
        await anlegen(client, name="C", raum="Bad")

        namen = [g["name"] for g in (await client.get("/geraete/")).json()]

        assert namen == ["C", "A", "B"]

    async def test_einzelnes_geraet(self, client: AsyncClient) -> None:
        angelegt = await anlegen(client)

        antwort = await client.get(f"/geraete/{angelegt['id']}")

        assert antwort.json()["id"] == angelegt["id"]

    async def test_unbekannte_kennung_ergibt_404(self, client: AsyncClient) -> None:
        antwort = await client.get("/geraete/00000000-0000-0000-0000-000000000000")

        assert antwort.status_code == 404
        assert antwort.json()["title"] == "Gerät unbekannt"

    async def test_zusammenfassung_kollidiert_nicht_mit_der_kennung(
        self, client: AsyncClient
    ) -> None:
        """Die Route steht vor /{geraet_id} - sonst laese FastAPI das Wort
        'zusammenfassung' als UUID und antwortete mit 422."""
        await anlegen(client, name="A", raum="Küche", eingeschaltet=True)
        await anlegen(client, name="B", raum="Bad", zustand="wartung")

        antwort = await client.get("/geraete/zusammenfassung")

        assert antwort.status_code == 200
        koerper = antwort.json()
        assert koerper == {
            "anzahl": 2,
            "eingeschaltet": 1,
            "in_wartung": 1,
            "raeume": {"Bad": 1, "Küche": 1},
        }


class TestSchalten:
    async def test_einschalten(self, client: AsyncClient) -> None:
        geraet = await anlegen(client)

        antwort = await client.patch(f"/geraete/{geraet['id']}", json={"eingeschaltet": True})

        assert antwort.json()["eingeschaltet"] is True
        assert (await client.get(f"/geraete/{geraet['id']}")).json()["eingeschaltet"] is True

    async def test_wartung_verhindert_das_schalten(self, client: AsyncClient) -> None:
        geraet = await anlegen(client, zustand="wartung")

        antwort = await client.patch(f"/geraete/{geraet['id']}", json={"eingeschaltet": True})

        assert antwort.status_code == 409
        koerper = antwort.json()
        assert koerper["title"] == "Gerät ist nicht schaltbar"
        assert koerper["geraet_id"] == geraet["id"]


class TestEntfernen:
    async def test_entfernen(self, client: AsyncClient) -> None:
        geraet = await anlegen(client)

        assert (await client.delete(f"/geraete/{geraet['id']}")).status_code == 204
        assert (await client.get(f"/geraete/{geraet['id']}")).status_code == 404

    async def test_unbekanntes_entfernen_ergibt_404(self, client: AsyncClient) -> None:
        antwort = await client.delete("/geraete/00000000-0000-0000-0000-000000000000")

        assert antwort.status_code == 404
