"""Wer spielen durfte — §§ 55, 56, 59 (7) und (8), 67 SpO SFV.

Bis hierher las das Programm das Spielrecht aus den DFBnet-Kennzeichen am
Namen ab („gesperrt", „nicht spielberechtigt") — aus Text also, den jemand
gesetzt haben muss und der in der Aufstellung gar nicht immer erscheint.

Die Aufstellungsschnittstelle führt dieselbe Frage als Felder:

    eligibleForTeam, eligibleForClub      darf für diese Mannschaft/diesen Verein
    beginDateForCompetitiveMatches        ab wann Pflichtspiele
    championshipEligibilityFrom           ab wann Meisterschaftsspiele
    noChampionshipEligibility             gar kein Meisterschaftsspielrecht
    guestEligibility                      nur Gastspielgenehmigung
    secondEligibility                     Zweitspielrecht
    suspensionLineUpError                 DFBnets eigener Sperrvermerk

Alle sieben waren am 2. Spieltag 2026/27 über 284 Personen hinweg sauber. Die
Regeln darauf melden also nichts, solange nichts ist — und sie melden es
sofort, wenn doch.

`None` heißt auch hier: nicht bekannt. Ältere gespeicherte Berichte und die
DOM-Rückfallebene kennen die Felder nicht, und Unwissen ist kein Verstoß.
"""

from datetime import date

import pytest

from homepi_pruefdienst import katalog as regelbruecke
from homepi_pruefdienst.aufstellung import spieler_aus_api as _api_player_to_raw
from homepi_pruefdienst.bericht import (
    MatchMeta,
    MatchReport,
    Player,
    SeasonAppearance,
    SeasonAppearances,
    SubEvent,
    TeamSquad,
)
from homepi_pruefdienst.regelwerk import vorlagen_ausrollen
from homepi_pruefdienst.regelwerk.uebersetzer import uebersetzen

from .hilfe import StaffelConfig
from .hilfe import spieler_aus_api as _spieler_aus_api

SPIELTAG = "04.09.2026"
KENNUNG = "ABC123"


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


def spieler(name, geburt="01.01.1990", **felder):
    grund = dict(
        name=name,
        pass_number=f"P-{name}",
        birthdate=geburt,
        jersey_number="7",
        photo_state="",
    )
    grund.update(felder)
    return Player(**grund)


def einsatz(datum, heim="A", gast="B", minuten=90, kennung="", wettbewerb="Meisterschaft"):
    return SeasonAppearance(
        match_id=kennung,
        kickoff=f"{datum}T15:00:00.000+02:00",
        home_team=heim,
        away_team=gast,
        division="3.Kreisliga (C)",
        competition=wettbewerb,
        minutes=minuten,
    )


def mit_historie(name, *auftritte, geburt="01.01.1990"):
    person = spieler(name, geburt=geburt)
    person.season_appearances = SeasonAppearances(count=len(auftritte), matches=list(auftritte))
    return person


def bericht(heim=(), gast=None, wechsel=(), wettbewerb="Meisterschaft", bank=()):
    if gast is None:
        # Die Gastmannschaft ist in diesen Tests nie der Prüfgegenstand — sie
        # muss aber regelkonform sein, sonst meldet jeder Test nebenbei den
        # fehlenden Spielführer des Gegners mit.
        gast = [spieler(f"G{i}", jersey_number=str(i + 1)) for i in range(11)]
        gast[0].is_captain = True
    return MatchReport(
        meta=MatchMeta(
            home_team="SV Loschwitz 2",
            away_team="SV Pillnitz",
            match_date=SPIELTAG,
            match_day="2",
            kickoff="15:00",
            league_class="3.Kreisliga (C)",
            competition=wettbewerb,
            match_id=KENNUNG,
        ),
        home_squad=TeamSquad(
            team="Heim",
            team_name="SV Loschwitz 2",
            starting_eleven=list(heim),
            bench=list(bank),
        ),
        away_squad=TeamSquad(team="Gast", team_name="SV Pillnitz", starting_eleven=list(gast)),
        substitutions=list(wechsel),
    )


def elf(erster=None, kapitaen=True):
    kader = [spieler(f"S{i}", jersey_number=str(i + 1)) for i in range(11)]
    if kapitaen:
        kader[0].is_captain = True
    if erster is not None:
        kader[0] = erster
        kader[0].is_captain = kapitaen
    return kader


