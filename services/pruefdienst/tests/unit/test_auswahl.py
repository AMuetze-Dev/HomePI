"""Matching a configured league name against the options DFBnet offers.

Two Ü35 staffeln were silently skipped in every check run: the config carried
"1. Stadtklasse Ü35" while the Spielklasse dropdown only offers
"1. Stadtklasse" — the age band lives in the Mannschaftsart dropdown. The
substring match ran the wrong way round and found nothing.
"""

import pytest

from homepi_pruefdienst.auswahl import (
    best_option,
    expand_candidates,
    normalise,
    without_age_band,
)

SPIELKLASSEN = [
    "1. Stadtklasse",
    "2. Stadtklasse",
    "11. Stadtklasse",
    "3.Kreisliga (C)",
    "Kreisoberliga",
]


class TestNormalisierung:
    @pytest.mark.parametrize(
        "a,b",
        [
            ("3.Kreisliga (C)", "3. Kreisliga (C)"),
            ("1. Stadtklasse", "1.Stadtklasse"),
            ("Kreisoberliga", "KREISOBERLIGA"),
            ("Straße", "Strasse"),
        ],
    )
    def test_harmless_differences_disappear(self, a, b):
        assert normalise(a) == normalise(b)

    def test_different_names_stay_different(self):
        assert normalise("1. Stadtklasse") != normalise("11. Stadtklasse")


class TestAltersband:
    @pytest.mark.parametrize(
        "eingabe,erwartet",
        [
            ("1. Stadtklasse Ü35", "1. Stadtklasse"),
            ("Ü35 1. Stadtklasse", "1. Stadtklasse"),
            ("Stadtklasse Ü40", "Stadtklasse"),
            ("3.Kreisliga (C)", "3.Kreisliga (C)"),
        ],
    )
    def test_the_band_is_stripped(self, eingabe, erwartet):
        assert without_age_band(eingabe) == erwartet

    def test_both_forms_are_offered_in_order(self):
        assert expand_candidates(["1. Stadtklasse Ü35"]) == [
            "1. Stadtklasse Ü35",
            "1. Stadtklasse",
        ]

    def test_duplicates_are_dropped(self):
        assert expand_candidates(["Kreisoberliga", "Kreisoberliga"]) == ["Kreisoberliga"]


class TestAuswahl:
    def test_the_reported_case_now_matches(self):
        """The regression: this returned None and the staffel was skipped."""
        kandidaten = expand_candidates(["1. Stadtklasse Ü35", "Ü35 1. Stadtklasse"])
        assert best_option(SPIELKLASSEN, kandidaten) == "1. Stadtklasse"

    def test_the_second_ue35_staffel_too(self):
        kandidaten = expand_candidates(["2. Stadtklasse Ü35", "Ü35 2. Stadtklasse"])
        assert best_option(SPIELKLASSEN, kandidaten) == "2. Stadtklasse"

    def test_the_working_staffel_keeps_working(self):
        kandidaten = expand_candidates(["3.Kreisliga (C)", "Stadtliga C"])
        assert best_option(SPIELKLASSEN, kandidaten) == "3.Kreisliga (C)"

    def test_a_spacing_difference_is_tolerated(self):
        assert best_option(SPIELKLASSEN, ["3. Kreisliga (C)"]) == "3.Kreisliga (C)"

    def test_a_shorter_option_never_wins_ambiguously(self):
        """ "1. Stadtklasse" must not be reachable from "Stadtklasse" alone."""
        assert best_option(SPIELKLASSEN, ["Stadtklasse"]) is None

    def test_an_unknown_name_matches_nothing(self):
        assert best_option(SPIELKLASSEN, ["Bezirksliga"]) is None

    def test_no_options_matches_nothing(self):
        assert best_option([], ["1. Stadtklasse"]) is None

    def test_exact_mode_stops_at_the_first_pass(self):
        """Mannschaftsart: "Herren" must not swallow "Herren Ü35"."""
        optionen = ["Herren", "Herren Ü35", "Frauen"]
        assert best_option(optionen, ["Herren Ü35"], exact=True) == "Herren Ü35"
        assert best_option(optionen, ["Herren"], exact=True) == "Herren"
        assert best_option(optionen, ["Senioren"], exact=True) is None

    def test_exact_mode_does_not_strip_the_band(self):
        """Stripping in exact mode would turn "Herren Ü35" into "Herren"."""
        optionen = ["Herren", "Herren Ü35"]
        kandidaten = expand_candidates(["Herren Ü35"])
        assert best_option(optionen, kandidaten, exact=True) == "Herren Ü35"


