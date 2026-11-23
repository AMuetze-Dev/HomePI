"""Was den naechsten Prueflauf uebersteht: Befunde und die Schreiben daran."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from .hilfen import befund, einspielen, spiel, staffel_anlegen

pytestmark = pytest.mark.integration


async def lauf(client: AsyncClient, staffel_id: str, *befunde: dict[str, Any]) -> None:
    antwort = await einspielen(client, staffel_id, spiel(befunde=list(befunde)))
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["befunde"] == len(befunde)


async def befunde_des_spiels(client: AsyncClient) -> list[dict[str, Any]]:
    spiel_id = (await client.get("/staffelpilot/")).json()[0]["id"]
    return list((await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"])


async def nach_text(client: AsyncClient) -> dict[str, dict[str, Any]]:
    return {b["text"]: b for b in await befunde_des_spiels(client)}


async def schreiben(
    client: AsyncClient, befund_id: str, zustaende: tuple[str, ...] = ()
) -> dict[str, Any]:
    antwort = await client.post(f"/staffelpilot/befunde/{befund_id}/vorgang", json={})
    assert antwort.status_code == 201, antwort.text
    vorgang_id = antwort.json()["id"]
    for zustand in zustaende:
        weiter = await client.post(
            f"/staffelpilot/vorgaenge/{vorgang_id}/zustand", json={"zustand": zustand}
        )
        assert weiter.status_code == 200, weiter.text
    return next(v for v in await vorgaenge(client) if v["id"] == vorgang_id)


async def innere_nummer(client: AsyncClient, vorgang: dict[str, Any]) -> str:
    """Die Liste zeigt sie nicht mehr, der einzelne Vorgang fuehrt sie noch."""
    return str(
        (await client.get(f"/staffelpilot/vorgaenge/{vorgang['id']}")).json()["aktenzeichen"]
    )


async def vorgaenge(client: AsyncClient) -> list[dict[str, Any]]:
    return list((await client.get("/staffelpilot/vorgaenge")).json())


MAHNUNG = befund(weg="mahnung")

ZUSTAENDE = [
    pytest.param((), id="entwurf"),
    pytest.param(("versandt",), id="versandt"),
    pytest.param(("versandt", "erledigt"), id="erledigt"),
]


class TestDerselbeBefund:
    @pytest.mark.parametrize("zustaende", ZUSTAENDE)
    async def test_sein_schreiben_bleibt_wie_es_war(
        self, client: AsyncClient, zustaende: tuple[str, ...]
    ) -> None:
        """Nachgestellt am 23.11.2026: nach jedem Prueflauf war die Liste leer."""
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, MAHNUNG)
        vorher = await schreiben(client, (await befunde_des_spiels(client))[0]["id"], zustaende)

        await lauf(client, staffel_id, MAHNUNG)

        assert await vorgaenge(client) == [vorher]
        gefunden = (await befunde_des_spiels(client))[0]
        assert gefunden["id"] == vorher["befund_id"]
        assert gefunden["vorgang_id"] == vorher["id"]

    async def test_die_nummer_wird_nicht_noch_einmal_vergeben(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        zweiter = befund(weg="mahnung", person="Jan Klein")
        await lauf(client, staffel_id, MAHNUNG, zweiter)
        nach_person = {b["person"]: b["id"] for b in await befunde_des_spiels(client)}
        erste = await schreiben(client, nach_person["Max Müller"], ("versandt",))

        await lauf(client, staffel_id, MAHNUNG, zweiter)
        nach_person = {b["person"]: b["id"] for b in await befunde_des_spiels(client)}
        andere = await schreiben(client, nach_person["Jan Klein"])

        assert await innere_nummer(client, erste) != await innere_nummer(client, andere)

    async def test_er_zeigt_was_der_letzte_lauf_gemeldet_hat(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, befund(text="in Minute 71", schwere="warnung"))
        vorher = (await befunde_des_spiels(client))[0]["id"]

        await lauf(
            client,
            staffel_id,
            befund(text="in Minute 72", schwere="kritisch", titel="Feldverweis", weg="mahnung"),
        )

        gefunden = (await befunde_des_spiels(client))[0]
        assert gefunden["id"] == vorher
        assert gefunden["text"] == "in Minute 72"
        assert gefunden["schwere"] == "kritisch"
        assert gefunden["titel"] == "Feldverweis"
        assert gefunden["weg"] == "mahnung"

    async def test_die_reihenfolge_ist_die_des_letzten_laufs(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        a, b = befund(regel="a", titel="A"), befund(regel="b", titel="B")
        await lauf(client, staffel_id, a, b)

        await lauf(client, staffel_id, b, a)

        flach = (await client.get("/staffelpilot/befunde")).json()
        assert [z["titel"] for z in flach] == ["B", "A"]


class TestZweiMitGleicherRegelUndPerson:
    async def test_jeder_behaelt_seine_entscheidung(self, client: AsyncClient) -> None:
        """Bis zum 23.11.2026 bekamen beide die des zweiten."""
        staffel_id = await staffel_anlegen(client)
        eins, zwei = befund(text="Minute 12"), befund(text="Minute 80")
        await lauf(client, staffel_id, eins, zwei)
        zweiter = (await nach_text(client))["Minute 80"]["id"]
        await client.post(
            f"/staffelpilot/befunde/{zweiter}/entscheidung",
            json={"art": "verworfen", "grund": "Verwechslung"},
        )

        await lauf(client, staffel_id, zwei, eins)

        danach = await nach_text(client)
        assert danach["Minute 12"]["entscheidung"] == "offen"
        assert danach["Minute 80"]["entscheidung"] == "verworfen"

    async def test_jeder_behaelt_sein_schreiben(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        eins = befund(text="Minute 12", weg="mahnung")
        zwei = befund(text="Minute 80", weg="mahnung")
        await lauf(client, staffel_id, eins, zwei)
        erster = (await nach_text(client))["Minute 12"]["id"]
        vorher = await schreiben(client, erster, ("versandt",))

        await lauf(client, staffel_id, zwei, eins)

        danach = await nach_text(client)
        assert danach["Minute 12"]["vorgang_id"] == vorher["id"]
        assert danach["Minute 80"]["vorgang_id"] is None

    async def test_heim_und_gast_werden_nicht_verwechselt(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        heim = befund(person="", mannschaft="SG Gittersee", text="zu spät", weg="mahnung")
        gast = befund(person="", mannschaft="SV Fortschritt", text="zu spät", weg="mahnung")
        await lauf(client, staffel_id, heim)
        heim_id = (await befunde_des_spiels(client))[0]["id"]
        vorher = await schreiben(client, heim_id, ("versandt",))

        await lauf(client, staffel_id, gast)

        danach = {b["mannschaft"]: b for b in await befunde_des_spiels(client)}
        assert danach["SG Gittersee"]["vorgang_id"] == vorher["id"]
        assert danach["SV Fortschritt"]["vorgang_id"] is None
        assert danach["SV Fortschritt"]["entscheidung"] == "offen"


class TestNichtMehrGemeldet:
    @pytest.mark.parametrize("zustaende", ZUSTAENDE)
    async def test_mit_schreiben_bleibt_er_stehen(
        self, client: AsyncClient, zustaende: tuple[str, ...]
    ) -> None:
        """Auch ein Entwurf: ein Lauf, der die Aufstellung nicht holen konnte,
        meldet weniger, und der Text darin kann von Hand geschrieben sein."""
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, MAHNUNG)
        vorher = await schreiben(client, (await befunde_des_spiels(client))[0]["id"], zustaende)

        await lauf(client, staffel_id)

        assert await vorgaenge(client) == [vorher]
        assert [b["id"] for b in await befunde_des_spiels(client)] == [vorher["befund_id"]]

    async def test_er_steht_hinter_dem_was_gemeldet_ist(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, MAHNUNG)
        await schreiben(client, (await befunde_des_spiels(client))[0]["id"])

        await lauf(client, staffel_id, befund(regel="neu", titel="Neu"))

        flach = (await client.get("/staffelpilot/befunde")).json()
        assert [z["titel"] for z in flach] == ["Neu", MAHNUNG["titel"]]

    async def test_meldet_ihn_ein_spaeterer_lauf_wieder_ist_es_derselbe(
        self, client: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, MAHNUNG)
        befund_id = (await befunde_des_spiels(client))[0]["id"]
        vorher = await schreiben(client, befund_id, ("versandt",))
        await lauf(client, staffel_id)

        await lauf(client, staffel_id, MAHNUNG)

        assert [b["vorgang_id"] for b in await befunde_des_spiels(client)] == [vorher["id"]]

    async def test_ist_der_entwurf_verworfen_geht_er_mit_dem_naechsten_lauf(
        self, client: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)
        await lauf(client, staffel_id, MAHNUNG)
        entwurf = await schreiben(client, (await befunde_des_spiels(client))[0]["id"])
        await lauf(client, staffel_id)
        geloescht = await client.delete(f"/staffelpilot/vorgaenge/{entwurf['id']}")
        assert geloescht.status_code == 204

        await lauf(client, staffel_id)

        assert await befunde_des_spiels(client) == []
