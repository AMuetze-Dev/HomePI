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
#: So viele, dass die Zahl keine Zweierpotenz ist - das ist der Normalfall.
NEUNZEHN = [f"Spieler {nummer:02d}" for nummer in range(1, 20)]
EINUNDZWANZIG = [f"Spieler {nummer:02d}" for nummer in range(1, 22)]


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

    async def test_die_vorschau_zaehlt_ein_freilos_nicht_als_spiel(
        self, client: AsyncClient
    ) -> None:
        """Die Zahl in der Vorschau ist die Grundlage fuer "wie lange dauert
        das". Ein Freilos dauert nichts - und es steht als Paarung mit dem
        Gegner "Freilos" da, nicht mit einer Leerstelle."""
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"], NEUNZEHN)

        vorschau = (
            await client.post(f"/tischtennis/turnier/{lauf['id']}/auslosung", json={"saat": 7})
        ).json()

        assert vorschau["anzahl_spiele"] == 18
        freilose = [p for p in vorschau["paarungen"] if p["gast"] == "Freilos"]
        assert len(freilose) == 3
        assert all(
            "None" not in p["heim"] and "None" not in p["gast"] for p in vorschau["paarungen"]
        )

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
        """Sechs im reinen KO: drei Spiele, danach bleibt einer uebrig."""
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"], ACHT[:6])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        assert len([s for s in alle if s["runde"] == 1]) == 3
        assert len([s for s in alle if not s["freilos"]]) == 5

    async def test_im_reinen_ko_spielt_in_der_ersten_runde_jeder(self, client: AsyncClient) -> None:
        """Neunzehn Angemeldete: neun Spiele und ein Freilos.

        Ein gesetztes Raster haette drei Spiele - und sechzehn Leute, die
        zusehen. Wer zu einem Feierabendturnier kommt, soll spielen.
        """
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"], NEUNZEHN)

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        erste = [s for s in await spiele(client, lauf["id"]) if s["runde"] == 1]
        assert len([s for s in erste if not s["freilos"]]) == 9
        angetreten = {wer for s in erste for wer in (s["heim_id"], s["gast_id"]) if wer is not None}
        assert len(angetreten) == 19

    async def test_das_freilos_ist_entschieden_und_steht_im_raster(
        self, client: AsyncClient
    ) -> None:
        """Es ist kein Spiel, sondern die Zeile, die erklaert, warum einer
        durch ist: beendet, mit Sieger, und der Gegner heisst "Freilos"."""
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"], NEUNZEHN)

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        erstes = next(s for s in alle if s["runde"] == 1 and s["freilos"])
        assert erstes["zustand"] == "beendet"
        assert erstes["sieger_id"] == erstes["heim_id"]
        assert erstes["gast_herkunft"] == "Freilos"
        assert erstes["heim_herkunft"] is None

    async def test_ein_spaeteres_freilos_wartet_auf_seinen_mann(self, client: AsyncClient) -> None:
        """Fuenf Leute: in der zweiten Runde ist wieder einer uebrig - nur
        steht da noch nicht fest, wer. Solange sagt die Zeile "Sieger aus
        Spiel 2" und nicht "Freilos"; sobald es feststeht, ist sie durch."""
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"], ACHT[:5])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        spaet = next(
            s for s in await spiele(client, lauf["id"]) if s["freilos"] and s["heim_id"] is None
        )
        assert spaet["zustand"] == "geplant"
        assert spaet["heim_herkunft"].startswith("Sieger aus Spiel")

        await alles_durchspielen(client, lauf["id"])

        nachher = next(s for s in await spiele(client, lauf["id"]) if s["id"] == spaet["id"])
        assert nachher["zustand"] == "beendet"
        assert nachher["sieger_id"] == nachher["heim_id"] is not None

    async def test_auch_mit_zweiter_chance_spielt_jeder_in_runde_eins(
        self, client: AsyncClient
    ) -> None:
        """Frueher bekam das Doppel-KO das gesetzte Raster - bei 19 Leuten
        hiess das drei Spiele und dreizehn Zuschauer in der ersten Runde.
        Jetzt wird auch hier ausgelost: neun Spiele, ein Freilos."""
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"], NEUNZEHN)

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        erste = [s for s in alle if s["runde"] == 1 and s["phase"] == "ko"]
        assert len([s for s in erste if not s["freilos"]]) == 9
        assert len([s for s in erste if s["freilos"]]) == 1

    async def test_ein_freilos_reicht_seinen_mann_sofort_weiter(self, client: AsyncClient) -> None:
        """Das Freilos in Runde 1 ist mit dem Ansetzen entschieden. Sein
        Sieger muss im Folgespiel schon stehen - sonst wartet es auf ein
        Ergebnis, das nie eingetragen wird, und das Turnier haengt."""
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"], NEUNZEHN)
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        for _ in range(2 * len(NEUNZEHN)):
            await alles_durchspielen(client, lauf["id"])

        alle = await spiele(client, lauf["id"])
        assert [s["nummer"] for s in alle if s["zustand"] != "beendet"] == []

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


