"""Die Entscheidungen des Prüfdienstes — ohne Browser, in Millisekunden.

Das Zerlegen einer Tabellenzeile ist die Stelle, die erfahrungsgemäß
kaputtgeht, wenn DFBnet eine Spalte verschiebt. Genau deshalb steht sie hier
und nicht in `dfbnet.py`.
"""

from __future__ import annotations

import datetime as dt

import pytest

from homepi_pruefdienst import dienst

# So sieht die heutige Trefferzeile aus:
# [Spiel, Anstoß, ST, Heim, "-", Gast, Ergebnis, Status]
HEUTE = [
    "011234",
    "13.09.2026 15:00",
    "3",
    "SG Gittersee",
    "-",
    "SV Fortschritt",
    "2 : 1",
    "freigegeben",
]

# Und so sah sie einmal aus: das Ergebnis zwischen den Mannschaften.
FRUEHER = ["011234", "13.09.26", "SG Gittersee", "2:1", "SV Fortschritt", ""]


class TestDatum:
    def test_vierstelliges_jahr(self) -> None:
        assert dienst.datum_lesen("13.09.2026 15:00") == dt.date(2026, 9, 13)

    def test_zweistelliges_jahr_liegt_im_jahrhundert(self) -> None:
        """Ein Bericht von 1926 waere ein Datumsfehler, den niemand bemerkt."""
        assert dienst.datum_lesen("13.09.26") == dt.date(2026, 9, 13)

    def test_ohne_datum_kommt_nichts(self) -> None:
        assert dienst.datum_lesen("Spielbericht") is None
        assert dienst.datum_lesen("") is None

    def test_einen_31_februar_gibt_es_nur_im_tabellenkopf(self) -> None:
        assert dienst.datum_lesen("31.02.2026") is None


class TestZeileZerlegen:
    def test_die_heutige_anordnung(self) -> None:
        zeile = dienst.zeile_zerlegen(HEUTE, "abc")

        assert zeile.dfbnet_id == "abc"
        assert zeile.datum == dt.date(2026, 9, 13)
        assert zeile.heim == "SG Gittersee"
        assert zeile.gast == "SV Fortschritt"
        assert zeile.ergebnis == "2 : 1"

    def test_die_frühere_anordnung(self) -> None:
        """Nicht auf Positionen gezaehlt, sondern gesucht - deshalb faellt
        eine verschobene Spalte nicht auf."""
        zeile = dienst.zeile_zerlegen(FRUEHER, "abc")

        assert zeile.heim == "SG Gittersee"
        assert zeile.gast == "SV Fortschritt"

    def test_ein_ergebnis_ohne_leerzeichen_wird_vereinheitlicht(self) -> None:
        assert dienst.zeile_zerlegen(FRUEHER, "abc").ergebnis == "2 : 1"

    def test_ein_spiel_ohne_ergebnis_behaelt_seine_paarung(self) -> None:
        zeilen = ["011234", "13.09.2026", "SG Gittersee", "-", "SV Fortschritt", "offen"]

        zeile = dienst.zeile_zerlegen(zeilen, "abc")

        assert zeile.heim == "SG Gittersee"
        assert zeile.gast == "SV Fortschritt"
        assert zeile.ergebnis == ""
        assert zeile.brauchbar

    def test_trennzeichen_sind_keine_mannschaft(self) -> None:
        zeile = dienst.zeile_zerlegen(HEUTE, "abc")

        assert zeile.heim != "-"
        assert zeile.gast != "-"

    def test_leerzeichen_werden_abgeschnitten(self) -> None:
        zeile = dienst.zeile_zerlegen(["  13.09.2026  ", " SG A ", "1 : 0", " SV B "], "x")

        assert zeile.heim == "SG A"
        assert zeile.gast == "SV B"

    def test_eine_zeile_ohne_datum_ist_unbrauchbar(self) -> None:
        """Lieber ueberspringen als einen Bericht mit leeren Feldern anlegen -
        der stuende in der Warteschlange und niemand wuesste, wozu er
        gehoert."""
        assert not dienst.zeile_zerlegen(["Summe", "", ""], "x").brauchbar

    def test_eine_zeile_ohne_paarung_auch(self) -> None:
        assert not dienst.zeile_zerlegen(["13.09.2026", "", ""], "x").brauchbar

    def test_eine_leere_zeile_faellt_nicht_um(self) -> None:
        zeile = dienst.zeile_zerlegen([], "x")

        assert not zeile.brauchbar
        assert zeile.status == ""


