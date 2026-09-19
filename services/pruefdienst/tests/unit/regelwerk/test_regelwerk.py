"""Das anpassbare Regelwerk.

Die Prüfungen der Spielordnung stehen jetzt in Dateien, die der Staffelleiter
selbst ändert. Damit verschiebt sich die Frage, die Tests beantworten müssen:
nicht mehr nur „rechnet die Regel richtig", sondern auch „was passiert, wenn
jemand sie kaputt macht".

Die Antwort muss immer dieselbe sein — **laut**. Eine Regel, die stillschweigend
nicht mehr prüft, ist von einem sauberen Spiel nicht zu unterscheiden, und genau
so verschwindet eine Prüfung, ohne dass es jemand merkt.
"""

from datetime import date
from pathlib import Path

import pytest

from homepi_pruefdienst import katalog as regelbruecke
from homepi_pruefdienst.bericht import (
    CardEvent,
    MatchMeta,
    MatchReport,
    Player,
    SeasonAppearance,
    SeasonAppearances,
    TeamOfficial,
    TeamSquad,
)
from homepi_pruefdienst.regeln import Severity
from homepi_pruefdienst.regelwerk import laden, uebersetzen, vorlagen_ausrollen
from homepi_pruefdienst.regelwerk.lader import VORLAGEN

from .hilfe import StaffelConfig


# ── Bausteine ────────────────────────────────────────────────────────────
def spieler(name, geburtsdatum="", badges=(), einsaetze=()):
    return Player(
        name=name,
        pass_number=f"P-{name[:3]}",
        birthdate=geburtsdatum,
        badges=list(badges),
        season_appearances=SeasonAppearances(count=len(einsaetze), matches=list(einsaetze)),
    )


def einsatz(datum, mannschaft, minuten=90, spieltag=None):
    return SeasonAppearance(
        kickoff=f"{datum} 15:00",
        home_team=mannschaft,
        away_team="Irgendwer",
        minutes=minuten,
        competition="Meisterschaft",
        match_day=spieltag,
    )


def stammspieler(name, geburtsdatum="01.01.1990", oben="SV Loschwitz"):
    """Jemand, der § 68 (2) b) erfüllt: fünf Spiele der höheren Mannschaft, alle
    mitgespielt. Das Kennzeichen allein reicht nicht mehr — die Regel rechnet
    die Quote, weil der Paragraf sie vorschreibt."""
    return spieler(
        name,
        geburtsdatum,
        badges=["Stammspieler"],
        einsaetze=[einsatz(f"2026-08-{10 + i:02d}", oben, spieltag=i) for i in range(1, 6)],
    )


def bericht(
    heim_spieler=(), gast_spieler=(), *, spieltag="1", datum="15.09.2026", karten=(), betreuer=()
):
    return MatchReport(
        meta=MatchMeta(
            home_team="SV Loschwitz 2",
            away_team="SV Pillnitz",
            match_date=datum,
            match_day=spieltag,
            kickoff="15:00",
            league_class="3.Kreisliga (C)",
            competition="Meisterschaft",
            match_id="ABC123",
        ),
        home_squad=TeamSquad(
            team="Heim",
            team_name="SV Loschwitz 2",
            starting_eleven=list(heim_spieler),
            officials=list(betreuer),
        ),
        away_squad=TeamSquad(
            team="Gast", team_name="SV Pillnitz", starting_eleven=list(gast_spieler)
        ),
        cards=list(karten),
    )


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


@pytest.fixture
def regelordner(tmp_path, monkeypatch):
    """Ein eigener Regelordner je Test, mit den mitgelieferten Vorlagen."""
    ordner = tmp_path / "regeln"
    vorlagen_ausrollen(ordner)
    regelbruecke.zuruecksetzen()
    yield ordner
    regelbruecke.zuruecksetzen()


def pruefe(report, staffel_konfiguration, ordner):
    return regelbruecke.pruefen(report, staffel_konfiguration, ordner)


def regeln_von(verstoesse):
    return sorted(v.rule for v in verstoesse)


