"""Die Übertragung nach DFBnet — eine Warteschlange, die stillsteht.

Hier wird nichts übertragen. Geprüft wird die Liste dessen, was einzutragen
wäre, und dass sie auf einer frischen Installation pausiert ist.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import UNBEKANNT, befund, einspielen, spiel, staffel_anlegen

pytestmark = pytest.mark.integration


async def einreihen(client: AsyncClient, **daten: object) -> dict[str, object]:
    vorgabe = {"aktion": "prueferfreigabe", "referenz": "M-1"}
    antwort = await client.post("/staffelpilot/uebertragungen", json={**vorgabe, **daten})
    assert antwort.status_code == 201, antwort.text
    return dict(antwort.json())


async def scheitern(
    client: AsyncClient, uebertragung_id: str, meldung: str = "Zeitüberschreitung"
) -> None:
    antwort = await client.post(
        f"/staffelpilot/uebertragungen/{uebertragung_id}/abschluss",
        json={"zustand": "fehler", "meldung": meldung},
    )
    assert antwort.status_code == 200, antwort.text


class TestPause:
    async def test_eine_frische_installation_ueberträgt_nichts(self, client: AsyncClient) -> None:
        """Eine Freigabe in DFBnet ist eine Handlung nach aussen. Sie soll
        nicht passieren, weil jemand die Software zum ersten Mal gestartet
        hat."""
        stand = (await client.get("/staffelpilot/uebertragungen")).json()

        assert stand["pausiert"] is True
        assert stand["offen"] == 0

    async def test_der_schalter_laesst_sie_laufen(self, client: AsyncClient) -> None:
        antwort = await client.post("/staffelpilot/uebertragungen/pause", json={"pausiert": False})

        assert antwort.json()["pausiert"] is False
        assert (await client.get("/staffelpilot/uebertragungen")).json()["pausiert"] is False

    async def test_die_pause_steht_bei_den_einstellungen(self, client: AsyncClient) -> None:
        """Ein Schalter, zwei Wege dorthin - aber nur ein Wert."""
        await client.post("/staffelpilot/uebertragungen/pause", json={"pausiert": False})

        werte = (await client.get("/staffelpilot/einstellungen")).json()

        assert werte["uebertragung_pausiert"] is False

    async def test_und_laesst_sich_auch_dort_setzen(self, client: AsyncClient) -> None:
        await client.put("/staffelpilot/einstellungen", json={"uebertragung_pausiert": False})

        assert (await client.get("/staffelpilot/uebertragungen")).json()["pausiert"] is False


class TestEinreihen:
    async def test_vorgemerkt_heisst_offen(self, client: AsyncClient) -> None:
        zeile = await einreihen(client)

        assert zeile["zustand"] == "offen"
        assert zeile["versuche"] == 0

    async def test_zweimal_dasselbe_bleibt_eine_zeile(self, client: AsyncClient) -> None:
        """Abhaken, Haken entfernen und wieder abhaken darf keine zwei
        Freigaben erzeugen."""
        erste = await einreihen(client)
        zweite = await einreihen(client)

        assert zweite["id"] == erste["id"]
        assert (await client.get("/staffelpilot/uebertragungen")).json()["offen"] == 1

    async def test_eine_andere_aktion_ist_eine_andere_zeile(self, client: AsyncClient) -> None:
        await einreihen(client)
        await einreihen(client, aktion="fallanlage")

        assert (await client.get("/staffelpilot/uebertragungen")).json()["offen"] == 2

    async def test_das_zweite_abhaken_setzt_einen_fehler_zurueck(self, client: AsyncClient) -> None:
        """Das ist der Staffelleiter, der es noch einmal versucht."""
        zeile = await einreihen(client)
        await scheitern(client, str(zeile["id"]))

        wieder = await einreihen(client)

        assert wieder["zustand"] == "offen"
        assert wieder["letzter_fehler"] == ""

    async def test_eine_fertige_bleibt_fertig(self, client: AsyncClient) -> None:
        """Dieselbe Freigabe zweimal einzutragen saehe in DFBnet aus wie zwei
        Vorgaenge zu einem Spiel."""
        zeile = await einreihen(client)
        await client.post(
            f"/staffelpilot/uebertragungen/{zeile['id']}/abschluss", json={"zustand": "fertig"}
        )

        assert (await einreihen(client))["zustand"] == "fertig"

    async def test_eine_unbekannte_aktion_wird_abgelehnt(self, client: AsyncClient) -> None:
        antwort = await client.post(
            "/staffelpilot/uebertragungen", json={"aktion": "mail", "referenz": "M-1"}
        )

        assert antwort.status_code == 422


class TestAbhaken:
    async def test_abhaken_merkt_die_freigabe_vor(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel())
        spiel_id = (await client.get("/staffelpilot/")).json()[0]["id"]

        await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")

        stand = (await client.get("/staffelpilot/uebertragungen")).json()
        assert stand["offen"] == 1
        assert stand["pausiert"] is True

    async def test_zweimal_abhaken_bleibt_eine_freigabe(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel())
        spiel_id = (await client.get("/staffelpilot/")).json()[0]["id"]
        await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")
        await client.delete(f"/staffelpilot/spiele/{spiel_id}/haken")
        await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")

        assert (await client.get("/staffelpilot/uebertragungen")).json()["offen"] == 1

    async def test_ein_blockiertes_abhaken_merkt_nichts_vor(self, client: AsyncClient) -> None:
        """Ein Bericht mit offenem Befund wird nicht abgehakt - und darf
        deshalb auch nicht in DFBnet freigegeben werden."""
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund()]))
        spiel_id = (await client.get("/staffelpilot/")).json()[0]["id"]

        assert (await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")).status_code == 409
        assert (await client.get("/staffelpilot/uebertragungen")).json()["offen"] == 0


class TestAbschluss:
    async def test_fertig_haelt_den_zeitpunkt_fest(self, client: AsyncClient) -> None:
        zeile = await einreihen(client)

        antwort = await client.post(
            f"/staffelpilot/uebertragungen/{zeile['id']}/abschluss", json={"zustand": "fertig"}
        )

        assert antwort.json()["zustand"] == "fertig"
        assert antwort.json()["erledigt_am"] is not None
        assert antwort.json()["versuche"] == 1

    async def test_ein_fehler_steht_ausgeschrieben_da(self, client: AsyncClient) -> None:
        """Die gescheiterten sind das Einzige, wozu jemand etwas tun muss."""
        zeile = await einreihen(client)
        await scheitern(client, str(zeile["id"]), "DFBnet antwortet nicht")

        stand = (await client.get("/staffelpilot/uebertragungen")).json()

        assert stand["fehler"] == 1
        assert stand["fehlerhafte"][0]["letzter_fehler"] == "DFBnet antwortet nicht"

    async def test_jeder_versuch_wird_gezaehlt(self, client: AsyncClient) -> None:
        zeile = await einreihen(client)
        await scheitern(client, str(zeile["id"]))
        await client.post("/staffelpilot/uebertragungen/wiederholen")
        await scheitern(client, str(zeile["id"]))

        stand = (await client.get("/staffelpilot/uebertragungen")).json()

        assert stand["fehlerhafte"][0]["versuche"] == 2

    async def test_eine_fertige_nimmt_nichts_mehr_an(self, client: AsyncClient) -> None:
        zeile = await einreihen(client)
        pfad = f"/staffelpilot/uebertragungen/{zeile['id']}/abschluss"
        await client.post(pfad, json={"zustand": "fertig"})

        assert (await client.post(pfad, json={"zustand": "fehler"})).status_code == 409

    async def test_unbekannte_uebertragung_gibt_404(self, client: AsyncClient) -> None:
        antwort = await client.post(
            f"/staffelpilot/uebertragungen/{UNBEKANNT}/abschluss", json={"zustand": "fertig"}
        )

        assert antwort.status_code == 404


class TestWiederholen:
    async def test_alle_gescheiterten_auf_einmal(self, client: AsyncClient) -> None:
        """Nach einem Netzausfall stehen dort zwanzig Zeilen mit demselben
        Fehler. Die einzeln anzuklicken ist keine Arbeit, sondern eine
        Strafe."""
        erste = await einreihen(client, referenz="M-1")
        zweite = await einreihen(client, referenz="M-2")
        await scheitern(client, str(erste["id"]))
        await scheitern(client, str(zweite["id"]))

        stand = (await client.post("/staffelpilot/uebertragungen/wiederholen")).json()

        assert stand["fehler"] == 0
        assert stand["offen"] == 2

    async def test_eine_einzelne(self, client: AsyncClient) -> None:
        erste = await einreihen(client, referenz="M-1")
        zweite = await einreihen(client, referenz="M-2")
        await scheitern(client, str(erste["id"]))
        await scheitern(client, str(zweite["id"]))

        stand = (
            await client.post(
                f"/staffelpilot/uebertragungen/wiederholen?uebertragung_id={erste['id']}"
            )
        ).json()

        assert stand["fehler"] == 1
        assert stand["offen"] == 1

    async def test_eine_offene_wird_nicht_wiederholt(self, client: AsyncClient) -> None:
        zeile = await einreihen(client)

        antwort = await client.post(
            f"/staffelpilot/uebertragungen/wiederholen?uebertragung_id={zeile['id']}"
        )

        assert antwort.status_code == 409

    async def test_ohne_gescheiterte_passiert_nichts(self, client: AsyncClient) -> None:
        await einreihen(client)

        stand = (await client.post("/staffelpilot/uebertragungen/wiederholen")).json()

        assert stand["offen"] == 1