class TestKennung:
    def test_aus_dem_link(self) -> None:
        """Sie ist der Schluessel, unter dem das Artefakt den Bericht
        wiederfindet - ein zweiter Prueflauf darf ihn nicht verdoppeln."""
        href = "/spielplus/match-report/report/0112345678?von=liste"

        assert dienst.kennung_aus_href(href) == "0112345678"

    def test_ohne_muster_bleibt_der_link_stehen(self) -> None:
        assert dienst.kennung_aus_href("/woanders") == "/woanders"

    def test_ein_leerer_link_gibt_leer(self) -> None:
        assert dienst.kennung_aus_href("") == ""


class TestStaffelkennung:
    """Was DFBnet braucht, um genau diese Staffel zu zeigen."""

    def test_die_spielklasse_kommt_zuerst(self) -> None:
        """Sie ist die Schreibweise von DFBnet -- "Stadtliga C" steht dort
        nicht."""
        k = dienst.Staffelkennung(name="Stadtliga C", spielklasse="3.Kreisliga (C)")

        assert k.kandidaten == ["3.Kreisliga (C)", "Stadtliga C"]

    def test_ohne_spielklasse_bleibt_der_name(self) -> None:
        assert dienst.Staffelkennung(name="Stadtliga C").kandidaten == ["Stadtliga C"]

    def test_derselbe_text_steht_nur_einmal_da(self) -> None:
        k = dienst.Staffelkennung(name="1.Kreisklasse", spielklasse=" 1.Kreisklasse ")

        assert k.kandidaten == ["1.Kreisklasse"]

    def test_ohne_alles_gibt_es_nichts_zu_versuchen(self) -> None:
        """Und der Leser sucht dann nicht -- eine Suche ohne Filter liefert
        alles, was das Konto sieht."""
        assert dienst.Staffelkennung(name="  ").kandidaten == []

    def test_aus_der_staffel_des_artefakts(self) -> None:
        k = dienst.kennung_aus(
            {
                "id": "s1",
                "name": "Stadtliga C",
                "spielklasse": "3.Kreisliga (C)",
                "altersklasse": "maenner",
                "saison": "26/27",
                "aktiv": True,
            }
        )

        assert (k.name, k.spielklasse, k.altersklasse, k.saison) == (
            "Stadtliga C",
            "3.Kreisliga (C)",
            "maenner",
            "26/27",
        )

    def test_fehlende_felder_werden_leer_und_nicht_none(self) -> None:
        k = dienst.kennung_aus({"name": "Stadtliga C"})

        assert k.spielklasse == ""
        assert k.altersklasse == ""
        assert k.saison == ""


class TestBerichtsadresse:
    def test_die_kennung_wird_eingesetzt(self) -> None:
        adresse = dienst.bericht_adresse("633203177")

        assert "match-report/report/633203177" in adresse
        assert adresse.startswith("https://www.dfbnet.org/")


class TestZeitraum:
    def test_bis_heute_und_nicht_weiter(self) -> None:
        """Ein Spiel in der Zukunft ist nicht gespielt, und ein Befund darauf
        waere eine Erfindung."""
        heute = dt.date(2026, 9, 19)

        von, bis = dienst.zeitraum(heute, 30)

        assert bis == heute
        assert von == dt.date(2026, 8, 20)

    def test_null_tage_werden_zu_einem(self) -> None:
        """Ein Zeitraum von null Tagen liefert stumm nichts."""
        von, bis = dienst.zeitraum(dt.date(2026, 9, 19), 0)

        assert (bis - von).days == 1

    def test_deutsches_datum_fuer_das_formular(self) -> None:
        assert dienst.als_dfbnet_datum(dt.date(2026, 9, 3)) == "03.09.2026"


