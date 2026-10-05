"""Erfundene Spiele kommen nicht in die scharfe Ansicht — und wieder heraus.

Der Anlass war echt: drei Spiele der Attrappe standen zwischen einunddreißig
Spielen aus DFBnet, weil der Prüfdienst mit `PRUEFDIENST_LESER=demo` lief und
in dieselbe Datenbank schrieb. Aus einer solchen Liste entstehen Mahnungen.

Zwei Zusicherungen stehen hier:

* **Aus heißt aus.** Der ganze Lauf wird abgewiesen, nicht ein Spiel still
  weggelassen — ein halb eingespielter Lauf sieht hinterher aus wie einer, bei
  dem nichts war.
* **Weg heißt nur die Attrappe.** Das Aufräumen hängt an der Kennung, nicht an
  einem Zeitraum.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import befund, einspielen, spiel, staffel_anlegen

pytestmark = pytest.mark.integration


async def _erlauben(client: AsyncClient, ja: bool) -> None:
    antwort = await client.put("/staffelpilot/einstellungen", json={"beispieldaten": ja})
    assert antwort.status_code == 200, antwort.text


class TestDieSperre:
    async def test_ein_erfundenes_spiel_wird_abgewiesen(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)

        antwort = await einspielen(client, staffel_id, spiel("DEMO-aa67-1"))

        assert antwort.status_code == 409, antwort.text
        assert "DEMO-aa67-1" in antwort.text

    async def test_der_ganze_lauf_wird_abgewiesen_und_nicht_halb(self, client: AsyncClient) -> None:
        """Die wichtigere der beiden Zusicherungen.

        Würde das echte Spiel durchgehen und das erfundene wegfallen, stünde
        in der Warteschlange ein Lauf, der vollständig aussieht.
        """
        staffel_id = await staffel_anlegen(client)

        await einspielen(client, staffel_id, spiel("031DHM03"), spiel("DEMO-aa67-1"))

        assert (await client.get("/staffelpilot/?nur_faellig=false")).json() == []

    async def test_echte_spiele_kommen_durch(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)

        antwort = await einspielen(client, staffel_id, spiel("031DHM03"))

        assert antwort.status_code == 200, antwort.text

    async def test_mit_schalter_kommt_die_attrappe_durch(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await _erlauben(client, True)

        antwort = await einspielen(client, staffel_id, spiel("DEMO-aa67-1"))

        assert antwort.status_code == 200, antwort.text

    async def test_der_schalter_ist_frisch_aus(self, client: AsyncClient) -> None:
        werte = (await client.get("/staffelpilot/einstellungen")).json()

        assert werte["beispieldaten"] is False


class TestDasAufraeumen:
    async def _mit_beiden(self, client: AsyncClient) -> str:
        staffel_id = await staffel_anlegen(client)
        await _erlauben(client, True)
        await einspielen(
            client,
            staffel_id,
            spiel("031DHM03", heim="SV Loschwitz"),
            spiel("DEMO-aa67-1", befunde=[befund()]),
        )
        await _erlauben(client, False)
        return staffel_id

    async def test_es_sagt_wie_viele_noch_stecken(self, client: AsyncClient) -> None:
        await self._mit_beiden(client)

        assert (await client.get("/staffelpilot/beispieldaten")).json()["anzahl"] == 1

    async def test_ohne_attrappe_steht_da_null(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel("031DHM03"))

        assert (await client.get("/staffelpilot/beispieldaten")).json()["anzahl"] == 0

    async def test_nur_die_erfundenen_gehen_weg(self, client: AsyncClient) -> None:
        """Die Bedingung steht auf der Kennung. Ein DELETE ohne sie wäre die
        Saison."""
        await self._mit_beiden(client)

        antwort = await client.delete("/staffelpilot/beispieldaten")

        assert antwort.json()["entfernt"] == 1
        uebrig = (await client.get("/staffelpilot/?nur_faellig=false")).json()
        assert [z["dfbnet_id"] for z in uebrig] == ["031DHM03"]

    async def test_die_befunde_gehen_mit(self, client: AsyncClient) -> None:
        """Ein Befund zu einem Spiel, das es nie gab, bleibt nicht als Waise
        in der Befundliste stehen."""
        await self._mit_beiden(client)
        vorher = (await client.get("/staffelpilot/befunde")).json()
        assert vorher, "der Test braucht einen Befund an der Attrappe"

        await client.delete("/staffelpilot/beispieldaten")

        assert (await client.get("/staffelpilot/befunde")).json() == []

    async def test_zweimal_aufraeumen_schadet_nicht(self, client: AsyncClient) -> None:
        await self._mit_beiden(client)
        await client.delete("/staffelpilot/beispieldaten")

        antwort = await client.delete("/staffelpilot/beispieldaten")

        assert antwort.status_code == 200
        assert antwort.json()["entfernt"] == 0
