"""Einen Sportgerichtsfall vormerken.

**Das eröffnet ein Verfahren gegen eine benannte Person.** Deshalb steht hier
mehr über das Abweisen als über das Gelingen, und deshalb hängt es an einem
eigenen Aufruf: anders als die Prüferfreigabe entsteht es nie nebenbei, weil
jemand einen Spielbericht abgehakt hat.

Die Pflichtangaben sind dieselben vier, die DFBnet im Erstellungsformular
verlangt. Geprüft werden sie **hier** — eine vorgemerkte Zeile, der eine davon
fehlt, scheitert sonst erst draußen, und ihre Ursache liegt zwei Klicks
entfernt in den Staffeleinstellungen.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import STAFFEL, befund, einspielen, spiel

pytestmark = pytest.mark.integration


async def _vorgang(
    client: AsyncClient,
    *,
    sportgericht: str = "Sportgericht Stadtverband Fußball Dresden e.V.",
    spielnummer: str = "633203004",
    weg: str = "sportgericht",
    grund: str = "Feldverweis auf Dauer wegen Tätlichkeit",
) -> str:
    """Eine Staffel, ein Spiel, ein Befund, ein Vorgang. Gibt die Vorgangskennung."""
    antwort = await client.post(
        "/staffelpilot/staffeln", json={**STAFFEL, "sportgericht": sportgericht}
    )
    assert antwort.status_code == 201, antwort.text
    staffel_id = antwort.json()["id"]

    await einspielen(
        client,
        staffel_id,
        spiel(
            "031DHM03",
            spielnummer=spielnummer,
            befunde=[befund(regel="player_eligibility", weg=weg)],
        ),
    )
    spiel_id = (await client.get("/staffelpilot/?nur_faellig=false")).json()[0]["id"]
    befund_id = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"][0]["id"]
    angelegt = await client.post(
        f"/staffelpilot/befunde/{befund_id}/vorgang",
        json={"verein": "SG Gittersee", "grund": grund},
    )
    assert angelegt.status_code in (200, 201), angelegt.text
    return str(angelegt.json()["id"])


class TestVormerken:
    async def test_es_entsteht_eine_zeile_in_der_warteschlange(self, client: AsyncClient) -> None:
        vorgang_id = await _vorgang(client)

        antwort = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")

        assert antwort.status_code == 201, antwort.text
        assert antwort.json()["aktion"] == "fallanlage"
        assert antwort.json()["referenz"] == vorgang_id

    async def test_sie_haengt_am_spiel(self, client: AsyncClient) -> None:
        """Der Dienst braucht daran die Spielnummer und die Staffel."""
        vorgang_id = await _vorgang(client)

        antwort = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")

        assert antwort.json()["spiel_id"]

    async def test_zweimal_vormerken_gibt_eine_zeile(self, client: AsyncClient) -> None:
        """Sonst stünden zwei Verfahren für dasselbe Vergehen an."""
        vorgang_id = await _vorgang(client)
        erste = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")
        zweite = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")

        assert zweite.status_code in (200, 201), zweite.text
        assert zweite.json()["id"] == erste.json()["id"]

    async def test_es_wird_nur_vorgemerkt_und_nicht_getan(self, client: AsyncClient) -> None:
        """Angelegt wird es vom Prüfdienst, und der steht frisch auf pausiert."""
        vorgang_id = await _vorgang(client)
        await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")

        stand = (await client.get("/staffelpilot/uebertragungen")).json()

        assert stand["pausiert"] is True
        assert stand["offen"] == 1


class TestAbgewiesen:
    async def test_ohne_sportgericht_an_der_staffel(self, client: AsyncClient) -> None:
        """Ein Verfahren vor dem falschen Gericht ist schlimmer als keines."""
        vorgang_id = await _vorgang(client, sportgericht="")

        antwort = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")

        assert antwort.status_code == 409, antwort.text
        assert "Sportgericht" in antwort.text

    async def test_ohne_spielnummer_am_bericht(self, client: AsyncClient) -> None:
        """Danach sucht das Formular in DFBnet."""
        vorgang_id = await _vorgang(client, spielnummer="")

        antwort = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")

        assert antwort.status_code == 409
        assert "Spielnummer" in antwort.text

    async def test_aus_einer_mahnung_wird_kein_verfahren(self, client: AsyncClient) -> None:
        """Die Art des Vorgangs entscheidet, nicht der Knopf, den jemand
        trifft."""
        vorgang_id = await _vorgang(client, weg="mahnung")

        antwort = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")

        assert antwort.status_code == 409
        assert "sportgericht" in antwort.text

    async def test_nach_dem_abweisen_steht_nichts_in_der_warteschlange(
        self, client: AsyncClient
    ) -> None:
        """Die wichtigere Hälfte: abgewiesen heißt auch nicht halb vorgemerkt."""
        vorgang_id = await _vorgang(client, sportgericht="")
        await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")

        assert (await client.get("/staffelpilot/uebertragungen")).json()["offen"] == 0

    async def test_einen_unbekannten_vorgang_gibt_es_nicht(self, client: AsyncClient) -> None:
        import uuid

        antwort = await client.post(f"/staffelpilot/vorgaenge/{uuid.uuid4()}/fallanlage")

        assert antwort.status_code == 404
