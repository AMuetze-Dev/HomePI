"""§ 60 und § 61 SpO SFV — Nichtantreten und Spielabbruch.

Der entscheidende Unterschied steht in § 61 (3), letzter Absatz:

    „Bei Spielabbrüchen nach a), b) und c) erfolgt Neuansetzung durch den
     Staffelleiter. In allen anderen Fällen ist durch das zuständige
     Sportgericht ein Verfahren durchzuführen."

Dunkelheit, unbespielbarer Platz und Witterung sind Terminarbeit. Tätlichkeit,
Widersetzlichkeit, bedrohliche Zuschauer sind ein Verfahren. Beides in einen
Befund zu werfen hieße, dem Staffelleiter die Frage zu stellen, die die Regel
beantworten soll.
"""

import pytest

from homepi_pruefdienst import katalog as regelbruecke
from homepi_pruefdienst.bericht import MatchMeta, MatchReport, TeamSquad
from homepi_pruefdienst.regelwerk import vorlagen_ausrollen

from .hilfe import StaffelConfig


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
        spieltage=26,
    )


def bericht(*vorkommnisse, text=""):
    return MatchReport(
        meta=MatchMeta(
            home_team="SV Loschwitz 2",
            away_team="SV Pillnitz",
            match_date="15.09.2026",
            match_day="2",
            kickoff="15:00",
            competition="Meisterschaft",
            match_id="ABC123",
        ),
        home_squad=TeamSquad(team="Heim", team_name="SV Loschwitz 2"),
        away_squad=TeamSquad(team="Gast", team_name="SV Pillnitz"),
        incidents_reported=bool(vorkommnisse or text),
        incidents_details={"checked_labels": list(vorkommnisse), "text": text},
    )


def regeln_von(report, ordner):
    return sorted(v.rule for v in regelbruecke.pruefen(report, staffel(), ordner))


def befund(report, ordner, kennung):
    treffer = [v for v in regelbruecke.pruefen(report, staffel(), ordner) if v.rule == kennung]
    return treffer[0] if treffer else None


class TestSpielabbruch:
    @pytest.mark.parametrize(
        "label",
        [
            "Spielabbruch als Folge der Vorkommnisse",
            "Spielabbruch wegen Tätlichkeit gegen den Schiedsrichter",
            "Spielabbruch wegen Widersetzlichkeit",
        ],
    )
    def test_an_abandonment_that_needs_proceedings(self, regelordner, label):
        namen = regeln_von(bericht(label), regelordner)
        assert "spielabbruch" in namen
        assert "spielabbruch_neuansetzung" not in namen

    @pytest.mark.parametrize(
        "label",
        [
            "Spielabbruch wegen starker Dunkelheit",
            "Spielabbruch wegen Unbespielbarkeit des Platzes",
            "Spielabbruch wegen Witterungsbedingungen",
        ],
    )
    def test_an_abandonment_the_staffelleiter_simply_reschedules(self, regelordner, label):
        """§ 61 (3) a) bis c): kein Verfahren. Das hier als Sportgerichtsfall
        zu melden hieße, wegen Regens ein Verfahren zu eröffnen."""
        namen = regeln_von(bericht(label), regelordner)
        assert "spielabbruch_neuansetzung" in namen
        assert "spielabbruch" not in namen

    def test_the_finding_says_what_to_do(self, regelordner):
        treffer = befund(bericht("Spielabbruch wegen Tätlichkeit"), regelordner, "spielabbruch")
        assert treffer is not None
        assert "Verfahren" in treffer.message
        assert treffer.severity.value == "critical"

    def test_the_rescheduling_finding_says_no_proceedings_are_needed(self, regelordner):
        treffer = befund(
            bericht("Spielabbruch wegen starker Dunkelheit"),
            regelordner,
            "spielabbruch_neuansetzung",
        )
        assert treffer is not None
        assert "nicht erforderlich" in treffer.message

    def test_a_normal_match_says_nothing(self, regelordner):
        namen = regeln_von(bericht(), regelordner)
        assert "spielabbruch" not in namen
        assert "spielabbruch_neuansetzung" not in namen

    def test_the_empty_questionnaire_is_not_an_abandonment(self, regelordner):
        """Der Fragebogen nennt „Spielabbruch als Folge der Vorkommnisse" als
        Beschriftung. Nur angekreuzte Felder kommen im Bericht an — sonst wäre
        jedes Spiel ein Abbruch."""
        report = bericht()
        report.incidents_details = {"checked_labels": [], "text": ""}
        assert "spielabbruch" not in regeln_von(report, regelordner)


class TestNichtantreten:
    def test_it_is_reported(self, regelordner):
        assert "nichtantreten" in regeln_von(
            bericht("Gastmannschaft nicht angetreten"), regelordner
        )

    def test_the_finding_names_the_three_day_deadline(self, regelordner):
        """§ 59 (12): die Umstände sind innerhalb von drei Tagen nachzuweisen.
        Die Frist läuft ab dem Spieltag, nicht ab dem Tag, an dem der
        Staffelleiter hinsieht."""
        treffer = befund(bericht("Heimmannschaft nicht angetreten"), regelordner, "nichtantreten")
        assert treffer is not None
        assert "3 Tagen" in treffer.message

    def test_a_normal_match_says_nothing(self, regelordner):
        assert "nichtantreten" not in regeln_von(bericht(), regelordner)


def test_these_rules_cite_their_paragraphs(regelordner):
    from homepi_pruefdienst.regelwerk import laden

    geladen = {r.id: r for r in laden(regelordner).registry}
    for kennung, erwartet in [
        ("spielabbruch", "61"),
        ("spielabbruch_neuansetzung", "61"),
        ("nichtantreten", "60"),
    ]:
        assert kennung in geladen, kennung
        assert erwartet in geladen[kennung].paragraf, kennung
