"""Die Regeln des Turniers - Ergebnis, Tabelle, Zeitplan, Zustaende.

Alles hier ist rein: keine Datenbank, kein await. Deshalb laeuft diese Datei
in Millisekunden, und nur deshalb wird die rot-gruen-Schleife wirklich
benutzt.

Der Zuschnitt seit dem Umbau auf Einfachheit: ein Ergebnis ist ein Sieger
und sonst nichts. Keine Saetze, keine Baelle, keine Differenzen. Was bei
Punktgleichheit passiert, entscheidet kein Rechenweg, sondern ein Spiel.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from homepi_tischtennis import dienst
from homepi_tischtennis.dienst import Ergebnis

JETZT = datetime(2026, 11, 8, 18, 0, tzinfo=UTC)


def sieg(sieger: str, verlierer: str) -> Ergebnis:
    return Ergebnis(heim=sieger, gast=verlierer, sieger=sieger)


class TestTabelle:
    def test_ein_sieg_zaehlt_zwei_punkte(self) -> None:
        zeilen = dienst.tabelle(["anna", "bernd"], [sieg("anna", "bernd")])

        assert [(z.teilnehmer, z.punkte, z.platz) for z in zeilen] == [
            ("anna", 2, 1),
            ("bernd", 0, 2),
        ]

    def test_wer_nicht_gespielt_hat_steht_trotzdem_in_der_tabelle(self) -> None:
        """Eine Tabelle, in der jemand erst auftaucht, wenn er gespielt hat,
        laesst beim Lesen offen, ob er fehlt oder nur noch nicht dran war."""
        zeilen = dienst.tabelle(["anna", "bernd", "cem"], [])

        assert len(zeilen) == 3
        assert all(z.spiele == 0 and z.platz == 1 for z in zeilen)

    def test_zaehlt_siege_und_niederlagen(self) -> None:
        zeilen = dienst.tabelle(
            ["anna", "bernd", "cem"],
            [sieg("anna", "bernd"), sieg("cem", "anna")],
        )
        anna = next(z for z in zeilen if z.teilnehmer == "anna")

        assert (anna.spiele, anna.siege, anna.niederlagen) == (2, 1, 1)

    def test_ein_spiel_ohne_sieger_zaehlt_nicht(self) -> None:
        """Ein laufendes Spiel steht in der Liste, hat aber keinen Sieger -
        und darf die Tabelle nicht anfassen."""
        zeilen = dienst.tabelle(
            ["anna", "bernd"], [Ergebnis(heim="anna", gast="bernd", sieger=None)]
        )

        assert all(z.spiele == 0 for z in zeilen)

    def test_punktgleiche_teilen_sich_den_platz(self) -> None:
        """Kein Rechenweg trennt sie: Satzdifferenz gibt es nicht mehr, und
        der direkte Vergleich waere eine stille Entscheidung. Geteilter Platz
        ist die ehrliche Auskunft - und der Anlass fuer ein Entscheidungsspiel."""
        zeilen = dienst.tabelle(
            ["anna", "bernd", "cem", "dana"],
            [sieg("anna", "cem"), sieg("bernd", "dana")],
        )

        nach_name = {z.teilnehmer: z.platz for z in zeilen}
        assert nach_name["anna"] == nach_name["bernd"] == 1
        assert nach_name["cem"] == nach_name["dana"] == 3, "zwei teilen Platz 1, dann kommt 3"

    def test_bei_gleichstand_bleibt_die_reihenfolge_alphabetisch(self) -> None:
        """Irgendeine Reihenfolge muss die Liste haben. Der Name ist die
        einzige, die bei zwei Abrufen dieselbe ist - eine Tabelle, die beim
        Neuladen springt, wirkt kaputt."""
        zeilen = dienst.tabelle(["dana", "anna", "cem"], [])

        assert [z.teilnehmer for z in zeilen] == ["anna", "cem", "dana"]

    def test_platzierung_als_namen(self) -> None:
        zeilen = dienst.tabelle(["anna", "bernd"], [sieg("bernd", "anna")])

        assert dienst.platzierung(zeilen) == ["bernd", "anna"]


class TestFreilose:
    def test_ein_freilos_zaehlt_wie_ein_sieg(self) -> None:
        """Im Schweizer System bei ungerader Zahl sitzt einer aus. Ohne
        Punkte stuerzte er in der Tabelle ab, obwohl er nichts falsch
        gemacht hat."""
        zeilen = dienst.tabelle(["anna", "bernd"], [], freilose={"anna": 1})
        anna = next(z for z in zeilen if z.teilnehmer == "anna")

        assert (anna.punkte, anna.siege, anna.platz) == (2, 1, 1)


class TestGleichstand:
    def test_ohne_gleichstand_an_der_grenze_ist_nichts_zu_tun(self) -> None:
        zeilen = dienst.tabelle(
            ["anna", "bernd", "cem", "dana"],
            [sieg("anna", "bernd"), sieg("anna", "cem"), sieg("bernd", "cem")],
        )

        assert dienst.gleichstand_an_der_grenze(zeilen, grenze=2) == []

    def test_zwei_auf_dem_letzten_weiterkommenden_platz(self) -> None:
        """Zwei kommen weiter, und der zweite Platz ist geteilt: genau dann
        muss gespielt werden, denn einer von beiden faellt sonst nach dem
        Alphabet heraus."""
        zeilen = dienst.tabelle(
            ["anna", "bernd", "cem", "dana"],
            [
                sieg("anna", "bernd"),
                sieg("anna", "cem"),
                sieg("bernd", "dana"),
                sieg("cem", "dana"),
            ],
        )

        assert dienst.gleichstand_an_der_grenze(zeilen, grenze=2) == ["bernd", "cem"]

    def test_gleichstand_oberhalb_der_grenze_bleibt_stehen(self) -> None:
        """Zwei punktgleiche auf den Plaetzen eins und zwei, und beide kommen
        weiter: wer von ihnen vorn steht, entscheidet nichts. Dafuer laesst
        man niemanden noch einmal antreten."""
        zeilen = dienst.tabelle(
            ["anna", "bernd", "cem", "dana"],
            [
                sieg("anna", "cem"),
                sieg("anna", "dana"),
                sieg("bernd", "cem"),
                sieg("bernd", "dana"),
            ],
        )

        assert dienst.gleichstand_an_der_grenze(zeilen, grenze=2) == []

    def test_drei_punktgleiche_spielen_alle_gegeneinander(self) -> None:
        zeilen = dienst.tabelle(["anna", "bernd", "cem", "dana"], [sieg("anna", "dana")])

        assert dienst.gleichstand_an_der_grenze(zeilen, grenze=2) == ["bernd", "cem", "dana"]

    def test_bei_einem_weiterkommenden_zaehlt_der_erste_platz(self) -> None:
        zeilen = dienst.tabelle(
            ["anna", "bernd", "cem"], [sieg("anna", "cem"), sieg("bernd", "cem")]
        )

        assert dienst.gleichstand_an_der_grenze(zeilen, grenze=1) == ["anna", "bernd"]

    def test_eine_leere_tabelle_verlangt_nichts(self) -> None:
        assert dienst.gleichstand_an_der_grenze([], grenze=2) == []

    def test_wer_schon_entschieden_hat_wird_nicht_noch_einmal_gefragt(self) -> None:
        """Nach dem Entscheidungsspiel hat einer der beiden einen Sieg mehr -
        damit loest sich der Gleichstand von selbst auf, und es entsteht kein
        zweites."""
        zeilen = dienst.tabelle(
            ["anna", "bernd", "cem", "dana"],
            [
                sieg("anna", "bernd"),
                sieg("anna", "cem"),
                sieg("bernd", "dana"),
                sieg("cem", "dana"),
                sieg("bernd", "cem"),
            ],
        )

        assert dienst.gleichstand_an_der_grenze(zeilen, grenze=2) == []


class TestEntscheidungsspiele:
    def test_zwei_ergeben_ein_spiel(self) -> None:
        assert dienst.entscheidungsspiele(["anna", "bernd"]) == [("anna", "bernd")]

    def test_drei_ergeben_eine_kleine_runde(self) -> None:
        paarungen = dienst.entscheidungsspiele(["anna", "bernd", "cem"])

        assert len(paarungen) == 3
        assert {frozenset(p) for p in paarungen} == {
            frozenset(("anna", "bernd")),
            frozenset(("anna", "cem")),
            frozenset(("bernd", "cem")),
        }

    def test_unter_zweien_gibt_es_nichts_zu_entscheiden(self) -> None:
        assert dienst.entscheidungsspiele(["anna"]) == []
        assert dienst.entscheidungsspiele([]) == []


def plan(*spiele: dienst.Spielstandzeile) -> list[dienst.Planzeile]:
    return dienst.planen(spiele, tische=2, minuten=12, jetzt=JETZT)


def geplant(kennung: str) -> dienst.Spielstandzeile:
    return dienst.Spielstandzeile(id=kennung, zustand="geplant")


class TestZeitplan:
    def test_so_viele_spiele_gleichzeitig_wie_tische(self) -> None:
        zeilen = plan(geplant("a"), geplant("b"), geplant("c"))

        assert [(z.spiel, z.tisch, z.erwartet_ab) for z in zeilen] == [
            ("a", 1, JETZT),
            ("b", 2, JETZT),
            ("c", 1, JETZT + timedelta(minutes=12)),
        ]

    def test_ein_laufendes_spiel_belegt_seinen_tisch(self) -> None:
        laeuft = dienst.Spielstandzeile(
            id="a", zustand="laeuft", tisch=1, begonnen_am=JETZT - timedelta(minutes=4)
        )

        zeilen = plan(laeuft, geplant("b"), geplant("c"))

        nach_spiel = {z.spiel: z for z in zeilen}
        assert nach_spiel["a"].laeuft
        assert nach_spiel["b"].tisch == 2
        assert nach_spiel["b"].erwartet_ab == JETZT
        assert nach_spiel["c"].tisch == 1
        assert nach_spiel["c"].erwartet_ab == JETZT + timedelta(minutes=8)

    def test_ein_ueberzogenes_spiel_blockiert_nicht_die_vergangenheit(self) -> None:
        """Laeuft ein Spiel laenger als geschaetzt, ist der Tisch jetzt frei
        und nicht in der Vergangenheit - sonst stuenden alle Folgezeiten vor
        dem aktuellen Zeitpunkt."""
        laeuft = dienst.Spielstandzeile(
            id="a", zustand="laeuft", tisch=1, begonnen_am=JETZT - timedelta(minutes=30)
        )

        zeilen = plan(laeuft, geplant("b"), geplant("c"), geplant("d"))

        assert next(z for z in zeilen if z.spiel == "d").erwartet_ab >= JETZT

    def test_beendete_spiele_stehen_nicht_im_plan(self) -> None:
        fertig = dienst.Spielstandzeile(id="a", zustand="beendet", tisch=1)

        zeilen = plan(fertig, geplant("b"))

        assert [z.spiel for z in zeilen] == ["b"]

    def test_wer_gleich_dran_ist_steht_am_naechsten_spiel_des_tisches(self) -> None:
        """Das ist die Glocke: sobald das Spiel vor meinem beginnt, ist meines
        das naechste - und genau dann soll die Nachricht kommen."""
        laeuft = dienst.Spielstandzeile(id="a", zustand="laeuft", tisch=1, begonnen_am=JETZT)

        zeilen = plan(laeuft, geplant("b"), geplant("c"))
        nach_spiel = {z.spiel: z for z in zeilen}

        assert nach_spiel["b"].gleich_dran is False, "b laeuft an Tisch 2, es wartet niemand"
        assert nach_spiel["c"].gleich_dran is True, "c folgt auf das laufende Spiel a"

    def test_ohne_laufendes_spiel_ist_niemand_gleich_dran(self) -> None:
        zeilen = plan(geplant("a"), geplant("b"), geplant("c"))

        assert all(not z.gleich_dran for z in zeilen)

    def test_die_reihenfolge_der_uebergabe_ist_die_reihenfolge_des_plans(self) -> None:
        zeilen = plan(geplant("c"), geplant("a"))

        assert [z.spiel for z in zeilen] == ["c", "a"]

    def test_ein_tisch_spielt_alles_hintereinander(self) -> None:
        zeilen = dienst.planen([geplant("a"), geplant("b")], tische=1, minuten=10, jetzt=JETZT)

        assert [z.erwartet_ab for z in zeilen] == [JETZT, JETZT + timedelta(minutes=10)]


class TestSchaetzung:
    def test_dauer_waechst_mit_den_spielen_und_faellt_mit_den_tischen(self) -> None:
        assert dienst.geschaetzte_dauer(anzahl_spiele=8, tische=2, minuten=12) == timedelta(
            minutes=48
        )

    def test_angefangene_belegung_zaehlt_voll(self) -> None:
        """Neun Spiele auf zwei Tischen sind fuenf Durchgaenge, nicht
        viereinhalb."""
        assert dienst.geschaetzte_dauer(anzahl_spiele=9, tische=2, minuten=12) == timedelta(
            minutes=60
        )

    def test_vorschlag_zielt_auf_vierergruppen(self) -> None:
        assert dienst.gruppen_vorschlag(4) == 1
        assert dienst.gruppen_vorschlag(8) == 2
        assert dienst.gruppen_vorschlag(12) == 3
        assert dienst.gruppen_vorschlag(14) == 4

    def test_vorschlag_bleibt_bei_wenigen_moeglich(self) -> None:
        assert dienst.gruppen_vorschlag(2) == 1
        assert dienst.gruppen_vorschlag(3) == 1
        assert dienst.gruppen_vorschlag(0) == 1


class TestZustaende:
    def test_in_der_planung_darf_ausgewuerfelt_werden(self) -> None:
        assert dienst.darf_auswuerfeln("planung").erlaubt

    def test_ein_laufendes_turnier_wird_nicht_neu_ausgewuerfelt(self) -> None:
        entscheidung = dienst.darf_auswuerfeln("laufend")

        assert not entscheidung.erlaubt
        assert entscheidung.grund

    def test_teilnehmer_aendern_geht_nur_in_der_planung(self) -> None:
        assert dienst.darf_teilnehmer_aendern("planung").erlaubt
        assert not dienst.darf_teilnehmer_aendern("laufend").erlaubt
        assert not dienst.darf_teilnehmer_aendern("beendet").erlaubt

    def test_eine_runde_ist_faellig_wenn_alle_spiele_fertig_sind(self) -> None:
        assert dienst.runde_vollstaendig(["beendet", "beendet"])
        assert not dienst.runde_vollstaendig(["beendet", "laeuft"])
        assert not dienst.runde_vollstaendig([])


def stand(**abweichend: object) -> dienst.Stand:
    vorgabe: dict[str, object] = {
        "modus": "gruppen_ko",
        "runde_angesetzt": 1,
        "runden": 4,
        "ko_steht": False,
        "offene_spiele": 0,
    }
    return dienst.Stand(**{**vorgabe, **abweichend})  # type: ignore[arg-type]


class TestNaechsterSchritt:
    def test_solange_spiele_offen_sind_wird_gespielt(self) -> None:
        assert dienst.naechster_schritt(stand(offene_spiele=3)) == "spielen"

    def test_nach_der_gruppenphase_kommt_das_raster(self) -> None:
        assert dienst.naechster_schritt(stand()) == "ko_ansetzen"

    def test_steht_das_raster_und_ist_durch_ist_das_turnier_fertig(self) -> None:
        assert dienst.naechster_schritt(stand(ko_steht=True)) == "fertig"

    def test_das_schweizer_system_setzt_runde_fuer_runde_nach(self) -> None:
        assert (
            dienst.naechster_schritt(stand(modus="schweizer", runde_angesetzt=2))
            == "runde_ansetzen"
        )

    def test_nach_der_letzten_runde_ist_schluss(self) -> None:
        assert (
            dienst.naechster_schritt(stand(modus="schweizer", runde_angesetzt=4, runden=4))
            == "fertig"
        )

    def test_im_ko_modus_gibt_es_nichts_nachzusetzen(self) -> None:
        """Im reinen KO rueckt der Sieger beim Eintragen des Ergebnisses auf -
        es gibt keine Runde, die jemand ansetzen muesste."""
        assert dienst.naechster_schritt(stand(modus="ko")) == "fertig"


class TestEinstellungen:
    def test_in_der_planung_ist_alles_aenderbar(self) -> None:
        assert dienst.darf_einstellung_aendern("planung", ["modus", "best_of"]).erlaubt

    def test_tische_und_minuten_gehen_auch_waehrend_des_turniers(self) -> None:
        """Ein Tisch faellt aus, einer kommt dazu - das muss gehen, sonst
        stimmt der Zeitplan den ganzen Abend nicht."""
        assert dienst.darf_einstellung_aendern("laufend", ["tische"]).erlaubt
        assert dienst.darf_einstellung_aendern("laufend", ["minuten_pro_spiel"]).erlaubt

    def test_best_of_geht_auch_spaeter_noch(self) -> None:
        """Es steht nirgends in den Daten, seit ein Ergebnis nur noch der
        Sieger ist - die Zahl sagt den Spielern, wie lange sie spielen, und
        das darf man mitten im Turnier noch kuerzen."""
        assert dienst.darf_einstellung_aendern("laufend", ["best_of"]).erlaubt

    def test_die_planfesten_stehen_fest_sobald_gespielt_wird(self) -> None:
        entscheidung = dienst.darf_einstellung_aendern("laufend", ["anzahl_gruppen", "tische"])

        assert not entscheidung.erlaubt
        assert "anzahl_gruppen" in entscheidung.grund

    def test_ohne_abweichung_ist_nichts_zu_pruefen(self) -> None:
        assert dienst.darf_einstellung_aendern("laufend", []).erlaubt


class TestKoBezeichnung:
    def test_die_letzte_runde_ist_das_endspiel(self) -> None:
        assert dienst.ko_bezeichnung(3, 3) == "Endspiel"

    def test_davor_liegen_halb_viertel_und_achtelfinale(self) -> None:
        assert dienst.ko_bezeichnung(2, 3) == "Halbfinale"
        assert dienst.ko_bezeichnung(1, 3) == "Viertelfinale"
        assert dienst.ko_bezeichnung(1, 4) == "Achtelfinale"

    def test_sehr_grosse_raster_werden_nur_gezaehlt(self) -> None:
        """Ab der Runde der letzten 32 gibt es keinen gaengigen Namen mehr -
        dann ist eine Nummer ehrlicher als ein erfundener."""
        assert dienst.ko_bezeichnung(1, 5) == "KO-Runde 1"

    def test_im_doppel_ko_heisst_die_letzte_sieger_runde_anders(self) -> None:
        """Dort ist sie nicht das Ende: der Verlierer hat noch eine Chance,
        und "Endspiel" wuerde am Tisch das Falsche versprechen."""
        assert dienst.ko_bezeichnung(3, 3, "sieger") == "Sieger-Finale"
        assert dienst.ko_bezeichnung(2, 3, "sieger") == "Halbfinale"

    def test_der_verliererzweig_wird_gezaehlt_und_endet_im_finale(self) -> None:
        assert dienst.ko_bezeichnung(1, 4, "verlierer") == "Verlierer-Runde 1"
        assert dienst.ko_bezeichnung(4, 4, "verlierer") == "Verlierer-Finale"

    def test_das_endspiel_steht_allein(self) -> None:
        assert dienst.ko_bezeichnung(1, 1, "finale") == "Endspiel"


class TestSieger:
    def test_der_sieger_muss_mitgespielt_haben(self) -> None:
        with pytest.raises(dienst.UngueltigesErgebnis):
            dienst.pruefe_sieger("cem", heim="anna", gast="bernd")

    def test_heim_oder_gast_sind_in_ordnung(self) -> None:
        dienst.pruefe_sieger("anna", heim="anna", gast="bernd")
        dienst.pruefe_sieger("bernd", heim="anna", gast="bernd")

    def test_ohne_gegner_gibt_es_keinen_sieger_einzutragen(self) -> None:
        with pytest.raises(dienst.UngueltigesErgebnis):
            dienst.pruefe_sieger("anna", heim="anna", gast=None)


class TestVerschieben:
    """Die Turnierleitung schiebt ein Spiel in der Warteschlange.

    Der Anlass ist nicht Bequemlichkeit: wer gerade nicht da ist, haelt sonst
    den ganzen Plan auf - und wenn trotzdem angepfiffen wird, zeigt das
    Dashboard das Falsche und die Glocke laeutet beim Falschen.
    """

    def test_ein_geplantes_spiel_tauscht_mit_dem_nachbarn(self) -> None:
        reihe = [
            dienst.Warteplatz(id="a", nummer=1, zustand="geplant", haengt_an=()),
            dienst.Warteplatz(id="b", nummer=2, zustand="geplant", haengt_an=()),
        ]

        assert dienst.tauschpartner(reihe, "a", "runter") == "b"
        assert dienst.tauschpartner(reihe, "b", "hoch") == "a"

    def test_am_rand_gibt_es_keinen_partner(self) -> None:
        reihe = [dienst.Warteplatz(id="a", nummer=1, zustand="geplant", haengt_an=())]

        with pytest.raises(dienst.FalscherZustand):
            dienst.tauschpartner(reihe, "a", "hoch")

    def test_was_laeuft_oder_gewertet_ist_wird_nicht_geschoben(self) -> None:
        reihe = [
            dienst.Warteplatz(id="a", nummer=1, zustand="laeuft", haengt_an=()),
            dienst.Warteplatz(id="b", nummer=2, zustand="geplant", haengt_an=()),
        ]

        with pytest.raises(dienst.FalscherZustand):
            dienst.tauschpartner(reihe, "a", "runter")

    def test_laufende_nachbarn_werden_uebersprungen(self) -> None:
        """Ein Spiel, das schon am Tisch steht, ist kein Tauschpartner - aber
        es soll den Tausch auch nicht blockieren."""
        reihe = [
            dienst.Warteplatz(id="a", nummer=1, zustand="geplant", haengt_an=()),
            dienst.Warteplatz(id="b", nummer=2, zustand="beendet", haengt_an=()),
            dienst.Warteplatz(id="c", nummer=3, zustand="geplant", haengt_an=()),
        ]

        assert dienst.tauschpartner(reihe, "a", "runter") == "c"

    def test_kein_spiel_rutscht_vor_seinen_zubringer(self) -> None:
        """Im KO laeuft hier der Sieger des Vorspiels ein. Vorgezogen waere
        es ein Spiel ohne Gegner."""
        reihe = [
            dienst.Warteplatz(id="a", nummer=1, zustand="geplant", haengt_an=()),
            dienst.Warteplatz(id="b", nummer=2, zustand="geplant", haengt_an=(1,)),
        ]

        with pytest.raises(dienst.FalscherZustand):
            dienst.tauschpartner(reihe, "b", "hoch")
        with pytest.raises(dienst.FalscherZustand):
            dienst.tauschpartner(reihe, "a", "runter")