# ── Übersetzung ──────────────────────────────────────────────────────────
class TestUebersetzer:
    def test_the_report_becomes_a_game_in_the_language_of_the_rules(self):
        spiel = uebersetzen(bericht([spieler("Max", "01.01.1990")]), staffel())
        assert spiel.heim == "SV Loschwitz 2"
        assert spiel.datum == date(2026, 9, 15)
        assert spiel.heim_mannschaft.spieler[0].name == "Max"

    def test_age_is_measured_on_the_match_day(self):
        spiel = uebersetzen(bericht([spieler("Max", "16.09.1990")]), staffel())
        # Geburtstag einen Tag nach dem Spiel: noch 35, nicht 36.
        assert spiel.heim_mannschaft.spieler[0].alter == 35

    def test_the_u23_cut_off_is_the_first_of_july(self):
        """Wer im Oktober 23 wird, ist die ganze Saison über U23 — am Spieltag
        zu messen ist der häufigste Weg, § 68 (2) c) um ein Jahr zu verfehlen."""
        spiel = uebersetzen(bericht([spieler("Jung", "01.10.2003")], datum="15.11.2026"), staffel())
        person = spiel.heim_mannschaft.spieler[0]
        assert person.alter == 23  # am Spieltag schon 23
        assert person.alter_am_1_juli == 22  # am Stichtag noch nicht

    def test_a_spring_match_looks_back_to_last_july(self):
        spiel = uebersetzen(bericht([spieler("Jung", "01.10.2003")], datum="15.03.2027"), staffel())
        assert spiel.heim_mannschaft.spieler[0].alter_am_1_juli == 22

    def test_cards_end_up_with_their_person(self):
        karte = CardEvent(minute="71", team="SV Loschwitz 2", player="Max", card_type="Rote Karte")
        spiel = uebersetzen(bericht([spieler("Max", "01.01.1990")], karten=[karte]), staffel())
        person = spiel.heim_mannschaft.spieler[0]
        assert len(person.karten) == 1
        assert person.karten[0].ist_rot
        assert person.karten[0].minute == 71

    def test_injury_time_counts_as_the_regular_minute(self):
        karte = CardEvent(
            minute="90+3", team="SV Loschwitz 2", player="Max", card_type="Gelbe Karte"
        )
        spiel = uebersetzen(bericht([spieler("Max")], karten=[karte]), staffel())
        assert spiel.heim_mannschaft.spieler[0].karten[0].minute == 90

    def test_officials_are_people_too(self):
        """§ 58 nennt Trainer und Funktionsträger gleichrangig mit Spielern."""
        spiel = uebersetzen(
            bericht(betreuer=[TeamOfficial(name="Chef", roles=["Trainer"])]), staffel()
        )
        assert [p.name for p in spiel.heim_mannschaft.betreuer] == ["Chef"]
        assert spiel.heim_mannschaft.mit_rolle("trainer")[0].name == "Chef"

    def test_the_last_four_match_days_are_countable(self):
        spiel = uebersetzen(bericht(spieltag="23"), staffel(spieltage=26))
        assert spiel.spieltage_bis_ende == 4

    def test_without_the_season_length_it_says_nothing(self):
        """`None`, nicht 0 — 0 hieße „letzter Spieltag" und würde die
        U23-Ausnahme in jedem Spiel aufheben."""
        assert uebersetzen(bericht(spieltag="5"), staffel()).spieltage_bis_ende is None

    def test_a_missing_birthdate_is_not_an_age_of_zero(self):
        spiel = uebersetzen(bericht([spieler("Ohne")]), staffel())
        assert spiel.heim_mannschaft.spieler[0].alter is None

    def test_an_unreadable_date_does_not_raise(self):
        spiel = uebersetzen(bericht([spieler("Krumm", "kein Datum")]), staffel())
        assert spiel.heim_mannschaft.spieler[0].geburtsdatum is None


class TestWartefrist:
    """§ 68 (2) a): „Der dem Spieltag folgende Tag ist der erste Tag."""

    def _spiel(self, tage_vorher):
        vor = date(2026, 9, 15) - __import__("datetime").timedelta(days=tage_vorher)
        return uebersetzen(
            bericht(
                [spieler("Max", "01.01.1990", einsaetze=[einsatz(vor.isoformat(), "SV Loschwitz")])]
            ),
            staffel(hoehere_mannschaften=["SV Loschwitz"]),
        )

    def test_the_day_of_the_appearance_does_not_count(self):
        person = self._spiel(5).heim_mannschaft.spieler[0]
        assert person.tage_seit_einsatz_bei(["SV Loschwitz"]) == 5

    def test_an_appearance_for_another_team_is_not_counted(self):
        person = self._spiel(2).heim_mannschaft.spieler[0]
        assert person.tage_seit_einsatz_bei(["SG Anderswo"]) is None

    def test_being_on_the_sheet_is_not_an_appearance(self):
        """§ 68 zählt Einsätze. Wer auf der Bank saß, hat nicht gespielt."""
        spiel = uebersetzen(
            bericht(
                [
                    spieler(
                        "Max",
                        "01.01.1990",
                        einsaetze=[einsatz("2026-09-13", "SV Loschwitz", minuten=0)],
                    )
                ]
            ),
            staffel(hoehere_mannschaften=["SV Loschwitz"]),
        )
        assert spiel.heim_mannschaft.spieler[0].einsaetze_bei(["SV Loschwitz"]) == []


