"""§ 58 SpO SFV — Verwarnungen und Spielsperren.

Der Paragraf, der die meiste Arbeit eines Staffelleiters macht und die meisten
Fallstricke enthält. Vier davon sind so leicht zu übersehen, dass sie jeweils
einen eigenen Test bekommen:

* Die gelbe Karte desselben Spiels ist bei Gelb-Rot **und** bei Rot verbraucht
  (§ 58 (1) c) und (2) d)).
* Pokal und übrige Pflichtspiele werden getrennt gezählt (§ 58 (2)).
* Nach jeder verwirkten Sperre beginnt der Zähler bei null — 5, dann wieder 5,
  nicht 5/10/15 als absolute Schwellen (§ 58 (2) b)).
* Im Pokal ist es die **zweite** Verwarnung, nicht die fünfte (§ 58 (2) c)).
"""

from datetime import date

import pytest

from homepi_pruefdienst import katalog as regelbruecke
from homepi_pruefdienst.bericht import (
    CardEvent,
    MatchMeta,
    MatchReport,
    Player,
    TeamOfficial,
    TeamSquad,
)
from homepi_pruefdienst.regelwerk import vorlagen_ausrollen

from .hilfe import FakeAuskunft, StaffelConfig


@pytest.fixture
def regelordner(tmp_path):
    ordner = tmp_path / "regeln"
    vorlagen_ausrollen(ordner)
    regelbruecke.zuruecksetzen()
    yield ordner
    regelbruecke.zuruecksetzen()


def staffel():
    return StaffelConfig(
        name="Stadtliga C",
        altersklasse="maenner",
        dfbnet_filter="3.Kreisliga (C)",
        sportrichter_email="sr@example.de",
        saison="26/27",
    )


def bericht(*, spieler=(), betreuer=(), karten=(), wettbewerb="Meisterschaft"):
    return MatchReport(
        meta=MatchMeta(
            home_team="SV Loschwitz 2",
            away_team="SV Pillnitz",
            match_date="15.09.2026",
            match_day="2",
            kickoff="15:00",
            league_class="3.Kreisliga (C)",
            competition=wettbewerb,
            match_id="ABC123",
        ),
        home_squad=TeamSquad(
            team="Heim",
            team_name="SV Loschwitz 2",
            starting_eleven=list(spieler),
            officials=list(betreuer),
        ),
        away_squad=TeamSquad(team="Gast", team_name="SV Pillnitz"),
        cards=list(karten),
    )


def person(name="Max Müller", pass_nr="P1"):
    return Player(name=name, pass_number=pass_nr, birthdate="01.01.1990")


def karte(art, person="Max Müller", minute="30"):
    return CardEvent(minute=minute, team="SV Loschwitz 2", player=person, card_type=art)


def pruefe(report, ordner, auskunft=None):
    return regelbruecke.pruefen(report, staffel(), ordner, auskunft=auskunft)


def regeln_von(verstoesse):
    return sorted(v.rule for v in verstoesse)


def befund(verstoesse, kennung):
    treffer = [v for v in verstoesse if v.rule == kennung]
    return treffer[0] if treffer else None