def pruefe(report, ordner, konfig=None):
    return regelbruecke.pruefen(report, konfig or staffel(), ordner)


def regeln_von(verstoesse):
    return sorted(v.rule for v in verstoesse)


def befund(verstoesse, kennung):
    treffer = [v for v in verstoesse if v.rule == kennung]
    return treffer[0] if treffer else None


# ─────────────────────────────────────────────────────── was DFBnet liefert
class TestAusDerApi:
    def test_die_spielrechtsfelder_kommen_an(self):
        roh = _api_player_to_raw(
            {
                "lastName": "Neu",
                "firstName": "Ingo",
                "eligibleForTeam": False,
                "eligibleForClub": True,
                "noChampionshipEligibility": True,
                "championshipEligibilityFrom": "2026-10-01",
                "beginDateForCompetitiveMatches": "2026-09-20",
                "guestEligibility": True,
                "secondEligibility": True,
                "suspensionLineUpError": "Spieler ist gesperrt",
            }
        )
        assert roh["eligible_for_team"] is False
        assert roh["eligible_for_club"] is True
        assert roh["no_championship_eligibility"] is True
        assert roh["championship_from"] == "2026-10-01"
        assert roh["competitive_from"] == "2026-09-20"
        assert roh["guest_eligibility"] is True
        assert roh["second_eligibility"] is True
        assert roh["suspension_note"] == "Spieler ist gesperrt"

    def test_fehlende_felder_bleiben_unbekannt(self):
        """Eine Antwort ohne diese Felder ist keine Aussage über das Spielrecht."""
        roh = _api_player_to_raw({"lastName": "Alt"})
        assert roh["eligible_for_team"] is None
        assert roh["no_championship_eligibility"] is None
        assert roh["competitive_from"] == ""
        assert roh["suspension_note"] == ""

    def test_die_felder_ueberstehen_den_weg_in_den_bericht(self):
        """In der alten Anwendung lag dazwischen die Datenbank, hier der
        Extraktor. Die Frage ist dieselbe: kommt das Spielrecht unversehrt an?"""
        zurueck = _spieler_aus_api(
            {
                "lastName": "Neu",
                "eligibleForTeam": False,
                "beginDateForCompetitiveMatches": "2026-09-20",
                "suspensionLineUpError": "gesperrt",
            }
        )
        assert zurueck.eligible_for_team is False
        assert zurueck.competitive_from == "2026-09-20"
        assert zurueck.suspension_note == "gesperrt"


# ─────────────────────────────────────────────────────── Vokabeln der Regel
class TestVokabeln:
    def test_die_person_kennt_ihr_spielrecht(self):
        report = bericht(
            elf(
                spieler(
                    "Neu",
                    eligible_for_team=False,
                    competitive_from="2026-09-20",
                    championship_from="2026-10-01",
                    guest_eligibility=True,
                    second_eligibility=True,
                    suspension_note="gesperrt bis 30.09.2026",
                )
            )
        )
        person = uebersetzen(report, staffel()).heim_mannschaft.spieler[0]
        assert person.spielrecht_mannschaft is False
        assert person.pflichtspielrecht_ab == date(2026, 9, 20)
        assert person.meisterschaftsrecht_ab == date(2026, 10, 1)
        assert person.gastspielrecht is True
        assert person.zweitspielrecht is True
        assert person.sperrvermerk == "gesperrt bis 30.09.2026"

    def test_ohne_angabe_ist_alles_unbekannt(self):
        person = uebersetzen(bericht(elf()), staffel()).heim_mannschaft.spieler[0]
        assert person.spielrecht_mannschaft is None
        assert person.pflichtspielrecht_ab is None
        assert person.sperrvermerk == ""

    def test_der_spielfuehrer_ist_bekannt(self):
        report = bericht(elf())
        aufstellung = uebersetzen(report, staffel()).heim_mannschaft.startelf
        assert [p.ist_spielfuehrer for p in aufstellung].count(True) == 1

    def test_andere_einsaetze_am_selben_tag(self):
        """Das Spiel selbst steht in der eigenen Historie — es zählt nicht mit."""
        person = mit_historie(
            "Doppelt",
            einsatz("2026-09-04", kennung=KENNUNG),
            einsatz("2026-09-04", heim="C", gast="D", kennung="XYZ"),
            einsatz("2026-08-30", kennung="OLD"),
        )
        gelesen = uebersetzen(bericht(elf(person)), staffel())
        andere = gelesen.andere_einsaetze(gelesen.heim_mannschaft.spieler[0])
        assert len(andere) == 1
        assert andere[0].heim == "C"

    def test_das_eigene_spiel_wird_auch_ohne_passende_kennung_erkannt(self):
        """Spielbericht und Einsatzhistorie führen verschiedene Kennungen.

        Der Bericht trägt die Spielnummer aus der Spielliste (633203004), die
        Historie die technische Kennung des Spiels (031DHM04MS…). Über die
        Kennung allein zählte sich jedes Spiel selbst mit — und meldete jeden
        Spieler, der ein zweites Mal auf dem Platz stand, als Doppeleinsatz.
        """
        person = mit_historie(
            "Einmal",
            einsatz(
                "2026-09-04",
                heim="SV Loschwitz 2",
                gast="SV Pillnitz",
                kennung="031DHM04MS000000",
            ),
        )
        gelesen = uebersetzen(bericht(elf(person)), staffel())
        assert gelesen.andere_einsaetze(gelesen.heim_mannschaft.spieler[0]) == ()