# ── Laden ────────────────────────────────────────────────────────────────
class TestLaden:
    def test_the_shipped_rules_load(self, regelordner):
        ladung = laden(regelordner)
        assert ladung.fehler == {}
        assert ladung.anzahl >= 7

    def test_they_are_rolled_out_only_once(self, tmp_path):
        ziel = tmp_path / "regeln"
        assert vorlagen_ausrollen(ziel)
        (ziel / "10_altersklassen.py").write_text("# von Hand", encoding="utf-8")
        assert vorlagen_ausrollen(ziel) == []
        assert (ziel / "10_altersklassen.py").read_text(encoding="utf-8") == "# von Hand"

    def test_an_update_never_overwrites_a_hand_edited_rule(self, tmp_path):
        """Eine Aktualisierung, die eine geschärfte Regel zurücksetzt, ist
        schlimmer als eine veraltete Vorlage — sie sagt nichts."""
        ziel = tmp_path / "regeln"
        vorlagen_ausrollen(ziel)
        eigene = ziel / "20_stammspieler.py"
        eigene.write_text(
            eigene.read_text(encoding="utf-8").replace(
                "WARTEFRIST_TAGE = 5", "WARTEFRIST_TAGE = 7"
            ),
            encoding="utf-8",
        )
        vorlagen_ausrollen(ziel)
        assert "WARTEFRIST_TAGE = 7" in eigene.read_text(encoding="utf-8")

    def test_a_later_file_may_replace_an_earlier_rule(self, regelordner):
        (regelordner / "90_eigene.py").write_text(
            '@regel(name="ue32_limit", schwere="hinweis")\n'
            "def meine(spiel, melde):\n"
            '    melde("meine Fassung")\n',
            encoding="utf-8",
        )
        ladung = laden(regelordner)
        assert ladung.registry.get("ue32_limit").quelle == "90_eigene.py"
        assert "ue32_limit" in ladung.registry.ersetzte

    def test_files_starting_with_an_underscore_are_helpers(self, regelordner):
        (regelordner / "_hilfen.py").write_text("kaputt(", encoding="utf-8")
        assert laden(regelordner).fehler == {}

    def test_a_rule_needs_a_valid_severity(self, regelordner):
        (regelordner / "90_kaputt.py").write_text(
            '@regel(name="x", schwere="ganz schlimm")\ndef meine(spiel, melde):\n    pass\n',
            encoding="utf-8",
        )
        ladung = laden(regelordner)
        assert "90_kaputt.py" in ladung.fehler
        assert "ganz schlimm" in ladung.fehler["90_kaputt.py"]

    def test_a_mahnung_without_a_box_is_refused(self, regelordner):
        """Die Liste des Verbandes ist geschlossen. Ein geratenes Kreuz stünde
        auf einem Schriftstück, das an einen Verein rausgeht."""
        (regelordner / "90_kaputt.py").write_text(
            '@regel(name="x", weg="mahnung")\ndef meine(spiel, melde):\n    pass\n',
            encoding="utf-8",
        )
        assert "bagatelle" in laden(regelordner).fehler["90_kaputt.py"]


# ── Fehlerverhalten ──────────────────────────────────────────────────────
class TestFehlerhafteRegeln:
    def test_a_broken_file_is_reported_at_every_match(self, regelordner):
        (regelordner / "90_kaputt.py").write_text("das ist kein Python", encoding="utf-8")
        verstoesse = pruefe(bericht(), staffel(), regelordner)
        fehler = [v for v in verstoesse if v.rule == "regel_fehlerhaft"]
        assert fehler and fehler[0].severity is Severity.CRITICAL
        assert "90_kaputt.py" in fehler[0].message

    def test_the_other_rules_keep_running(self, regelordner):
        (regelordner / "90_kaputt.py").write_text("das ist kein Python", encoding="utf-8")
        verstoesse = pruefe(
            bericht([spieler("Jung", "01.01.2005")]),
            staffel(altersklasse="ue35"),
            regelordner,
        )
        assert "altersklasse_zu_jung" in regeln_von(verstoesse)

    def test_a_rule_that_stumbles_names_itself_and_its_line(self, regelordner):
        (regelordner / "90_kaputt.py").write_text(
            '@regel(name="stolpert")\ndef meine(spiel, melde):\n    return 1 / 0\n',
            encoding="utf-8",
        )
        verstoesse = pruefe(bericht(), staffel(), regelordner)
        fehler = [v for v in verstoesse if v.rule == "regel_fehlerhaft"]
        assert any("stolpert" in v.message for v in fehler)
        assert any("Zeile 3" in v.message for v in fehler)

    def test_a_broken_rule_is_critical_so_the_match_cannot_be_ticked_off(self, regelordner):
        """Der entscheidende Punkt: still ausfallen sähe aus wie ein sauberes
        Spiel, und das Spiel ließe sich abhaken und freigeben."""
        (regelordner / "90_kaputt.py").write_text(
            '@regel(name="stolpert")\ndef m(spiel, melde):\n    raise ValueError("x")\n',
            encoding="utf-8",
        )
        verstoesse = pruefe(bericht(), staffel(), regelordner)
        assert any(v.severity is Severity.CRITICAL for v in verstoesse)

    def test_findings_made_before_the_stumble_are_kept(self, regelordner):
        (regelordner / "90_teilweise.py").write_text(
            '@regel(name="halb")\n'
            "def m(spiel, melde):\n"
            '    melde("erst das hier")\n'
            '    raise ValueError("dann das")\n',
            encoding="utf-8",
        )
        verstoesse = pruefe(bericht(), staffel(), regelordner)
        assert "halb" in regeln_von(verstoesse)
        assert "regel_fehlerhaft" in regeln_von(verstoesse)