# ── § 58 (2) a) Die 5. Verwarnung ────────────────────────────────────────
class TestFuenfteVerwarnung:
    """„Erhält eine Spielerin/ein Spieler, Trainer/in oder Funktionsträger/in
    in einem Meisterschafts-, Aufstiegs- oder Entscheidungsspiel innerhalb
    einer Spiel- und Altersklasse die 5. Verwarnung, so ist sie/er für das
    nächste … Spiel dieser Mannschaft gesperrt."""

    def _auskunft(self, anzahl, wettbewerb="Meisterschaft"):
        return FakeAuskunft({("P1", wettbewerb): anzahl})

    def test_the_fifth_caution_is_reported(self, regelordner):
        verstoesse = pruefe(
            bericht(spieler=[person()], karten=[karte("Gelbe Karte")]),
            regelordner,
            self._auskunft(5),
        )
        treffer = befund(verstoesse, "verwarnung_fuenf")
        assert treffer is not None
        assert "Max Müller" in treffer.message

    def test_the_fourth_is_not(self, regelordner):
        verstoesse = pruefe(
            bericht(spieler=[person()], karten=[karte("Gelbe Karte")]),
            regelordner,
            self._auskunft(4),
        )
        assert "verwarnung_fuenf" not in regeln_von(verstoesse)

    def test_someone_without_a_card_today_is_not_reported(self, regelordner):
        """Der Zähler steht auf fünf, aber heute gab es keine Verwarnung — die
        Sperre wurde also an einem früheren Spieltag ausgelöst und dort
        gemeldet. Sie hier erneut zu melden hieße, sie jede Woche zu melden."""
        verstoesse = pruefe(bericht(spieler=[person()]), regelordner, self._auskunft(5))
        assert "verwarnung_fuenf" not in regeln_von(verstoesse)

    def test_without_a_database_it_says_so_rather_than_nothing(self, regelordner):
        """Ohne Zähler kann die Regel nicht prüfen. Stillschweigen sähe aus wie
        „alles in Ordnung"."""
        verstoesse = pruefe(bericht(spieler=[person()], karten=[karte("Gelbe Karte")]), regelordner)
        assert "verwarnungszaehler_fehlt" in regeln_von(verstoesse)

    def test_a_coach_counts_too(self, regelordner):
        """§ 58 nennt Trainer und Funktionsträger in jedem Absatz gleichrangig."""
        verstoesse = pruefe(
            bericht(
                betreuer=[TeamOfficial(name="Chef", roles=["Trainer"])],
                karten=[karte("Gelbe Karte", person="Chef")],
            ),
            regelordner,
            FakeAuskunft({("", "Meisterschaft"): 5}),
        )
        # Ohne Passnummer gibt es keinen Zähler — die Regel muss das sagen und
        # darf nicht so tun, als sei nichts.
        assert "verwarnungszaehler_fehlt" in regeln_von(verstoesse)


# ── § 58 (2) b) Der Rhythmus ─────────────────────────────────────────────
class TestRhythmus:
    """„nach einer verwirkten Sperre 5 weitere Verwarnungen … Es ergibt sich
    ein Rhythmus von 5 – 10 – 15 usw., wobei immer nur einmal ausgesetzt
    werden muss."""

    def test_after_a_suspension_the_count_restarts(self, regelordner):
        """Zehn Verwarnungen insgesamt, fünf davon nach der Sperre: die zehnte
        löst aus. Wer stattdessen auf die absolute 10 prüft, kommt hier zufällig
        aufs selbe Ergebnis — und liegt daneben, sobald jemand zwischen zwei
        Sperren sechs Verwarnungen sammelt."""
        auskunft = FakeAuskunft(
            {("P1", "Meisterschaft"): 5},
            {("P1", "Meisterschaft"): date(2026, 8, 1)},
        )
        verstoesse = pruefe(
            bericht(spieler=[person()], karten=[karte("Gelbe Karte")]),
            regelordner,
            auskunft,
        )
        assert "verwarnung_fuenf" in regeln_von(verstoesse)

    def test_four_since_the_last_suspension_is_not_enough(self, regelordner):
        auskunft = FakeAuskunft(
            {("P1", "Meisterschaft"): 4},
            {("P1", "Meisterschaft"): date(2026, 8, 1)},
        )
        verstoesse = pruefe(
            bericht(spieler=[person()], karten=[karte("Gelbe Karte")]),
            regelordner,
            auskunft,
        )
        assert "verwarnung_fuenf" not in regeln_von(verstoesse)


