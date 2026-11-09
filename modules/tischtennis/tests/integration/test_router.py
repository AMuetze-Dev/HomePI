"""Der Router gegen eine echte Datenbank.

Als Integration markiert, weil er fast nur aus Datenbankzugriff besteht: gegen
eine nachgebaute Sitzung wuerde man vor allem den Nachbau testen.

    make dev
    HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
        uv run pytest -m 'not smoke'
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

ACHT = ["Anna", "Bernd", "Cem", "Dana", "Elif", "Fiete", "Gesa", "Hanna"]


async def turnier_anlegen(client: AsyncClient, **abweichend: Any) -> dict[str, Any]:
    daten: dict[str, Any] = {
        "name": "Betriebsturnier",
        "modus": "gruppen_ko",
        "tische": 2,
        "best_of": 3,
        "minuten_pro_spiel": 12,
        "anzahl_gruppen": 2,
        "weiter_pro_gruppe": 2,
        "runden": 3,
    }
    daten.update(abweichend)
    antwort = await client.post("/tischtennis/turnier", json=daten)
    assert antwort.status_code == 201, antwort.text
    return dict(antwort.json())


async def leute_eintragen(
    client: AsyncClient, turnier_id: str, namen: list[str] = ACHT
) -> list[dict[str, Any]]:
    angelegt = []
    for name in namen:
        antwort = await client.post(
            f"/tischtennis/turnier/{turnier_id}/teilnehmer", json={"name": name, "notiz": ""}
        )
        assert antwort.status_code == 201, antwort.text
        angelegt.append(dict(antwort.json()))
    return angelegt


async def spiele(client: AsyncClient, turnier_id: str) -> list[dict[str, Any]]:
    antwort = await client.get(f"/tischtennis/turnier/{turnier_id}/spiele")
    assert antwort.status_code == 200, antwort.text
    return list(antwort.json())


async def werte(client: AsyncClient, spiel: dict[str, Any], sieger: str) -> dict[str, Any]:
    antwort = await client.put(
        f"/tischtennis/spiel/{spiel['id']}/ergebnis", json={"sieger_id": sieger}
    )
    assert antwort.status_code == 200, antwort.text
    return dict(antwort.json())


async def alles_durchspielen(client: AsyncClient, turnier_id: str, gewinner: str = "heim") -> None:
    """Jedes offene Spiel mit zwei bekannten Gegnern werten.

    Standardmaessig gewinnt der Heimspieler - fuer die Zusagen, um die es
    geht, ist das gleichgueltig, und es macht den Verlauf nachvollziehbar.
    """
    for spiel in await spiele(client, turnier_id):
        if spiel["zustand"] == "beendet" or not spiel["heim_id"] or not spiel["gast_id"]:
            continue
        await werte(client, spiel, spiel[f"{gewinner}_id"])


class TestTurnierUndTeilnehmer:
    async def test_leere_liste(self, client: AsyncClient) -> None:
        assert (await client.get("/tischtennis/")).json() == []

    async def test_anlegen_und_lesen(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)

        assert lauf["zustand"] == "planung"
        assert lauf["saat"] is None
        assert [t["name"] for t in (await client.get("/tischtennis/")).json()] == [
            "Betriebsturnier"
        ]

    async def test_best_of_eins_ist_erlaubt(self, client: AsyncClient) -> None:
        """Ein Satz, ein Spiel - bei zwanzig Kollegen und zwei Tischen die
        einzige Variante, die an einem Abend durchlaeuft."""
        lauf = await turnier_anlegen(client, best_of=1)

        assert lauf["best_of"] == 1

    async def test_doppelter_name_wird_abgelehnt(self, client: AsyncClient) -> None:
        await turnier_anlegen(client)

        antwort = await client.post(
            "/tischtennis/turnier", json={"name": "Betriebsturnier", "modus": "ko"}
        )

        assert antwort.status_code == 409
        assert "problem+json" in antwort.headers["content-type"]

    async def test_name_aus_leerzeichen_nennt_das_feld(self, client: AsyncClient) -> None:
        antwort = await client.post("/tischtennis/turnier", json={"name": "   "})

        assert antwort.status_code == 422
        assert any("name" in fehler["feld"] for fehler in antwort.json()["fehler"])

    async def test_teilnehmer_eintragen(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)

        await leute_eintragen(client, lauf["id"], ["Anna", "Bernd"])

        liste = (await client.get(f"/tischtennis/turnier/{lauf['id']}/teilnehmer")).json()
        assert [t["name"] for t in liste] == ["Anna", "Bernd"]

    async def test_derselbe_name_zweimal_wird_abgelehnt(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"], ["Anna"])

        antwort = await client.post(
            f"/tischtennis/turnier/{lauf['id']}/teilnehmer", json={"name": "Anna"}
        )

        assert antwort.status_code == 409

    async def test_unbekanntes_turnier_ergibt_404(self, client: AsyncClient) -> None:
        antwort = await client.get("/tischtennis/turnier/00000000-0000-0000-0000-000000000000")

        assert antwort.status_code == 404


class TestAuslosung:
    async def test_die_vorschau_speichert_nichts(self, client: AsyncClient) -> None:
        """Der Grund, warum "nochmal wuerfeln" ohne Aufraeumen geht."""
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])

        vorschau = await client.post(
            f"/tischtennis/turnier/{lauf['id']}/auslosung", json={"saat": 7}
        )

        assert vorschau.status_code == 200
        assert len(vorschau.json()["gruppen"]) == 2
        assert vorschau.json()["anzahl_spiele"] == 12
        assert await spiele(client, lauf["id"]) == []

    async def test_dieselbe_saat_ergibt_dieselbe_vorschau(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])

        erste = await client.post(f"/tischtennis/turnier/{lauf['id']}/auslosung", json={"saat": 7})
        zweite = await client.post(f"/tischtennis/turnier/{lauf['id']}/auslosung", json={"saat": 7})

        assert erste.json()["gruppen"] == zweite.json()["gruppen"]

    async def test_zu_wenige_teilnehmer_sagen_es(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"], ["Anna"])

        antwort = await client.post(f"/tischtennis/turnier/{lauf['id']}/auslosung", json={})

        assert antwort.status_code == 409
        assert "zwei" in antwort.json()["detail"]

    async def test_auswuerfeln_schreibt_den_plan_und_startet(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])

        gestartet = await client.post(
            f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7}
        )

        assert gestartet.status_code == 200
        assert gestartet.json()["zustand"] == "laufend"
        assert gestartet.json()["saat"] == 7
        assert len(await spiele(client, lauf["id"])) == 12

    async def test_zweimal_auswuerfeln_wird_abgelehnt(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        antwort = await client.post(
            f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 8}
        )

        assert antwort.status_code == 409
        assert "zurueck in die Planung" in antwort.json()["detail"]

    async def test_zuruecksetzen_erlaubt_ein_neues_los(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        zurueck = await client.post(f"/tischtennis/turnier/{lauf['id']}/zuruecksetzen")

        assert zurueck.json()["zustand"] == "planung"
        assert await spiele(client, lauf["id"]) == []

    async def test_teilnehmer_nach_dem_auswuerfeln_wird_abgelehnt(
        self, client: AsyncClient
    ) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        antwort = await client.post(
            f"/tischtennis/turnier/{lauf['id']}/teilnehmer", json={"name": "Zuspaet"}
        )

        assert antwort.status_code == 409

    async def test_gewinnsaetze_bleiben_aenderbar_die_gruppen_nicht(
        self, client: AsyncClient
    ) -> None:
        """best_of steht in keinem Ergebnis mehr - es sagt nur, wie lange
        gespielt wird, und das darf man mitten im Abend kuerzen."""
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        einstellungen = {
            "modus": "gruppen_ko",
            "tische": 2,
            "best_of": 3,
            "minuten_pro_spiel": 12,
            "anzahl_gruppen": 2,
            "weiter_pro_gruppe": 2,
            "runden": 3,
        }
        erlaubt = await client.put(
            f"/tischtennis/turnier/{lauf['id']}", json={**einstellungen, "best_of": 1}
        )
        verboten = await client.put(
            f"/tischtennis/turnier/{lauf['id']}", json={**einstellungen, "anzahl_gruppen": 4}
        )

        assert erlaubt.status_code == 200
        assert erlaubt.json()["best_of"] == 1
        assert verboten.status_code == 409
        assert "anzahl_gruppen" in verboten.json()["detail"]


class TestErgebnisse:
    async def test_ein_sieger_genuegt(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]

        gewertet = await werte(client, spiel, spiel["gast_id"])

        assert gewertet["zustand"] == "beendet"
        assert gewertet["sieger_id"] == spiel["gast_id"]

    async def test_ein_fremder_sieger_wird_abgelehnt(self, client: AsyncClient) -> None:
        """Zwei Fenster offen, und das Ergebnis landet am falschen Spiel -
        der einzige Fehler, den diese Eingabe noch machen kann."""
        lauf = await turnier_anlegen(client)
        leute = await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]
        fremder = next(
            wer for wer in leute if wer["id"] not in (spiel["heim_id"], spiel["gast_id"])
        )

        antwort = await client.put(
            f"/tischtennis/spiel/{spiel['id']}/ergebnis", json={"sieger_id": fremder["id"]}
        )

        assert antwort.status_code == 422
        assert "problem+json" in antwort.headers["content-type"]
        assert "Gegner" in antwort.json()["detail"]

    async def test_spiel_beginnen_setzt_den_tisch(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]

        antwort = await client.post(f"/tischtennis/spiel/{spiel['id']}/beginnen", json={})

        assert antwort.json()["zustand"] == "laeuft"
        assert antwort.json()["tisch"] in {1, 2}

    async def test_ergebnis_zuruecknehmen(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]
        await werte(client, spiel, spiel["heim_id"])

        antwort = await client.delete(f"/tischtennis/spiel/{spiel['id']}/ergebnis")

        assert antwort.json()["zustand"] == "geplant"
        assert antwort.json()["sieger_id"] is None

    async def test_tabelle_zaehlt_siege_und_punkte(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])

        tabellen = (await client.get(f"/tischtennis/turnier/{lauf['id']}/tabellen")).json()

        assert [t["titel"] for t in tabellen] == ["Gruppe A", "Gruppe B"]
        for tabelle in tabellen:
            assert sum(zeile["siege"] for zeile in tabelle["zeilen"]) >= 6
            for zeile in tabelle["zeilen"]:
                assert zeile["punkte"] == zeile["siege"] * 2


#: Ein Ergebnis je Paarung, unabhaengig davon, wie das Los sie angesetzt hat.
#: Ergibt Anna 2 Siege, Bernd 2, Cem 1, Dana 1 - zwei teilen sich Platz eins,
#: zwei den Platz drei. Ohne diese Vorgabe haengt die Tabelle am Los, und der
#: Test prueft dann mal das eine und mal das andere.
AUSGANG = {
    frozenset(("Anna", "Bernd")): "Bernd",
    frozenset(("Anna", "Cem")): "Anna",
    frozenset(("Anna", "Dana")): "Anna",
    frozenset(("Bernd", "Cem")): "Bernd",
    frozenset(("Bernd", "Dana")): "Dana",
    frozenset(("Cem", "Dana")): "Cem",
}


async def nach_vorgabe_spielen(client: AsyncClient, turnier_id: str) -> None:
    leute = (await client.get(f"/tischtennis/turnier/{turnier_id}/teilnehmer")).json()
    nach_name = {wer["name"]: wer["id"] for wer in leute}

    for spiel in await spiele(client, turnier_id):
        if spiel["zustand"] == "beendet" or not spiel["heim"] or not spiel["gast"]:
            continue
        sieger = AUSGANG[frozenset((spiel["heim"], spiel["gast"]))]
        await werte(client, spiel, nach_name[sieger])


class TestEntscheidungsspiel:
    async def test_punktgleiche_an_der_grenze_spielen_von_selbst(self, client: AsyncClient) -> None:
        """Anna und Bernd stehen punktgleich auf Platz eins, und nur einer
        kommt weiter. Ohne Entscheidungsspiel fiele die Wahl nach dem
        Alphabet - die unauffaelligste Art, ein Turnier unfair zu machen."""
        lauf = await turnier_anlegen(client, anzahl_gruppen=1, weiter_pro_gruppe=1)
        await leute_eintragen(client, lauf["id"], ACHT[:4])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        await nach_vorgabe_spielen(client, lauf["id"])

        entscheidungen = [
            s for s in await spiele(client, lauf["id"]) if s["phase"] == "entscheidung"
        ]
        assert len(entscheidungen) == 1
        assert {entscheidungen[0]["heim"], entscheidungen[0]["gast"]} == {"Anna", "Bernd"}
        assert entscheidungen[0]["bezeichnung"].endswith("Entscheidungsspiel")
        assert (await client.get(f"/tischtennis/turnier/{lauf['id']}")).json()[
            "zustand"
        ] == "laufend", "nicht durch, solange das Entscheidungsspiel offen ist"

    async def test_die_tabelle_nennt_die_offene_entscheidung(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, anzahl_gruppen=1, weiter_pro_gruppe=1)
        await leute_eintragen(client, lauf["id"], ACHT[:4])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await nach_vorgabe_spielen(client, lauf["id"])

        tabelle = (await client.get(f"/tischtennis/turnier/{lauf['id']}/tabellen")).json()[0]

        assert sorted(tabelle["entscheidung_offen"]) == ["Anna", "Bernd"]

    async def test_das_entscheidungsspiel_loest_den_gleichstand_auf(
        self, client: AsyncClient
    ) -> None:
        """Es ist eine ganz normale Begegnung derselben Gruppe - deshalb
        loest sein Ergebnis den Gleichstand in der Tabelle selbst auf, ohne
        eine zweite Rangregel."""
        lauf = await turnier_anlegen(client, anzahl_gruppen=1, weiter_pro_gruppe=1)
        await leute_eintragen(client, lauf["id"], ACHT[:4])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await nach_vorgabe_spielen(client, lauf["id"])

        spiel = next(s for s in await spiele(client, lauf["id"]) if s["phase"] == "entscheidung")
        await werte(client, spiel, spiel["heim_id"])

        tabelle = (await client.get(f"/tischtennis/turnier/{lauf['id']}/tabellen")).json()[0]
        assert tabelle["entscheidung_offen"] == []
        assert [z["platz"] for z in tabelle["zeilen"]][:2] == [1, 2]

    async def test_punktgleich_ohne_folgen_bleibt_stehen(self, client: AsyncClient) -> None:
        """Dieselbe Tabelle, aber zwei kommen weiter: dann entscheidet die
        Reihenfolge von Anna und Bernd nichts, und niemand muss noch einmal
        antreten."""
        lauf = await turnier_anlegen(client, anzahl_gruppen=1, weiter_pro_gruppe=2)
        await leute_eintragen(client, lauf["id"], ACHT[:4])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        await nach_vorgabe_spielen(client, lauf["id"])

        alle = await spiele(client, lauf["id"])
        assert [s for s in alle if s["phase"] == "entscheidung"] == []
        tabelle = (await client.get(f"/tischtennis/turnier/{lauf['id']}/tabellen")).json()[0]
        assert [z["platz"] for z in tabelle["zeilen"]] == [1, 1, 3, 3]

    async def test_geteilte_plaetze_stehen_in_der_tabelle(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, anzahl_gruppen=1, weiter_pro_gruppe=1)
        await leute_eintragen(client, lauf["id"], ACHT[:4])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        tabelle = (await client.get(f"/tischtennis/turnier/{lauf['id']}/tabellen")).json()[0]

        assert all(zeile["platz"] == 1 for zeile in tabelle["zeilen"]), (
            "vor dem ersten Spiel sind alle punktgleich und teilen sich Platz eins"
        )


class TestKoRaster:
    async def test_das_raster_entsteht_nach_der_gruppenphase(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])
        await alles_durchspielen(client, lauf["id"])  # etwaige Entscheidungsspiele

        angesetzt = await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        assert angesetzt.status_code == 200, angesetzt.text
        assert angesetzt.json()["ko_steht"] is True
        ko = [s for s in await spiele(client, lauf["id"]) if s["phase"] == "ko"]
        assert [s["bezeichnung"] for s in ko] == ["Halbfinale", "Halbfinale", "Endspiel"]

    async def test_vor_der_zeit_angesetzt_sagt_es_das(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        antwort = await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        assert antwort.status_code == 409
        assert "noch Spiele offen" in antwort.json()["detail"]

    async def test_das_endspiel_kennt_seine_gegner_erst_spaeter(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])
        await alles_durchspielen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        endspiel = next(
            s for s in await spiele(client, lauf["id"]) if s["bezeichnung"] == "Endspiel"
        )

        assert endspiel["heim"] is None
        assert endspiel["heim_herkunft"].startswith("Sieger aus Spiel ")

    async def test_der_sieger_rueckt_ins_endspiel_auf(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])
        await alles_durchspielen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        halbfinale = [
            s for s in await spiele(client, lauf["id"]) if s["bezeichnung"] == "Halbfinale"
        ]
        gewertet = await werte(client, halbfinale[0], halbfinale[0]["heim_id"])

        endspiel = next(
            s for s in await spiele(client, lauf["id"]) if s["bezeichnung"] == "Endspiel"
        )
        assert endspiel["heim_id"] == gewertet["sieger_id"]

    async def test_eine_korrektur_nimmt_das_folgespiel_mit(self, client: AsyncClient) -> None:
        """Der Fall, der ohne diese Regel still falsch waere: das Endspiel
        war mit dem falschen Sieger schon gewertet."""
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])
        await alles_durchspielen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")
        await alles_durchspielen(client, lauf["id"])
        await alles_durchspielen(client, lauf["id"])

        vorher = await spiele(client, lauf["id"])
        assert next(s for s in vorher if s["bezeichnung"] == "Endspiel")["zustand"] == "beendet"
        halbfinale = next(s for s in vorher if s["bezeichnung"] == "Halbfinale")

        await client.delete(f"/tischtennis/spiel/{halbfinale['id']}/ergebnis")

        endspiel = next(
            s for s in await spiele(client, lauf["id"]) if s["bezeichnung"] == "Endspiel"
        )
        assert endspiel["zustand"] == "geplant"
        assert endspiel["heim_id"] is None


class TestWeitereModi:
    async def test_reines_ko_steht_sofort(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        assert len(alle) == 7
        assert {s["bezeichnung"] for s in alle} == {"Viertelfinale", "Halbfinale", "Endspiel"}

    async def test_ko_mit_freilosen(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"], ACHT[:6])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        assert len([s for s in alle if s["runde"] == 1]) == 2
        assert len(alle) == 5

    async def test_schweizer_setzt_runde_fuer_runde(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="schweizer", runden=3)
        await leute_eintragen(client, lauf["id"])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        assert len(await spiele(client, lauf["id"])) == 4

        await alles_durchspielen(client, lauf["id"])
        zweite = await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        assert zweite.json()["runde_angesetzt"] == 2
        assert len(await spiele(client, lauf["id"])) == 8

    async def test_ungerade_zahl_bekommt_ein_freilos(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="schweizer", runden=2)
        await leute_eintragen(client, lauf["id"], ACHT[:5])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        freilose = [s for s in await spiele(client, lauf["id"]) if s["freilos"]]
        assert len(freilose) == 1
        assert freilose[0]["zustand"] == "beendet"

    async def test_eine_gruppe_ist_jeder_gegen_jeden(self, client: AsyncClient) -> None:
        """Gruppen + KO mit einer Gruppe und einem Weiterkommenden: das ist
        die Variante "alle gegen alle, eine Tabelle"."""
        lauf = await turnier_anlegen(client, anzahl_gruppen=1, weiter_pro_gruppe=1)
        await leute_eintragen(client, lauf["id"], ACHT[:4])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        assert len(await spiele(client, lauf["id"])) == 6

        await alles_durchspielen(client, lauf["id"])
        await alles_durchspielen(client, lauf["id"])
        angesetzt = await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        assert angesetzt.json()["ko_steht"] is True
        assert [s for s in await spiele(client, lauf["id"]) if s["phase"] == "ko"] == []


class TestDashboard:
    async def test_ohne_turnier_bleibt_es_leer_statt_zu_scheitern(
        self, besucher: AsyncClient
    ) -> None:
        antwort = await besucher.get("/tischtennis/dashboard")

        assert antwort.status_code == 200
        assert antwort.json()["turnier"] is None

    async def test_der_besucher_sieht_das_laufende_turnier(
        self, client: AsyncClient, besucher: AsyncClient
    ) -> None:
        """Der ganze Zweck dieses Artefakts: ohne Konto, ohne Cookie."""
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        antwort = await besucher.get("/tischtennis/dashboard")

        assert antwort.status_code == 200
        inhalt = antwort.json()
        assert inhalt["turnier"]["name"] == "Betriebsturnier"
        assert len(inhalt["tische"]) == 2
        assert len(inhalt["naechste"]) > 0
        assert len(inhalt["teilnehmer"]) == 8

    async def test_das_laufende_spiel_steht_an_seinem_tisch(
        self, client: AsyncClient, besucher: AsyncClient
    ) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]
        await client.post(f"/tischtennis/spiel/{spiel['id']}/beginnen", json={"tisch": 1})

        inhalt = (await besucher.get("/tischtennis/dashboard")).json()

        tisch_eins = next(t for t in inhalt["tische"] if t["tisch"] == 1)
        assert tisch_eins["laeuft"]["id"] == spiel["id"]

    async def test_wer_gleich_dran_ist_steht_im_dashboard(
        self, client: AsyncClient, besucher: AsyncClient
    ) -> None:
        lauf = await turnier_anlegen(client, tische=1)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]
        await client.post(f"/tischtennis/spiel/{spiel['id']}/beginnen", json={"tisch": 1})

        inhalt = (await besucher.get("/tischtennis/dashboard")).json()

        assert inhalt["naechste"][0]["gleich_dran"] is True
        assert inhalt["naechste"][1]["gleich_dran"] is False

    async def test_beendete_spiele_stehen_als_letzte_ergebnisse(
        self, client: AsyncClient, besucher: AsyncClient
    ) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]
        await werte(client, spiel, spiel["heim_id"])

        inhalt = (await besucher.get("/tischtennis/dashboard")).json()

        assert [s["id"] for s in inhalt["letzte"]] == [spiel["id"]]
        assert inhalt["letzte"][0]["sieger_id"] == spiel["heim_id"]


class TestRechte:
    async def test_der_besucher_darf_nichts_schreiben(self, besucher: AsyncClient) -> None:
        """Ohne diese Zusage koennte jeder mit dem Link neu auswuerfeln."""
        antwort = await besucher.post("/tischtennis/turnier", json={"name": "Fremd"})

        assert antwort.status_code == 401

    async def test_ohne_recht_gibt_es_403_statt_401(self, fremder: AsyncClient) -> None:
        antwort = await fremder.post("/tischtennis/turnier", json={"name": "Fremd"})

        assert antwort.status_code == 403

    async def test_ergebnisse_sind_nicht_oeffentlich(
        self, client: AsyncClient, besucher: AsyncClient
    ) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]

        antwort = await besucher.put(
            f"/tischtennis/spiel/{spiel['id']}/ergebnis", json={"sieger_id": spiel["heim_id"]}
        )

        assert antwort.status_code == 401

    async def test_lesen_bleibt_fuer_jeden_offen(
        self, client: AsyncClient, besucher: AsyncClient
    ) -> None:
        lauf = await turnier_anlegen(client)

        for pfad in (
            "/tischtennis/",
            "/tischtennis/dashboard",
            f"/tischtennis/turnier/{lauf['id']}",
            f"/tischtennis/turnier/{lauf['id']}/teilnehmer",
            f"/tischtennis/turnier/{lauf['id']}/spiele",
            f"/tischtennis/turnier/{lauf['id']}/tabellen",
        ):
            assert (await besucher.get(pfad)).status_code == 200, pfad

    async def test_das_artefakt_steht_im_manifest_auch_ohne_anmeldung(
        self, besucher: AsyncClient
    ) -> None:
        antwort = await besucher.get("/module")

        assert antwort.status_code == 200
        assert "tischtennis" in {eintrag["id"] for eintrag in antwort.json()}
