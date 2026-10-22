"""Der Bearbeitungsstand einer Zeile der Trefferliste.

Am 22.10.2026 an der echten Liste abgelesen: die Statusspalte trägt **keinen
Text**. Der Stand steht als `title` am Symbol — `zellen[-1]` war immer leer,
und ein Filter darauf hätte auf nichts gestanden.

Die Titel einer Zeile, so wie sie wirklich kommen:

    ['Einzelspielbericht (neue Version) bearbeiten',
     'Spiel ist freigegeben',
     'Prüferfreigabe']

Zwei davon sind Knopf und Haken, einer ist der Stand.
"""

from __future__ import annotations

import pytest

from homepi_pruefdienst import dienst

ECHTE_TITEL = [
    "Einzelspielbericht (neue Version) bearbeiten",
    "Spiel ist freigegeben",
    "Prüferfreigabe",
]


class TestStandLesen:
    def test_aus_den_echten_titeln(self) -> None:
        assert dienst.stand_aus(ECHTE_TITEL) == "Prüferfreigabe"

    def test_knopf_und_haken_sind_kein_stand(self) -> None:
        """Sonst stünde in jeder Zeile „Einzelspielbericht bearbeiten"."""
        assert dienst.stand_aus(ECHTE_TITEL[:2]) == ""

    @pytest.mark.parametrize(
        "stand", ["Prüferfreigabe", "Schiedsrichterfreigabe", "In Nacherfassung"]
    )
    def test_alle_drei_staende(self, stand: str) -> None:
        assert dienst.stand_aus(["irgendwas", stand]) == stand

    def test_gross_und_klein_egal(self) -> None:
        assert dienst.stand_aus(["prüferfreigabe"]) == "Prüferfreigabe"

    def test_ohne_titel_bleibt_er_leer(self) -> None:
        assert dienst.stand_aus([]) == ""


class TestSchonBearbeitet:
    def test_prueferfreigabe_heisst_bearbeitet(self) -> None:
        """Das ist der Stand, den **seine eigene** Freigabe setzt."""
        assert dienst.schon_bearbeitet("Prüferfreigabe")

    @pytest.mark.parametrize("stand", ["Schiedsrichterfreigabe", "In Nacherfassung"])
    def test_die_anderen_warten_noch_auf_ihn(self, stand: str) -> None:
        assert not dienst.schon_bearbeitet(stand)

    def test_ein_leerer_stand_zaehlt_nicht_als_bearbeitet(self) -> None:
        """Die wichtigere Hälfte.

        Leer heißt *nicht bekannt*. Ein unbekannter Stand muss geprüft werden;
        ihn zu überspringen wäre die gefährlichste Zeile in der
        Warteschlange — ein Bericht, den niemand angesehen hat und der
        aussieht, als sei er erledigt.
        """
        assert not dienst.schon_bearbeitet("")
        assert not dienst.schon_bearbeitet("   ")

    def test_ein_unbekannter_stand_ebenso(self) -> None:
        assert not dienst.schon_bearbeitet("Irgendein neuer Stand")


class TestZeileZerlegen:
    def test_der_stand_landet_an_der_zeile(self) -> None:
        zeile = dienst.zeile_zerlegen(
            ["", "", "030", "Sa. 26.09.2026 13:00", "5", "Heim", "-", "Gast", "7 : 1", ""],
            "031DHM02RS",
            ECHTE_TITEL,
        )

        assert zeile.status == "Prüferfreigabe"

    def test_ohne_titel_bleibt_er_leer(self) -> None:
        """Vorher stand hier `zellen[-1]` -- und das war immer "". Jetzt ist
        es ausdruecklich leer und bedeutet *nicht bekannt*."""
        zeile = dienst.zeile_zerlegen(["", "", "030", "26.09.2026", "7 : 1", ""], "M-1")

        assert zeile.status == ""
