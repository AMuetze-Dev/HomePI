"""Die Regeln des Quiz - ohne Datenbank, in Millisekunden."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

from homepi_quiz import dienst
from homepi_quiz.schemas import (
    AntwortEingabe,
    AuswahlDaten,
    BildDaten,
    BuzzerDaten,
    FrageAusgabe,
    FreitextDaten,
    HotspotDaten,
    Option,
    SchaetzDaten,
    SortierDaten,
    ZahlDaten,
    Ziel,
)

JETZT = dt.datetime(2026, 11, 28, 20, 0, tzinfo=dt.UTC)
FRAGE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _frage(daten, *, punkte: int = 2, hat_bild: bool = False) -> FrageAusgabe:
    return FrageAusgabe(
        id=FRAGE_ID,
        position=0,
        text="Wie heisst die Frage?",
        kategorie="Allgemein",
        punkte=punkte,
        zeitlimit=30,
        hat_bild=hat_bild,
        daten=daten,
    )


# ------------------------------------------------------------- Spielernamen


class TestSpielername:
    def test_wird_getrimmt_und_zusammengezogen(self) -> None:
        assert dienst.pruefe_spielername("  Anna   Lena ") == ("Anna Lena", "anna lena")

    def test_schluessel_ignoriert_gross_und_kleinschreibung(self) -> None:
        assert dienst.pruefe_spielername("ANNA")[1] == dienst.pruefe_spielername("anna")[1]

    def test_schluessel_faltet_auch_sonderformen(self) -> None:
        """ß und ss sind fuer das Auge derselbe Name - also auch hier."""
        assert dienst.pruefe_spielername("Strauß")[1] == dienst.pruefe_spielername("STRAUSS")[1]

    @pytest.mark.parametrize("name", ["", "   ", "a" * 25])
    def test_leer_oder_zu_lang_wird_abgelehnt(self, name: str) -> None:
        with pytest.raises(dienst.NameUngueltig):
            dienst.pruefe_spielername(name)

    def test_steuerzeichen_werden_abgelehnt(self) -> None:
        with pytest.raises(dienst.NameUngueltig):
            dienst.pruefe_spielername("Anna​")

    def test_unsichtbare_doppelgaenger_sind_kein_neuer_name(self) -> None:
        """Ein Name mit vorgesetztem Nullbreitenzeichen saehe auf der Tafel
        genauso aus wie das Original - das waere die Uebernahme durch die
        Hintertuer."""
        with pytest.raises(dienst.NameUngueltig):
            dienst.pruefe_spielername("​Anna")


class TestBeitritt:
    def test_nach_dem_ende_tritt_niemand_mehr_bei(self) -> None:
        dienst.pruefe_beitritt("lobby")
        dienst.pruefe_beitritt("laeuft")
        with pytest.raises(dienst.AktionNichtMoeglich, match="beendet"):
            dienst.pruefe_beitritt("beendet")

    def test_wiederkehr_nur_mit_passendem_gueltigem_code(self) -> None:
        from homepi_core.auth.passwoerter import hashe_token

        code = "ABCD-EFGH"
        gespeichert = hashe_token(code)
        bis = JETZT + dt.timedelta(minutes=5)

        assert dienst.wiederkehr_erlaubt(gespeichert, bis, "abcd efgh", JETZT)
        assert not dienst.wiederkehr_erlaubt(gespeichert, bis, "ABCD-EFGX", JETZT)
        assert not dienst.wiederkehr_erlaubt(
            gespeichert, JETZT - dt.timedelta(seconds=1), code, JETZT
        )
        assert not dienst.wiederkehr_erlaubt(None, bis, code, JETZT)


class TestSpielerzahl:
    def test_bis_zur_grenze_erlaubt(self) -> None:
        dienst.pruefe_spielerzahl(dienst.MAX_SPIELER - 1)

    def test_volle_runde_nimmt_niemanden_mehr(self) -> None:
        with pytest.raises(dienst.RundeVoll):
            dienst.pruefe_spielerzahl(dienst.MAX_SPIELER)


# ------------------------------------------------------------- Codes


class TestCodes:
    def test_rundencode_hat_sechs_eindeutige_zeichen(self) -> None:
        code = dienst.neuer_rundencode()
        assert len(code) == 6
        assert set(code) <= set(dienst.CODEALPHABET)

    def test_alphabet_ohne_verwechsler(self) -> None:
        assert not set("0O1IL") & set(dienst.CODEALPHABET)

    def test_code_wird_beim_eintippen_vergeben(self) -> None:
        assert dienst.normalisiere_code(" ab c-12x ") == "ABC12X"

    def test_unmoeglicher_code_ist_unbekannt(self) -> None:
        with pytest.raises(dienst.RundeUnbekannt):
            dienst.normalisiere_code("zu-lang-fuer-einen-code")

    def test_wiederkehrcode_ist_lesbar_gruppiert(self) -> None:
        code = dienst.neuer_wiederkehrcode()
        assert len(code) == 9 and code[4] == "-"

    def test_wiederkehrcode_vergleich_ignoriert_schreibweise(self) -> None:
        assert dienst.normalisiere_wiederkehrcode("abcd efgh") == "ABCD-EFGH"
        assert dienst.normalisiere_wiederkehrcode("ABCD-EFGH") == "ABCD-EFGH"

    def test_wiederkehrcode_laeuft_ab(self) -> None:
        bis = dienst.wiederkehr_gueltig_bis(JETZT)
        assert dienst.wiederkehr_gilt(bis, JETZT + dt.timedelta(minutes=5))
        assert not dienst.wiederkehr_gilt(bis, JETZT + dt.timedelta(hours=1))
        assert not dienst.wiederkehr_gilt(None, JETZT)


# ------------------------------------------------------------- Ablauf


class TestAblauf:
    def test_erste_frage_startet_die_runde(self) -> None:
        assert dienst.naechste_phase("lobby", "keine", "waehlen") == "bereit"

    def test_zeigen_oeffnet_eine_bereite_frage(self) -> None:
        assert dienst.naechste_phase("laeuft", "bereit", "zeigen") == "offen"

    def test_sperren_und_wieder_oeffnen(self) -> None:
        assert dienst.naechste_phase("laeuft", "offen", "sperren") == "gesperrt"
        assert dienst.naechste_phase("laeuft", "gesperrt", "oeffnen") == "offen"

    @pytest.mark.parametrize("phase", ["offen", "gesperrt"])
    def test_aufloesen_aus_offen_oder_gesperrt(self, phase) -> None:
        assert dienst.naechste_phase("laeuft", phase, "aufloesen") == "aufgeloest"

    def test_aufloesen_vor_dem_zeigen_geht_nicht(self) -> None:
        with pytest.raises(dienst.AktionNichtMoeglich, match="noch nicht gezeigt"):
            dienst.naechste_phase("laeuft", "bereit", "aufloesen")

    def test_ohne_frage_gibt_es_nichts_zu_zeigen(self) -> None:
        with pytest.raises(dienst.AktionNichtMoeglich):
            dienst.naechste_phase("lobby", "keine", "zeigen")

    def test_naechste_frage_jederzeit(self) -> None:
        for phase in ("bereit", "offen", "gesperrt", "aufgeloest"):
            assert dienst.naechste_phase("laeuft", phase, "waehlen") == "bereit"

    def test_nach_dem_ende_geht_nichts_mehr(self) -> None:
        with pytest.raises(dienst.AktionNichtMoeglich, match="beendet"):
            dienst.naechste_phase("beendet", "aufgeloest", "waehlen")

    def test_beenden_aus_jeder_phase(self) -> None:
        assert dienst.naechste_phase("laeuft", "offen", "beenden") == "aufgeloest"
        assert dienst.naechste_phase("lobby", "keine", "beenden") == "keine"

    def test_eine_schon_aufgeloeste_frage_kommt_aufgeloest_zurueck(self) -> None:
        """Wer zur vorigen Frage zurueckblaettert, will die Loesung zeigen und
        nicht die Punkte des Abends neu verteilen."""
        assert dienst.phase_nach_wahl(erledigt=True) == "aufgeloest"
        assert dienst.phase_nach_wahl(erledigt=False) == "bereit"

    def test_gesehen_wird_nicht_bei_jedem_abruf_geschrieben(self) -> None:
        assert dienst.gesehen_aktualisieren(None, JETZT)
        assert not dienst.gesehen_aktualisieren(JETZT - dt.timedelta(seconds=3), JETZT)
        assert dienst.gesehen_aktualisieren(JETZT - dt.timedelta(seconds=30), JETZT)

    def test_verbunden_heisst_kuerzlich_gesehen(self) -> None:
        assert dienst.verbunden(JETZT - dt.timedelta(seconds=10), JETZT)
        assert not dienst.verbunden(JETZT - dt.timedelta(minutes=2), JETZT)

    def test_frage_mit_bildpflicht_braucht_ein_bild(self) -> None:
        with pytest.raises(dienst.AktionNichtMoeglich, match="Bild"):
            dienst.pruefe_zeigbar(_frage(HotspotDaten(ziele=[Ziel(x=1, y=1)])))
        dienst.pruefe_zeigbar(_frage(HotspotDaten(ziele=[Ziel(x=1, y=1)]), hat_bild=True))
        dienst.pruefe_zeigbar(_frage(ZahlDaten(loesung=1)))

    def test_frist_nur_mit_timer_und_zeitlimit(self) -> None:
        assert dienst.frist_fuer(30, True, JETZT) == JETZT + dt.timedelta(seconds=30)
        assert dienst.frist_fuer(30, False, JETZT) is None
        assert dienst.frist_fuer(None, True, JETZT) is None


class TestAntwortErlaubt:
    def test_offene_frage_nimmt_antworten(self) -> None:
        dienst.pruefe_antwort_erlaubt("laeuft", "offen", "zahl", None, JETZT)

    @pytest.mark.parametrize("phase", ["bereit", "gesperrt", "aufgeloest"])
    def test_sonst_nicht(self, phase) -> None:
        with pytest.raises(dienst.AntwortNichtMoeglich):
            dienst.pruefe_antwort_erlaubt("laeuft", phase, "zahl", None, JETZT)

    def test_nach_der_frist_nicht_mehr(self) -> None:
        frist = JETZT - dt.timedelta(seconds=5)
        with pytest.raises(dienst.AntwortNichtMoeglich, match="Zeit"):
            dienst.pruefe_antwort_erlaubt("laeuft", "offen", "zahl", frist, JETZT)

    def test_kulanz_fuer_die_letzte_sekunde(self) -> None:
        """Wer bei 0 abschickt, kommt eine halbe Sekunde spaeter an."""
        frist = JETZT - dt.timedelta(milliseconds=800)
        dienst.pruefe_antwort_erlaubt("laeuft", "offen", "zahl", frist, JETZT)

    def test_buzzerfragen_nehmen_keine_antwort(self) -> None:
        with pytest.raises(dienst.AntwortNichtMoeglich, match="Buzzer"):
            dienst.pruefe_antwort_erlaubt("laeuft", "offen", "buzzer", None, JETZT)


# ------------------------------------------------------------- Antworten


class TestAntwortPruefen:
    def test_freitext(self) -> None:
        wert = dienst.pruefe_antwort(
            FreitextDaten(loesungen=["x"]), AntwortEingabe(text="  Paris ")
        )
        assert wert == {"text": "Paris"}

    def test_freitext_ohne_text(self) -> None:
        with pytest.raises(dienst.AntwortUngueltig):
            dienst.pruefe_antwort(FreitextDaten(loesungen=["x"]), AntwortEingabe(zahl=3))

    def test_zahl(self) -> None:
        assert dienst.pruefe_antwort(ZahlDaten(loesung=1), AntwortEingabe(zahl=16)) == {"zahl": 16}

    def test_schaetzung_im_bereich(self) -> None:
        daten = SchaetzDaten(minimum=0, maximum=10, loesung=3.7)
        assert dienst.pruefe_antwort(daten, AntwortEingabe(zahl=4)) == {"zahl": 4}
        with pytest.raises(dienst.AntwortUngueltig, match="zwischen"):
            dienst.pruefe_antwort(daten, AntwortEingabe(zahl=11))

    def test_auswahl_einzeln_nur_eine(self) -> None:
        daten = AuswahlDaten(optionen=[Option(text="a", richtig=True), Option(text="b")])
        assert dienst.pruefe_antwort(daten, AntwortEingabe(auswahl=[1])) == {"auswahl": [1]}
        with pytest.raises(dienst.AntwortUngueltig, match="eine"):
            dienst.pruefe_antwort(daten, AntwortEingabe(auswahl=[0, 1]))

    def test_auswahl_mehrfach_sortiert_und_ohne_doppelte(self) -> None:
        daten = AuswahlDaten(
            optionen=[
                Option(text="a", richtig=True),
                Option(text="b", richtig=True),
                Option(text="c"),
            ]
        )
        assert dienst.pruefe_antwort(daten, AntwortEingabe(auswahl=[2, 0, 2])) == {
            "auswahl": [0, 2]
        }

    def test_auswahl_unbekannte_option(self) -> None:
        daten = AuswahlDaten(optionen=[Option(text="a", richtig=True), Option(text="b")])
        with pytest.raises(dienst.AntwortUngueltig):
            dienst.pruefe_antwort(daten, AntwortEingabe(auswahl=[5]))

    def test_hotspot(self) -> None:
        daten = HotspotDaten(ziele=[Ziel(x=50, y=50)])
        assert dienst.pruefe_antwort(daten, AntwortEingabe(x=10, y=20)) == {"x": 10, "y": 20}
        with pytest.raises(dienst.AntwortUngueltig):
            dienst.pruefe_antwort(daten, AntwortEingabe(x=10))

    def test_sortieren_verlangt_jedes_element_genau_einmal(self) -> None:
        daten = SortierDaten(elemente=["a", "b", "c"])
        kennungen = [dienst.elementkennung(FRAGE_ID, i) for i in (2, 0, 1)]
        wert = dienst.pruefe_antwort(daten, AntwortEingabe(reihenfolge=kennungen), FRAGE_ID)
        assert wert == {"reihenfolge": kennungen}
        with pytest.raises(dienst.AntwortUngueltig):
            dienst.pruefe_antwort(
                daten, AntwortEingabe(reihenfolge=kennungen[:2] + kennungen[:1]), FRAGE_ID
            )

    def test_buzzer_hat_keine_antwort(self) -> None:
        with pytest.raises(dienst.AntwortUngueltig):
            dienst.pruefe_antwort(BuzzerDaten(), AntwortEingabe(text="x"))


class TestAnzeige:
    def test_jede_antwort_als_text(self) -> None:
        auswahl = AuswahlDaten(optionen=[Option(text="Rot", richtig=True), Option(text="Blau")])
        sortier = SortierDaten(elemente=["eins", "zwei"])
        reihen = [dienst.elementkennung(FRAGE_ID, 1), dienst.elementkennung(FRAGE_ID, 0)]

        assert (
            dienst.anzeige(FreitextDaten(loesungen=["x"]), {"text": "Paris"}, FRAGE_ID) == "Paris"
        )
        assert dienst.anzeige(ZahlDaten(loesung=1, einheit="m"), {"zahl": 2.5}, FRAGE_ID) == "2,5 m"
        assert dienst.anzeige(auswahl, {"auswahl": [0, 1]}, FRAGE_ID) == "Rot, Blau"
        assert dienst.anzeige(sortier, {"reihenfolge": reihen}, FRAGE_ID) == "zwei → eins"
        assert dienst.anzeige(
            HotspotDaten(ziele=[Ziel(x=1, y=1)]), {"x": 10, "y": 20}, FRAGE_ID
        ) == ("Klick bei 10 % / 20 %")


# ------------------------------------------------------------- Bewertung


class TestBewertung:
    def test_freitext_ohne_ruecksicht_auf_schreibweise(self) -> None:
        daten = FreitextDaten(loesungen=["Berlin"])
        ergebnis = dienst.bewerte(
            daten, 2, {"a": {"text": " berlin"}, "b": {"text": "Bonn"}}, FRAGE_ID
        )
        assert ergebnis == {"a": dienst.Bewertung(2, True), "b": dienst.Bewertung(0, False)}

    def test_bildfrage_ohne_loesung_bewertet_die_leitung(self) -> None:
        ergebnis = dienst.bewerte(BildDaten(), 2, {"a": {"text": "Turm"}}, FRAGE_ID)
        assert ergebnis == {"a": dienst.Bewertung(None, None)}

    def test_bildfrage_mit_loesung_wie_freitext(self) -> None:
        ergebnis = dienst.bewerte(
            BildDaten(loesungen=["Turm"]), 2, {"a": {"text": "turm"}}, FRAGE_ID
        )
        assert ergebnis["a"] == dienst.Bewertung(2, True)

    def test_zahl_mit_toleranz(self) -> None:
        daten = ZahlDaten(loesung=100, toleranz=5)
        ergebnis = dienst.bewerte(daten, 1, {"a": {"zahl": 104}, "b": {"zahl": 106}}, FRAGE_ID)
        assert ergebnis["a"].richtig and not ergebnis["b"].richtig

    def test_schaetzung_wer_am_naechsten_liegt_gewinnt(self) -> None:
        daten = SchaetzDaten(minimum=0, maximum=10, loesung=3.7)
        ergebnis = dienst.bewerte(
            daten, 2, {"a": {"zahl": 3}, "b": {"zahl": 4.4}, "c": {"zahl": 8}}, FRAGE_ID
        )
        assert ergebnis["a"] == dienst.Bewertung(2, True)
        assert ergebnis["b"] == dienst.Bewertung(2, True), "Gleich nah heisst beide gewinnen"
        assert ergebnis["c"] == dienst.Bewertung(0, False)

    def test_schaetzung_ohne_antworten(self) -> None:
        assert dienst.bewerte(SchaetzDaten(minimum=0, maximum=1, loesung=0), 2, {}, FRAGE_ID) == {}

    def test_auswahl_einzeln(self) -> None:
        daten = AuswahlDaten(optionen=[Option(text="a", richtig=True), Option(text="b")])
        ergebnis = dienst.bewerte(
            daten, 3, {"a": {"auswahl": [0]}, "b": {"auswahl": [1]}}, FRAGE_ID
        )
        assert ergebnis == {"a": dienst.Bewertung(3, True), "b": dienst.Bewertung(0, False)}

    def test_auswahl_mehrfach_richtig_minus_falsch(self) -> None:
        """+1 je richtige, -1 je falsche, nie unter null - auf die Punkte der
        Frage umgerechnet."""
        daten = AuswahlDaten(
            optionen=[
                Option(text="a", richtig=True),
                Option(text="b", richtig=True),
                Option(text="c"),
                Option(text="d"),
            ]
        )
        ergebnis = dienst.bewerte(
            daten,
            4,
            {
                "alles": {"auswahl": [0, 1]},
                "halb": {"auswahl": [0]},
                "gemischt": {"auswahl": [0, 2]},
                "falsch": {"auswahl": [2, 3]},
            },
            FRAGE_ID,
        )
        assert ergebnis["alles"] == dienst.Bewertung(4, True)
        assert ergebnis["halb"] == dienst.Bewertung(2, False)
        assert ergebnis["gemischt"] == dienst.Bewertung(0, False)
        assert ergebnis["falsch"] == dienst.Bewertung(0, False)

    def test_hotspot_im_kreis(self) -> None:
        daten = HotspotDaten(ziele=[Ziel(x=50, y=50, radius=10)])
        ergebnis = dienst.bewerte(
            daten, 1, {"a": {"x": 55, "y": 55}, "b": {"x": 70, "y": 50}}, FRAGE_ID
        )
        assert ergebnis["a"].richtig and not ergebnis["b"].richtig

    def test_sortieren_anteilig(self) -> None:
        daten = SortierDaten(elemente=["a", "b", "c", "d"])
        k = [dienst.elementkennung(FRAGE_ID, i) for i in range(4)]
        ergebnis = dienst.bewerte(
            daten,
            4,
            {"alles": {"reihenfolge": k}, "halb": {"reihenfolge": [k[0], k[1], k[3], k[2]]}},
            FRAGE_ID,
        )
        assert ergebnis["alles"] == dienst.Bewertung(4, True)
        assert ergebnis["halb"] == dienst.Bewertung(2, False)

    def test_buzzer_wird_nicht_automatisch_bewertet(self) -> None:
        assert dienst.bewerte(BuzzerDaten(), 3, {"a": {}}, FRAGE_ID) == {}


# ------------------------------------------------------------- Buzzer


class TestBuzzer:
    def test_wer_zuerst_drueckt_ist_dran(self) -> None:
        assert dienst.buzzer_dran([("a", "falsch"), ("b", "wartet"), ("c", "wartet")]) == "b"
        assert dienst.buzzer_dran([("a", "falsch")]) is None
        assert dienst.buzzer_dran([]) is None

    def test_buzzern_nur_bei_offener_buzzerfrage(self) -> None:
        dienst.pruefe_buzzer_erlaubt("laeuft", "offen", "buzzer", schon_gedrueckt=False)
        with pytest.raises(dienst.AntwortNichtMoeglich):
            dienst.pruefe_buzzer_erlaubt("laeuft", "offen", "zahl", schon_gedrueckt=False)
        with pytest.raises(dienst.AntwortNichtMoeglich):
            dienst.pruefe_buzzer_erlaubt("laeuft", "gesperrt", "buzzer", schon_gedrueckt=False)

    def test_jeder_nur_einmal(self) -> None:
        with pytest.raises(dienst.AntwortNichtMoeglich, match="schon"):
            dienst.pruefe_buzzer_erlaubt("laeuft", "offen", "buzzer", schon_gedrueckt=True)

    def test_urteil_braucht_jemanden_der_dran_ist(self) -> None:
        with pytest.raises(dienst.AktionNichtMoeglich):
            dienst.pruefe_buzzer_urteil("buzzer", "offen", None)
        with pytest.raises(dienst.AktionNichtMoeglich):
            dienst.pruefe_buzzer_urteil("zahl", "offen", "a")
        dienst.pruefe_buzzer_urteil("buzzer", "gesperrt", "a")


# ------------------------------------------------------------- Rangliste


class TestRangliste:
    def test_gleiche_punkte_teilen_sich_den_platz(self) -> None:
        plaetze = dienst.rangliste(
            [("a", "Zoe", 3), ("b", "anna", 5), ("c", "Ben", 3), ("d", "Dan", 1)]
        )
        assert [(p.name, p.rang) for p in plaetze] == [
            ("anna", 1),
            ("Ben", 2),
            ("Zoe", 2),
            ("Dan", 4),
        ]
        assert plaetze[0].schluessel == "b"


# ------------------------------------------------------------- Oeffentliche Sicht


class TestOeffentlicheFrage:
    def test_vor_dem_zeigen_nur_nummer_und_kategorie(self) -> None:
        sicht = dienst.oeffentliche_frage(_frage(ZahlDaten(loesung=16)), 2, 10, "bereit")
        assert sicht.nummer == 3 and sicht.anzahl == 10
        assert sicht.text is None
        assert sicht.loesung is None

    def test_offen_ohne_loesung(self) -> None:
        daten = AuswahlDaten(
            optionen=[
                Option(text="Rot", richtig=True),
                Option(text="Blau", richtig=True),
                Option(text="Grün"),
            ]
        )
        sicht = dienst.oeffentliche_frage(_frage(daten), 0, 1, "offen")
        assert sicht.text == "Wie heisst die Frage?"
        assert sicht.optionen == ["Rot", "Blau", "Grün"]
        assert sicht.mehrfach
        assert sicht.loesung is None
        assert "richtig" not in sicht.model_dump_json()

    def test_aufgeloest_mit_loesung(self) -> None:
        sicht = dienst.oeffentliche_frage(
            _frage(ZahlDaten(loesung=16, toleranz=1)), 0, 1, "aufgeloest"
        )
        assert sicht.loesung is not None
        assert sicht.loesung.zahl == 16
        assert sicht.loesung.anzeige == "16 (± 1)"

    def test_sortieren_gemischt_und_ohne_verraeterische_kennung(self) -> None:
        daten = SortierDaten(elemente=["a", "b", "c", "d", "e", "f"])
        sicht = dienst.oeffentliche_frage(_frage(daten), 0, 1, "offen")
        assert sorted(e.text for e in sicht.elemente) == ["a", "b", "c", "d", "e", "f"]
        assert [e.text for e in sicht.elemente] != ["a", "b", "c", "d", "e", "f"]
        assert all(not e.kennung.isdigit() for e in sicht.elemente)
        # Jedes Mal dieselbe Mischung, sonst springt die Liste beim Neuladen.
        assert dienst.oeffentliche_frage(_frage(daten), 0, 1, "offen").elemente == sicht.elemente

    def test_schaetzung_zeigt_den_bereich(self) -> None:
        daten = SchaetzDaten(minimum=0, maximum=10, schritt=0.5, loesung=3, einheit="Mio")
        sicht = dienst.oeffentliche_frage(_frage(daten), 0, 1, "offen")
        assert (sicht.minimum, sicht.maximum, sicht.schritt, sicht.einheit) == (0, 10, 0.5, "Mio")

    def test_loesung_jedes_typs_lesbar(self) -> None:
        assert dienst.loesung(FreitextDaten(loesungen=["Berlin", "berlin"]), FRAGE_ID).anzeige == (
            "Berlin / berlin"
        )
        assert dienst.loesung(BuzzerDaten(loesung="Zugspitze"), FRAGE_ID).anzeige == "Zugspitze"
        assert dienst.loesung(BildDaten(), FRAGE_ID).anzeige == "Bewertet die Spielleitung"
        assert dienst.loesung(
            AuswahlDaten(optionen=[Option(text="a"), Option(text="b", richtig=True)]), FRAGE_ID
        ).optionen == [1]
        assert dienst.loesung(SortierDaten(elemente=["x", "y"]), FRAGE_ID).anzeige == "x → y"
        assert dienst.loesung(HotspotDaten(ziele=[Ziel(x=1, y=2)]), FRAGE_ID).ziele
        assert dienst.loesung(
            SchaetzDaten(minimum=0, maximum=9, loesung=3.5, einheit="kg"), FRAGE_ID
        ).anzeige == ("3,5 kg")


# ------------------------------------------------------------- Bilder und Kataloge


class TestBild:
    def test_bild_umschalten_nur_wenn_eines_da_ist(self) -> None:
        dienst.pruefe_bild_vorhanden(True)
        with pytest.raises(dienst.AktionNichtMoeglich):
            dienst.pruefe_bild_vorhanden(False)

    def test_spieler_sehen_das_bild_erst_mit_der_frage(self) -> None:
        assert dienst.bild_oeffentlich("offen", True)
        assert dienst.bild_oeffentlich("aufgeloest", True)
        assert not dienst.bild_oeffentlich("offen", False)
        assert not dienst.bild_oeffentlich("bereit", True), (
            "Vor dem Zeigen verraet das Bild die Frage"
        )

    def test_gaengige_formate(self) -> None:
        assert dienst.pruefe_bild("image/png", 1000) == "image/png"
        assert dienst.pruefe_bild("image/jpeg; charset=binary", 1000) == "image/jpeg"

    def test_kein_svg(self) -> None:
        """SVG kann Skript enthalten - ein Bild aus einem Quizkatalog soll die
        Seite nicht uebernehmen koennen."""
        with pytest.raises(dienst.BildUngueltig):
            dienst.pruefe_bild("image/svg+xml", 1000)

    def test_zu_gross_oder_leer(self) -> None:
        with pytest.raises(dienst.BildUngueltig, match="MB"):
            dienst.pruefe_bild("image/png", dienst.MAX_BILD_BYTES + 1)
        with pytest.raises(dienst.BildUngueltig):
            dienst.pruefe_bild("image/png", 0)


class TestKatalog:
    def test_reihenfolge_muss_alle_fragen_nennen(self) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        dienst.pruefe_reihenfolge([a, b], [b, a])
        with pytest.raises(dienst.ReihenfolgeUngueltig):
            dienst.pruefe_reihenfolge([a, b], [a])
        with pytest.raises(dienst.ReihenfolgeUngueltig):
            dienst.pruefe_reihenfolge([a, b], [a, a])

    def test_katalog_mit_laufender_runde_bleibt(self) -> None:
        dienst.pruefe_katalog_loeschbar(0)
        with pytest.raises(dienst.KatalogInBenutzung):
            dienst.pruefe_katalog_loeschbar(1)

    def test_runde_braucht_fragen(self) -> None:
        with pytest.raises(dienst.KatalogLeer):
            dienst.pruefe_katalog_spielbar(0)
        dienst.pruefe_katalog_spielbar(3)