# ── Die mitgelieferten Regeln ────────────────────────────────────────────
class TestAltersklassen:
    def test_a_too_young_player_in_an_ue35_staffel(self, regelordner):
        verstoesse = pruefe(
            bericht([spieler("Jung", "01.01.2005")]),
            staffel(altersklasse="ue35"),
            regelordner,
        )
        treffer = [v for v in verstoesse if v.rule == "altersklasse_zu_jung"]
        assert treffer and treffer[0].severity is Severity.CRITICAL
        assert "SV Loschwitz 2" in treffer[0].message

    def test_a_herren_staffel_has_no_lower_bound(self, regelordner):
        verstoesse = pruefe(bericht([spieler("Jung", "01.01.2008")]), staffel(), regelordner)
        assert "altersklasse_zu_jung" not in regeln_von(verstoesse)

    def test_the_ue32_band_is_allowed_up_to_the_limit(self, regelordner):
        elf = [spieler(f"S{i}", "01.01.1993") for i in range(2)]  # 33 Jahre
        verstoesse = pruefe(
            bericht(elf),
            staffel(altersklasse="ue35", ue32_erlaubt=True, max_ue32_spieler=2),
            regelordner,
        )
        assert "ue32_limit" not in regeln_von(verstoesse)
        assert "altersklasse_zu_jung" not in regeln_von(verstoesse)

    def test_one_too_many_in_the_ue32_band(self, regelordner):
        # Vier statt drei: die Obergrenze steht seit 09/2026 in der Regeldatei
        # (HOECHSTENS_UNTER_DEM_BAND) und nicht mehr an der Staffel. Fuer den
        # Kreis Dresden sind es drei -- muendlich bestaetigt am 06.09.2026,
        # eine schriftliche Fundstelle gibt es nicht.
        elf = [spieler(f"S{i}", "01.01.1993") for i in range(4)]
        verstoesse = pruefe(
            bericht(elf),
            staffel(altersklasse="ue35", ue32_erlaubt=True, max_ue32_spieler=2),
            regelordner,
        )
        treffer = [v for v in verstoesse if v.rule == "ue32_limit"]
        assert treffer and treffer[0].details["anzahl"] == 4

    def test_a_full_ue35_squad_is_not_reported_as_sixteen_exceptions(self, regelordner):
        """Der alte Fehler: gezählt wurde jeder ab 32 — in einer Ü35-Mannschaft
        also die ganze Elf, „16 Spieler, Maximum ist 2"."""
        elf = [spieler(f"S{i}", "01.01.1985") for i in range(16)]  # 41 Jahre
        verstoesse = pruefe(
            bericht(elf),
            staffel(altersklasse="ue35", ue32_erlaubt=True, max_ue32_spieler=2),
            regelordner,
        )
        assert "ue32_limit" not in regeln_von(verstoesse)

    def test_a_birthdate_in_the_future_is_a_typo_not_a_child(self, regelordner):
        verstoesse = pruefe(
            bericht([spieler("Zukunft", "01.01.2030")]),
            staffel(altersklasse="ue35"),
            regelordner,
        )
        namen = regeln_von(verstoesse)
        assert "geburtsdatum_unplausibel" in namen
        assert "altersklasse_zu_jung" not in namen


class TestKarten:
    def test_a_red_card_goes_to_the_sportgericht(self, regelordner):
        karte = CardEvent(minute="71", team="SV Loschwitz 2", player="Max", card_type="Rote Karte")
        verstoesse = pruefe(
            bericht([spieler("Max", "01.01.1990")], karten=[karte]),
            staffel(),
            regelordner,
        )
        treffer = [v for v in verstoesse if v.rule == "red_card"]
        assert treffer and treffer[0].severity is Severity.CRITICAL
        assert "Minute 71" in treffer[0].message

    def test_a_yellow_red_is_a_note_not_an_offence(self, regelordner):
        karte = CardEvent(
            minute="80", team="SV Loschwitz 2", player="Max", card_type="Gelb-Rote Karte"
        )
        verstoesse = pruefe(
            bericht([spieler("Max", "01.01.1990")], karten=[karte]),
            staffel(),
            regelordner,
        )
        treffer = [v for v in verstoesse if v.rule == "yellow_red_card"]
        assert treffer and treffer[0].severity is Severity.WARNING

    def test_a_yellow_red_is_not_counted_as_a_red_one(self, regelordner):
        karte = CardEvent(team="SV Loschwitz 2", player="Max", card_type="Gelb-Rote Karte")
        verstoesse = pruefe(bericht([spieler("Max")], karten=[karte]), staffel(), regelordner)
        assert "red_card" not in regeln_von(verstoesse)

    def test_a_card_against_an_official_is_seen(self, regelordner):
        """§ 58 nennt Trainer und Funktionsträger gleichrangig."""
        karte = CardEvent(team="SV Loschwitz 2", player="Chef", card_type="Rote Karte")
        verstoesse = pruefe(
            bericht(betreuer=[TeamOfficial(name="Chef", roles=["Trainer"])], karten=[karte]),
            staffel(),
            regelordner,
        )
        assert "red_card" in regeln_von(verstoesse)


