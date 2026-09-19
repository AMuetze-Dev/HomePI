"""§ 59 SpO SFV — Spieldurchführung.

Drei prüfbare Sätze, die bisher niemand geprüft hat:

* (17) belegt die Bestätigungsfrist, die bisher unbelegt im Code stand:
  „nach der Schiedsrichterfreigabe … unmittelbar vor Ort bis 18:00 Uhr
  spätestens aber 60 Minuten nach Spielende die Kenntnisnahme zu bestätigen."
* (18) „In allen Alters- und Spielklassen sind Rückennummern zu tragen. Dabei
  darf ein Feldspieler nur unter einer Nummer im Spiel eingesetzt werden.
  Lediglich die Torhüter dürfen mit zwei Rückennummern … vermerkt werden."
* (10) „Als angetreten gilt eine Mannschaft, wenn … im Frauen- und
  Herrenbereich (Großfeld) mindestens 7 Spielerinnen/Spieler … erschienen sind."
"""

import pytest

from homepi_pruefdienst import katalog as regelbruecke
from homepi_pruefdienst.bericht import MatchMeta, MatchReport, Player, TeamSquad
from homepi_pruefdienst.regelwerk import vorlagen_ausrollen

from .hilfe import StaffelConfig


@pytest.fixture
def regelordner(tmp_path):
    ordner = tmp_path / "regeln"
    vorlagen_ausrollen(ordner)
    regelbruecke.zuruecksetzen()
    yield ordner
    regelbruecke.zuruecksetzen()


def staffel(**felder):
    grund = dict(
        name="Stadtliga C",
        altersklasse="maenner",
        dfbnet_filter="3.Kreisliga (C)",
        sportrichter_email="sr@example.de",
        saison="26/27",
    )
    grund.update(felder)
    return StaffelConfig(**grund)


def spieler(name, trikot="", torwart=False):
    return Player(
        name=name,
        pass_number=f"P-{name}",
        birthdate="01.01.1990",
        jersey_number=trikot,
        is_goalkeeper=torwart,
    )


def bericht(heim=(), gast=None):
    if gast is None:
        gast = [spieler(f"G{i}", str(i + 1)) for i in range(11)]
    return MatchReport(
        meta=MatchMeta(
            home_team="SV Loschwitz 2",
            away_team="SV Pillnitz",
            match_date="15.09.2026",
            match_day="2",
            kickoff="15:00",
            league_class="3.Kreisliga (C)",
            competition="Meisterschaft",
            match_id="ABC123",
        ),
        home_squad=TeamSquad(team="Heim", team_name="SV Loschwitz 2", starting_eleven=list(heim)),
        away_squad=TeamSquad(team="Gast", team_name="SV Pillnitz", starting_eleven=list(gast)),
    )


def pruefe(report, ordner, konfig=None):
    return regelbruecke.pruefen(report, konfig or staffel(), ordner)


def regeln_von(verstoesse):
    return sorted(v.rule for v in verstoesse)


def befund(verstoesse, kennung):
    treffer = [v for v in verstoesse if v.rule == kennung]
    return treffer[0] if treffer else None


def elf(**abweichungen):
    """Eine reguläre Elf mit den Nummern 1 bis 11."""
    mannschaft = [spieler(f"S{i}", str(i + 1), torwart=(i == 0)) for i in range(11)]
    for index, trikot in abweichungen.items():
        mannschaft[int(index)] = spieler(f"S{index}", trikot, torwart=(int(index) == 0))
    return mannschaft


