"""Die eigenen Staffeln aus DFBnet übernehmen.

Der Anlass ist echt und peinlich: die Staffeln von Hand einzutippen hat genau
die Tippfehler erzeugt, an denen die Prüfung dann scheiterte — eine
Spielklasse „Stadtliga C", die DFBnet nicht kennt, und ein Name, der nicht in
der Meisterschaftsliste steht.

Und der erste Versuch dieses Abgleichs war selbst der Fehler: er verglich
ohne Normalisierung, traf `1. Kreisklasse` nicht auf `1.Kreisklasse` und legte
drei Staffeln neben die drei vorhandenen. Die alten behielten die
Spielberichte, die neuen waren leer. **Deshalb steht hier mehr über das
Wiedererkennen als über das Anlegen.**
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import einspielen, spiel, staffel_anlegen

pytestmark = pytest.mark.integration

#: Wie DFBnet sie am 21.10.2026 lieferte.
AUS_DFBNET = {
    "staffeln": [
        {
            "kennung": "633203",
            "name": "Brandible Stadtliga C",
            "spielklasse": "Kreisliga C",
            "altersklasse": "maenner",
            "saison": "26/27",
            "spieltage": 26,
        },
        {
            "kennung": "633222",
            "name": "1. Stadtklasse Ü35",
            "spielklasse": "1.Kreisklasse",
            "altersklasse": "ue35",
            "saison": "26/27",
            "spieltage": 18,
        },
    ]
}


async def uebernehmen(client: AsyncClient, daten: dict | None = None) -> dict:
    antwort = await client.put("/staffelpilot/staffeln/aus-dfbnet", json=daten or AUS_DFBNET)
    assert antwort.status_code == 200, antwort.text
    return dict(antwort.json())


class TestZumErstenMal:
    async def test_sie_werden_angelegt(self, client: AsyncClient) -> None:
        ergebnis = await uebernehmen(client)

        assert ergebnis["angelegt"] == 2
        assert ergebnis["aktualisiert"] == 0

    async def test_die_kennung_bleibt_haengen(self, client: AsyncClient) -> None:
        """Sie ist das einzig Stabile: Bezeichnungen tragen Sponsornamen."""
        await uebernehmen(client)

        liste = (await client.get("/staffelpilot/staffeln")).json()

        assert sorted(s["dfbnet_kennung"] for s in liste) == ["633203", "633222"]

    async def test_spielklasse_und_altersklasse_kommen_mit(self, client: AsyncClient) -> None:
        await uebernehmen(client)

        liste = {
            s["dfbnet_kennung"]: s for s in (await client.get("/staffelpilot/staffeln")).json()
        }

        assert liste["633222"]["spielklasse"] == "1.Kreisklasse"
        assert liste["633222"]["altersklasse"] == "ue35"


class TestZumZweitenMal:
    """Der Teil, der beim ersten Anlauf kaputt war."""

    async def test_dieselbe_liste_legt_nichts_neu_an(self, client: AsyncClient) -> None:
        await uebernehmen(client)

        ergebnis = await uebernehmen(client)

        assert ergebnis["angelegt"] == 0
        assert ergebnis["aktualisiert"] == 2
        assert len((await client.get("/staffelpilot/staffeln")).json()) == 2

    async def test_eine_von_hand_getippte_wird_wiedererkannt(self, client: AsyncClient) -> None:
        """`1. Kreisklasse` von Hand, `1.Kreisklasse` aus DFBnet.

        Das Leerzeichen nach dem Punkt war der ganze Unterschied — und es hat
        eine zweite Staffel erzeugt, während die erste die Spielberichte
        behielt.
        """
        await staffel_anlegen(
            client,
            name="1. Kreisklasse",
            spielklasse="1. Kreisklasse",
            altersklasse="ue35",
        )

        ergebnis = await uebernehmen(client, {"staffeln": [AUS_DFBNET["staffeln"][1]]})

        assert ergebnis["angelegt"] == 0
        assert ergebnis["aktualisiert"] == 1

    async def test_die_spielberichte_bleiben_an_ihrer_staffel(self, client: AsyncClient) -> None:
        """Die eigentliche Zusicherung. Ein Doppelgänger nähme sie nicht mit —
        er ließe sie an der alten Staffel zurück, und die Warteschlange zeigte
        sie unter einem Namen, den DFBnet nicht kennt."""
        staffel_id = await staffel_anlegen(
            client, name="1. Kreisklasse", spielklasse="1. Kreisklasse", altersklasse="ue35"
        )
        await einspielen(client, staffel_id, spiel("031DHM03"))

        await uebernehmen(client, {"staffeln": [AUS_DFBNET["staffeln"][1]]})

        liste = (await client.get("/staffelpilot/staffeln")).json()
        assert len(liste) == 1
        assert liste[0]["id"] == staffel_id
        assert liste[0]["name"] == "1. Stadtklasse Ü35"
        assert len((await client.get("/staffelpilot/?nur_faellig=false")).json()) == 1

    async def test_zwei_kandidaten_werden_nicht_geraten(self, client: AsyncClient) -> None:
        """Dann legt es lieber eine neue an.

        Eine zusammengelegte Staffel, die es nicht war, nimmt die
        Spielberichte der falschen mit — und das merkt niemand.
        """
        await staffel_anlegen(
            client, name="1. Kreisklasse", spielklasse="egal", altersklasse="ue35"
        )
        await staffel_anlegen(
            client, name="anders", spielklasse="1.Kreisklasse", altersklasse="ue35"
        )

        ergebnis = await uebernehmen(client, {"staffeln": [AUS_DFBNET["staffeln"][1]]})

        assert ergebnis["angelegt"] == 1


class TestWasUnberuehrtBleibt:
    async def test_eine_fremde_staffel_wird_nicht_geloescht(self, client: AsyncClient) -> None:
        """Sie kann aus einer früheren Saison stammen — und sie zu entfernen
        nähme ihre Spielberichte mit."""
        await staffel_anlegen(client, name="Aus 25/26", spielklasse="Kreisoberliga")

        await uebernehmen(client)

        namen = [s["name"] for s in (await client.get("/staffelpilot/staffeln")).json()]
        assert "Aus 25/26" in namen

    async def test_stillgelegt_bleibt_stillgelegt(self, client: AsyncClient) -> None:
        """Ob eine Staffel mitläuft, entscheidet der Staffelleiter, nicht
        DFBnet."""
        staffel_id = await staffel_anlegen(
            client, name="1. Stadtklasse Ü35", spielklasse="1.Kreisklasse", altersklasse="ue35"
        )
        await client.patch(f"/staffelpilot/staffeln/{staffel_id}", json={"aktiv": False})

        await uebernehmen(client, {"staffeln": [AUS_DFBNET["staffeln"][1]]})

        liste = (await client.get("/staffelpilot/staffeln")).json()
        assert liste[0]["aktiv"] is False

    async def test_eine_null_bei_spieltagen_ueberschreibt_keine_zahl(
        self, client: AsyncClient
    ) -> None:
        """0 heißt *nicht bekannt*. Siehe `modelle.Staffel.spieltage`."""
        await staffel_anlegen(
            client,
            name="1. Stadtklasse Ü35",
            spielklasse="1.Kreisklasse",
            altersklasse="ue35",
            spieltage=18,
        )

        ohne = {**AUS_DFBNET["staffeln"][1], "spieltage": 0}
        await uebernehmen(client, {"staffeln": [ohne]})

        assert (await client.get("/staffelpilot/staffeln")).json()[0]["spieltage"] == 18


class TestAbgewiesen:
    async def test_ohne_kennung_geht_es_nicht(self, client: AsyncClient) -> None:
        """Ohne sie waere der naechste Abgleich wieder auf Namen angewiesen."""
        ohne = {**AUS_DFBNET["staffeln"][0], "kennung": ""}

        antwort = await client.put("/staffelpilot/staffeln/aus-dfbnet", json={"staffeln": [ohne]})

        assert antwort.status_code == 422

    async def test_eine_unbekannte_altersklasse_wird_abgewiesen(self, client: AsyncClient) -> None:
        """Eine geratene liest beim naechsten Lauf die Spiele einer anderen
        Mannschaft."""
        falsch = {**AUS_DFBNET["staffeln"][0], "altersklasse": "senioren"}

        antwort = await client.put("/staffelpilot/staffeln/aus-dfbnet", json={"staffeln": [falsch]})

        assert antwort.status_code == 422