class TestStammspieler:
    def test_the_limit_only_fires_above_the_threshold(self, regelordner):
        elf = [stammspieler(f"S{i}") for i in range(2)]
        verstoesse = pruefe(bericht(elf), staffel(), regelordner)
        assert "stammspieler_limit" not in regeln_von(verstoesse)

    def test_three_regulars_are_one_finding_not_three(self, regelordner):
        """Jeden einzeln zu melden war der größte Posten an Falschbefunden."""
        elf = [stammspieler(f"S{i}") for i in range(3)]
        verstoesse = pruefe(bericht(elf), staffel(), regelordner)
        treffer = [v for v in verstoesse if v.rule == "stammspieler_limit"]
        assert len(treffer) == 1
        assert treffer[0].details["anzahl"] == 3

    def test_u23_players_do_not_count_towards_the_limit(self, regelordner):
        elf = [stammspieler(f"S{i}", "01.01.2005") for i in range(3)]
        verstoesse = pruefe(bericht(elf, spieltag="5"), staffel(spieltage=26), regelordner)
        assert "stammspieler_limit" not in regeln_von(verstoesse)

    def test_on_the_last_four_match_days_they_do(self, regelordner):
        """§ 68 (2) c): die Ausnahme entfällt an den letzten vier Spieltagen."""
        elf = [stammspieler(f"S{i}", "01.01.2005") for i in range(3)]
        verstoesse = pruefe(bericht(elf, spieltag="23"), staffel(spieltage=26), regelordner)
        assert "stammspieler_limit" in regeln_von(verstoesse)

    def test_the_badge_alone_is_not_enough(self, regelordner):
        """§ 68 (2) b) definiert Stammspieler über die Einsatzquote, nicht über
        ein Kennzeichen. Drei Spieler mit Badge, aber ohne Spiele oben, sind
        keine drei Stammspieler."""
        elf = [spieler(f"S{i}", "01.01.1990", badges=["Stammspieler"]) for i in range(3)]
        verstoesse = pruefe(bericht(elf), staffel(), regelordner)
        assert "stammspieler_limit" not in regeln_von(verstoesse)

    def test_below_the_fifth_match_nobody_is_one(self, regelordner):
        """„nach dem fünften Pflichtspiel der höherklassigen Mannschaft" — an
        Spieltag 2 eine Quote von 100 % zu melden wäre eine Zahl, die noch
        nichts bedeuten kann."""
        elf = [
            spieler(
                f"S{i}",
                "01.01.1990",
                einsaetze=[
                    einsatz(f"2026-08-{10 + j:02d}", "SV Loschwitz", spieltag=j)
                    for j in range(1, 3)
                ],
            )
            for i in range(3)
        ]
        verstoesse = pruefe(bericht(elf), staffel(), regelordner)
        assert "stammspieler_limit" not in regeln_von(verstoesse)

    def test_a_missing_season_length_is_said_out_loud(self, regelordner):
        verstoesse = pruefe(bericht(spieltag="5"), staffel(), regelordner)
        assert "spieltage_unbekannt" in regeln_von(verstoesse)

    def test_an_ue_staffel_is_not_asked_for_it(self, regelordner):
        """Dort ist der jüngste zulässige Spieler 32; U23 kann nie greifen."""
        verstoesse = pruefe(bericht(spieltag="5"), staffel(altersklasse="ue35"), regelordner)
        assert "spieltage_unbekannt" not in regeln_von(verstoesse)


# ── Zwischenspeicher ─────────────────────────────────────────────────────
class TestZwischenspeicher:
    def test_an_edited_rule_takes_effect_without_a_restart(self, regelordner):
        """Wer eine Regel anpasst, will sie im nächsten Lauf sehen."""
        elf = [spieler(f"S{i}", "01.01.1993") for i in range(4)]
        vorher = pruefe(
            bericht(elf),
            staffel(altersklasse="ue35", ue32_erlaubt=True, max_ue32_spieler=2),
            regelordner,
        )
        assert "ue32_limit" in regeln_von(vorher)

        datei = regelordner / "10_altersklassen.py"
        datei.write_text(
            datei.read_text(encoding="utf-8").replace(
                "if ANZAHL(ausnahmen) > erlaubt:", "if ANZAHL(ausnahmen) > 99:"
            ),
            encoding="utf-8",
        )
        nachher = pruefe(
            bericht(elf),
            staffel(altersklasse="ue35", ue32_erlaubt=True, max_ue32_spieler=2),
            regelordner,
        )
        assert "ue32_limit" not in regeln_von(nachher)


