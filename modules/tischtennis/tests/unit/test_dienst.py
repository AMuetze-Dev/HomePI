"""Die Regeln des Turniers - Saetze, Tabelle, Zeitplan, Zustaende.

Alles hier ist rein: keine Datenbank, kein await. Deshalb laeuft diese Datei
in Millisekunden, und nur deshalb wird die rot-gruen-Schleife wirklich
benutzt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from homepi_tischtennis import dienst
from homepi_tischtennis.dienst import Ergebnis, UngueltigesErgebnis

JETZT = datetime(2026, 11, 7, 18, 0, tzinfo=UTC)


class TestSatz:
    @pytest.mark.parametrize("heim,gast", [(11, 9), (11, 0), (12, 10), (15, 13)])
    def test_gueltige_saetze(self, heim: int, gast: int) -> None:
        dienst.satz_pruefen((heim, gast), punkte_bis=11)

    def test_bei_zehn_zu_zehn_geht_es_bis_zwei_punkte_vorsprung(self) -> None:
        """11:10 gibt es nicht. Das ist die Regel, die am haeufigsten falsch
        eingetippt wird - deshalb faellt sie hier auf und nicht in der
        Tabelle."""
        with pytest.raises(UngueltigesErgebnis):
            dienst.satz_pruefen((11, 10), punkte_bis=11)

    def test_ohne_erreichte_punktzahl_ist_der_satz_nicht_zu_ende(self) -> None:
        with pytest.raises(UngueltigesErgebnis):
            dienst.satz_pruefen((10, 5), punkte_bis=11)

    def test_unentschieden_gibt_es_nicht(self) -> None:
        with pytest.raises(UngueltigesErgebnis):
            dienst.satz_pruefen((11, 11), punkte_bis=11)

    def test_negative_punkte_werden_abgelehnt(self) -> None:
        with pytest.raises(UngueltigesErgebnis):
            dienst.satz_pruefen((11, -1), punkte_bis=11)

    def test_bis_einundzwanzig_gilt_dasselbe(self) -> None:
        dienst.satz_pruefen((21, 19), punkte_bis=21)
        with pytest.raises(UngueltigesErgebnis):
            dienst.satz_pruefen((21, 20), punkte_bis=21)


class TestSpielstand:
    def test_drei_gewonnene_saetze_entscheiden_bei_best_of_five(self) -> None:
        stand = dienst.spielstand([(11, 9), (11, 5), (9, 11), (11, 7)], best_of=5, punkte_bis=11)

        assert (stand.saetze_heim, stand.saetze_gast) == (3, 1)
        assert stand.sieger == "heim"
        assert stand.entschieden

    def test_ein_unfertiges_spiel_hat_keinen_sieger(self) -> None:
        stand = dienst.spielstand([(11, 9), (9, 11)], best_of=5, punkte_bis=11)

        assert stand.sieger is None
        assert not stand.entschieden

    def test_der_gast_kann_auch_gewinnen(self) -> None:
        stand = dienst.spielstand([(9, 11), (5, 11), (7, 11)], best_of=5, punkte_bis=11)

        assert stand.sieger == "gast"

    def test_mehr_saetze_als_moeglich_werden_abgelehnt(self) -> None:
        with pytest.raises(UngueltigesErgebnis):
            dienst.spielstand(
                [(11, 9), (11, 9), (11, 9), (11, 9), (11, 9), (11, 9)], best_of=5, punkte_bis=11
            )

    def test_nach_der_entscheidung_wird_nicht_weitergespielt(self) -> None:
        """3:0 und danach noch ein Satz: das ist kein Spielstand, sondern ein
        Tippfehler - und er wuerde die Satzdifferenz in der Tabelle
        verfaelschen."""
        with pytest.raises(UngueltigesErgebnis):
            dienst.spielstand([(11, 9), (11, 9), (11, 9), (11, 9)], best_of=5, punkte_bis=11)

    def test_best_of_three_ist_nach_zwei_saetzen_entschieden(self) -> None:
        stand = dienst.spielstand([(11, 9), (11, 9)], best_of=3, punkte_bis=11)

        assert stand.entschieden
        assert stand.sieger == "heim"

    def test_ein_leeres_ergebnis_ist_kein_fehler(self) -> None:
        """Ein Spiel ohne eingetragene Saetze ist der Normalzustand, solange
        es nicht gespielt wurde."""
        stand = dienst.spielstand([], best_of=5, punkte_bis=11)

        assert stand.sieger is None
        assert (stand.saetze_heim, stand.saetze_gast) == (0, 0)


class TestTabelle:
    def test_ein_sieg_zaehlt_zwei_punkte(self) -> None:
        zeilen = dienst.tabelle(
            ["anna", "bernd"], [Ergebnis("anna", "bernd", ((11, 9), (11, 5), (11, 7)))]
        )

        assert [(z.teilnehmer, z.punkte, z.platz) for z in zeilen] == [
            ("anna", 2, 1),
            ("bernd", 0, 2),
        ]

    def test_wer_nicht_gespielt_hat_steht_trotzdem_in_der_tabelle(self) -> None:
        """Eine Tabelle, in der ein Teilnehmer erst auftaucht, wenn er
        gespielt hat, laesst beim Lesen offen, ob er fehlt oder nur noch
        nicht dran war."""
        zeilen = dienst.tabelle(["anna", "bernd", "cem"], [])

        assert len(zeilen) == 3
        assert all(z.spiele == 0 for z in zeilen)

    def test_zaehlt_saetze_und_baelle(self) -> None:
        zeilen = dienst.tabelle(
            ["anna", "bernd"], [Ergebnis("anna", "bernd", ((11, 9), (9, 11), (11, 5), (11, 7)))]
        )
        anna = next(z for z in zeilen if z.teilnehmer == "anna")

        assert (anna.saetze_fuer, anna.saetze_gegen) == (3, 1)
        assert (anna.baelle_fuer, anna.baelle_gegen) == (42, 32)
        assert anna.satzdifferenz == 2
        assert anna.balldifferenz == 10

    def test_bei_punktgleichheit_entscheidet_der_direkte_vergleich(self) -> None:
        """Zwei mit je einem Sieg: die Satzdifferenz ueber alle Spiele kann
        der eine aus einem Kantersieg gegen Dritte haben. Zuerst zaehlt, wer
        das Spiel gegeneinander gewonnen hat."""
        ergebnisse = [
            # bernd schlaegt anna knapp; anna raeumt dafuer gegen die beiden
            # anderen ab und steht danach mit bernd punktgleich.
            Ergebnis("bernd", "anna", ((11, 9), (11, 9), (11, 9))),
            Ergebnis("anna", "cem", ((11, 0), (11, 0), (11, 0))),
            Ergebnis("anna", "dana", ((11, 0), (11, 0), (11, 0))),
            Ergebnis("bernd", "cem", ((11, 9), (11, 9), (11, 9))),
            Ergebnis("dana", "bernd", ((11, 9), (11, 9), (11, 9))),
            Ergebnis("cem", "dana", ((11, 9), (11, 9), (11, 9))),
        ]

        zeilen = dienst.tabelle(["anna", "bernd", "cem", "dana"], ergebnisse)
        punkte = {z.teilnehmer: z.punkte for z in zeilen}

        assert punkte["anna"] == punkte["bernd"] == 4
        # Nach Balldifferenz stuende anna vorn - sie hat gegen bernd aber
        # verloren, und das zaehlt zuerst.
        assert [z.teilnehmer for z in zeilen] == ["bernd", "anna", "cem", "dana"]

    def test_ohne_direkten_vergleich_entscheidet_die_satzdifferenz(self) -> None:
        ergebnisse = [
            Ergebnis("anna", "cem", ((11, 0), (11, 0), (11, 0))),
            Ergebnis("bernd", "dana", ((11, 9), (9, 11), (11, 9), (11, 9))),
        ]

        zeilen = dienst.tabelle(["anna", "bernd", "cem", "dana"], ergebnisse)

        assert [z.teilnehmer for z in zeilen[:2]] == ["anna", "bernd"]

    def test_bei_gleicher_satzdifferenz_entscheidet_die_balldifferenz(self) -> None:
        ergebnisse = [
            Ergebnis("anna", "cem", ((11, 0), (11, 0), (11, 0))),
            Ergebnis("bernd", "dana", ((11, 9), (11, 9), (11, 9))),
        ]

        zeilen = dienst.tabelle(["anna", "bernd", "cem", "dana"], ergebnisse)

        assert [z.teilnehmer for z in zeilen[:2]] == ["anna", "bernd"]

    def test_voellig_gleichstand_bleibt_alphabetisch(self) -> None:
        """Irgendwann ist jedes Merkmal gleich. Dann entscheidet der Name -
        nicht die Einfuegereihenfolge, denn die ist beim Neuladen eine
        andere, und eine Tabelle, die bei jedem Abruf springt, wirkt
        kaputt."""
        zeilen = dienst.tabelle(["dana", "anna", "cem"], [])

        assert [z.teilnehmer for z in zeilen] == ["anna", "cem", "dana"]

    def test_unfertige_spiele_zaehlen_nicht_als_sieg(self) -> None:
        zeilen = dienst.tabelle(["anna", "bernd"], [Ergebnis("anna", "bernd", ((11, 9),))])

        assert all(z.siege == 0 for z in zeilen)
        assert all(z.spiele == 0 for z in zeilen)

    def test_platzierung_als_namen(self) -> None:
        ergebnisse = [Ergebnis("anna", "bernd", ((11, 9), (11, 9), (11, 9)))]

        assert dienst.platzierung(dienst.tabelle(["anna", "bernd"], ergebnisse)) == [
            "anna",
            "bernd",
        ]


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
        # Tisch 2 ist sofort frei, Tisch 1 erst in acht Minuten: b faengt
        # gleich an, c wartet auf Tisch 1.
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
        """Sonst sind die eingetragenen Ergebnisse Ergebnisse von Spielen,
        die es nicht mehr gibt."""
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


class TestFreilose:
    def test_ein_freilos_zaehlt_punkte_aber_keine_saetze(self) -> None:
        """Im Schweizer System bei ungerader Zahl sitzt einer aus. Ohne
        Punkte stuerzte er in der Tabelle ab, mit Saetzen stiege er auf -
        beides waere eine Folge des Losglueks und nicht des Spiels."""
        zeilen = dienst.tabelle(["anna", "bernd"], [], freilose={"anna": 1})
        anna = next(z for z in zeilen if z.teilnehmer == "anna")

        assert anna.punkte == 2
        assert anna.siege == 1
        assert (anna.saetze_fuer, anna.baelle_fuer) == (0, 0)
        assert anna.platz == 1


class TestEinstellungen:
    def test_in_der_planung_ist_alles_aenderbar(self) -> None:
        assert dienst.darf_einstellung_aendern("planung", ["modus", "best_of"]).erlaubt

    def test_tische_und_minuten_gehen_auch_waehrend_des_turniers(self) -> None:
        """Ein Tisch faellt aus, einer kommt dazu - das muss gehen, sonst
        stimmt der Zeitplan den ganzen Abend nicht."""
        assert dienst.darf_einstellung_aendern("laufend", ["tische"]).erlaubt
        assert dienst.darf_einstellung_aendern("laufend", ["minuten_pro_spiel"]).erlaubt

    def test_die_regeln_stehen_fest_sobald_gespielt_wird(self) -> None:
        entscheidung = dienst.darf_einstellung_aendern("laufend", ["best_of", "tische"])

        assert not entscheidung.erlaubt
        assert "best_of" in entscheidung.grund

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
