"""Fälligkeit in der Warteschlange und der Regelkatalog."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from httpx import AsyncClient

from .hilfen import UNBEKANNT, einspielen, spiel, staffel_anlegen

pytestmark = pytest.mark.integration


def regel(schluessel: str = "rote_karte", **abweichend: Any) -> dict[str, Any]:
    return {
        "schluessel": schluessel,
        "name": "Feldverweis auf Dauer",
        "beschreibung": "Meldet jeden Feldverweis auf Dauer.",
        "schwere": "kritisch",
        "weg": "sportgericht",
        **abweichend,
    }


def vor(tagen: int) -> str:
    return (dt.date.today() - dt.timedelta(days=tagen)).isoformat()


# ── Fälligkeit ────────────────────────────────────────────────────────────


class TestFaelligkeit:
    async def test_ein_spiel_von_gestern_ist_faellig(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel("M-1", datum=vor(1)))

        assert (await client.get("/staffelpilot/")).json()[0]["faellig"] is True

    async def test_ein_altes_spiel_faellt_aus_dem_zeitraum(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel("M-1", datum=vor(40)))

        assert (await client.get("/staffelpilot/")).json()[0]["faellig"] is False

    async def test_der_zeitraum_folgt_den_einstellungen(self, client: AsyncClient) -> None:
        """Berechnet und nicht gespeichert: sonst waere der Wert am Morgen nach
        dem Schreiben falsch - und nach einer Aenderung der Einstellung auch."""
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel("M-1", datum=vor(40)))
        await client.put("/staffelpilot/einstellungen", json={"pruefzeitraum_tage": 60})

        assert (await client.get("/staffelpilot/")).json()[0]["faellig"] is True

    async def test_ein_spiel_in_der_zukunft_ist_nicht_faellig(self, client: AsyncClient) -> None:
        """Es ist noch nicht gespielt, und ein Befund darauf waere eine
        Erfindung."""
        staffel_id = await staffel_anlegen(client)
        morgen = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        await einspielen(client, staffel_id, spiel("M-1", datum=morgen))

        assert (await client.get("/staffelpilot/")).json()[0]["faellig"] is False

    async def test_der_filter_laesst_nur_faellige_durch(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(
            client,
            staffel_id,
            spiel("M-1", datum=vor(1)),
            spiel("M-2", datum=vor(40)),
        )

        zeilen = (await client.get("/staffelpilot/?nur_faellig=true")).json()

        assert [z["dfbnet_id"] for z in zeilen] == ["M-1"]

    async def test_ohne_filter_kommt_alles(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(
            client, staffel_id, spiel("M-1", datum=vor(1)), spiel("M-2", datum=vor(40))
        )

        assert len((await client.get("/staffelpilot/")).json()) == 2


# ── Regelkatalog ──────────────────────────────────────────────────────────


class TestRegelkatalog:
    async def test_am_anfang_ist_er_leer(self, client: AsyncClient) -> None:
        assert (await client.get("/staffelpilot/regeln")).json() == []

    async def test_einspielen_und_lesen(self, client: AsyncClient) -> None:
        antwort = await client.put("/staffelpilot/regeln", json={"regeln": [regel()]})

        assert antwort.status_code == 200, antwort.text
        katalog = antwort.json()
        assert katalog[0]["schluessel"] == "rote_karte"
        assert katalog[0]["weg"] == "sportgericht"

    async def test_eine_neue_regel_ist_zunaechst_an(self, client: AsyncClient) -> None:
        """Wer nichts sagt, bekommt die Pruefung - eine Regel, die still aus
        waere, ist eine Pruefung, die niemand vermisst und die fehlt."""
        antwort = await client.put("/staffelpilot/regeln", json={"regeln": [regel()]})

        assert antwort.json()[0]["aktiv"] is True

    async def test_umschalten(self, client: AsyncClient) -> None:
        katalog = (await client.put("/staffelpilot/regeln", json={"regeln": [regel()]})).json()
        antwort = await client.patch(
            f"/staffelpilot/regeln/{katalog[0]['id']}", json={"aktiv": False}
        )

        assert antwort.json()["aktiv"] is False

    async def test_der_schalter_ueberlebt_das_naechste_einspielen(
        self, client: AsyncClient
    ) -> None:
        """`aktiv` gehoert dem Staffelleiter. Der Katalog meldet, was es gibt -
        nicht, was jemand davon sehen will."""
        katalog = (await client.put("/staffelpilot/regeln", json={"regeln": [regel()]})).json()
        await client.patch(f"/staffelpilot/regeln/{katalog[0]['id']}", json={"aktiv": False})

        wieder = (
            await client.put("/staffelpilot/regeln", json={"regeln": [regel(name="Neuer Name")]})
        ).json()

        assert wieder[0]["aktiv"] is False
        assert wieder[0]["name"] == "Neuer Name"

    async def test_was_nicht_mehr_gemeldet_wird_verschwindet(self, client: AsyncClient) -> None:
        """Ein Schalter fuer eine Regel, die niemand mehr prueft, verspricht
        etwas, das nicht passiert."""
        await client.put(
            "/staffelpilot/regeln",
            json={"regeln": [regel(), regel("ordnungsdienst", name="Ordnungsdienst")]},
        )

        wieder = (await client.put("/staffelpilot/regeln", json={"regeln": [regel()]})).json()

        assert [r["schluessel"] for r in wieder] == ["rote_karte"]

    async def test_ein_leerer_katalog_raeumt_auf(self, client: AsyncClient) -> None:
        await client.put("/staffelpilot/regeln", json={"regeln": [regel()]})

        assert (await client.put("/staffelpilot/regeln", json={"regeln": []})).json() == []

    async def test_unbekannte_regel_gibt_404(self, client: AsyncClient) -> None:
        antwort = await client.patch(f"/staffelpilot/regeln/{UNBEKANNT}", json={"aktiv": False})

        assert antwort.status_code == 404

    async def test_die_regeln_stehen_vor_der_spiel_route(self, client: AsyncClient) -> None:
        """Waere es umgekehrt, versuchte FastAPI 'regeln' als UUID zu lesen."""
        assert (await client.get("/staffelpilot/regeln")).status_code == 200


class TestDieSaetze:
    """Die Saetze fuer das Schreiben gehoeren dem Staffelleiter.

    Sie stehen spaeter in einem Brief an einen Verein. Was hier schiefgeht,
    faellt deshalb nicht in einem Log auf, sondern im Briefkasten.
    """

    async def _angelegt(self, client: AsyncClient, schluessel: str = "confirmation_late") -> str:
        katalog = (
            await client.put("/staffelpilot/regeln", json={"regeln": [regel(schluessel)]})
        ).json()
        return str(katalog[0]["id"])

    async def test_am_anfang_stehen_sie_leer_und_die_vorgabe_daneben(
        self, client: AsyncClient
    ) -> None:
        """Leer und nicht vorgefuellt: sonst friert der erste Blick auf die
        Liste den heutigen Wortlaut ein, samt Paragraf."""
        katalog = (
            await client.put(
                "/staffelpilot/regeln", json={"regeln": [regel("order_manager_missing")]}
            )
        ).json()

        assert katalog[0]["sachverhalt"] == ""
        assert "kein Leiter Ordnungsdienst" in katalog[0]["vorgabe_sachverhalt"]
        assert "\u00a7 53" in katalog[0]["vorgabe_hinweis"]

    async def test_eine_unbekannte_regel_hat_keine_vorgabe(self, client: AsyncClient) -> None:
        katalog = (
            await client.put("/staffelpilot/regeln", json={"regeln": [regel("ganz_eigene")]})
        ).json()

        assert katalog[0]["vorgabe_sachverhalt"] == ""

    async def test_ein_eigener_satz_bleibt_stehen(self, client: AsyncClient) -> None:
        regel_id = await self._angelegt(client)

        antwort = await client.patch(
            f"/staffelpilot/regeln/{regel_id}", json={"sachverhalt": "war etwas anderes."}
        )

        assert antwort.json()["sachverhalt"] == "war etwas anderes."
        assert (await client.get("/staffelpilot/regeln")).json()[0]["sachverhalt"] == (
            "war etwas anderes."
        )

    async def test_umschalten_loescht_die_saetze_nicht(self, client: AsyncClient) -> None:
        """Zwei Knoepfe, eine Zeile -- und der eine darf den anderen nicht
        ueberschreiben."""
        regel_id = await self._angelegt(client)
        await client.patch(f"/staffelpilot/regeln/{regel_id}", json={"sachverhalt": "eigener Satz"})

        antwort = await client.patch(f"/staffelpilot/regeln/{regel_id}", json={"aktiv": False})

        assert antwort.json()["sachverhalt"] == "eigener Satz"
        assert antwort.json()["aktiv"] is False

    async def test_die_saetze_loeschen_den_schalter_nicht(self, client: AsyncClient) -> None:
        regel_id = await self._angelegt(client)
        await client.patch(f"/staffelpilot/regeln/{regel_id}", json={"aktiv": False})

        antwort = await client.patch(f"/staffelpilot/regeln/{regel_id}", json={"hinweis": "x"})

        assert antwort.json()["aktiv"] is False

    async def test_ein_neuer_katalog_laesst_sie_stehen(self, client: AsyncClient) -> None:
        """Ein Update spielt den Katalog neu ein. Was jemand formuliert hat,
        ist damit nicht gemeint."""
        regel_id = await self._angelegt(client)
        await client.patch(f"/staffelpilot/regeln/{regel_id}", json={"sachverhalt": "meiner"})

        wieder = (
            await client.put(
                "/staffelpilot/regeln", json={"regeln": [regel("confirmation_late", name="Neu")]}
            )
        ).json()

        assert wieder[0]["sachverhalt"] == "meiner"
        assert wieder[0]["name"] == "Neu"

    async def test_sie_ueberleben_auch_ein_verschwinden_und_wiederkommen(
        self, client: AsyncClient
    ) -> None:
        """Ein Prueflauf mit einer halben Regelliste soll keine Arbeit
        loeschen."""
        regel_id = await self._angelegt(client)
        await client.patch(f"/staffelpilot/regeln/{regel_id}", json={"sachverhalt": "meiner"})
        await client.put("/staffelpilot/regeln", json={"regeln": []})

        wieder = (
            await client.put("/staffelpilot/regeln", json={"regeln": [regel("confirmation_late")]})
        ).json()

        assert wieder[0]["sachverhalt"] == "meiner"
