"""Der Regelsatz je Staffelleiter -- und welcher davon im Prueflauf gilt.

Jeder schaltet fuer sich. Welcher Regelsatz an einem Spiel gilt, haengt an
der Staffel: an dem, der sie leitet. Eine Staffel ohne Staffelleiter prueft
mit den Vorgaben.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from .hilfen import UNBEKANNT, staffel_anlegen

pytestmark = pytest.mark.integration

FRISTEN = [
    {
        "schluessel": "frist",
        "name": "Frist am Spieltag",
        "art": "uhrzeit",
        "vorgabe": "18:00",
        "erklaerung": "Bis wann am Spieltag bestaetigt sein muss.",
    },
    {
        "schluessel": "kulanz",
        "name": "Kulanz",
        "art": "stunden",
        "vorgabe": 0,
        "kleinst": 0,
        "groesst": 24,
    },
]


def regel(schluessel: str = "confirmation_late", **abweichend: Any) -> dict[str, Any]:
    return {
        "schluessel": schluessel,
        "name": "Kenntnisnahme verspaetet",
        "schwere": "kritisch",
        "weg": "mahnung",
        "parameter": FRISTEN,
        **abweichend,
    }


async def katalog(client: AsyncClient, *regeln: dict[str, Any]) -> list[dict[str, Any]]:
    antwort = await client.put("/staffelpilot/regeln", json={"regeln": list(regeln) or [regel()]})
    assert antwort.status_code == 200, antwort.text
    return list(antwort.json())


async def eine(client: AsyncClient, schluessel: str = "confirmation_late") -> dict[str, Any]:
    alle = (await client.get("/staffelpilot/regeln")).json()
    return next(r for r in alle if r["schluessel"] == schluessel)


class TestParameter:
    async def test_der_katalog_bringt_seine_parameter_mit(self, client: AsyncClient) -> None:
        await katalog(client)
        r = await eine(client)

        assert [p["schluessel"] for p in r["parameter"]] == ["frist", "kulanz"]
        assert r["parameter"][0]["vorgabe"] == "18:00"
        assert r["parameter"][0]["wert"] is None
        assert r["parameter"][1]["groesst"] == 24
        assert r["angepasst"] is False

    async def test_ein_eigener_wert_bleibt_stehen(self, client: AsyncClient) -> None:
        await katalog(client)
        r = await eine(client)

        antwort = await client.patch(
            f"/staffelpilot/regeln/{r['id']}", json={"werte": {"kulanz": "6"}}
        )

        assert antwort.status_code == 200, antwort.text
        kulanz = antwort.json()["parameter"][1]
        assert kulanz["wert"] == 6
        assert antwort.json()["angepasst"] is True
        assert (await eine(client))["parameter"][1]["wert"] == 6

    async def test_ein_falscher_wert_sagt_was_geht(self, client: AsyncClient) -> None:
        await katalog(client)
        r = await eine(client)

        antwort = await client.patch(
            f"/staffelpilot/regeln/{r['id']}", json={"werte": {"kulanz": 30}}
        )

        assert antwort.status_code == 422
        assert antwort.json()["detail"] == "Kulanz: Bitte einen Wert zwischen 0 und 24 angeben."

    async def test_leere_werte_setzen_zurueck(self, client: AsyncClient) -> None:
        await katalog(client)
        r = await eine(client)
        await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"werte": {"kulanz": 6}})

        antwort = await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"werte": {}})

        assert antwort.json()["parameter"][1]["wert"] is None
        assert antwort.json()["angepasst"] is False

    async def test_umschalten_laesst_die_werte_stehen(self, client: AsyncClient) -> None:
        await katalog(client)
        r = await eine(client)
        await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"werte": {"kulanz": 6}})

        await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"aktiv": False})

        danach = await eine(client)
        assert danach["aktiv"] is False
        assert danach["parameter"][1]["wert"] == 6

    async def test_ein_neuer_katalog_laesst_die_werte_stehen(self, client: AsyncClient) -> None:
        await katalog(client)
        r = await eine(client)
        await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"werte": {"kulanz": 6}})

        await katalog(client)

        assert (await eine(client))["parameter"][1]["wert"] == 6

    async def test_auch_nicht_wenn_die_regel_einmal_fehlte(self, client: AsyncClient) -> None:
        """Eine Regeldatei mit Tippfehler genuegt, und ein Lauf meldet die halbe
        Liste. Die Einstellung soll das ueberleben."""
        await katalog(client)
        r = await eine(client)
        await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"werte": {"kulanz": 6}})

        await katalog(client, regel("andere", parameter=[]))
        await katalog(client)

        assert (await eine(client))["parameter"][1]["wert"] == 6

    async def test_ein_katalog_ohne_parameter_geht_weiter(self, client: AsyncClient) -> None:
        """Ein Pruefdienst von gestern kennt das Feld nicht."""
        antwort = await client.put(
            "/staffelpilot/regeln",
            json={"regeln": [{"schluessel": "red_card", "name": "Feldverweis"}]},
        )

        assert antwort.status_code == 200, antwort.text
        assert antwort.json()[0]["parameter"] == []

    async def test_eine_unbekannte_parameterart_wird_abgewiesen(self, client: AsyncClient) -> None:
        falsch = [{**FRISTEN[0], "art": "datum"}]
        antwort = await client.put(
            "/staffelpilot/regeln", json={"regeln": [regel(parameter=falsch)]}
        )

        assert antwort.status_code == 422


class TestJederFuerSich:
    async def test_abschalten_gilt_nur_fuer_den_der_schaltet(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        await katalog(client)
        r = await eine(client)

        await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"aktiv": False})

        assert (await eine(client))["aktiv"] is False
        assert (await eine(zweite))["aktiv"] is True

    async def test_werte_gelten_nur_fuer_den_der_sie_setzt(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        await katalog(client)
        r = await eine(zweite)

        await zweite.patch(f"/staffelpilot/regeln/{r['id']}", json={"werte": {"kulanz": 6}})

        assert (await eine(zweite))["parameter"][1]["wert"] == 6
        assert (await eine(client))["parameter"][1]["wert"] is None

    async def test_wer_wie_die_vorgabe_schaltet_ist_nicht_angepasst(
        self, client: AsyncClient
    ) -> None:
        await katalog(client)
        r = await eine(client)
        await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"aktiv": False})

        antwort = await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"aktiv": True})

        assert antwort.json()["angepasst"] is False

    async def test_ein_leser_schaltet_nichts(self, client: AsyncClient, leser: AsyncClient) -> None:
        await katalog(client)
        r = await eine(leser)

        antwort = await leser.patch(f"/staffelpilot/regeln/{r['id']}", json={"aktiv": False})

        assert antwort.status_code == 403


class TestStaffelleitung:
    async def test_wer_eine_staffel_anlegt_leitet_sie(self, client: AsyncClient) -> None:
        await staffel_anlegen(client)

        staffel = (await client.get("/staffelpilot/staffeln")).json()[0]

        assert staffel["staffelleiter"] == "Staffelleiter"
        assert staffel["leite_ich"] is True

    async def test_die_andere_sieht_wer_sie_leitet(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        await staffel_anlegen(client)

        staffel = (await zweite.get("/staffelpilot/staffeln")).json()[0]

        assert staffel["staffelleiter"] == "Staffelleiter"
        assert staffel["leite_ich"] is False

    async def test_eine_fremde_laesst_sich_nicht_uebernehmen(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)

        antwort = await zweite.post(f"/staffelpilot/staffeln/{staffel_id}/leitung")

        assert antwort.status_code == 409
        assert "Staffelleiter" in antwort.json()["detail"]

    async def test_abgegeben_laesst_sie_sich_uebernehmen(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)

        abgegeben = await client.delete(f"/staffelpilot/staffeln/{staffel_id}/leitung")
        assert abgegeben.status_code == 200, abgegeben.text
        assert abgegeben.json()["staffelleiter"] == ""

        antwort = await zweite.post(f"/staffelpilot/staffeln/{staffel_id}/leitung")
        assert antwort.status_code == 200, antwort.text
        assert antwort.json()["staffelleiter"] == "Erika Muster"
        assert antwort.json()["leite_ich"] is True

    async def test_eine_fremde_abgeben_darf_nur_der_verwalter(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)

        antwort = await zweite.delete(f"/staffelpilot/staffeln/{staffel_id}/leitung")

        assert antwort.status_code == 409
        assert antwort.json()["detail"] == "Abgeben kann eine Staffel nur, wer sie leitet."

    async def test_alle_freien_auf_einmal(self, client: AsyncClient, zweite: AsyncClient) -> None:
        """Was vor den Staffelleitern angelegt wurde, hat keinen -- das
        uebernimmt man mit einem Knopf und nicht Zeile fuer Zeile."""
        eigene = await staffel_anlegen(client, name="Eigene")
        frei = await staffel_anlegen(client, name="Frei")
        await client.delete(f"/staffelpilot/staffeln/{frei}/leitung")

        antwort = await zweite.post("/staffelpilot/staffeln/leitung")

        assert antwort.status_code == 200, antwort.text
        assert antwort.json() == {"uebernommen": 1}
        staffeln = {s["id"]: s for s in (await zweite.get("/staffelpilot/staffeln")).json()}
        assert staffeln[frei]["leite_ich"] is True
        assert staffeln[eigene]["leite_ich"] is False

    async def test_unbekannte_staffel(self, client: AsyncClient) -> None:
        antwort = await client.post(f"/staffelpilot/staffeln/{UNBEKANNT}/leitung")

        assert antwort.status_code == 404

    async def test_ein_leser_uebernimmt_nichts(
        self, client: AsyncClient, leser: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)
        await client.delete(f"/staffelpilot/staffeln/{staffel_id}/leitung")

        antwort = await leser.post(f"/staffelpilot/staffeln/{staffel_id}/leitung")

        assert antwort.status_code == 403


class TestRegelsatzFuerDenPrueflauf:
    async def test_es_gilt_der_satz_dessen_der_die_staffel_leitet(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        await katalog(client, regel(), regel("red_card", parameter=[]))
        staffel_id = await staffel_anlegen(client)
        bestaetigung = await eine(client)
        karte = await eine(client, "red_card")
        await client.patch(f"/staffelpilot/regeln/{karte['id']}", json={"aktiv": False})
        await client.patch(
            f"/staffelpilot/regeln/{bestaetigung['id']}", json={"werte": {"kulanz": 6}}
        )
        # Was die andere schaltet, gilt hier nicht.
        await zweite.patch(f"/staffelpilot/regeln/{bestaetigung['id']}", json={"aktiv": False})

        antwort = await client.get("/staffelpilot/regelsatz", params={"staffel_id": staffel_id})

        assert antwort.status_code == 200, antwort.text
        satz = antwort.json()
        assert satz["staffelleiter"] == "Staffelleiter"
        assert satz["aus"] == ["red_card"]
        assert satz["werte"] == {"confirmation_late": {"frist": "18:00", "kulanz": 6}}

    async def test_ohne_staffelleiter_gelten_die_vorgaben(self, client: AsyncClient) -> None:
        await katalog(client)
        staffel_id = await staffel_anlegen(client)
        r = await eine(client)
        await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"aktiv": False})
        await client.delete(f"/staffelpilot/staffeln/{staffel_id}/leitung")

        satz = (
            await client.get("/staffelpilot/regelsatz", params={"staffel_id": staffel_id})
        ).json()

        assert satz["staffelleiter"] == ""
        assert satz["aus"] == []
        assert satz["werte"] == {"confirmation_late": {"frist": "18:00", "kulanz": 0}}

    async def test_unbekannte_staffel(self, client: AsyncClient) -> None:
        antwort = await client.get("/staffelpilot/regelsatz", params={"staffel_id": UNBEKANNT})

        assert antwort.status_code == 404

    async def test_nur_der_verwalter_liest_einen_fremden_satz(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        """Der Pruefdienst meldet sich als Verwalter an. Was jemand fuer sich
        eingestellt hat, geht die anderen Staffelleiter nichts an."""
        staffel_id = await staffel_anlegen(client)

        antwort = await zweite.get("/staffelpilot/regelsatz", params={"staffel_id": staffel_id})

        assert antwort.status_code == 403