# ───────────────────────────────────────────────── § 56 (1) und (3): Spielrecht
class TestSpielrecht:
    def test_ein_sauberer_kader_ist_still(self, regelordner):
        kader = elf(
            spieler(
                "Sauber",
                eligible_for_team=True,
                eligible_for_club=True,
                no_championship_eligibility=False,
                competitive_from="2020-01-01",
                guest_eligibility=False,
                second_eligibility=False,
            )
        )
        namen = regeln_von(pruefe(bericht(kader), regelordner))
        assert "spielrecht_fehlt" not in namen
        assert "pflichtspielrecht_spaeter" not in namen
        assert "meisterschaftsrecht_fehlt" not in namen
        assert "gastspielrecht_im_pflichtspiel" not in namen

    def test_kein_spielrecht_fuer_diese_mannschaft(self, regelordner):
        kader = elf(spieler("Fremd", eligible_for_team=False))
        treffer = befund(pruefe(bericht(kader), regelordner), "spielrecht_fehlt")
        assert treffer is not None
        assert "Fremd" in treffer.message

    def test_kein_spielrecht_fuer_den_verein(self, regelordner):
        kader = elf(spieler("Fremd", eligible_for_club=False))
        assert "spielrecht_fehlt" in regeln_von(pruefe(bericht(kader), regelordner))

    def test_pflichtspielrecht_beginnt_erst_nach_dem_spiel(self, regelordner):
        """Der klassische Vereinswechsel: der Pass ist da, das Spielrecht noch nicht."""
        kader = elf(spieler("Neu", competitive_from="2026-09-20"))
        treffer = befund(pruefe(bericht(kader), regelordner), "pflichtspielrecht_spaeter")
        assert treffer is not None
        assert "20.09.2026" in treffer.message

    def test_am_ersten_tag_des_spielrechts_ist_es_da(self, regelordner):
        kader = elf(spieler("Neu", competitive_from="2026-09-04"))
        assert "pflichtspielrecht_spaeter" not in regeln_von(pruefe(bericht(kader), regelordner))

    def test_gar_kein_meisterschaftsspielrecht(self, regelordner):
        kader = elf(spieler("Ohne", no_championship_eligibility=True))
        treffer = befund(pruefe(bericht(kader), regelordner), "meisterschaftsrecht_fehlt")
        assert treffer is not None

    def test_meisterschaftsspielrecht_beginnt_spaeter(self, regelordner):
        kader = elf(spieler("Neu", championship_from="2026-10-01"))
        assert "meisterschaftsrecht_fehlt" in regeln_von(pruefe(bericht(kader), regelordner))

    def test_im_pokal_wird_das_meisterschaftsrecht_nicht_verlangt(self, regelordner):
        """`noChampionshipEligibility` sagt etwas über Meisterschaftsspiele.

        Im Pokal daraus einen Verstoß zu machen hieße, eine Vorschrift auf
        einen Wettbewerb anzuwenden, für den sie nicht geschrieben ist.
        """
        kader = elf(spieler("Ohne", no_championship_eligibility=True))
        namen = regeln_von(pruefe(bericht(kader, wettbewerb="Kreispokal Herren"), regelordner))
        assert "meisterschaftsrecht_fehlt" not in namen


