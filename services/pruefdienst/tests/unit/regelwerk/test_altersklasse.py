"""Altersklassen in Ü-Staffeln.

In einer Ü35-Staffel muss jeder 35 erreicht haben; bis zu
`HOECHSTENS_UNTER_DEM_BAND` dürfen „nur" Ü32 sein, also 32 bis 34. Wer jünger
ist, ist gar nicht spielberechtigt.

Die Zahlen standen bis zum 06.09.2026 in der Staffelverwaltung und stehen seit
dem oben in der Regeldatei — § 42 (2) überlässt die Untergrenze dem
Kreisverband, damit ist sie Teil der Regel. Mehrere Tests hier ändern deshalb
die ausgerollte Datei und prüfen, dass die Änderung wirkt: genau das ist der
Weg, den ein Staffelleiter eines anderen Kreises gehen muss.

Die frühere Prüfung zählte *jeden* ab 32 gegen die Grenze von zwei — in einer
Ü35-Mannschaft also die ganze Elf, und aus einer völlig legalen Aufstellung
wurde „16 Ü32/Ü35-Spieler im Kader, Maximum ist 2".

Die Regel steht seit dem anpassbaren Regelwerk in
`config/regeln/10_altersklassen.py`. Diese Tests laufen deshalb über die
Regeldateien statt über eine Funktion im Programm — sie prüfen, was der
Staffelleiter tatsächlich ausgeliefert bekommt.
"""

from datetime import date

import pytest

from homepi_pruefdienst import katalog as regelbruecke
from homepi_pruefdienst.bericht import MatchMeta, MatchReport, Player, TeamSquad
from homepi_pruefdienst.regelwerk import vorlagen_ausrollen
from homepi_pruefdienst.regelwerk.spiel import Person, datum_lesen

from .hilfe import StaffelConfig

SPIELTAG = "30.08.2026"


@pytest.fixture
def regelordner(tmp_path):
    ordner = tmp_path / "regeln"
    vorlagen_ausrollen(ordner)
    regelbruecke.zuruecksetzen()
    yield ordner
    regelbruecke.zuruecksetzen()


def staffel(altersklasse="ue35"):
    return StaffelConfig(
        name="Ü35 1. Stadtklasse",
        altersklasse=altersklasse,
        dfbnet_filter="1.Kreisklasse",
        sportrichter_email="",
    )


def untergrenzen_setzen(ordner, tabelle, hoechstens=2):
    """Die Zahlen in der ausgerollten Regeldatei ändern.

    So, wie es ein Staffelleiter täte: Datei öffnen, Zahl ändern. Der Test
    fasst nur die Zeile an, die er auch anfassen würde.
    """
    datei = ordner / "10_altersklassen.py"
    text = datei.read_text(encoding="utf-8")
    anfang = text.index("UNTERGRENZEN = {")
    ende = text.index("}", anfang) + 1
    zeilen = [f"    {band}: {grenze}," for band, grenze in tabelle.items()]
    neu = "\n".join(["UNTERGRENZEN = {", *zeilen, "}"])
    text = text[:anfang] + neu + text[ende:]
    text = text.replace(
        "HOECHSTENS_UNTER_DEM_BAND = 2", f"HOECHSTENS_UNTER_DEM_BAND = {hoechstens}"
    )
    datei.write_text(text, encoding="utf-8")
    regelbruecke.zuruecksetzen()


def spieler(name, geburt):
    return Player(name=name, pass_number=f"P-{name}", birthdate=geburt)


def report(kader):
    return MatchReport(
        meta=MatchMeta(match_date=SPIELTAG, home_team="SV Motor Sörnewitz", away_team="Gast"),
        home_squad=TeamSquad(
            team="Heim", team_name="SV Motor Sörnewitz", starting_eleven=list(kader)
        ),
        away_squad=TeamSquad(team="Gast", team_name="Gast"),
    )


