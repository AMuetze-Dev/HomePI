"""Der Regelsatz je Staffelleiter.

Jeder schaltet fuer sich, und sein Satz gilt fuer alle seine Staffeln.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

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


class TestAufgeloest:
    """Was der Prueflauf bekommt: alles, mit den Vorgaben aufgefuellt."""

    async def test_schalter_und_werte(self, client: AsyncClient, zweite: AsyncClient) -> None:
        await katalog(client, regel(), regel("red_card", parameter=[]))
        bestaetigung = await eine(client)
        karte = await eine(client, "red_card")
        await client.patch(f"/staffelpilot/regeln/{karte['id']}", json={"aktiv": False})
        await client.patch(
            f"/staffelpilot/regeln/{bestaetigung['id']}", json={"werte": {"kulanz": 6}}
        )
        # Was die andere schaltet, gilt hier nicht.
        await zweite.patch(f"/staffelpilot/regeln/{bestaetigung['id']}", json={"aktiv": False})

        satz = (await client.get("/staffelpilot/regelsatz")).json()

        assert satz["staffelleiter"] == "Staffelleiter"
        assert satz["aus"] == ["red_card"]
        assert satz["werte"] == {"confirmation_late": {"frist": "18:00", "kulanz": 6}}

    async def test_ohne_eigenes_gelten_die_vorgaben(self, client: AsyncClient) -> None:
        await katalog(client)

        satz = (await client.get("/staffelpilot/regelsatz")).json()

        assert satz["aus"] == []
        assert satz["werte"] == {"confirmation_late": {"frist": "18:00", "kulanz": 0}}