def test_no_rule_is_checked_twice(regelordner):
    """Die Regeln des Katalogs duerfen nicht zusaetzlich eingebaut sein.

    Sonst meldet jedes Spiel jeden Verstoss doppelt -- und wer die Regel in der
    Datei aendert, sieht die alte Fassung weiterlaufen. Das waere "anpassbar"
    nur dem Namen nach.

    Uebernommen und umgestellt: in der alten Anwendung wurde dafuer der
    Quelltext der Engine durchsucht. Hier stehen die eingebauten Regeln in
    `regeln.py` und lassen sich einfach fragen.
    """
    from homepi_pruefdienst import katalog
    from homepi_pruefdienst import regeln as eingebaut

    aus_dateien = {r.id for r in katalog.regeln(regelordner).registry}
    eingebaute = set(eingebaut._TITEL)

    assert aus_dateien & eingebaute == set()


def test_the_shipped_rules_are_the_ones_that_get_rolled_out():
    """Vorlagen, die nirgends ankommen, sind Dokumentation ohne Wirkung."""
    assert VORLAGEN.is_dir()
    assert sorted(p.name for p in VORLAGEN.glob("*.py")) == [
        "10_altersklassen.py",
        "20_stammspieler.py",
        "30_karten.py",
        "40_spieldurchfuehrung.py",
        "50_spielabbruch.py",
        "60_spielerfoto.py",
        "70_spielrecht.py",
        "80_wechsel_und_spielfuehrer.py",
        "85_spielbericht.py",
    ]


class TestStammspielerNenner:
    """Wogegen die Einsatzquote gerechnet wird.

    Gegen die **bisherigen** Spiele der höheren Mannschaft, nicht gegen die
    Saisonlänge. Der Unterschied ist nicht akademisch: `spieltage` wird seit
    „Initialisieren" gefüllt, und als Nenner eingesetzt macht es aus fünf von
    fünf Spielen „5 von 26". Damit hätte ausgerechnet der Knopf, der die Staffel
    einrichtet, die Stammspieler-Obergrenze stillgelegt — ohne ein Wort.
    """

    def _elf(self, anzahl_einsaetze=5):
        return [
            spieler(
                f"S{i}",
                "01.01.1990",
                einsaetze=[
                    einsatz(f"2026-08-{10 + j:02d}", "SV Loschwitz", spieltag=j)
                    for j in range(1, anzahl_einsaetze + 1)
                ],
            )
            for i in range(3)
        ]

    def test_a_configured_season_length_does_not_dilute_the_ratio(self, regelordner):
        mit = pruefe(bericht(self._elf()), staffel(spieltage=26), regelordner)
        ohne = pruefe(bericht(self._elf()), staffel(), regelordner)
        assert "stammspieler_limit" in regeln_von(mit)
        assert "stammspieler_limit" in regeln_von(ohne)

    def test_half_the_matches_is_enough(self, regelordner):
        """§ 68 (2) b): „in mindestens 50 %"."""
        elf = [
            spieler(
                f"S{i}",
                "01.01.1990",
                einsaetze=[
                    einsatz(f"2026-08-{10 + j:02d}", "SV Loschwitz", spieltag=j * 2)
                    for j in range(1, 4)
                ],
            )
            for i in range(3)
        ]
        # Drei Einsätze, höchster Spieltag 6 → Quote 0,5.
        assert "stammspieler_limit" in regeln_von(pruefe(bericht(elf), staffel(), regelordner))

    def test_below_half_is_not(self, regelordner):
        elf = [
            spieler(
                f"S{i}",
                "01.01.1990",
                einsaetze=[
                    einsatz(f"2026-08-{10 + j:02d}", "SV Loschwitz", spieltag=j * 3)
                    for j in range(1, 4)
                ],
            )
            for i in range(3)
        ]
        # Drei Einsätze, höchster Spieltag 9 → Quote 0,33.
        assert "stammspieler_limit" not in regeln_von(pruefe(bericht(elf), staffel(), regelordner))


def test_the_shipped_rules_travel_with_the_package():
    """Ohne die Vorlagen im Paket rollt der Lader nichts aus, laedt keine
    Regel und prueft nichts -- ohne Fehlermeldung, weil ein leerer Regelordner
    kein Fehler ist. Genau die Art von Ausfall, die erst auffaellt, wenn eine
    Saison ungeprueft durch ist.

    In der alten Anwendung hing das an einem Eintrag in der PyInstaller-Spec.
    Hier liegen sie im Paket, und `hatchling` nimmt mit, was unter
    `src/homepi_pruefdienst` liegt -- gepruefte Zusicherung statt Vertrauen.
    """
    import homepi_pruefdienst

    paket = Path(homepi_pruefdienst.__file__).resolve().parent
    vorlagen = paket / "regelwerk" / "vorlagen"

    assert vorlagen.is_dir()
    assert len(list(vorlagen.glob("*.py"))) >= 9


