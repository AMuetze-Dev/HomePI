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

#: Ein 3:0 bei best of 5 - das kuerzeste vollstaendige Ergebnis.
GLATT = {"saetze": [{"heim": 11, "gast": 0}, {"heim": 11, "gast": 0}, {"heim": 11, "gast": 0}]}

ACHT = ["Anna", "Bernd", "Cem", "Dana", "Elif", "Fiete", "Gesa", "Hanna"]


async def turnier_anlegen(client: AsyncClient, **abweichend: Any) -> dict[str, Any]:
    daten: dict[str, Any] = {
        "name": "Betriebsturnier",
        "modus": "gruppen_ko",
        "tische": 2,
        "best_of": 5,
        "punkte_bis": 11,
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


async def alles_durchspielen(client: AsyncClient, turnier_id: str) -> None:
    """Jedes offene Spiel mit zwei bekannten Gegnern glatt werten.

    Der Heimspieler gewinnt immer - fuer die Zusagen, um die es hier geht,
    ist das egal, und es macht den Verlauf nachvollziehbar.
    """
    for spiel in await spiele(client, turnier_id):
        if spiel["zustand"] == "beendet" or not spiel["heim_id"] or not spiel["gast_id"]:
            continue
        antwort = await client.put(f"/tischtennis/spiel/{spiel['id']}/ergebnis", json=GLATT)
        assert antwort.status_code == 200, antwort.text


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
        assert (await client.get(f"/tischtennis/turnier/{lauf['id']}")).json()[
            "zustand"
        ] == "planung"

    async def test_dieselbe_saat_ergibt_dieselbe_vorschau(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])

        erste = await client.post(f"/tischtennis/turnier/{lauf['id']}/auslosung", json={"saat": 7})
        zweite = await client.post(f"/tischtennis/turnier/{lauf['id']}/auslosung", json={"saat": 7})

        assert erste.json()["gruppen"] == zweite.json()["gruppen"]

    async def test_ohne_saat_wird_eine_gezogen(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])

        vorschau = await client.post(f"/tischtennis/turnier/{lauf['id']}/auslosung", json={})

        assert vorschau.json()["saat"] >= 0

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
        # Zwei Gruppen zu vier: je sechs Spiele.
        assert len(await spiele(client, lauf["id"])) == 12

    async def test_jedes_gruppenspiel_hat_zwei_namen_und_eine_bezeichnung(
        self, client: AsyncClient
    ) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        for spiel in await spiele(client, lauf["id"]):
            assert spiel["heim"] and spiel["gast"]
            assert spiel["bezeichnung"].startswith("Gruppe ")
            assert spiel["gruppe"] in {"Gruppe A", "Gruppe B"}

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
        assert (
            await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 8})
        ).status_code == 200

    async def test_teilnehmer_nach_dem_auswuerfeln_wird_abgelehnt(
        self, client: AsyncClient
    ) -> None:
        """Wer jetzt dazukaeme, haette keine Spiele."""
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        antwort = await client.post(
            f"/tischtennis/turnier/{lauf['id']}/teilnehmer", json={"name": "Zuspaet"}
        )

        assert antwort.status_code == 409

    async def test_regeln_sind_nach_dem_start_fest_tische_nicht(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        einstellungen = {
            "modus": "gruppen_ko",
            "tische": 3,
            "best_of": 5,
            "punkte_bis": 11,
            "minuten_pro_spiel": 15,
            "anzahl_gruppen": 2,
            "weiter_pro_gruppe": 2,
            "runden": 3,
        }
        erlaubt = await client.put(f"/tischtennis/turnier/{lauf['id']}", json=einstellungen)
        verboten = await client.put(
            f"/tischtennis/turnier/{lauf['id']}", json={**einstellungen, "best_of": 3}
        )

        assert erlaubt.status_code == 200
        assert erlaubt.json()["tische"] == 3
        assert verboten.status_code == 409
        assert "best_of" in verboten.json()["detail"]


class TestErgebnisse:
    async def test_ergebnis_eintragen_beendet_das_spiel(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]

        antwort = await client.put(f"/tischtennis/spiel/{spiel['id']}/ergebnis", json=GLATT)

        assert antwort.status_code == 200
        assert antwort.json()["zustand"] == "beendet"
        assert antwort.json()["sieger_id"] == spiel["heim_id"]
        assert antwort.json()["saetze_heim"] == 3

    async def test_ein_zwischenstand_laesst_das_spiel_laufen(self, client: AsyncClient) -> None:
        """Wer am Tisch steht, traegt nach jedem Satz ein - und das
        Dashboard zeigt den Stand, solange gespielt wird."""
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]

        antwort = await client.put(
            f"/tischtennis/spiel/{spiel['id']}/ergebnis",
            json={"saetze": [{"heim": 11, "gast": 9}]},
        )

        assert antwort.json()["zustand"] == "laeuft"
        assert antwort.json()["sieger_id"] is None
        assert antwort.json()["begonnen_am"] is not None

    async def test_einen_satz_den_es_nicht_gibt_lehnt_das_backend_ab(
        self, client: AsyncClient
    ) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]

        antwort = await client.put(
            f"/tischtennis/spiel/{spiel['id']}/ergebnis",
            json={"saetze": [{"heim": 11, "gast": 10}]},
        )

        assert antwort.status_code == 422
        assert "problem+json" in antwort.headers["content-type"]
        assert "zwei Punkten" in antwort.json()["detail"]

    async def test_spiel_beginnen_setzt_den_tisch(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        spiel = (await spiele(client, lauf["id"]))[0]

        antwort = await client.post(f"/tischtennis/spiel/{spiel['id']}/beginnen", json={})

        assert antwort.json()["zustand"] == "laeuft"
        assert antwort.json()["tisch"] in {1, 2}

    async def test_tabelle_entsteht_aus_den_ergebnissen(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])

        tabellen = (await client.get(f"/tischtennis/turnier/{lauf['id']}/tabellen")).json()

        assert [t["titel"] for t in tabellen] == ["Gruppe A", "Gruppe B"]
        for tabelle in tabellen:
            assert [zeile["platz"] for zeile in tabelle["zeilen"]] == [1, 2, 3, 4]
            assert sum(zeile["siege"] for zeile in tabelle["zeilen"]) == 6


