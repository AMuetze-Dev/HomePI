"""Welche Mannschaft eines Vereins ein Name meint.

Daran hängt die Wartefrist nach § 68 (2) a): ohne diese Rückfallebene prüft
sie gar nicht mehr, sobald in der Staffel keine höheren Mannschaften
hinterlegt sind — die Regel liefe durch und fände nichts.

Übernommen mitsamt dem Fehler, der hier einmal steckte: eine nummerierte
Mannschaft gegen eine unnummerierte verglichen warf
`'<' not supported between 'int' and 'NoneType'`, die Regel brach ab, und
jedes betroffene Spiel bekam einen kritischen `rule_error`.
"""

from __future__ import annotations

import pytest

from homepi_pruefdienst.regelwerk.mannschaftsnamen import (
    club_name_and_suffix,
    is_higher_class,
    is_same_club,
)


class TestName:
    @pytest.mark.parametrize(
        ("name", "verein", "nummer"),
        [
            ("SV Loschwitz", "SV Loschwitz", None),
            ("SV Loschwitz 2", "SV Loschwitz", 2),
            ("1. FC Pirna 2.", "1. FC Pirna", 2),
            ("SV Loschwitz II", "SV Loschwitz", 2),
            ("", "", None),
        ],
    )
    def test_verein_und_nummer(self, name: str, verein: str, nummer: int | None) -> None:
        assert club_name_and_suffix(name) == (verein, nummer)

    def test_eine_jahreszahl_ist_keine_mannschaftsnummer(self) -> None:
        """„Dresdner SC 1898" hat keine 1898 Mannschaften."""
        assert club_name_and_suffix("Dresdner SC 1898") == ("Dresdner SC 1898", None)

    def test_derselbe_verein(self) -> None:
        assert is_same_club("SV Loschwitz", "SV Loschwitz 2") is True
        assert is_same_club("SV Loschwitz", "SV Blasewitz") is False


class TestHoeherklassig:
    def test_die_erste_steht_ueber_der_zweiten(self) -> None:
        assert is_higher_class("SV Loschwitz", "SV Loschwitz 2") is True

    def test_und_die_zweite_nicht_ueber_der_ersten(self) -> None:
        """Der Fall, der einmal geworfen hat."""
        assert is_higher_class("SV Loschwitz 2", "SV Loschwitz") is False

    def test_zwei_gegen_drei(self) -> None:
        assert is_higher_class("SV Loschwitz 2", "SV Loschwitz 3") is True
        assert is_higher_class("SV Loschwitz 3", "SV Loschwitz 2") is False

    def test_eine_erste_ist_nicht_hoeher_als_sie_selbst(self) -> None:
        assert is_higher_class("SV Loschwitz", "SV Loschwitz") is False

    def test_ein_anderer_verein_zaehlt_nie(self) -> None:
        assert is_higher_class("SV Blasewitz", "SV Loschwitz 2") is False

    def test_das_vereinswappen_entscheidet_wenn_es_da_ist(self) -> None:
        """Zwei Schreibweisen desselben Vereins sind aus den Namen nicht zu
        erkennen — die Kennung des Wappens schon."""
        assert (
            is_higher_class(
                "SV Loschwitz",
                "SV Loschwitz e.V. 2",
                team_logo_id="4711",
                current_logo_id="4711",
            )
            is True
        )

    def test_und_verschiedene_wappen_schliessen_es_aus(self) -> None:
        assert (
            is_higher_class(
                "SV Loschwitz",
                "SV Loschwitz 2",
                team_logo_id="4711",
                current_logo_id="0815",
            )
            is False
        )

    def test_die_eigene_nummer_darf_gesagt_werden(self) -> None:
        """„SV Loschwitz" ist mal die Erste und mal eine Staffel, in der die
        Zweite ohne Zusatz geführt wird."""
        assert is_higher_class("SV Loschwitz", "SV Loschwitz", current_team_suffix=2) is True