class TestIdUndName:
    """Regelname und Regel-Identität sind zwei verschiedene Dinge.

    Der Name steht in der Oberfläche und soll lesbar sein — „Ü32-Obergrenze
    überschritten", mit Leerzeichen und Umlauten. Die ID steht in der Datenbank,
    in der Triage-Zuordnung und auf dem Mahnungsformular.

    Beides zu vermischen hieße: eine Regel umbenennen und damit alle
    gespeicherten Befunde entwerten, weil sie auf eine ID zeigen, die es nicht
    mehr gibt.
    """

    def _regel(self, regelordner, kopf, name="pruefung"):
        (regelordner / "90_eigene.py").write_text(
            f"@regel({kopf})\ndef {name}(spiel, melde):\n    melde('x')\n",
            encoding="utf-8",
        )
        return laden(regelordner)

    def test_a_display_name_may_contain_spaces(self, regelordner):
        ladung = self._regel(regelordner, 'id="mit_luecken", name="Zwei Wörter hier"')
        assert ladung.fehler == {}
        assert ladung.registry.get("mit_luecken").name == "Zwei Wörter hier"

    def test_the_id_stays_the_key(self, regelordner):
        ladung = self._regel(regelordner, 'id="stabil", name="Ein schöner Name"')
        assert "stabil" in ladung.registry
        assert ladung.registry.get("stabil").id == "stabil"

    def test_renaming_does_not_change_the_id(self, regelordner):
        """Der ganze Grund für zwei Felder: gespeicherte Befunde überleben."""
        vorher = self._regel(regelordner, 'id="fest", name="Alter Name"')
        nachher = self._regel(regelordner, 'id="fest", name="Ganz neuer Name"')
        assert vorher.registry.get("fest").id == nachher.registry.get("fest").id

    def test_without_an_id_one_is_derived_from_the_name(self, regelordner):
        ladung = self._regel(regelordner, 'name="Ü32-Obergrenze überschritten"')
        assert ladung.fehler == {}
        assert "ue32_obergrenze_ueberschritten" in ladung.registry

    @pytest.mark.parametrize(
        "name,erwartet",
        [
            ("Rote Karte", "rote_karte"),
            ("Ü35 zu jung", "ue35_zu_jung"),
            ("Größe prüfen", "groesse_pruefen"),
            ("Straße/Weg", "strasse_weg"),
            ("  viele   Lücken  ", "viele_luecken"),
            ("§ 58 Verwarnung", "58_verwarnung"),
        ],
    )
    def test_the_derived_id_is_readable_and_stable(self, name, erwartet):
        from homepi_pruefdienst.regelwerk.dekorator import id_aus_name

        assert id_aus_name(name) == erwartet

    def test_a_name_that_derives_to_nothing_is_refused(self, regelordner):
        """„§§§" ergibt keine ID. Lieber ein Ladefehler als eine Regel, die
        unter dem leeren Namen alles andere überschreibt."""
        ladung = self._regel(regelordner, 'name="§§§"')
        assert "90_eigene.py" in ladung.fehler

    def test_the_same_id_twice_in_one_file_is_a_mistake(self, regelordner):
        """Zwischen zwei Dateien ist es Absicht — so ersetzt man eine Regel.
        In derselben Datei ist es ein Versehen, und die zweite verschwände
        stillschweigend."""
        (regelordner / "90_eigene.py").write_text(
            '@regel(id="doppelt", name="Erste")\n'
            "def a(spiel, melde):\n    pass\n\n"
            '@regel(id="doppelt", name="Zweite")\n'
            "def b(spiel, melde):\n    pass\n",
            encoding="utf-8",
        )
        ladung = laden(regelordner)
        assert "90_eigene.py" in ladung.fehler
        assert "doppelt" in ladung.fehler["90_eigene.py"]

    def test_an_invalid_explicit_id_is_refused(self, regelordner):
        ladung = self._regel(regelordner, 'id="Mit Leerzeichen", name="X"')
        assert "90_eigene.py" in ladung.fehler

    def test_the_finding_carries_the_display_name(self, regelordner):
        """Ohne das müsste die Oberfläche die IDs kennen, um sie zu übersetzen."""
        self._regel(regelordner, 'id="sichtbar", name="Gut lesbarer Name"')
        verstoesse = pruefe(bericht(), staffel(), regelordner)
        treffer = [v for v in verstoesse if v.rule == "sichtbar"]
        assert treffer and treffer[0].details["regelname"] == "Gut lesbarer Name"

    def test_the_shipped_rules_keep_their_ids(self, regelordner):
        """Bestandsschutz: gespeicherte Befunde, die Triage-Zuordnung und die
        Mahnungsfelder zeigen auf diese acht."""
        ladung = laden(regelordner)
        for kennung in (
            "altersklasse_zu_jung",
            "ue32_limit",
            "geburtsdatum_unplausibel",
            "red_card",
            "yellow_red_card",
            "stammspieler_limit",
            "stammspieler_wartefrist",
            "spieltage_unbekannt",
        ):
            assert kennung in ladung.registry, kennung

    def test_every_shipped_rule_has_a_readable_name(self, regelordner):
        """Eine Regel ohne Anzeigenamen zeigt dem Nutzer ihre ID — und
        „ue32_limit" sagt niemandem etwas."""
        for regel in laden(regelordner).registry:
            assert regel.name, regel.id
            assert regel.name != regel.id, f"{regel.id} hat keinen eigenen Namen"