class TestDoppelKo:
    """Die zweite Chance, durch den ganzen Stapel.

    Die Rechnung dahinter steht in ``test_los.py`` und laeuft in
    Millisekunden. Hier geht es um das, was nur die Datenbank beantwortet:
    dass der VERLIERER eines Spiels im Verliererzweig einlaeuft - und zwar
    derselbe, der eben verloren hat.
    """

    async def test_das_raster_ist_fast_doppelt_so_gross(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])

        assert len(alle) == 2 * len(ACHT) - 2
        assert {s["phase"] for s in alle} == {"ko", "ko_verlierer", "ko_finale"}

    async def test_der_verlierer_laeuft_im_verliererzweig_ein(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        erstes = alle[0]
        verlierer_id = erstes["gast_id"]
        await werte(client, erstes, erstes["heim_id"])

        danach = await spiele(client, lauf["id"])
        auffangend = [
            s
            for s in danach
            if s["phase"] == "ko_verlierer" and verlierer_id in (s["heim_id"], s["gast_id"])
        ]

        assert len(auffangend) == 1, "der Verlierer muss genau einmal weiterspielen"

    async def test_vor_dem_spiel_steht_verlierer_aus_spiel_da(self, client: AsyncClient) -> None:
        """Das Raster haengt an der Wand, bevor gespielt wird. Stuende dort
        "Sieger aus Spiel 1", waere es an jedem Platz des Verliererzweigs
        falsch."""
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        erste_verliererrunde = next(s for s in alle if s["phase"] == "ko_verlierer")

        assert erste_verliererrunde["heim_herkunft"].startswith("Verlierer aus Spiel")
        assert erste_verliererrunde["gast_herkunft"].startswith("Verlierer aus Spiel")

    async def test_die_herkunft_nennt_das_spiel_auch_als_zahl(self, client: AsyncClient) -> None:
        """Das Raster hebt das Spiel hervor, auf das "Verlierer aus Spiel 3"
        zeigt. Dafuer braucht es die Nummer als Feld - aus dem Satz
        herausgelesen, braeche es mit der ersten anderen Formulierung."""
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        nummern = {s["nummer"] for s in alle}
        unten = next(s for s in alle if s["phase"] == "ko_verlierer")

        assert unten["heim_aus_spiel"] in nummern
        assert unten["heim_herkunft"] == f"Verlierer aus Spiel {unten['heim_aus_spiel']}"
        assert unten["gast_aus_spiel"] in nummern
        # Ein Spiel der ersten Runde kommt aus keinem anderen.
        anfang = next(s for s in alle if s["phase"] == "ko" and s["runde"] == 1)
        assert anfang["heim_aus_spiel"] is None

    async def test_eine_korrektur_zieht_den_verliererzweig_mit(self, client: AsyncClient) -> None:
        """Wird ein Ergebnis gedreht, wechselt nicht nur der Sieger oben,
        sondern auch der Verlierer unten - sonst spielt im Verliererzweig
        jemand, der gar nicht verloren hat."""
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        erstes = alle[0]
        await werte(client, erstes, erstes["heim_id"])
        await werte(client, erstes, erstes["gast_id"])

        danach = await spiele(client, lauf["id"])
        verliererzweig = [s for s in danach if s["phase"] == "ko_verlierer"]
        aufgefangen = {s["heim_id"] for s in verliererzweig} | {
            s["gast_id"] for s in verliererzweig
        }

        assert erstes["heim_id"] in aufgefangen
        assert erstes["gast_id"] not in aufgefangen

    async def test_das_turnier_endet_im_endspiel(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        for _ in range(2 * len(ACHT)):
            await alles_durchspielen(client, lauf["id"])

        alle = await spiele(client, lauf["id"])
        endspiel = next(s for s in alle if s["phase"] == "ko_finale")

        assert [s for s in alle if s["zustand"] != "beendet"] == []
        assert endspiel["sieger_id"] is not None

    async def test_die_vorschau_nennt_verlierer_und_zweige(self, client: AsyncClient) -> None:
        """Die Vorschau ist dieselbe Rechnung wie das Festschreiben - dann muss
        sie auch dasselbe sagen. Stand dort "Sieger aus Spiel 1", wo der
        Verlierer einlaeuft, war das Los vor dem Speichern nicht zu lesen."""
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"])

        antwort = await client.post(
            f"/tischtennis/turnier/{lauf['id']}/auslosung", json={"saat": 7}
        )

        paarungen = antwort.json()["paarungen"]
        assert any(p["heim"].startswith("Verlierer aus Spiel") for p in paarungen)
        assert any(p["bezeichnung"].startswith("Verlierer-Runde") for p in paarungen)
        assert paarungen[-1]["bezeichnung"] == "Endspiel"

    async def test_mit_21_spielt_jeder_in_der_ersten_runde(self, client: AsyncClient) -> None:
        """Der Fall vom Weihnachtsturnier, durch Speicher und Router: zehn
        Spiele und ein Freilos in Runde 1, und das Turnier laeuft bis zum
        Endspiel durch, ohne dass irgendwo jemand fehlt."""
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"], EINUNDZWANZIG)
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 3})

        alle = await spiele(client, lauf["id"])
        erste = [s for s in alle if s["phase"] == "ko" and s["runde"] == 1]
        echte = [s for s in erste if not s["freilos"]]

        assert len(echte) == 10
        assert len(erste) == 11
        assert all(s["heim_id"] and s["gast_id"] for s in echte)
        assert len([s for s in alle if not s["freilos"]]) == 2 * 21 - 2

        for _ in range(4 * 21):
            await alles_durchspielen(client, lauf["id"])
        danach = await spiele(client, lauf["id"])
        endspiel = next(s for s in danach if s["phase"] == "ko_finale")

        assert [s["nummer"] for s in danach if s["zustand"] != "beendet"] == []
        assert endspiel["sieger_id"] is not None

    async def test_doppel_ko_laesst_sich_im_lauf_nicht_umstellen(self, client: AsyncClient) -> None:
        """Daran haengt der halbe Spielplan. Mitten im Turnier umgestellt,
        gehoerte die eine Haelfte zu anderen Regeln als die andere."""
        lauf = await turnier_anlegen(client, modus="ko", doppel_ko=True)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        antwort = await client.put(
            f"/tischtennis/turnier/{lauf['id']}",
            json={
                "modus": "ko",
                "tische": 2,
                "best_of": 3,
                "minuten_pro_spiel": 12,
                "anzahl_gruppen": 2,
                "weiter_pro_gruppe": 2,
                "runden": 3,
                "doppel_ko": False,
            },
        )

        assert antwort.status_code == 409, antwort.text