class TestRueckennummern:
    """§ 59 (18)."""

    def test_a_regular_squad_is_silent(self, regelordner):
        assert "rueckennummer_doppelt" not in regeln_von(pruefe(bericht(elf()), regelordner))

    def test_two_field_players_with_the_same_number(self, regelordner):
        kader = elf()
        kader[5] = spieler("Doppelt", "3")  # dieselbe Nummer wie S2
        treffer = befund(pruefe(bericht(kader), regelordner), "rueckennummer_doppelt")
        assert treffer is not None
        assert "3" in treffer.message
        assert "Doppelt" in treffer.message

    def test_a_missing_number_is_reported_separately(self, regelordner):
        """„In allen Alters- und Spielklassen sind Rückennummern zu tragen."
        Zwei Spieler ohne Nummer sind nicht „zweimal dieselbe Nummer"."""
        kader = elf()
        kader[4] = spieler("Ohne", "")
        namen = regeln_von(pruefe(bericht(kader), regelordner))
        assert "rueckennummer_fehlt" in namen
        assert "rueckennummer_doppelt" not in namen

    def test_two_players_without_a_number_are_not_a_duplicate(self, regelordner):
        kader = elf()
        kader[4] = spieler("Ohne A", "")
        kader[6] = spieler("Ohne B", "")
        assert "rueckennummer_doppelt" not in regeln_von(pruefe(bericht(kader), regelordner))

    def test_the_goalkeepers_second_number_is_not_representable(self, regelordner):
        """„Lediglich die Torhüter dürfen mit zwei Rückennummern auf dem
        Spielbericht vermerkt werden."

        Diese Ausnahme lässt sich aus den Daten nicht ablesen: DFBnet führt je
        Person genau ein Trikotfeld. Zwei Personen mit derselben Nummer sind
        deshalb immer ein Treffer — auch wenn eine davon der Torhüter ist. Der
        Test hält fest, dass das eine bewusste Entscheidung ist und keine
        vergessene Ausnahme."""
        from homepi_pruefdienst.bericht import Player

        assert not hasattr(Player, "jersey_numbers")
        kader = elf()
        kader.append(spieler("Zweiter mit 1", "1", torwart=True))
        assert "rueckennummer_doppelt" in regeln_von(pruefe(bericht(kader), regelordner))

    def test_a_field_player_sharing_the_keepers_number_is_reported(self, regelordner):
        kader = elf()
        kader.append(spieler("Feldspieler", "1"))
        assert "rueckennummer_doppelt" in regeln_von(pruefe(bericht(kader), regelordner))

    def test_the_two_teams_are_looked_at_separately(self, regelordner):
        """Beide Mannschaften tragen die 1 bis 11 — das ist der Normalfall und
        kein einziger Verstoß."""
        assert "rueckennummer_doppelt" not in regeln_von(pruefe(bericht(elf(), elf()), regelordner))


class TestMannschaftsstaerke:
    """§ 59 (10): im Herrenbereich mindestens 7."""

    def test_eleven_is_fine(self, regelordner):
        assert "mannschaftsstaerke" not in regeln_von(pruefe(bericht(elf()), regelordner))

    def test_seven_is_still_fine(self, regelordner):
        assert "mannschaftsstaerke" not in regeln_von(pruefe(bericht(elf()[:7]), regelordner))

    def test_six_is_not(self, regelordner):
        treffer = befund(pruefe(bericht(elf()[:6]), regelordner), "mannschaftsstaerke")
        assert treffer is not None
        assert "6" in treffer.message

    def test_an_empty_squad_is_not_reported_as_a_thin_one(self, regelordner):
        """Kein Kader im Bericht heißt „noch nicht erfasst", nicht „null
        Spieler angetreten". Das wäre an jedem geplanten Spiel ein Befund."""
        assert "mannschaftsstaerke" not in regeln_von(pruefe(bericht([], []), regelordner))


def test_the_rules_of_this_paragraph_cite_it(regelordner):
    from homepi_pruefdienst.regelwerk import laden

    betroffen = {"rueckennummer_doppelt", "rueckennummer_fehlt", "mannschaftsstaerke"}
    geladen = {r.id: r for r in laden(regelordner).registry}
    for kennung in betroffen:
        assert kennung in geladen, kennung
        assert "59" in geladen[kennung].paragraf, kennung


def test_the_confirmation_deadline_is_now_documented():
    """§ 59 (17) belegt die 18-Uhr-Frist und die 60 Minuten, die bisher als
    unbelegte Annahme im Code standen.

    Die Fristen stehen in diesem Dienst nicht im Regelkatalog, sondern in
    `regeln.py` -- sie sind Verfahren und nichts, was ein Staffelleiter
    anpassen soll. Die Fundstelle muss trotzdem dort stehen.
    """
    from pathlib import Path

    from homepi_pruefdienst import regeln

    quelle = Path(regeln.__file__).read_text(encoding="utf-8")

    assert "§ 59" in quelle, "die Fundstelle fehlt weiterhin"
    assert regeln.CONFIRMATION_DEADLINE_HOUR == 18
    assert regeln.CONFIRMATION_GRACE_MINUTES == 60
