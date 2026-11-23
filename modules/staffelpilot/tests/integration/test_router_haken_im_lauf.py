"""Was ein weiterer Prueflauf mit einem abgehakten Spiel macht.

Abgehakt heisst: zu jedem Befund liegt eine Entscheidung vor. Das muss auch
nach einem Lauf noch stimmen, den niemand angesehen hat.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from .hilfen import befund, einspielen, spiel, staffel_anlegen

pytestmark = pytest.mark.integration

BEKANNT = befund()
NEU = befund(regel="foto_fehlt", titel="Kein Foto", person="Jan Klein")


async def lauf(client: AsyncClient, staffel_id: str, *spiele: dict[str, Any]) -> None:
    antwort = await einspielen(client, staffel_id, *spiele)
    assert antwort.status_code == 200, antwort.text


async def stand(client: AsyncClient, dfbnet_id: str = "M-1") -> dict[str, Any]:
    """Das Spiel, wie es nach dem letzten Lauf dasteht."""
    zeilen = {z["dfbnet_id"]: z["id"] for z in (await client.get("/staffelpilot/")).json()}
    return dict((await client.get(f"/staffelpilot/spiele/{zeilen[dfbnet_id]}")).json())


async def entscheiden(client: AsyncClient, dfbnet_id: str = "M-1") -> None:
    for b in (await stand(client, dfbnet_id))["befunde"]:
        antwort = await client.post(
            f"/staffelpilot/befunde/{b['id']}/entscheidung", json={"art": "kenntnis"}
        )
        assert antwort.status_code == 200, antwort.text


async def abhaken(client: AsyncClient, dfbnet_id: str = "M-1") -> dict[str, Any]:
    """Alles entscheiden und abhaken -- und damit die Freigabe vormerken."""
    await entscheiden(client, dfbnet_id)
    spiel_id = (await stand(client, dfbnet_id))["id"]
    antwort = await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")
    assert antwort.status_code == 200, antwort.text
    return dict(antwort.json())


async def freigaben(client: AsyncClient) -> dict[str, int]:
    """Wie viele Uebertragungen in welchem Zustand stehen, ohne die leeren."""
    zahlen = (await client.get("/staffelpilot/uebertragungen")).json()
    return {z: zahlen[z] for z in ("offen", "laeuft", "fertig", "fehler") if zahlen[z]}


async def uebernehmen(client: AsyncClient) -> str:
    await client.post("/staffelpilot/uebertragungen/pause", json={"pausiert": False})
    return str((await client.post("/staffelpilot/uebertragungen/naechste")).json()["id"])


async def melden(client: AsyncClient, uebertragung_id: str, zustand: str) -> None:
    antwort = await client.post(
        f"/staffelpilot/uebertragungen/{uebertragung_id}/abschluss", json={"zustand": zustand}
    )
    assert antwort.status_code == 200, antwort.text


class TestHaken:
    async def test_ein_neuer_offener_befund_nimmt_ihn(self, client: AsyncClient) -> None:
        """Nachgestellt am 23.11.2026: der Haken blieb, der Befund war offen."""
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel(befunde=[BEKANNT]))
        assert (await abhaken(client))["abgehakt"] is True

        await lauf(client, staffel_id, spiel(befunde=[BEKANNT, NEU]))

        danach = await stand(client)
        assert danach["abgehakt"] is False
        assert danach["abgehakt_am"] is None
        assert {b["person"]: b["entscheidung"] for b in danach["befunde"]} == {
            "Max Müller": "kenntnis",
            "Jan Klein": "offen",
        }

    async def test_auch_ein_spiel_das_ohne_befund_abgehakt_war(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel())
        await abhaken(client)

        await lauf(client, staffel_id, spiel(befunde=[NEU]))

        assert (await stand(client))["abgehakt"] is False

    @pytest.mark.parametrize(
        "gemeldet",
        [
            pytest.param([BEKANNT], id="derselbe befund"),
            pytest.param([befund(text="Feldverweis in Minute 72.")], id="neu formuliert"),
            pytest.param([], id="nichts mehr gemeldet"),
        ],
    )
    async def test_ohne_offenen_befund_bleibt_er_mit_seinem_zeitpunkt(
        self, client: AsyncClient, gemeldet: list[dict[str, Any]]
    ) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel(befunde=[BEKANNT]))
        vorher = await abhaken(client)

        await lauf(client, staffel_id, spiel(befunde=gemeldet))

        danach = await stand(client)
        assert danach["abgehakt"] is True
        assert danach["abgehakt_am"] == vorher["abgehakt_am"]

    async def test_er_faellt_nur_an_dem_spiel_mit_dem_befund(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel("M-1"), spiel("M-2"))
        await abhaken(client, "M-1")
        await abhaken(client, "M-2")

        await lauf(client, staffel_id, spiel("M-1", befunde=[NEU]), spiel("M-2"))

        assert (await stand(client, "M-1"))["abgehakt"] is False
        assert (await stand(client, "M-2"))["abgehakt"] is True
        assert await freigaben(client) == {"offen": 1}

    async def test_ist_er_entschieden_laesst_sich_das_spiel_wieder_abhaken(
        self, client: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel())
        await abhaken(client)
        await lauf(client, staffel_id, spiel(befunde=[NEU]))

        assert (await abhaken(client))["abgehakt"] is True
        assert await freigaben(client) == {"offen": 1}


class TestVorgemerkteFreigabe:
    """Sie sagt dem Verein, der Bericht sei geprueft."""

    async def test_eine_wartende_wird_zurueckgezogen(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel())
        await abhaken(client)
        assert await freigaben(client) == {"offen": 1}

        await lauf(client, staffel_id, spiel(befunde=[NEU]))

        assert await freigaben(client) == {}

    async def test_eine_gescheiterte_auch(self, client: AsyncClient) -> None:
        """Sonst ginge sie mit "alle wiederholen" doch noch hinaus."""
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel())
        await abhaken(client)
        await melden(client, await uebernehmen(client), "fehler")

        await lauf(client, staffel_id, spiel(befunde=[NEU]))

        assert await freigaben(client) == {}

    async def test_auch_wenn_der_haken_schon_von_hand_entfernt_war(
        self, client: AsyncClient
    ) -> None:
        """Vorgemerkt bleibt sie dabei -- und ginge mit offenem Befund hinaus."""
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel())
        spiel_id = (await abhaken(client))["id"]
        await client.delete(f"/staffelpilot/spiele/{spiel_id}/haken")

        await lauf(client, staffel_id, spiel(befunde=[NEU]))

        assert await freigaben(client) == {}

    async def test_eine_laufende_bleibt(self, client: AsyncClient) -> None:
        """Der Pruefdienst ist schon dabei. Ohne Zeile koennte er nicht mehr
        melden, was in DFBnet herauskam."""
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel())
        await abhaken(client)
        uebernommen = await uebernehmen(client)

        await lauf(client, staffel_id, spiel(befunde=[NEU]))

        assert (await stand(client))["abgehakt"] is False
        assert await freigaben(client) == {"laeuft": 1}
        await melden(client, uebernommen, "fertig")

    async def test_eine_erledigte_bleibt_und_geht_kein_zweites_mal_hinaus(
        self, client: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel())
        await abhaken(client)
        await melden(client, await uebernehmen(client), "fertig")

        await lauf(client, staffel_id, spiel(befunde=[NEU]))
        await abhaken(client)

        assert await freigaben(client) == {"fertig": 1}

    async def test_ohne_offenen_befund_bleibt_sie_vorgemerkt(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel(befunde=[BEKANNT]))
        await abhaken(client)

        await lauf(client, staffel_id, spiel(befunde=[BEKANNT]))

        assert await freigaben(client) == {"offen": 1}

    async def test_eine_fallanlage_bleibt(self, client: AsyncClient) -> None:
        """Sie gehoert zu ihrem Vorgang und nicht zum Haken."""
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, spiel(befunde=[befund(weg="sportgericht")]))
        befund_id = (await stand(client))["befunde"][0]["id"]
        vorgang = await client.post(f"/staffelpilot/befunde/{befund_id}/vorgang", json={})
        fall = await client.post(
            "/staffelpilot/uebertragungen",
            json={"aktion": "fallanlage", "referenz": vorgang.json()["id"]},
        )
        assert fall.status_code == 201, fall.text
        await abhaken(client)
        assert await freigaben(client) == {"offen": 2}

        await lauf(client, staffel_id, spiel(befunde=[befund(weg="sportgericht"), NEU]))

        assert await freigaben(client) == {"offen": 1}
        uebrig = await client.post("/staffelpilot/uebertragungen/pause", json={"pausiert": False})
        assert uebrig.status_code == 200
        naechste = (await client.post("/staffelpilot/uebertragungen/naechste")).json()
        assert naechste["id"] == fall.json()["id"]