# ─────────────────────────────────────────────────────── § 59 (8) a): Sperre
class TestSperrvermerk:
    def test_dfbnet_meldet_einen_gesperrten_spieler(self, regelordner):
        """§ 59 (8) a): während einer Sperrfrist nicht spielberechtigt.

        Der Vermerk kommt aus DFBnet selbst. Die eigene Tabelle `sperren` ist
        lückenhaft; dieses Feld ist es nicht.
        """
        kader = elf(spieler("Gesperrt", suspension_note="Spieler ist gesperrt"))
        treffer = befund(pruefe(bericht(kader), regelordner), "sperrvermerk_dfbnet")
        assert treffer is not None
        assert "Gesperrt" in treffer.message
        assert "Spieler ist gesperrt" in treffer.message

    def test_ohne_vermerk_kein_befund(self, regelordner):
        assert "sperrvermerk_dfbnet" not in regeln_von(pruefe(bericht(elf()), regelordner))


# ───────────────────────────────────────────────── § 67 (1) und (5): Gastspiel
class TestGastspielrecht:
    def test_gastspielgenehmigung_im_meisterschaftsspiel(self, regelordner):
        """§ 67 (1): Gastspielgenehmigung nur für Freundschaftsspiele."""
        kader = elf(spieler("Gast", guest_eligibility=True))
        treffer = befund(pruefe(bericht(kader), regelordner), "gastspielrecht_im_pflichtspiel")
        assert treffer is not None
        assert "Gast" in treffer.message

    def test_im_freundschaftsspiel_ist_sie_zulaessig(self, regelordner):
        kader = elf(spieler("Gast", guest_eligibility=True))
        namen = regeln_von(pruefe(bericht(kader, wettbewerb="Freundschaftsspiel"), regelordner))
        assert "gastspielrecht_im_pflichtspiel" not in namen


# ──────────────────────────────────────────── § 56 (6): zwei Spiele an einem Tag
class TestZweiSpieleAmTag:
    """§ 56 (6): „Alle Spieler, die das 18. Lebensjahr … vollendet haben, dürfen
    am gleichen Kalendertag in zwei Spielen eingesetzt werden. Alle anderen
    Spieler/Spielerinnen dürfen am gleichen Tag nur in einem Spiel/einem
    Turnier eingesetzt werden."
    """

    def test_ein_erwachsener_darf_zweimal_spielen(self, regelordner):
        person = mit_historie(
            "Zweimal",
            einsatz("2026-09-04", kennung=KENNUNG),
            einsatz("2026-09-04", heim="C", gast="D", kennung="XYZ"),
        )
        assert "zwei_spiele_am_tag" not in regeln_von(pruefe(bericht(elf(person)), regelordner))

    def test_ein_erwachsener_nicht_dreimal(self, regelordner):
        person = mit_historie(
            "Dreimal",
            einsatz("2026-09-04", kennung=KENNUNG),
            einsatz("2026-09-04", heim="C", gast="D", kennung="XYZ"),
            einsatz("2026-09-04", heim="E", gast="F", kennung="UVW"),
        )
        treffer = befund(pruefe(bericht(elf(person)), regelordner), "zwei_spiele_am_tag")
        assert treffer is not None
        assert "Dreimal" in treffer.message

    def test_ein_siebzehnjaehriger_darf_nur_einmal(self, regelordner):
        person = mit_historie(
            "Jung",
            einsatz("2026-09-04", kennung=KENNUNG),
            einsatz("2026-09-04", heim="C", gast="D", kennung="XYZ"),
            geburt="01.01.2009",
        )
        assert "zwei_spiele_am_tag" in regeln_von(pruefe(bericht(elf(person)), regelordner))

    def test_auf_dem_bogen_zu_stehen_ist_kein_einsatz(self, regelordner):
        """§ 56 (6) spricht von „eingesetzt". Ohne Spielminuten war niemand im
        Spiel — sonst meldete jeder Ersatzspieler eines Parallelspiels."""
        person = mit_historie(
            "Jung",
            einsatz("2026-09-04", kennung=KENNUNG),
            einsatz("2026-09-04", heim="C", gast="D", kennung="XYZ", minuten=0),
            geburt="01.01.2009",
        )
        assert "zwei_spiele_am_tag" not in regeln_von(pruefe(bericht(elf(person)), regelordner))