class TestFortschritt:
    @pytest.mark.parametrize(
        ("erledigt", "gesamt", "erwartet"),
        [(0, 4, 0), (1, 4, 25), (2, 4, 50), (4, 4, 99)],
    )
    def test_in_prozent(self, erledigt: int, gesamt: int, erwartet: int) -> None:
        assert dienst.fortschritt(erledigt, gesamt) == erwartet

    def test_nie_hundert(self) -> None:
        """Die Hundert setzt der Abschluss. Ein Balken, der voll ist und
        trotzdem weiterlaeuft, ist die Anzeige, der man nicht mehr glaubt."""
        assert dienst.fortschritt(99, 1) == 99

    def test_ohne_gesamtzahl_bleibt_es_bei_null(self) -> None:
        assert dienst.fortschritt(3, 0) == 0


class TestWartezeit:
    def test_mit_arbeit_bleibt_der_grundtakt(self) -> None:
        assert dienst.wartezeit(0) == 2.0

    def test_ohne_arbeit_wird_der_abstand_groesser(self) -> None:
        assert dienst.wartezeit(1) > dienst.wartezeit(0)
        assert dienst.wartezeit(3) > dienst.wartezeit(1)

    def test_aber_nicht_beliebig(self) -> None:
        """Ein Dienst, der im Sekundentakt fragt, haelt den Pi wach - einer,
        der stundenlang schweigt, reagiert nicht mehr."""
        assert dienst.wartezeit(99) == dienst.LEERLAUF_GRENZE_S


class TestErlaubnis:
    def test_beide_schalter_muessen_an_sein(self) -> None:
        assert dienst.Erlaubnis(pausiert=False, darf_schreiben=True).uebertraegt

    @pytest.mark.parametrize(
        ("pausiert", "darf"),
        [(True, True), (False, False), (True, False)],
    )
    def test_sonst_geht_nichts_hinaus(self, pausiert: bool, darf: bool) -> None:
        erlaubnis = dienst.Erlaubnis(pausiert=pausiert, darf_schreiben=darf)

        assert not erlaubnis.uebertraegt
        assert erlaubnis.grund

    def test_der_eigene_schalter_wird_zuerst_genannt(self) -> None:
        """Wer den Dienst gerade aufgesetzt hat, sucht sonst im Artefakt."""
        erlaubnis = dienst.Erlaubnis(pausiert=True, darf_schreiben=False)

        assert "PRUEFDIENST_DARF_SCHREIBEN" in erlaubnis.grund

    def test_wenn_es_laeuft_gibt_es_keinen_grund(self) -> None:
        assert dienst.Erlaubnis(pausiert=False, darf_schreiben=True).grund == ""


class TestAusbeute:
    def test_brauchbare_zeilen_werden_zu_spielen(self) -> None:
        ausbeute = dienst.Ausbeute()

        ausbeute.aufnehmen(dienst.zeile_zerlegen(HEUTE, "abc"))

        assert ausbeute.spiele == [
            {
                "dfbnet_id": "abc",
                "datum": "2026-09-13",
                "heim": "SG Gittersee",
                "gast": "SV Fortschritt",
                "ergebnis": "2 : 1",
                "befunde": [],
            }
        ]

    def test_unbrauchbare_werden_gezaehlt_und_nicht_verschwiegen(self) -> None:
        ausbeute = dienst.Ausbeute()

        ausbeute.aufnehmen(dienst.zeile_zerlegen(["Summe"], "x"))

        assert ausbeute.spiele == []
        assert ausbeute.uebersprungen == 1

    def test_befunde_bleiben_leer_und_das_ist_die_aussage(self) -> None:
        """Die Regelpruefung ist nicht portiert. Ein leeres Feld heisst: der
        Bericht ist da, geprueft ist er nicht."""
        ausbeute = dienst.Ausbeute()

        ausbeute.aufnehmen(dienst.zeile_zerlegen(HEUTE, "abc"))

        assert ausbeute.spiele[0]["befunde"] == []