class TestKoRaster:
    async def test_das_raster_entsteht_nach_der_gruppenphase(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])

        angesetzt = await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        assert angesetzt.status_code == 200
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
        """Das Raster steht vollstaendig, bevor es gespielt ist - mit
        "Sieger aus Spiel 13" statt einer Leerstelle."""
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
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
        await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        halbfinale = [
            s for s in await spiele(client, lauf["id"]) if s["bezeichnung"] == "Halbfinale"
        ]
        gewertet = await client.put(
            f"/tischtennis/spiel/{halbfinale[0]['id']}/ergebnis", json=GLATT
        )

        endspiel = next(
            s for s in await spiele(client, lauf["id"]) if s["bezeichnung"] == "Endspiel"
        )
        assert endspiel["heim_id"] == gewertet.json()["sieger_id"]
        assert endspiel["heim"] == halbfinale[0]["heim"]

    async def test_eine_korrektur_nimmt_das_folgespiel_mit(self, client: AsyncClient) -> None:
        """Der Fall, der ohne diese Regel still falsch waere: das Endspiel
        war mit dem falschen Sieger schon gewertet."""
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")
        await alles_durchspielen(client, lauf["id"])  # Halbfinals
        await alles_durchspielen(client, lauf["id"])  # Endspiel

        vorher = await spiele(client, lauf["id"])
        assert next(s for s in vorher if s["bezeichnung"] == "Endspiel")["zustand"] == "beendet"
        halbfinale = next(s for s in vorher if s["bezeichnung"] == "Halbfinale")

        await client.delete(f"/tischtennis/spiel/{halbfinale['id']}/ergebnis")

        endspiel = next(
            s for s in await spiele(client, lauf["id"]) if s["bezeichnung"] == "Endspiel"
        )
        assert endspiel["zustand"] == "geplant"
        assert endspiel["saetze"] == []
        assert endspiel["heim_id"] is None

    async def test_am_ende_ist_das_turnier_beendet(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")
        await alles_durchspielen(client, lauf["id"])
        await alles_durchspielen(client, lauf["id"])

        assert (await client.get(f"/tischtennis/turnier/{lauf['id']}")).json()[
            "zustand"
        ] == "beendet"


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
        erste_runde = [s for s in alle if s["runde"] == 1]
        assert len(erste_runde) == 2, "Sechs Leute im Raster fuer acht: zwei Freilose"
        assert len(alle) == 5

    async def test_schweizer_setzt_runde_fuer_runde(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="schweizer", runden=3)
        await leute_eintragen(client, lauf["id"])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        assert len(await spiele(client, lauf["id"])) == 4

        await alles_durchspielen(client, lauf["id"])
        zweite = await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        assert zweite.json()["runde_angesetzt"] == 2
        alle = await spiele(client, lauf["id"])
        assert len(alle) == 8
        assert {s["bezeichnung"] for s in alle} == {"Runde 1", "Runde 2"}

    async def test_schweizer_wiederholt_keine_paarung(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="schweizer", runden=3)
        await leute_eintragen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        await alles_durchspielen(client, lauf["id"])
        await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        paarungen = [
            frozenset((s["heim_id"], s["gast_id"]))
            for s in await spiele(client, lauf["id"])
            if s["gast_id"]
        ]

        assert len(paarungen) == len(set(paarungen))

    async def test_ungerade_zahl_bekommt_ein_freilos(self, client: AsyncClient) -> None:
        lauf = await turnier_anlegen(client, modus="schweizer", runden=2)
        await leute_eintragen(client, lauf["id"], ACHT[:5])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})

        alle = await spiele(client, lauf["id"])
        freilose = [s for s in alle if s["freilos"]]
        assert len(freilose) == 1
        assert freilose[0]["zustand"] == "beendet"
        assert freilose[0]["gast_herkunft"] == "Freilos"

    async def test_eine_gruppe_ist_jeder_gegen_jeden(self, client: AsyncClient) -> None:
        """Gruppen + KO mit einer Gruppe und einem Weiterkommenden: das ist
        die Variante "alle gegen alle, eine Tabelle"."""
        lauf = await turnier_anlegen(client, anzahl_gruppen=1, weiter_pro_gruppe=1)
        await leute_eintragen(client, lauf["id"], ACHT[:4])

        await client.post(f"/tischtennis/turnier/{lauf['id']}/auswuerfeln", json={"saat": 7})
        assert len(await spiele(client, lauf["id"])) == 6

        await alles_durchspielen(client, lauf["id"])
        angesetzt = await client.post(f"/tischtennis/turnier/{lauf['id']}/naechste-runde")

        assert angesetzt.json()["ko_steht"] is True
        assert angesetzt.json()["zustand"] == "beendet"
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
        assert tisch_eins["danach"]

    async def test_wer_gleich_dran_ist_steht_im_dashboard(
        self, client: AsyncClient, besucher: AsyncClient
    ) -> None:
        """Die Glocke haengt an diesem Haekchen: das Spiel nach dem
        laufenden ist das, fuer das die Nachricht faellig ist."""
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
        await client.put(f"/tischtennis/spiel/{spiel['id']}/ergebnis", json=GLATT)

        inhalt = (await besucher.get("/tischtennis/dashboard")).json()

        assert [s["id"] for s in inhalt["letzte"]] == [spiel["id"]]
        assert inhalt["letzte"][0]["saetze_heim"] == 3


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

        antwort = await besucher.put(f"/tischtennis/spiel/{spiel['id']}/ergebnis", json=GLATT)

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
        """Die Kachel ist der Weg zum Dashboard - ohne sie braeuchte jeder
        Kollege den vollen Link."""
        antwort = await besucher.get("/module")

        assert antwort.status_code == 200
        assert "tischtennis" in {eintrag["id"] for eintrag in antwort.json()}
