"""Einen Sportgerichtsfall anlegen -- gegen eine nachgebaute Seite.

Woertlich uebernommen aus `D:/DevLibrary/StaffelPilot/tests/test_fallanlage.py`.

**Nichts hier darf an das echte Modul kommen:** das ist die eine Handlung, die
ein Verfahren gegen eine benannte Person eroeffnet, und eine Testsammlung, die
eines anlegen koennte, ist eine, die niemand zu starten wagt.

Die Formen stammen vom lebenden Formular am 31.08.2026, abgelaufen bis vor das
Speichern.
"""

import pytest

from homepi_pruefdienst.fallanlage import (
    AKTENZEICHEN_MUSTER,
    Anlage,
    FallanlageFehler,
    aktenzeichen_lesen,
    fall_anlegen,
)


def anlage(**felder) -> Anlage:
    daten = {
        "spielkennung": "633203004",
        "saison": "26/27",
        "gericht": "Sportgericht Stadtverband Fußball Dresden e.V.",
        "tatbestand": "Feldverweis auf Dauer wegen Beleidigung des Schiedsrichters.",
    }
    daten.update(felder)
    return Anlage(**daten)


class FakeLocator:
    def __init__(self, seite, treffer, art=""):
        self._seite = seite
        self._treffer = treffer
        self._art = art

    @property
    def first(self):
        return FakeLocator(self._seite, self._treffer[:1], self._art)

    def count(self):
        return len(self._treffer)

    def is_visible(self):
        return bool(self._treffer)

    def click(self, timeout=0):
        if not self._treffer:
            raise TimeoutError("kein Treffer")
        self._seite.klick(self._art)

    def fill(self, wert):
        self._seite.felder[self._art] = wert

    def input_value(self):
        return self._seite.felder.get(self._art, "")


class FakeDFBnet:
    """The Sportgerichtsbarkeit module, with the parts that matter."""

    def __init__(
        self,
        treffer=True,
        formular_vollstaendig=True,
        gezeigte_kennung="633203004",
        gericht_waehlbar=True,
        aktenzeichen="00042-26/27-SPG_DD",
    ):
        self._treffer = treffer
        self._formular_vollstaendig = formular_vollstaendig
        self._aktenzeichen = aktenzeichen
        self._gericht_waehlbar = gericht_waehlbar

        self.gesucht = False
        self.formular_offen = False
        self.gespeichert = False
        self.geschlossen = False
        self.felder = {"anzeige_kennung": gezeigte_kennung}
        self.auswahl = {}

    # -- Playwright surface ------------------------------------------------
    def wait_for_timeout(self, ms):
        pass

    def wait_for_load_state(self, zustand=None):
        pass

    def close(self):
        self.geschlossen = True

    def get_by_role(self, rolle, name="", exact=False):
        return FakeLocator(self, [{"name": name}], f"menu:{name}")

    def select_option(self, auswahl, label=None):
        if "sitzung.gericht" in auswahl and not self._gericht_waehlbar:
            raise RuntimeError("Option gibt es nicht")
        self.auswahl[auswahl] = label

    def locator(self, auswahl):
        if "SEARCH" in auswahl:
            return FakeLocator(self, [{}], "suchen")
        if "Bearbeiten" in auswahl:
            return FakeLocator(self, [{}] if self.gesucht and self._treffer else [], "bearbeiten")
        if "tatbestand" in auswahl:
            da = self.formular_offen and self._formular_vollstaendig
            return FakeLocator(self, [{}] if da else [], "tatbestand")
        if "_kontext.fall.spielKennung" in auswahl:
            return FakeLocator(self, [{}], "anzeige_kennung")
        if "SAVE_ERSTELLUNG" in auswahl:
            return FakeLocator(self, [{}] if self.formular_offen else [], "speichern")
        if "suche.spielkennung" in auswahl:
            return FakeLocator(self, [{}], "such_kennung")
        for schluessel in ("currentVorgang.datum", "datumAnzeige", "anzeigeVon"):
            if schluessel in auswahl:
                return FakeLocator(self, [{}], schluessel)
        return FakeLocator(self, [{}], "sonstiges")

    def evaluate(self, js, arg=None):
        if not self.gespeichert:
            return "Fall\nErstellung\nTatbestand"
        return f"Fall gespeichert.\nAktenzeichen {self._aktenzeichen}\nSitzung"

    # -- behaviour ---------------------------------------------------------
    def klick(self, art):
        if art == "suchen":
            self.gesucht = True
        elif art == "bearbeiten":
            self.formular_offen = True
        elif art == "speichern":
            self.gespeichert = True


class FakeContext:
    def __init__(self, seite):
        self._seite = seite

    def new_page(self):
        return self._seite


def anlegen(seite, **felder):
    return fall_anlegen(FakeContext(seite), anlage(**felder))