def regeln(ordner, kader, konfig=None):
    """Nur die Altersbefunde — die übrigen Regeln laufen mit, gehören aber
    nicht in diese Datei."""
    interessant = {"altersklasse_zu_jung", "ue32_limit", "geburtsdatum_unplausibel"}
    return [
        v
        for v in regelbruecke.pruefen(report(kader), konfig or staffel(), ordner)
        if v.rule in interessant
    ]


class TestAlterBerechnung:
    def test_the_birthday_itself_counts(self):
        person = Person(geburtsdatum=date(1991, 8, 30), _spieltag=date(2026, 8, 30))
        assert person.alter == 35

    def test_the_day_before_does_not(self):
        person = Person(geburtsdatum=date(1991, 8, 31), _spieltag=date(2026, 8, 30))
        assert person.alter == 34

    def test_an_unparsable_birthdate_yields_nothing(self):
        assert datum_lesen("") is None
        assert Person(_spieltag=date(2026, 8, 30)).alter is None


class TestUe35:
    def test_a_squad_of_older_players_is_silent(self, regelordner):
        """Der gemeldete Fall: sechzehn zulässige Spieler, sechzehn Fehlbefunde."""
        kader = [spieler(f"Alt {i}", "01.01.1980") for i in range(16)]
        assert regeln(regelordner, kader) == []

    def test_exactly_the_band_is_enough(self, regelordner):
        assert regeln(regelordner, [spieler("Genau", "30.08.1991")]) == []

    def test_two_ue32_players_are_allowed(self, regelordner):
        kader = [
            spieler("Alt", "01.01.1980"),
            spieler("Ue32 A", "01.01.1994"),
            spieler("Ue32 B", "01.01.1993"),
        ]
        assert regeln(regelordner, kader) == []

    def test_a_fourth_ue32_player_is_reported(self, regelordner):
        # Drei sind erlaubt: HOECHSTENS_UNTER_DEM_BAND in
        # 10_altersklassen.py. Fuer den Kreis Dresden hat der Vorsitzende des
        # Stadtverbands das am 06.09.2026 muendlich bestaetigt -- eine
        # schriftliche Fundstelle gibt es nicht, und genau deshalb steht die
        # Zahl in einer Datei, die der Staffelleiter aendern kann.
        kader = [
            spieler("Ue32 A", "01.01.1994"),
            spieler("Ue32 B", "01.01.1993"),
            spieler("Ue32 C", "01.01.1992"),
            spieler("Ue32 D", "01.01.1994"),
        ]
        befunde = [v for v in regeln(regelordner, kader) if v.rule == "ue32_limit"]
        assert len(befunde) == 1
        assert befunde[0].details["anzahl"] == 4
        assert befunde[0].details["limit"] == 3

    def test_the_message_names_who_is_over_the_limit(self, regelordner):
        kader = [spieler(f"Ue32 {i}", "01.01.1994") for i in range(4)]
        befund = [v for v in regeln(regelordner, kader) if v.rule == "ue32_limit"][0]
        assert "Ue32 0" in befund.message

    def test_a_player_below_the_exception_band_is_critical(self, regelordner):
        befunde = regeln(regelordner, [spieler("Jung", "01.01.1996")])
        assert [v.rule for v in befunde] == ["altersklasse_zu_jung"]
        assert befunde[0].severity.value == "critical"
        assert befunde[0].details["alter"] == 30

    def test_a_too_young_player_does_not_also_count_as_an_exception(self, regelordner):
        kader = [spieler("Jung", "01.01.1996"), spieler("Ue32", "01.01.1994")]
        assert [v.rule for v in regeln(regelordner, kader)] == ["altersklasse_zu_jung"]

    def test_without_the_exception_every_younger_player_is_critical(self, regelordner):
        """Ein Kreis ohne Ausnahme trägt die Altersklasse selbst ein."""
        untergrenzen_setzen(regelordner, {35: 35})
        befunde = regeln(regelordner, [spieler("Ue32", "01.01.1994")])
        assert [v.rule for v in befunde] == ["altersklasse_zu_jung"]