# ───────────────────────────────────────────── § 59 (7): Zahl der Wechselspieler
class TestEinwechslungen:
    """§ 59 (7): „im Spielbetrieb der Herren und Frauen bis zu fünf
    Wechselspieler". Im Senioren- und Breitensport sowie in
    Freundschaftsspielen ist die Ein- und Auswechslung unbegrenzt.
    """

    def bank(self, anzahl):
        return [spieler(f"E{i}") for i in range(anzahl)]

    def wechsel(self, anzahl):
        return [
            SubEvent(minute=str(50 + i), team="home", player_in=f"E{i}", player_out=f"S{i}")
            for i in range(anzahl)
        ]

    def test_fuenf_sind_erlaubt(self, regelordner):
        report = bericht(elf(), wechsel=self.wechsel(5), bank=self.bank(5))
        assert "einwechslungen_zu_viele" not in regeln_von(pruefe(report, regelordner))

    def test_sechs_sind_zu_viele(self, regelordner):
        report = bericht(elf(), wechsel=self.wechsel(6), bank=self.bank(6))
        treffer = befund(pruefe(report, regelordner), "einwechslungen_zu_viele")
        assert treffer is not None
        assert "6" in treffer.message

    def test_derselbe_spieler_zweimal_zaehlt_einmal(self, regelordner):
        """Unterhalb der Kreisoberligen darf wieder eingewechselt werden.

        § 59 (7) begrenzt die Zahl der *Wechselspieler*, nicht die der
        Wechselvorgänge — wer zweimal kommt, ist eine Person.
        """
        wechsel = self.wechsel(5) + [
            SubEvent(minute="80", team="home", player_in="E0", player_out="S9")
        ]
        report = bericht(elf(), wechsel=wechsel, bank=self.bank(5))
        assert "einwechslungen_zu_viele" not in regeln_von(pruefe(report, regelordner))

    def test_im_seniorenbereich_gibt_es_keine_grenze(self, regelordner):
        report = bericht(elf(), wechsel=self.wechsel(8), bank=self.bank(8))
        konfig = staffel(name="Ü35 2. Stadtklasse", altersklasse="ue35")
        assert "einwechslungen_zu_viele" not in regeln_von(pruefe(report, regelordner, konfig))

    def test_im_freundschaftsspiel_gibt_es_keine_grenze(self, regelordner):
        report = bericht(
            elf(),
            wechsel=self.wechsel(8),
            bank=self.bank(8),
            wettbewerb="Freundschaftsspiel",
        )
        assert "einwechslungen_zu_viele" not in regeln_von(pruefe(report, regelordner))


# ──────────────────────────────────────────────────────── § 55 (1): Spielführer
class TestSpielfuehrer:
    """§ 55 (1): „Der Spielführer ist auf dem Spielbericht zu benennen.""" ""

    def test_eine_elf_mit_spielfuehrer_ist_still(self, regelordner):
        assert "spielfuehrer_fehlt" not in regeln_von(pruefe(bericht(elf()), regelordner))

    def test_ohne_spielfuehrer_wird_gemeldet(self, regelordner):
        report = bericht(elf(kapitaen=False))
        treffer = befund(pruefe(report, regelordner), "spielfuehrer_fehlt")
        assert treffer is not None
        assert "SV Loschwitz 2" in treffer.message

    def test_eine_leere_aufstellung_meldet_nichts(self, regelordner):
        """Ein Spielbericht ohne Aufstellung ist ein anderes Problem, und
        `mannschaftsstaerke` meldet es bereits. Zweimal dasselbe zu melden
        macht die Liste länger, nicht klarer."""
        report = bericht([], gast=[])
        assert "spielfuehrer_fehlt" not in regeln_von(pruefe(report, regelordner))
