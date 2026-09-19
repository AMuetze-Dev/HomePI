"""Prüfläufe und Initialisierungen als Auftrag.

Hier laufen keine Browser. Geprüft wird der Datensatz: wer ihn anfordert, wie
er fortschreibt, wie er endet — und dass er die eine DFBnet-Sitzung schützt.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import UNBEKANNT, staffel_anlegen

pytestmark = pytest.mark.integration


async def anfordern(client: AsyncClient, **daten: object) -> dict[str, object]:
    antwort = await client.post("/staffelpilot/auftraege", json=daten)
    assert antwort.status_code == 201, antwort.text
    return dict(antwort.json())


class TestAnfordern:
    async def test_ein_frisch_angeforderter_wartet(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)

        assert auftrag["art"] == "pruflauf"
        assert auftrag["zustand"] == "angefordert"
        assert auftrag["fortschritt"] == 0
        assert auftrag["gestartet_am"] is None

    async def test_ohne_staffel_gilt_er_fuer_alle(self, client: AsyncClient) -> None:
        assert (await anfordern(client))["staffel_id"] is None

    async def test_fuer_eine_staffel(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)

        assert (await anfordern(client, staffel_id=staffel_id))["staffel_id"] == staffel_id

    async def test_eine_initialisierung_ist_auch_ein_auftrag(self, client: AsyncClient) -> None:
        assert (await anfordern(client, art="initialisierung"))["art"] == "initialisierung"

    async def test_eine_unbekannte_art_wird_abgelehnt(self, client: AsyncClient) -> None:
        antwort = await client.post("/staffelpilot/auftraege", json={"art": "kaffee"})

        assert antwort.status_code == 422

    async def test_eine_unbekannte_staffel_gibt_404(self, client: AsyncClient) -> None:
        antwort = await client.post("/staffelpilot/auftraege", json={"staffel_id": UNBEKANNT})

        assert antwort.status_code == 404

    async def test_zwei_gleichzeitig_gehen_nicht(self, client: AsyncClient) -> None:
        """Es gibt genau eine DFBnet-Sitzung. Der zweite Browser wuerfe den
        ersten hinaus, mitten in einem halb gelesenen Spielbericht."""
        await anfordern(client)

        antwort = await client.post("/staffelpilot/auftraege", json={})

        assert antwort.status_code == 409
        assert "unterwegs" in antwort.text

    async def test_nach_dem_abschluss_geht_der_naechste(self, client: AsyncClient) -> None:
        erster = await anfordern(client)
        await client.post(
            f"/staffelpilot/auftraege/{erster['id']}/abschluss", json={"zustand": "fertig"}
        )

        assert (await client.post("/staffelpilot/auftraege", json={})).status_code == 201


class TestOffener:
    async def test_ohne_auftrag_kommt_null(self, client: AsyncClient) -> None:
        """Die Oberflaeche fragt das im Sekundentakt ab. Ein 404 waere dort ein
        Fehler und kein Ergebnis."""
        antwort = await client.get("/staffelpilot/auftraege/offen")

        assert antwort.status_code == 200
        assert antwort.json() is None

    async def test_der_wartende_steht_da(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)

        assert (await client.get("/staffelpilot/auftraege/offen")).json()["id"] == auftrag["id"]

    async def test_ein_beendeter_steht_nicht_mehr_da(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)
        await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/abschluss", json={"zustand": "fertig"}
        )

        assert (await client.get("/staffelpilot/auftraege/offen")).json() is None

    async def test_offen_steht_vor_der_kennung(self, client: AsyncClient) -> None:
        """Waere es umgekehrt, versuchte FastAPI 'offen' als UUID zu lesen."""
        assert (await client.get("/staffelpilot/auftraege/offen")).status_code == 200


class TestFortschritt:
    async def test_die_erste_meldung_startet_ihn(self, client: AsyncClient) -> None:
        """Dass er sich meldet, *ist* der Beleg dafuer, dass er angefangen hat
        - ein eigener Startaufruf waere eine zweite Stelle fuer denselben
        Umstand."""
        auftrag = await anfordern(client)

        antwort = await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/fortschritt",
            json={"schritt": "Melde mich bei DFBnet an"},
        )

        assert antwort.json()["zustand"] == "laeuft"
        assert antwort.json()["gestartet_am"] is not None
        assert antwort.json()["schritt"] == "Melde mich bei DFBnet an"

    async def test_zahlen_werden_uebernommen(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)

        antwort = await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/fortschritt",
            json={"fortschritt": 40, "gepruefte": 12, "befunde": 3},
        )

        assert antwort.json()["fortschritt"] == 40
        assert antwort.json()["gepruefte"] == 12

    async def test_ausgelassene_felder_bleiben_stehen(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)
        pfad = f"/staffelpilot/auftraege/{auftrag['id']}/fortschritt"
        await client.post(pfad, json={"gepruefte": 12, "schritt": "Prüfe M-1"})

        antwort = await client.post(pfad, json={"fortschritt": 50})

        assert antwort.json()["gepruefte"] == 12
        assert antwort.json()["schritt"] == "Prüfe M-1"

    async def test_ein_verrechneter_fortschritt_haelt_nichts_an(self, client: AsyncClient) -> None:
        """Die Zahl ist eine Anzeige, kein Ergebnis - ein Dienst, der sich
        verrechnet, soll deswegen nicht mitten im Lauf stehenbleiben."""
        auftrag = await anfordern(client)
        pfad = f"/staffelpilot/auftraege/{auftrag['id']}/fortschritt"

        assert (await client.post(pfad, json={"fortschritt": 250})).json()["fortschritt"] == 100
        assert (await client.post(pfad, json={"fortschritt": -5})).json()["fortschritt"] == 0

    async def test_protokollzeilen_haengen_sich_an(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)
        pfad = f"/staffelpilot/auftraege/{auftrag['id']}/fortschritt"
        await client.post(pfad, json={"zeile": "Angemeldet"})
        antwort = await client.post(pfad, json={"zeile": "M-1 geprüft"})

        protokoll = antwort.json()["protokoll"]
        assert [z["text"] for z in protokoll] == ["Angemeldet", "M-1 geprüft"]
        assert protokoll[0]["zeit"]

    async def test_die_liste_traegt_kein_protokoll(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)
        await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/fortschritt", json={"zeile": "x"}
        )

        zeilen = (await client.get("/staffelpilot/auftraege")).json()

        assert len(zeilen) == 1
        assert "protokoll" not in zeilen[0]

    async def test_unbekannter_auftrag_gibt_404(self, client: AsyncClient) -> None:
        antwort = await client.post(
            f"/staffelpilot/auftraege/{UNBEKANNT}/fortschritt", json={"zeile": "x"}
        )

        assert antwort.status_code == 404


class TestAbschluss:
    async def test_fertig_setzt_den_balken_auf_voll(self, client: AsyncClient) -> None:
        """Ein Lauf, der bei 97 % endet, sieht abgebrochen aus."""
        auftrag = await anfordern(client)
        await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/fortschritt", json={"fortschritt": 97}
        )

        antwort = await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/abschluss", json={"zustand": "fertig"}
        )

        assert antwort.json()["fortschritt"] == 100
        assert antwort.json()["beendet_am"] is not None

    async def test_gescheitert_haelt_die_meldung_fest(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)

        antwort = await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/abschluss",
            json={"zustand": "gescheitert", "meldung": "DFBnet antwortet nicht"},
        )

        assert antwort.json()["zustand"] == "gescheitert"
        assert antwort.json()["meldung"] == "DFBnet antwortet nicht"
        assert antwort.json()["fortschritt"] == 0

    async def test_abbrechen_geht_auch_aus_dem_wartezustand(self, client: AsyncClient) -> None:
        """Wer zu frueh geklickt hat, soll den Auftrag wieder loswerden, ohne
        dass je ein Browser gestartet ist."""
        auftrag = await anfordern(client)

        antwort = await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/abschluss", json={"zustand": "abgebrochen"}
        )

        assert antwort.json()["zustand"] == "abgebrochen"

    async def test_ein_beendeter_laesst_sich_nicht_fortsetzen(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)
        pfad = f"/staffelpilot/auftraege/{auftrag['id']}/abschluss"
        await client.post(pfad, json={"zustand": "fertig"})

        antwort = await client.post(pfad, json={"zustand": "gescheitert"})

        assert antwort.status_code == 409

    async def test_und_nimmt_auch_keinen_fortschritt_mehr_an(self, client: AsyncClient) -> None:
        """Eine spaete Meldung eines Dienstes, der sich schon abgemeldet hat,
        wuerde sonst den Endstand ueberschreiben."""
        auftrag = await anfordern(client)
        await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/abschluss", json={"zustand": "fertig"}
        )

        antwort = await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/fortschritt", json={"fortschritt": 10}
        )

        assert antwort.status_code == 409

    async def test_ein_lauf_ohne_arbeit_ist_sofort_fertig(self, client: AsyncClient) -> None:
        """Ein Prueflauf, fuer den es nichts zu pruefen gibt, hat nie einen
        Schritt gemeldet - und ist trotzdem durch."""
        auftrag = await anfordern(client)

        antwort = await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/abschluss", json={"zustand": "fertig"}
        )

        assert antwort.status_code == 200, antwort.text
        assert antwort.json()["zustand"] == "fertig"


class TestListe:
    async def test_der_juengste_steht_oben(self, client: AsyncClient) -> None:
        erster = await anfordern(client)
        await client.post(
            f"/staffelpilot/auftraege/{erster['id']}/abschluss", json={"zustand": "fertig"}
        )
        zweiter = await anfordern(client, art="initialisierung")

        zeilen = (await client.get("/staffelpilot/auftraege")).json()

        assert [z["id"] for z in zeilen] == [zweiter["id"], erster["id"]]

    async def test_das_protokoll_steht_im_einzelnen(self, client: AsyncClient) -> None:
        auftrag = await anfordern(client)
        await client.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/fortschritt", json={"zeile": "Angemeldet"}
        )

        einzeln = (await client.get(f"/staffelpilot/auftraege/{auftrag['id']}")).json()

        assert einzeln["protokoll"][0]["text"] == "Angemeldet"

    async def test_unbekannter_auftrag_gibt_404(self, client: AsyncClient) -> None:
        assert (await client.get(f"/staffelpilot/auftraege/{UNBEKANNT}")).status_code == 404