class TestVerschieben:
    """Spiele schieben, wenn jemand gerade keine Zeit hat."""

    async def test_ein_spiel_wandert_nach_hinten(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        vorher = await spiele(client, lauf["id"])

        antwort = await client.post(
            f"/tischtennis/spiel/{vorher[0]['id']}/verschieben", json={"richtung": "runter"}
        )
        assert antwort.status_code == 200, antwort.text

        nachher = await spiele(client, lauf["id"])
        assert [s["id"] for s in nachher[:2]] == [vorher[1]["id"], vorher[0]["id"]]

    async def test_die_nummern_bleiben_wie_sie_waren(self, client: AsyncClient) -> None:
        """Daran haengen die Verweise des Rasters. Wuerden sie mitwandern,
        zeigte "Sieger aus Spiel 7" auf ein anderes Spiel."""
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        vorher = {s["id"]: s["nummer"] for s in await spiele(client, lauf["id"])}

        erstes = next(iter(vorher))
        await client.post(f"/tischtennis/spiel/{erstes}/verschieben", json={"richtung": "runter"})

        nachher = {s["id"]: s["nummer"] for s in await spiele(client, lauf["id"])}
        assert nachher == vorher

    async def test_ein_angepfiffenes_spiel_wird_nicht_geschoben(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        alle = await spiele(client, lauf["id"])
        await client.post(f"/tischtennis/spiel/{alle[0]['id']}/beginnen", json={})

        antwort = await client.post(
            f"/tischtennis/spiel/{alle[0]['id']}/verschieben", json={"richtung": "runter"}
        )

        assert antwort.status_code == 409, antwort.text

    async def test_ohne_recht_geht_es_nicht(
        self, client: AsyncClient, besucher: AsyncClient
    ) -> None:
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        alle = await spiele(client, lauf["id"])

        antwort = await besucher.post(
            f"/tischtennis/spiel/{alle[0]['id']}/verschieben", json={"richtung": "runter"}
        )

        assert antwort.status_code in (401, 403), antwort.text


class TestTeilnehmerlisten:
    """Namen einmal speichern, vor jedem Turnier laden.

    Ausloeser war das Testen: vor jedem Probelauf 21 Namen von Hand. Eine
    Liste haengt an keinem Turnier - sie ist eine Vorlage, und Laden heisst
    "fehlende Namen eintragen", nie "vorhandene ersetzen".
    """

    async def speichern(
        self, client: AsyncClient, name: str, namen: list[str], erwartet: int = 201
    ) -> dict[str, Any]:
        antwort = await client.post("/tischtennis/listen", json={"name": name, "namen": namen})
        assert antwort.status_code == erwartet, antwort.text
        return dict(antwort.json())

    async def test_gespeichert_steht_sie_in_der_uebersicht(self, client: AsyncClient) -> None:
        liste = await self.speichern(client, "Stammtisch", [" Anna", "Bernd", "anna", ""])

        alle = (await client.get("/tischtennis/listen")).json()

        assert liste["namen"] == ["Anna", "Bernd"]
        assert [(eine["name"], eine["namen"]) for eine in alle] == [
            ("Stammtisch", ["Anna", "Bernd"])
        ]

    async def test_derselbe_name_zweimal_wird_abgelehnt(self, client: AsyncClient) -> None:
        await self.speichern(client, "Stammtisch", ACHT)

        antwort = await client.post(
            "/tischtennis/listen", json={"name": "Stammtisch", "namen": ["Anna"]}
        )

        assert antwort.status_code == 409
        assert "Stammtisch" in antwort.json()["detail"]

    async def test_ueberschreiben_ersetzt_die_namen(self, client: AsyncClient) -> None:
        liste = await self.speichern(client, "Stammtisch", ACHT)

        antwort = await client.put(
            f"/tischtennis/listen/{liste['id']}",
            json={"name": "Stammtisch", "namen": ["Cem", "Dana"]},
        )

        assert antwort.status_code == 200, antwort.text
        alle = (await client.get("/tischtennis/listen")).json()
        assert alle[0]["namen"] == ["Cem", "Dana"]

    async def test_eine_leere_liste_gibt_es_nicht(self, client: AsyncClient) -> None:
        antwort = await client.post("/tischtennis/listen", json={"name": "Leer", "namen": [" "]})

        assert antwort.status_code == 422

    async def test_laden_traegt_fehlende_ein_und_laesst_vorhandene_stehen(
        self, client: AsyncClient
    ) -> None:
        liste = await self.speichern(client, "Stammtisch", ACHT)
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"], ["bernd", "Zoe"])

        antwort = await client.post(
            f"/tischtennis/turnier/{lauf['id']}/teilnehmer/aus-liste/{liste['id']}"
        )

        assert antwort.status_code == 200, antwort.text
        ergebnis = antwort.json()
        assert [wer["name"] for wer in ergebnis["eingetragen"]] == [n for n in ACHT if n != "Bernd"]
        assert ergebnis["schon_dabei"] == ["Bernd"]
        dabei = (await client.get(f"/tischtennis/turnier/{lauf['id']}/teilnehmer")).json()
        assert len(dabei) == 2 + 7

    async def test_zweimal_laden_traegt_niemanden_doppelt_ein(self, client: AsyncClient) -> None:
        liste = await self.speichern(client, "Stammtisch", ACHT)
        lauf = await turnier_anlegen(client, modus="ko")
        pfad = f"/tischtennis/turnier/{lauf['id']}/teilnehmer/aus-liste/{liste['id']}"

        await client.post(pfad)
        zweites = (await client.post(pfad)).json()

        assert zweites["eingetragen"] == []
        assert len((await client.get(f"/tischtennis/turnier/{lauf['id']}/teilnehmer")).json()) == 8

    async def test_ins_laufende_turnier_wird_nichts_geladen(self, client: AsyncClient) -> None:
        liste = await self.speichern(client, "Stammtisch", ["Zoe"])
        lauf = await turnier_anlegen(client, modus="ko")
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 1})

        antwort = await client.post(
            f"/tischtennis/turnier/{lauf['id']}/teilnehmer/aus-liste/{liste['id']}"
        )

        assert antwort.status_code == 409

    async def test_loeschen(self, client: AsyncClient) -> None:
        liste = await self.speichern(client, "Stammtisch", ACHT)

        geloescht = await client.delete(f"/tischtennis/listen/{liste['id']}")
        noch_einmal = await client.delete(f"/tischtennis/listen/{liste['id']}")

        assert geloescht.status_code == 204
        assert noch_einmal.status_code == 404
        assert (await client.get("/tischtennis/listen")).json() == []