# ── § 58 (2) c) Pokal ────────────────────────────────────────────────────
class TestPokal:
    """„Eine Spielerin/ein Spieler …, die/der in Pokalspielen oder in einem
    Meisterschaftsturnier die 2. Verwarnung erhalten hat, ist für das nächste
    Spiel des Pokals bzw. des Turniers gesperrt."""

    def test_the_second_caution_in_a_cup_match(self, regelordner):
        verstoesse = pruefe(
            bericht(
                spieler=[person()],
                karten=[karte("Gelbe Karte")],
                wettbewerb="Kreispokal Herren",
            ),
            regelordner,
            FakeAuskunft({("P1", "Pokal"): 2}),
        )
        assert "verwarnung_pokal_zwei" in regeln_von(verstoesse)

    def test_two_cautions_in_the_league_are_harmless(self, regelordner):
        verstoesse = pruefe(
            bericht(spieler=[person()], karten=[karte("Gelbe Karte")]),
            regelordner,
            FakeAuskunft({("P1", "Meisterschaft"): 2}),
        )
        assert "verwarnung_pokal_zwei" not in regeln_von(verstoesse)
        assert "verwarnung_fuenf" not in regeln_von(verstoesse)

    def test_the_league_rule_does_not_fire_in_a_cup_match(self, regelordner):
        """§ 58 (2) a) nennt ausdrücklich nur Meisterschafts-, Aufstiegs- und
        Entscheidungsspiele."""
        verstoesse = pruefe(
            bericht(
                spieler=[person()],
                karten=[karte("Gelbe Karte")],
                wettbewerb="Kreispokal Herren",
            ),
            regelordner,
            FakeAuskunft({("P1", "Pokal"): 5}),
        )
        assert "verwarnung_fuenf" not in regeln_von(verstoesse)


# ── § 58 (1) c) und (2) d) Die verbrauchte Verwarnung ────────────────────
class TestVerbrauchteVerwarnung:
    """„Die in diesem Spiel erhaltene Verwarnung (gelbe Karte) gilt als
    verbraucht und wird nicht registriert" — bei Gelb-Rot (1) c) und ebenso
    im Falle eines Feldverweises auf Dauer (2) d)."""

    def test_a_yellow_before_a_yellow_red_does_not_count(self, regelordner):
        verstoesse = pruefe(
            bericht(
                spieler=[person()],
                karten=[karte("Gelbe Karte", minute="20"), karte("Gelb-Rote Karte", minute="70")],
            ),
            regelordner,
            FakeAuskunft({("P1", "Meisterschaft"): 5}),
        )
        assert "verwarnung_fuenf" not in regeln_von(verstoesse)

    def test_a_yellow_before_a_red_does_not_count_either(self, regelordner):
        """§ 58 (2) d) — der im Code bisher fehlende Fall."""
        verstoesse = pruefe(
            bericht(
                spieler=[person()],
                karten=[karte("Gelbe Karte", minute="20"), karte("Rote Karte", minute="70")],
            ),
            regelordner,
            FakeAuskunft({("P1", "Meisterschaft"): 5}),
        )
        assert "verwarnung_fuenf" not in regeln_von(verstoesse)

    def test_the_red_card_itself_is_still_reported(self, regelordner):
        verstoesse = pruefe(
            bericht(spieler=[person()], karten=[karte("Rote Karte")]),
            regelordner,
        )
        assert "red_card" in regeln_von(verstoesse)


# ── § 58 (1) b) Gelb-Rot ─────────────────────────────────────────────────
class TestGelbRot:
    def test_it_names_the_scope_of_the_suspension(self, regelordner):
        """„das darauffolgende Pflichtspiel der gleichen Wettbewerbskategorie
        dieser Mannschaft … auch für das jeweils nächstfolgende Spiel jeder
        anderen Mannschaft ihres/seines Vereins … längstens bis zum Ablauf von
        10 Tagen." Der Staffelleiter muss beides im Blick behalten."""
        treffer = befund(
            pruefe(
                bericht(spieler=[person()], karten=[karte("Gelb-Rote Karte")]),
                regelordner,
            ),
            "yellow_red_card",
        )
        assert treffer is not None
        assert "10 Tage" in treffer.message


def test_every_rule_of_this_paragraph_cites_it(regelordner):
    """Ein Befund ohne Fundstelle zwingt den Verein, auf gut Glück zu suchen."""
    from homepi_pruefdienst.regelwerk import laden

    betroffen = {
        "verwarnung_fuenf",
        "verwarnung_pokal_zwei",
        "red_card",
        "yellow_red_card",
    }
    for regel in laden(regelordner).registry:
        if regel.id in betroffen:
            assert "58" in regel.paragraf, regel.id