class TestAndereStaffeln:
    def test_a_herren_staffel_has_no_age_band(self, regelordner):
        kader = [spieler("Jung", "01.01.2008")]
        assert regeln(regelordner, kader, staffel(altersklasse="maenner")) == []

    def test_a_ue40_staffel_uses_its_own_band(self, regelordner):
        """Das Band kommt aus der Staffel, nicht aus einer festen 35."""
        kader = [spieler("Ue35", "01.01.1990")]  # am Spieltag 36
        befunde = regeln(regelordner, kader, staffel(altersklasse="ue40"))
        assert [v.rule for v in befunde] == ["altersklasse_zu_jung"]
        assert befunde[0].details["mindestalter"] == 40
        # § 42 (2): für Ü40 ist die Untergrenze 38, nicht 32.
        assert befunde[0].details["untergrenze"] == 38

    def test_the_lower_bound_comes_from_the_rule_file(self, regelordner):
        """§ 42 (2): „Die Kreisverbände können bzgl. der Altersuntergrenze
        andere Regelungen treffen." Ein Kreis, der 34 festlegt, ändert die
        Zeile in seiner Regeldatei — am Programm ändert sich nichts."""
        kader = [spieler("Ue33", "01.01.1993")]  # am Spieltag 33

        untergrenzen_setzen(regelordner, {35: 34}, hoechstens=5)
        assert [v.rule for v in regeln(regelordner, kader)] == ["altersklasse_zu_jung"]

        untergrenzen_setzen(regelordner, {35: 32}, hoechstens=5)
        assert regeln(regelordner, kader) == []

    def test_an_age_class_without_an_entry_falls_back_to_its_own_band(self, regelordner):
        """Eine Altersklasse, die in der Tabelle fehlt, darf nicht auf 0 fallen
        und jeden zulassen — dann gilt die Altersklasse selbst."""
        untergrenzen_setzen(regelordner, {40: 38}, hoechstens=5)
        assert [v.rule for v in regeln(regelordner, [spieler("Ue33", "01.01.1993")])] == [
            "altersklasse_zu_jung"
        ]

    def test_a_ue40_staffel_uses_its_own_lower_bound(self, regelordner):
        """Nicht 32 für alle: § 42 (2) b) nennt für Ü40 die 38."""
        untergrenzen_setzen(regelordner, {35: 32, 40: 38}, hoechstens=5)
        offen = staffel(altersklasse="ue40")
        assert regeln(regelordner, [spieler("Ue39", "01.01.1987")], offen) == []
        assert [v.rule for v in regeln(regelordner, [spieler("Ue35", "01.01.1991")], offen)] == [
            "altersklasse_zu_jung"
        ]

    def test_an_older_player_is_always_welcome(self, regelordner):
        """§ 42 (2), letzter Satz: „Die Teilnahme am Spielbetrieb der jüngeren
        Altersklassen ist möglich." Ein Ü50-Spieler in einer Ü35-Staffel ist
        ausdrücklich zulässig — eine Obergrenze wäre hier ein Fehler."""
        kader = [spieler(f"Alt {i}", "01.01.1970") for i in range(11)]  # 56 Jahre
        assert regeln(regelordner, kader) == []


class TestOhneKonfiguration:
    def test_without_a_staffel_nothing_is_claimed(self, regelordner):
        verstoesse = regelbruecke.pruefen(report([spieler("X", "01.01.2010")]), None, regelordner)
        assert "altersklasse_zu_jung" not in {v.rule for v in verstoesse}

    def test_a_player_without_a_birthdate_is_skipped(self, regelordner):
        """Kein Datum, keine Behauptung — ein erfundenes Alter wäre schlimmer
        als Schweigen."""
        assert regeln(regelordner, [Player(name="Ohne", pass_number="P")]) == []
