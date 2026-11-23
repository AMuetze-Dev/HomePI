"""Welcher Befund von gestern ist welcher von heute?

Daran haengt, ob ein Schreiben den naechsten Prueflauf uebersteht: der Vorgang
haengt am Befund, und ein ersetzter Befund nimmt ihn mit.
"""

from __future__ import annotations

from homepi_staffelpilot.dienst import Abgleich, BefundSpur, abgleichen


def spur(
    text: str = "Feldverweis in Minute 71.",
    *,
    regel: str = "rote_karte",
    person: str = "Max Müller",
    mannschaft: str = "SG Gittersee",
    mit_vorgang: bool = False,
) -> BefundSpur:
    return BefundSpur(
        regel=regel, person=person, mannschaft=mannschaft, text=text, mit_vorgang=mit_vorgang
    )


class TestWiedererkennen:
    def test_an_regel_und_person_auch_mit_neuem_wortlaut(self) -> None:
        assert abgleichen([spur("in Minute 71")], [spur("in Minute 72")]).weiter == [0]

    def test_ein_erster_lauf_kennt_nichts(self) -> None:
        assert abgleichen([], [spur()]) == Abgleich(weiter=[None], bleiben=[], gehen=[])

    def test_eine_andere_regel_ist_ein_anderer_befund(self) -> None:
        assert abgleichen([spur(regel="a")], [spur(regel="b")]).weiter == [None]

    def test_eine_andere_person_ist_ein_anderer_befund(self) -> None:
        assert abgleichen([spur(person="Max")], [spur(person="Jan")]).weiter == [None]

    def test_die_andere_mannschaft_ist_ein_anderer_befund(self) -> None:
        """Eine verspaetete Bestaetigung nennt keine Person. Ohne die Mannschaft
        bekaeme der Gast das Schreiben, das an den Heimverein ging."""
        heim = spur(person="", mannschaft="SG Gittersee", mit_vorgang=True)
        gast = spur(person="", mannschaft="SV Fortschritt")

        assert abgleichen([heim], [gast]) == Abgleich(weiter=[None], bleiben=[0], gehen=[])


class TestZweiMitGleicherRegelUndPerson:
    def test_der_text_entscheidet_und_nicht_die_reihenfolge(self) -> None:
        eins, zwei = spur("Minute 12"), spur("Minute 80")

        assert abgleichen([eins, zwei], [zwei, eins]).weiter == [1, 0]

    def test_faellt_der_erste_weg_bleibt_der_zweite_der_zweite(self) -> None:
        ergebnis = abgleichen([spur("Minute 12"), spur("Minute 80")], [spur("Minute 80")])

        assert ergebnis == Abgleich(weiter=[1], bleiben=[], gehen=[0])

    def test_wortgleiche_werden_der_reihe_nach_vergeben(self) -> None:
        assert abgleichen([spur(), spur()], [spur(), spur()]).weiter == [0, 1]

    def test_aendert_sich_jeder_wortlaut_gilt_die_reihenfolge(self) -> None:
        """Die Regel formuliert neu, die Verstoesse sind dieselben."""
        alte = [spur("Minute 12"), spur("Minute 80")]
        neue = [spur("12. Spielminute"), spur("80. Spielminute")]

        assert abgleichen(alte, neue).weiter == [0, 1]

    def test_wer_neben_einem_wortgleichen_uebrig_bleibt_ist_ein_neuer(self) -> None:
        """Die Regel formuliert wie bisher. Ein anderer Text ist dann ein anderer
        Verstoss, und das Schreiben zum frueheren gehoert nicht dazu."""
        alte = [spur("Minute 12", mit_vorgang=True), spur("Minute 80")]
        neue = [spur("Minute 80"), spur("Minute 88")]

        assert abgleichen(alte, neue) == Abgleich(weiter=[1, None], bleiben=[0], gehen=[])

    def test_bei_ungleicher_anzahl_wird_nicht_geraten(self) -> None:
        alte = [spur("Minute 12", mit_vorgang=True)]
        neue = [spur("12. Spielminute"), spur("80. Spielminute")]

        assert abgleichen(alte, neue) == Abgleich(weiter=[None, None], bleiben=[0], gehen=[])


class TestNichtMehrGemeldet:
    def test_ohne_vorgang_geht_er(self) -> None:
        assert abgleichen([spur()], []) == Abgleich(weiter=[], bleiben=[], gehen=[0])

    def test_mit_vorgang_bleibt_er(self) -> None:
        ergebnis = abgleichen([spur(mit_vorgang=True)], [])

        assert ergebnis == Abgleich(weiter=[], bleiben=[0], gehen=[])
