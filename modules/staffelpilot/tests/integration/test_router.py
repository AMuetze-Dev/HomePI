"""Der Router gegen eine echte Datenbank.

Als Integration markiert, weil er fast nur aus Datenbankzugriff besteht: gegen
eine nachgebaute Sitzung wuerde man vor allem den Nachbau testen.

    make dev
    DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' uv run pytest -m ''
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import (
    STAFFEL,
    UNBEKANNT,
    befund,
    einspielen,
    erste_zeile,
    erster_befund,
    spiel,
    staffel_anlegen,
)

# Weitergereicht, damit beide Dateien dieselben Daten benutzen.
__all__ = ["STAFFEL", "UNBEKANNT"]

pytestmark = pytest.mark.integration


# ── Staffeln ──────────────────────────────────────────────────────────────


class TestStaffeln:
    async def test_am_anfang_ist_nichts_da(self, client: AsyncClient) -> None:
        assert (await client.get("/staffelpilot/staffeln")).json() == []

    async def test_anlegen_und_lesen(self, client: AsyncClient) -> None:
        await staffel_anlegen(client)
        namen = [s["name"] for s in (await client.get("/staffelpilot/staffeln")).json()]
        assert namen == ["Stadtliga C"]

    async def test_derselbe_name_zweimal_wird_abgelehnt(self, client: AsyncClient) -> None:
        await staffel_anlegen(client)
        antwort = await client.post("/staffelpilot/staffeln", json=STAFFEL)
        assert antwort.status_code == 409
        assert "problem+json" in antwort.headers["content-type"]

    async def test_ein_name_aus_leerzeichen_nennt_das_feld(self, client: AsyncClient) -> None:
        antwort = await client.post("/staffelpilot/staffeln", json={**STAFFEL, "name": "   "})
        assert antwort.status_code == 422
        assert "name" in antwort.text

    async def test_eine_unbekannte_altersklasse_wird_abgelehnt(self, client: AsyncClient) -> None:
        antwort = await client.post(
            "/staffelpilot/staffeln", json={**STAFFEL, "altersklasse": "ue99"}
        )
        assert antwort.status_code == 422

    async def test_umschalten(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        antwort = await client.patch(f"/staffelpilot/staffeln/{staffel_id}", json={"aktiv": False})
        assert antwort.status_code == 200
        assert antwort.json()["aktiv"] is False

    async def test_umschalten_einer_unbekannten_staffel(self, client: AsyncClient) -> None:
        antwort = await client.patch(f"/staffelpilot/staffeln/{UNBEKANNT}", json={"aktiv": True})
        assert antwort.status_code == 404

    async def test_loeschen_nimmt_die_spiele_mit(self, client: AsyncClient) -> None:
        """Sonst blieben Spielberichte ohne Staffel zurueck und tauchten in der
        Warteschlange auf, ohne dass man sie zuordnen koennte."""
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel())

        assert (await client.delete(f"/staffelpilot/staffeln/{staffel_id}")).status_code == 204
        assert (await client.get("/staffelpilot/")).json() == []

    async def test_loeschen_einer_unbekannten_staffel(self, client: AsyncClient) -> None:
        assert (await client.delete(f"/staffelpilot/staffeln/{UNBEKANNT}")).status_code == 404


# ── Einspielen ────────────────────────────────────────────────────────────


class TestEinspielen:
    async def test_ein_spiel_mit_befunden(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        zweiter = befund(
            regel="gelb_rot", schwere="warnung", titel="Gelb-Rote Karte", person="Jan Klein"
        )

        antwort = await einspielen(client, staffel_id, spiel(befunde=[befund(), zweiter]))

        assert antwort.status_code == 200
        assert antwort.json() == {"angelegt": 1, "aktualisiert": 0, "befunde": 2}

    async def test_in_eine_unbekannte_staffel_geht_nicht(self, client: AsyncClient) -> None:
        assert (await einspielen(client, UNBEKANNT, spiel())).status_code == 404

    async def test_derselbe_bericht_verdoppelt_sich_nicht(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel())

        antwort = await einspielen(client, staffel_id, spiel(ergebnis="3 : 1"))

        assert antwort.json() == {"angelegt": 0, "aktualisiert": 1, "befunde": 0}
        zeilen = (await client.get("/staffelpilot/")).json()
        assert len(zeilen) == 1
        assert zeilen[0]["ergebnis"] == "3 : 1"

    async def test_eine_getroffene_entscheidung_ueberlebt_den_zweiten_lauf(
        self, client: AsyncClient
    ) -> None:
        """Sonst faengt der Staffelleiter nach jedem Prueflauf von vorn an -
        und genau das macht den zweiten Lauf unbenutzbar."""
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund()]))
        spiel_id = (await erste_zeile(client))["id"]
        befund_id = (await erster_befund(client, spiel_id))["id"]
        await client.post(
            f"/staffelpilot/befunde/{befund_id}/entscheidung",
            json={"art": "verworfen", "grund": "Spieler war spielberechtigt"},
        )

        await einspielen(client, staffel_id, spiel(befunde=[befund()]))

        danach = await erster_befund(client, spiel_id)
        assert danach["entscheidung"] == "verworfen"
        assert danach["grund"] == "Spieler war spielberechtigt"

    async def test_ein_verschwundener_befund_bleibt_nicht_stehen(self, client: AsyncClient) -> None:
        """Ein Prueflauf ist die vollstaendige Aussage ueber einen Bericht.
        Was er nicht mehr meldet, ist keine offene Arbeit mehr."""
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund()]))

        await einspielen(client, staffel_id, spiel(befunde=[]))

        spiel_id = (await erste_zeile(client))["id"]
        assert (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"] == []


# ── Warteschlange ─────────────────────────────────────────────────────────


class TestWarteschlange:
    async def test_sie_zaehlt_offene_und_kritische(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        hinweis = befund(regel="foto", schwere="hinweis", titel="Spielerfoto fehlt")
        await einspielen(client, staffel_id, spiel(befunde=[befund(), hinweis]))

        zeile = await erste_zeile(client)

        assert zeile["offene_befunde"] == 2
        assert zeile["kritische_befunde"] == 1

    async def test_nach_staffel_gefiltert(self, client: AsyncClient) -> None:
        eine = await staffel_anlegen(client)
        andere = await staffel_anlegen(client, name="Ü35 1. Stadtklasse", altersklasse="ue35")
        await einspielen(client, eine, spiel("M-1"))
        await einspielen(client, andere, spiel("M-2"))

        zeilen = (await client.get(f"/staffelpilot/?staffel_id={andere}")).json()

        assert [z["dfbnet_id"] for z in zeilen] == ["M-2"]

    async def test_ein_unbekanntes_spiel(self, client: AsyncClient) -> None:
        assert (await client.get(f"/staffelpilot/spiele/{UNBEKANNT}")).status_code == 404

    async def test_die_befunde_kommen_sortiert(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(
            client,
            staffel_id,
            spiel(
                befunde=[
                    befund(regel="a", schwere="hinweis", titel="Hinweis"),
                    befund(regel="b", schwere="kritisch", titel="Kritisch"),
                    befund(regel="c", schwere="warnung", titel="Warnung"),
                ]
            ),
        )
        spiel_id = (await erste_zeile(client))["id"]

        befunde = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"]

        assert [b["titel"] for b in befunde] == ["Kritisch", "Warnung", "Hinweis"]


# ── Entscheiden ───────────────────────────────────────────────────────────


class TestEntscheiden:
    async def test_zur_kenntnis_nehmen(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund()]))
        spiel_id = (await erste_zeile(client))["id"]
        befund_id = (await erster_befund(client, spiel_id))["id"]

        antwort = await client.post(
            f"/staffelpilot/befunde/{befund_id}/entscheidung", json={"art": "kenntnis"}
        )

        assert antwort.status_code == 200
        assert antwort.json()["entscheidung"] == "kenntnis"

    async def test_verwerfen_ohne_grund_wird_abgelehnt(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund()]))
        spiel_id = (await erste_zeile(client))["id"]
        befund_id = (await erster_befund(client, spiel_id))["id"]

        antwort = await client.post(
            f"/staffelpilot/befunde/{befund_id}/entscheidung",
            json={"art": "verworfen", "grund": "   "},
        )

        assert antwort.status_code == 422
        assert "Begründung" in antwort.text

    async def test_eine_unbekannte_art_wird_abgelehnt(self, client: AsyncClient) -> None:
        antwort = await client.post(
            f"/staffelpilot/befunde/{UNBEKANNT}/entscheidung", json={"art": "vielleicht"}
        )
        assert antwort.status_code == 422

    async def test_ein_unbekannter_befund(self, client: AsyncClient) -> None:
        antwort = await client.post(
            f"/staffelpilot/befunde/{UNBEKANNT}/entscheidung", json={"art": "kenntnis"}
        )
        assert antwort.status_code == 404


# ── Abhaken ───────────────────────────────────────────────────────────────


class TestAbhaken:
    async def test_ein_sauberes_spiel_laesst_sich_abhaken(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel())
        spiel_id = (await erste_zeile(client))["id"]

        antwort = await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")

        assert antwort.status_code == 200
        assert antwort.json()["abgehakt"] is True
        assert antwort.json()["abgehakt_am"] is not None

    async def test_ein_offener_befund_blockiert(self, client: AsyncClient) -> None:
        """Die eine Zusage des Artefakts, hier ueber HTTP."""
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund()]))
        spiel_id = (await erste_zeile(client))["id"]

        antwort = await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")

        assert antwort.status_code == 409
        assert "problem+json" in antwort.headers["content-type"]
        assert "Entscheidung" in antwort.text

    async def test_nach_der_entscheidung_geht_es(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel(befunde=[befund()]))
        spiel_id = (await erste_zeile(client))["id"]
        befund_id = (await erster_befund(client, spiel_id))["id"]
        await client.post(
            f"/staffelpilot/befunde/{befund_id}/entscheidung", json={"art": "kenntnis"}
        )

        assert (await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")).status_code == 200

    async def test_der_haken_laesst_sich_wieder_loesen(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel())
        spiel_id = (await erste_zeile(client))["id"]
        await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")

        antwort = await client.delete(f"/staffelpilot/spiele/{spiel_id}/haken")

        assert antwort.json()["abgehakt"] is False
        assert antwort.json()["abgehakt_am"] is None

    async def test_abhaken_eines_unbekannten_spiels(self, client: AsyncClient) -> None:
        assert (await client.post(f"/staffelpilot/spiele/{UNBEKANNT}/haken")).status_code == 404

    async def test_haken_loesen_bei_unbekanntem_spiel(self, client: AsyncClient) -> None:
        assert (await client.delete(f"/staffelpilot/spiele/{UNBEKANNT}/haken")).status_code == 404


# ── Zusammenfassung ───────────────────────────────────────────────────────


class TestZusammenfassung:
    async def test_ohne_daten(self, client: AsyncClient) -> None:
        antwort = await client.get("/staffelpilot/zusammenfassung")
        assert antwort.status_code == 200
        assert antwort.json()["spiele"] == 0

    async def test_sie_steht_vor_der_spiel_route(self, client: AsyncClient) -> None:
        """Waere es umgekehrt, versuchte FastAPI 'zusammenfassung' als UUID zu
        lesen und antwortete mit 422."""
        assert (await client.get("/staffelpilot/zusammenfassung")).status_code == 200

    async def test_sie_zaehlt_mit(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel("M-1", befunde=[befund()]), spiel("M-2"))
        zeilen = (await client.get("/staffelpilot/")).json()
        sauber = next(z for z in zeilen if z["dfbnet_id"] == "M-2")
        await client.post(f"/staffelpilot/spiele/{sauber['id']}/haken")

        werte = (await client.get("/staffelpilot/zusammenfassung")).json()

        assert werte == {
            "spiele": 2,
            "offen": 1,
            "abgehakt": 1,
            "befunde_offen": 1,
            "vorgaenge_entwurf": 0,
            "befunde_kritisch": 1,
            "staffeln_aktiv": 1,
        }