class TestDerLeserVergleichtNichtSelbst:
    """Der Browser waehlt aus, verglichen wird in `auswahl.py`.

    Uebernommen aus der alten Anwendung, wo dieselbe Zusicherung am Navigator
    hing. Ein zweiter Vergleich im Browserteil waere einer, den niemand ohne
    Browser pruefen kann -- und genau dort sassen die zwei uebersprungenen
    Staffeln.
    """

    def quelle(self) -> str:
        import inspect

        from homepi_pruefdienst import dfbnet

        return inspect.getsource(dfbnet)

    def test_der_leser_fragt_den_vergleicher(self):
        quelle = self.quelle()

        assert "auswahl.best_option" in quelle
        assert "auswahl.expand_candidates" in quelle

    def test_er_vergleicht_nicht_selbst(self):
        """Kein `in`-Vergleich auf Optionstexten im Browserteil."""
        quelle = self.quelle()

        assert "text.lower() in " not in quelle
        assert ".lower() in option" not in quelle

    def test_ein_fehlschlag_nennt_die_angebotenen_optionen(self):
        """Die alte Meldung sagte nur, dass nichts passte."""
        quelle = self.quelle()

        assert "Angeboten" in quelle

    def test_ohne_treffer_wird_nicht_gesucht(self):
        """Eine Suche ohne Filter liefert alles, was das Konto sieht -- und das
        landete dann als Spiele dieser Staffel im Artefakt."""
        quelle = self.quelle()

        assert "StaffelNichtGefunden" in quelle


class TestRandfaelle:
    """Was passiert, wenn nichts oder zu vieles passt.

    Jede dieser Zusicherungen verhindert dasselbe: dass ein Lauf still die
    falsche Liga liest.
    """

    def test_leerer_text_wird_zu_nichts(self):
        assert normalise("") == ""
        assert without_age_band("") == ""

    def test_ein_leerer_kandidat_trifft_nichts(self):
        assert best_option(["1. Stadtklasse"], [""]) is None
        assert best_option(["1. Stadtklasse"], []) is None

    def test_ohne_treffer_kommt_none(self):
        assert best_option(["1. Stadtklasse", "2. Stadtklasse"], ["Bezirksliga"]) is None

    def test_mehrdeutig_ist_kein_treffer(self):
        """ "Stadtklasse" sitzt in dreien -- die erste von drei zu nehmen ist,
        wie ein Prueflauf in der falschen Liga endet."""
        optionen = ["1. Stadtklasse", "2. Stadtklasse", "11. Stadtklasse"]

        assert best_option(optionen, ["Stadtklasse"]) is None

    def test_ein_platzhalter_gewinnt_nie(self):
        """ "Keine Auswahl" zu klicken loescht den Filter, und die Suche
        liefert dann jeden Wettbewerb."""
        assert best_option(["Keine Auswahl"], ["Keine Auswahl"]) is None

    def test_genau_hoert_nach_dem_ersten_durchgang_auf(self):
        """Damit "Herren" nicht "Herren Ue35" verschluckt."""
        assert best_option(["Herren \u00dc35"], ["Herren"], exact=True) is None
        assert best_option(["Herren \u00dc35"], ["Herren"]) == "Herren \u00dc35"

    def test_eine_option_im_kandidaten_zaehlt_nur_wenn_sie_eindeutig_ist(self):
        """ "1. Stadtklasse" steckt in "1. Stadtklasse \u00dc35" -- aber nur, wenn
        nicht zwei Optionen darin stecken."""
        assert best_option(["1. Stadtklasse"], ["1. Stadtklasse \u00dc35"]) == "1. Stadtklasse"

    def test_doppelte_kandidaten_werden_nicht_doppelt_versucht(self):
        assert expand_candidates(["A", "A", "", "  "]) == ["A"]


class TestMannschaftsart:
    def test_jede_altersklasse_hat_ihre_texte(self):
        from homepi_pruefdienst.auswahl import mannschaftsart_kandidaten

        assert mannschaftsart_kandidaten("maenner") == ["Herren"]
        assert mannschaftsart_kandidaten("UE35")[0] == "Herren \u00dc35"

    def test_eine_unbekannte_altersklasse_gibt_nichts(self):
        """Und dann bleibt das Feld stehen, statt auf gut Glueck etwas zu
        waehlen."""
        from homepi_pruefdienst.auswahl import mannschaftsart_kandidaten

        assert mannschaftsart_kandidaten("ue99") == []
        assert mannschaftsart_kandidaten("") == []