class TestErfolg:
    def test_it_creates_the_case_and_reports_the_aktenzeichen(self):
        seite = FakeDFBnet()
        ergebnis = anlegen(seite)
        assert ergebnis.erfolg
        assert ergebnis.aktenzeichen == "00042-26/27-SPG_DD"
        assert seite.gespeichert

    def test_the_tatbestand_reaches_the_form(self):
        seite = FakeDFBnet()
        anlegen(seite, tatbestand="Feldverweis wegen Tätlichkeit.")
        assert seite.felder["tatbestand"] == "Feldverweis wegen Tätlichkeit."

    def test_the_court_is_chosen_on_the_form(self):
        seite = FakeDFBnet()
        anlegen(seite)
        assert any("sitzung.gericht" in k for k in seite.auswahl)

    def test_dates_left_empty_are_not_overwritten(self):
        """DFBnet pre-fills them, and its defaults are usually right."""
        seite = FakeDFBnet()
        anlegen(seite)
        assert "datumAnzeige" not in seite.felder

    def test_a_given_date_is_written(self):
        seite = FakeDFBnet()
        anlegen(seite, datum_anzeige="31.08.2026")
        assert seite.felder["datumAnzeige"] == "31.08.2026"

    def test_the_tab_is_closed(self):
        seite = FakeDFBnet()
        anlegen(seite)
        assert seite.geschlossen


class TestVerweigert:
    @pytest.mark.parametrize("feld", ["spielkennung", "saison", "gericht", "tatbestand"])
    def test_an_incomplete_case_is_refused_before_a_browser_acts(self, feld):
        seite = FakeDFBnet()
        ergebnis = anlegen(seite, **{feld: ""})
        assert not ergebnis.erfolg
        assert not seite.gespeichert

    def test_a_match_that_is_not_found_stops_the_run(self):
        seite = FakeDFBnet(treffer=False)
        with pytest.raises(FallanlageFehler, match="kein Spiel gefunden"):
            anlegen(seite)
        assert not seite.gespeichert

    def test_a_half_rendered_form_is_not_filled_in(self):
        seite = FakeDFBnet(formular_vollstaendig=False)
        with pytest.raises(FallanlageFehler, match="nicht vollständig"):
            anlegen(seite)
        assert not seite.gespeichert

    def test_a_form_for_the_wrong_match_is_refused(self):
        """The one mistake that would be invisible afterwards: a case opened
        against a match nobody meant."""
        seite = FakeDFBnet(gezeigte_kennung="999999999")
        with pytest.raises(FallanlageFehler, match="gehört zu Spiel"):
            anlegen(seite)
        assert not seite.gespeichert

    def test_a_court_that_is_not_offered_stops_the_run(self):
        seite = FakeDFBnet(gericht_waehlbar=False)
        with pytest.raises(FallanlageFehler, match="nicht zur Auswahl"):
            anlegen(seite)
        assert not seite.gespeichert

    def test_the_tab_is_closed_even_when_it_fails(self):
        seite = FakeDFBnet(treffer=False)
        with pytest.raises(FallanlageFehler):
            anlegen(seite)
        assert seite.geschlossen


class TestAktenzeichen:
    def test_it_is_read_out_of_the_page(self):
        class Seite:
            def evaluate(self, js, arg=None):
                return "Fall gespeichert\nAktenzeichen 00042-26/27-SPG_DD\nweiter"

        assert aktenzeichen_lesen(Seite()) == "00042-26/27-SPG_DD"

    def test_a_page_without_one_yields_empty(self):
        class Seite:
            def evaluate(self, js, arg=None):
                return "Fall gespeichert"

        assert aktenzeichen_lesen(Seite()) == ""

    def test_a_missing_number_still_counts_as_created(self):
        """Reporting failure would invite a second case for the same offence,
        which is worse than a number typed in by hand."""
        seite = FakeDFBnet(aktenzeichen="")
        ergebnis = anlegen(seite)
        assert ergebnis.erfolg
        assert ergebnis.aktenzeichen == ""
        assert "nachsehen" in ergebnis.meldung

    @pytest.mark.parametrize(
        "text,erwartet",
        [
            ("00042-26/27-SPG_DD", "00042-26/27-SPG_DD"),
            ("Az. 00007-26/27-SPG_L vom 31.08.", "00007-26/27-SPG_L"),
            ("Spielkennung 633203004", ""),
            ("26/27", ""),
        ],
    )
    def test_the_pattern_matches_a_number_and_not_a_season(self, text, erwartet):
        treffer = AKTENZEICHEN_MUSTER.search(text)
        assert (treffer.group(0) if treffer else "") == erwartet


def test_the_pattern_is_the_shape_the_verband_assigns():
    """Die Form des Aktenzeichens, festgehalten an einem echten.

    In der alten Anwendung stand dem ein zweiter Test gegenueber, der
    dieselbe Form in `src.core.sportrichtermail` prueft -- beide Seiten
    mussten sich einig sein, wie eines aussieht. Die Mail an den
    Sportrichter ist hier noch nicht uebernommen; sobald sie es ist,
    gehoert der Vergleich zurueck.
    """
    assert AKTENZEICHEN_MUSTER.search("00042-26/27-SPG_DD")
    assert not AKTENZEICHEN_MUSTER.search("26/27")
