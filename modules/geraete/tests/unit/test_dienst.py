"""Reine Fachlogik - keine Datenbank, keine Fixtures, Millisekunden."""

from __future__ import annotations

from homepi_geraete.dienst import GeraetSicht, darf_geschaltet_werden, zusammenfassen


def sicht(raum: str = "Wohnzimmer", zustand: str = "bereit", an: bool = False) -> GeraetSicht:
    return GeraetSicht(raum=raum, zustand=zustand, eingeschaltet=an)


class TestSchaltbarkeit:
    def test_bereites_geraet_darf_geschaltet_werden(self) -> None:
        assert darf_geschaltet_werden("bereit").erlaubt is True

    def test_wartung_verhindert_das_schalten(self) -> None:
        entscheidung = darf_geschaltet_werden("wartung")

        assert entscheidung.erlaubt is False
        assert "Wartung" in entscheidung.grund

    def test_der_grund_haengt_an_der_entscheidung(self) -> None:
        """Ein blosses False zwingt den Aufrufer, den Grund zu erraten."""
        assert darf_geschaltet_werden("bereit").grund == ""


class TestZusammenfassung:
    def test_leere_liste(self) -> None:
        ergebnis = zusammenfassen([])

        assert ergebnis.anzahl == 0
        assert ergebnis.raeume == {}

    def test_zaehlt_eingeschaltete(self) -> None:
        ergebnis = zusammenfassen([sicht(an=True), sicht(an=True), sicht(an=False)])

        assert ergebnis.anzahl == 3
        assert ergebnis.eingeschaltet == 2

    def test_zaehlt_wartung(self) -> None:
        ergebnis = zusammenfassen([sicht(zustand="wartung"), sicht()])

        assert ergebnis.in_wartung == 1

    def test_gruppiert_nach_raum(self) -> None:
        ergebnis = zusammenfassen([sicht(raum="Küche"), sicht(raum="Bad"), sicht(raum="Küche")])

        assert ergebnis.raeume == {"Bad": 1, "Küche": 2}

    def test_raeume_sind_sortiert(self) -> None:
        """Sonst springt die Reihenfolge in der Oberflaeche bei jedem Aufruf."""
        ergebnis = zusammenfassen([sicht(raum="Z"), sicht(raum="A"), sicht(raum="M")])

        assert list(ergebnis.raeume) == ["A", "M", "Z"]
