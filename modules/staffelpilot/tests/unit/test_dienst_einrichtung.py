"""Wo der Staffelleiter bei der Einrichtung steht.

Zwei Dinge müssen stehen, bevor dieses Artefakt irgendetwas kann: ein
DFBnet-Zugang und mindestens eine Staffel. Fehlt eines davon, hilft keine
Liste und keine Kennzahl — die Spielprüfung bliebe leer, und niemand sähe
warum.

Die Entscheidung steht hier und nicht in der Oberfläche: sonst beantwortet
jede Ansicht sie selbst, und zwei von ihnen antworten irgendwann
verschieden.
"""

from __future__ import annotations

from homepi_staffelpilot import dienst


class TestEinrichtungSchritt:
    def test_ohne_zugang_zuerst_der_zugang(self) -> None:
        schritt = dienst.einrichtung_schritt(zugang=False, staffeln=0, erledigt=False)

        assert schritt == "zugang"

    def test_ohne_zugang_auch_wenn_staffeln_dastehen(self) -> None:
        """Von Hand angelegte Staffeln ersetzen den Zugang nicht — ohne ihn
        liest der Prüfdienst keinen einzigen Spielbericht."""
        schritt = dienst.einrichtung_schritt(zugang=False, staffeln=3, erledigt=False)

        assert schritt == "zugang"

    def test_mit_zugang_dann_die_staffeln(self) -> None:
        schritt = dienst.einrichtung_schritt(zugang=True, staffeln=0, erledigt=False)

        assert schritt == "staffeln"

    def test_beides_da_heisst_fertig(self) -> None:
        schritt = dienst.einrichtung_schritt(zugang=True, staffeln=1, erledigt=False)

        assert schritt == "fertig"

    def test_abgehakt_heisst_fertig_auch_wenn_etwas_fehlt(self) -> None:
        """Wer die Einrichtung übersprungen hat, soll sie nicht bei jedem
        Aufruf wieder vorgesetzt bekommen. Ein Hinweis bleibt; ein Weg, der
        sich nicht schließen lässt, ist eine Sackgasse."""
        schritt = dienst.einrichtung_schritt(zugang=False, staffeln=0, erledigt=True)

        assert schritt == "fertig"
