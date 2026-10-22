"""Vorschläge für die höherklassigen Mannschaften.

Welche Mannschaft eines Vereins über welcher steht, liefert DFBnet nicht mit.
Ein falscher Schluss fällt nicht laut auf: er ändert still, wessen Einsätze
nach § 68 als Stammspieler zählen — und dann prüft eine Regel leise das
Falsche.

Deshalb heißt es hier **Vorschlag** und nicht Zuordnung. Gespeichert wird nur,
was jemand angeklickt hat.
"""

from __future__ import annotations

import pytest

from homepi_staffelpilot import dienst


class TestMitNummer:
    def test_die_dritte_hat_zwei_ueber_sich(self) -> None:
        """Der Fall, der im Alltag zählt."""
        assert dienst.hoehere_vorschlaege("Dresdner SC 1898 3") == [
            "Dresdner SC 1898 2",
            "Dresdner SC 1898",
        ]

    def test_die_erste_traegt_keine_nummer(self) -> None:
        """Schreibweise des Verbandes, nicht unsere Annahme: über der Zweiten
        steht „Dresdner SC 1898" und nicht „Dresdner SC 1898 1"."""
        assert dienst.hoehere_vorschlaege("SV Loschwitz 2") == ["SV Loschwitz"]

    def test_die_vierte_bekommt_drei(self) -> None:
        assert dienst.hoehere_vorschlaege("Post SV Dresden 4") == [
            "Post SV Dresden 3",
            "Post SV Dresden 2",
            "Post SV Dresden",
        ]

    def test_die_naechsthoehere_steht_vorn(self) -> None:
        """Absteigend: wer eine aussucht, nimmt meistens die direkt darüber."""
        assert dienst.hoehere_vorschlaege("Post SV Dresden 4")[0] == "Post SV Dresden 3"


class TestOhneVorschlag:
    def test_ueber_der_ersten_steht_nichts(self) -> None:
        assert dienst.hoehere_vorschlaege("SG Gittersee") == []

    def test_eine_jahreszahl_ist_keine_mannschaftsnummer(self) -> None:
        """„Dresdner SC 1898" ist die Erste und nicht die 1898. Ohne diese
        Grenze stünden hier tausendachthundertsiebenundneunzig Vorschläge."""
        assert dienst.hoehere_vorschlaege("Dresdner SC 1898") == []

    def test_eine_spielgemeinschaft_bekommt_keinen(self) -> None:
        """Der entscheidende Fall.

        „SpG Kickers 2 / Hafen 2" gehört zwei Vereinen; darüber stehen
        „FV Löbtauer Kickers" und „FV Hafen Dresden" — keiner der beiden Namen
        steckt im Namen der SG. Ein Vorschlag wäre hier geraten, und ein
        falscher ändert still, wessen Einsätze zählen. Dafür gibt es das
        Textfeld.
        """
        assert dienst.hoehere_vorschlaege("SpG Kickers 2 / Hafen 2", ist_sg=True) == []

    def test_auch_eine_sg_mit_sauberer_nummer_nicht(self) -> None:
        assert dienst.hoehere_vorschlaege("SpG Dresdner SSV / ESV Dresden 2", ist_sg=True) == []

    @pytest.mark.parametrize("name", ["", "   ", "2", " 3"])
    def test_aus_nichts_kommt_nichts(self, name: str) -> None:
        assert dienst.hoehere_vorschlaege(name) == []


def test_die_vorschlaege_sind_keine_zuordnung() -> None:
    """Eine reine Funktion ohne Nebenwirkung: sie schlägt vor, sie speichert
    nicht. Was gilt, steht an der Mannschaft und wird dort bestätigt."""
    name = "Dresdner SC 1898 3"

    zweimal = [dienst.hoehere_vorschlaege(name) for _ in range(2)]

    assert zweimal[0] == zweimal[1]