def test_every_shipped_rule_file_actually_parses():
    """Dreimal in einer Nacht dieselbe Falle: ein deutsches Anführungszeichen
    „…" schließt eine Zeichenkette nicht, ein ASCII-" schon.

    `"Rote Karte — „in jedem Falle …".",` ist deshalb ein Syntaxfehler, und der
    kostet die ganze Datei — jede Regel darin wäre weg. Ein Fehlerbefund je
    Spiel würde es melden, aber erst nach dem Ausliefern.
    """
    import ast

    from homepi_pruefdienst.regelwerk.lader import VORLAGEN

    for pfad in sorted(VORLAGEN.glob("*.py")):
        quelle = pfad.read_text(encoding="utf-8")
        try:
            ast.parse(quelle, filename=str(pfad))
        except SyntaxError as fehler:
            raise AssertionError(f"{pfad.name} Zeile {fehler.lineno}: {fehler.msg}") from fehler


def test_the_shipped_rules_all_load_without_an_error():
    """Der Gegenprobe zum Syntaxtest: eine Datei kann fehlerfrei geparst werden
    und trotzdem beim Laden scheitern — doppelte Kennung, unbekannte Schwere,
    fehlendes bagatelle."""
    import tempfile
    from pathlib import Path

    ordner = Path(tempfile.mkdtemp()) / "regeln"
    vorlagen_ausrollen(ordner)
    ladung = laden(ordner)
    assert ladung.fehler == {}, ladung.fehler
    assert ladung.anzahl >= 11


class TestKeineEigeneMannschaft:
    """Eine Mannschaft ist nie höherklassig als sie selbst.

    An echten Daten aufgefallen, bevor es jemanden traf: für „SG Gittersee"
    wurde „SG Gittersee" als höhere Mannschaft abgeleitet. Damit zählte jeder
    Einsatz der eigenen Elf als Einsatz oben, und die Wartefrist schlug bei
    jedem an, der vorige Woche gespielt hatte — 20 Befunde auf 15 Spiele.

    Der Grund steckt in `_ranks_higher`: ein Name ohne Zahl ist die erste
    Mannschaft des Vereins und damit „höher als jede nummerierte". Vergleicht
    man sie mit sich selbst, kommt dieselbe Antwort heraus.
    """

    def _spiel(self, teamname, oben):
        report = bericht(
            [spieler("Max", "01.01.1990", einsaetze=[einsatz("2026-09-13", oben, spieltag=3)])]
        )
        report.meta.home_team = teamname
        report.home_squad.team_name = teamname
        return uebersetzen(report, staffel())

    def test_a_first_team_is_not_its_own_higher_team(self):
        elf = self._spiel("SG Gittersee", "SG Gittersee").heim_mannschaft
        assert "SG Gittersee" not in elf.hoehere

    def test_a_reserve_team_still_finds_the_first_one(self):
        """Die Ableitung soll ja etwas finden — nur nicht sich selbst."""
        elf = self._spiel("TSV Boxdorf 2", "TSV Boxdorf").heim_mannschaft
        assert "TSV Boxdorf" in elf.hoehere

    def test_a_configured_list_is_cleaned_too(self):
        """Auch die gepflegte Liste kann den eigenen Namen enthalten — durch
        einen Tippfehler im Dialog oder durch eine Initialisierung, die den
        Verein zweimal sah."""
        report = bericht([spieler("Max", "01.01.1990")])
        spiel = uebersetzen(
            report,
            staffel(hoehere_mannschaften=["SV Loschwitz 2", "SV Loschwitz"]),
        )
        elf = spiel.heim_mannschaft  # heißt „SV Loschwitz 2"
        assert "SV Loschwitz 2" not in elf.hoehere
        assert "SV Loschwitz" in elf.hoehere

    def test_the_waiting_period_stays_quiet_for_ones_own_matches(self, regelordner):
        """Der gemeldete Fall, von der Regel her."""
        report = bericht(
            [
                spieler(
                    "Max",
                    "01.01.1990",
                    einsaetze=[einsatz("2026-09-13", "SG Gittersee", spieltag=3)],
                )
            ]
        )
        report.meta.home_team = "SG Gittersee"
        report.home_squad.team_name = "SG Gittersee"
        verstoesse = pruefe(report, staffel(), regelordner)
        assert "stammspieler_wartefrist" not in regeln_von(verstoesse)
