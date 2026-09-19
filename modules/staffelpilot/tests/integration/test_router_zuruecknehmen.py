"""Zurücknehmen, Staffel bearbeiten, die flache Befundliste."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import UNBEKANNT, befund, einspielen, spiel, staffel_anlegen

pytestmark = pytest.mark.integration


async def ein_befund(client: AsyncClient, weg: str = "kein") -> tuple[str, str]:
    """Gibt (spiel_id, befund_id) eines eingespielten Berichts zurück."""
    staffel_id = await staffel_anlegen(client)
    await einspielen(client, staffel_id, spiel(befunde=[befund(weg=weg)]))
    spiel_id = (await client.get("/staffelpilot/")).json()[0]["id"]
    befunde = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"]
    return spiel_id, str(befunde[0]["id"])


async def abhaken(client: AsyncClient, spiel_id: str, befund_id: str) -> None:
    await client.post(f"/staffelpilot/befunde/{befund_id}/entscheidung", json={"art": "kenntnis"})
    antwort = await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")
    assert antwort.status_code == 200, antwort.text


# ── Entscheidung zurücknehmen ─────────────────────────────────────────────


class TestZuruecknehmen:
    async def test_der_befund_ist_danach_wieder_offen(self, client: AsyncClient) -> None:
        _, befund_id = await ein_befund(client)
        await client.post(
            f"/staffelpilot/befunde/{befund_id}/entscheidung",
            json={"art": "verworfen", "grund": "war doch keiner"},
        )

        antwort = await client.delete(f"/staffelpilot/befunde/{befund_id}/entscheidung")

        assert antwort.status_code == 200, antwort.text
        assert antwort.json()["entscheidung"] == "offen"
        assert antwort.json()["grund"] == ""

    async def test_der_haken_faellt_mit(self, client: AsyncClient) -> None:
        """Abgehakt heisst: zu jedem Befund liegt eine Entscheidung vor. Den
        Haken stehen zu lassen waere genau diese Zusage gebrochen."""
        spiel_id, befund_id = await ein_befund(client)
        await abhaken(client, spiel_id, befund_id)

        await client.delete(f"/staffelpilot/befunde/{befund_id}/entscheidung")

        bericht = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()
        assert bericht["abgehakt"] is False
        assert bericht["abgehakt_am"] is None

    async def test_danach_blockiert_das_abhaken_wieder(self, client: AsyncClient) -> None:
        spiel_id, befund_id = await ein_befund(client)
        await abhaken(client, spiel_id, befund_id)
        await client.delete(f"/staffelpilot/befunde/{befund_id}/entscheidung")

        assert (await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")).status_code == 409

    async def test_ein_entwurf_steht_dem_nicht_im_weg(self, client: AsyncClient) -> None:
        """Solange nichts hinaus ist, laesst sich alles geradeziehen."""
        _, befund_id = await ein_befund(client, weg="mahnung")
        await client.post(
            f"/staffelpilot/befunde/{befund_id}/entscheidung", json={"art": "kenntnis"}
        )
        await client.post(f"/staffelpilot/befunde/{befund_id}/vorgang", json={})

        antwort = await client.delete(f"/staffelpilot/befunde/{befund_id}/entscheidung")

        assert antwort.status_code == 200, antwort.text

    async def test_ein_versandtes_schreiben_schon(self, client: AsyncClient) -> None:
        """Der Verein hat es. Ein Befund, der hier wieder 'offen' heisst, waere
        eine Akte, die dem widerspricht, was draussen steht."""
        _, befund_id = await ein_befund(client, weg="mahnung")
        await client.post(
            f"/staffelpilot/befunde/{befund_id}/entscheidung", json={"art": "kenntnis"}
        )
        vorgang = (await client.post(f"/staffelpilot/befunde/{befund_id}/vorgang", json={})).json()
        await client.post(
            f"/staffelpilot/vorgaenge/{vorgang['id']}/zustand", json={"zustand": "versandt"}
        )

        antwort = await client.delete(f"/staffelpilot/befunde/{befund_id}/entscheidung")

        assert antwort.status_code == 409
        assert "zurueck in den Entwurf" in antwort.text

    async def test_nach_dem_zurueckholen_geht_es_wieder(self, client: AsyncClient) -> None:
        _, befund_id = await ein_befund(client, weg="mahnung")
        await client.post(
            f"/staffelpilot/befunde/{befund_id}/entscheidung", json={"art": "kenntnis"}
        )
        vorgang = (await client.post(f"/staffelpilot/befunde/{befund_id}/vorgang", json={})).json()
        pfad = f"/staffelpilot/vorgaenge/{vorgang['id']}/zustand"
        await client.post(pfad, json={"zustand": "versandt"})
        await client.post(pfad, json={"zustand": "entwurf"})

        antwort = await client.delete(f"/staffelpilot/befunde/{befund_id}/entscheidung")

        assert antwort.status_code == 200, antwort.text

    async def test_unbekannter_befund_gibt_404(self, client: AsyncClient) -> None:
        antwort = await client.delete(f"/staffelpilot/befunde/{UNBEKANNT}/entscheidung")

        assert antwort.status_code == 404


# ── Staffel bearbeiten ────────────────────────────────────────────────────


class TestStaffelBearbeiten:
    async def test_name_und_spielklasse_aendern(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)

        antwort = await client.patch(
            f"/staffelpilot/staffeln/{staffel_id}",
            json={"name": "Stadtliga D", "spielklasse": "4.Kreisliga (D)"},
        )

        assert antwort.json()["name"] == "Stadtliga D"
        assert antwort.json()["spielklasse"] == "4.Kreisliga (D)"

    async def test_ausgelassene_felder_bleiben_stehen(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)

        await client.patch(f"/staffelpilot/staffeln/{staffel_id}", json={"aktiv": False})
        danach = (await client.get("/staffelpilot/staffeln")).json()[0]

        assert danach["aktiv"] is False
        assert danach["name"] == "Stadtliga C"
        assert danach["saison"] == "26/27"

    async def test_der_schalter_allein_geht_weiterhin(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)

        assert (
            await client.patch(f"/staffelpilot/staffeln/{staffel_id}", json={"aktiv": False})
        ).json()["aktiv"] is False

    async def test_ein_vergebener_name_wird_abgelehnt(self, client: AsyncClient) -> None:
        await staffel_anlegen(client)
        zweite = await staffel_anlegen(client, name="Stadtliga D")

        antwort = await client.patch(
            f"/staffelpilot/staffeln/{zweite}", json={"name": "Stadtliga C"}
        )

        assert antwort.status_code == 409

    async def test_unbekannte_staffel_gibt_404(self, client: AsyncClient) -> None:
        antwort = await client.patch(f"/staffelpilot/staffeln/{UNBEKANNT}", json={"aktiv": False})

        assert antwort.status_code == 404


# ── Alle Befunde ──────────────────────────────────────────────────────────


class TestAlleBefunde:
    async def test_am_anfang_ist_nichts_da(self, client: AsyncClient) -> None:
        assert (await client.get("/staffelpilot/befunde")).json() == []

    async def test_jede_zeile_traegt_ihr_spiel(self, client: AsyncClient) -> None:
        """Ohne das Spiel an der Zeile ist ein Befund nicht zuzuordnen."""
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund()]))

        zeile = (await client.get("/staffelpilot/befunde")).json()[0]

        assert zeile["heim"] == "SG Gittersee"
        assert zeile["dfbnet_id"] == "M-1"
        assert zeile["titel"] == "Feldverweis auf Dauer"

    async def test_ueber_alle_spiele_hinweg(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(
            client,
            staffel_id,
            spiel("M-1", befunde=[befund()]),
            spiel("M-2", befunde=[befund(), befund(regel="anderes")]),
        )

        assert len((await client.get("/staffelpilot/befunde")).json()) == 3

    async def test_nach_staffel_filtern(self, client: AsyncClient) -> None:
        erste = await staffel_anlegen(client)
        zweite = await staffel_anlegen(client, name="Stadtliga D")
        await einspielen(client, erste, spiel("M-1", befunde=[befund()]))
        await einspielen(client, zweite, spiel("M-2", befunde=[befund()]))

        zeilen = (await client.get(f"/staffelpilot/befunde?staffel_id={erste}")).json()

        assert [z["dfbnet_id"] for z in zeilen] == ["M-1"]

    async def test_nur_offene(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund(), befund(regel="anderes")]))
        erster = (await client.get("/staffelpilot/befunde")).json()[0]
        await client.post(
            f"/staffelpilot/befunde/{erster['id']}/entscheidung", json={"art": "kenntnis"}
        )

        offen = (await client.get("/staffelpilot/befunde?nur_offen=true")).json()

        assert len(offen) == 1
        assert offen[0]["id"] != erster["id"]

    async def test_der_vorgang_steht_an_der_zeile(self, client: AsyncClient) -> None:
        _, befund_id = await ein_befund(client, weg="mahnung")
        vorgang = (await client.post(f"/staffelpilot/befunde/{befund_id}/vorgang", json={})).json()

        zeile = (await client.get("/staffelpilot/befunde")).json()[0]

        assert zeile["vorgang_id"] == vorgang["id"]
