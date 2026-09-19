"""Widerspricht sich der Spielbericht selbst?

Zwei Prüfungen, die keine Vorschrift zitieren, sondern den Bogen gegen sich
selbst halten. Beide hängen an etwas, das sonst still danebengeht:

* **Ergebnis gegen Torfolge.** Ein falsch eingetragenes Ergebnis wandert
  ungeprüft in die Tabelle.
* **Karte ohne Person.** Der Verwarnungszähler hängt an der Passnummer, und
  die kommt aus der Aufstellung. Steht der Name im Spielverlauf anders als in
  der Aufstellung, findet ihn niemand — die Karte zählt dann für niemanden,
  und die fünfte Verwarnung kommt nie.

Der zweite Fall ist der Grund, warum `spiel.karten` hier nicht genügt: die
Liste entsteht aus den Personen, eine unzuordenbare Karte steht gar nicht
darin. Dafür gibt es `spiel.alle_karten`.
"""

import pytest

from homepi_pruefdienst import katalog as regelbruecke
from homepi_pruefdienst.bericht import (
    CardEvent,
    GoalEvent,
    MatchMeta,
    MatchReport,
    Player,
    TeamSquad,
)
from homepi_pruefdienst.regelwerk import vorlagen_ausrollen
from homepi_pruefdienst.regelwerk.uebersetzer import uebersetzen

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


def spieler(name, nummer):
    return Player(
        name=name, pass_number=f"P-{name}", birthdate="01.01.1990", jersey_number=str(nummer)
    )


def elf(praefix):
    kader = [spieler(f"{praefix}{i}", i + 1) for i in range(11)]
    kader[0].is_captain = True
    return kader


def tor(minute, seite, schuetze):
    return GoalEvent(minute=str(minute), team=seite, scorer=schuetze)


def karte(minute, seite, person, art="Gelbe Karte"):
    return CardEvent(minute=str(minute), team=seite, player=person, card_type=art)


def bericht(ergebnis="2 : 1", tore=(), karten=(), wettbewerb="Meisterschaft", vorkommnisse=None):
    return MatchReport(
        meta=MatchMeta(
            home_team="SV Loschwitz 2",
            away_team="SV Pillnitz",
            match_date="04.09.2026",
            match_day="2",
            kickoff="15:00",
            league_class="3.Kreisliga (C)",
            competition=wettbewerb,
            match_id="ABC123",
            result=ergebnis,
        ),
        home_squad=TeamSquad(team="Heim", team_name="SV Loschwitz 2", starting_eleven=elf("H")),
        away_squad=TeamSquad(team="Gast", team_name="SV Pillnitz", starting_eleven=elf("G")),
        goals=list(tore),
        cards=list(karten),
        incidents_details=(vorkommnisse or {}),
    )


def pruefe(report, ordner):
    return regelbruecke.pruefen(report, staffel(), ordner)


def regeln_von(verstoesse):
    return sorted(v.rule for v in verstoesse)


def befund(verstoesse, kennung):
    treffer = [v for v in verstoesse if v.rule == kennung]
    return treffer[0] if treffer else None


DREI_TORE = (tor(10, "home", "H1"), tor(20, "home", "H2"), tor(80, "away", "G1"))


class TestVokabeln:
    def test_das_ergebnis_wird_in_zahlen_gelesen(self):
        spiel = uebersetzen(bericht(ergebnis="5 : 3"), staffel())
        assert spiel.ergebnis_tore == (5, 3)

    def test_ein_unlesbares_ergebnis_ist_none(self):
        assert uebersetzen(bericht(ergebnis="n. a."), staffel()).ergebnis_tore is None

    def test_die_tore_stehen_bei_ihrer_mannschaft(self):
        spiel = uebersetzen(bericht(tore=DREI_TORE), staffel())
        assert len(spiel.tore) == 3
        assert [t.mannschaft for t in spiel.tore].count("SV Loschwitz 2") == 2

    def test_alle_karten_enthaelt_auch_die_unzuordenbaren(self):
        report = bericht(karten=(karte(30, "home", "Wer Auch Immer"),))
        spiel = uebersetzen(report, staffel())
        assert spiel.karten == []  # keiner Person zugeordnet
        assert len(spiel.alle_karten) == 1  # im Verlauf steht sie trotzdem


class TestErgebnis:
    def test_ein_stimmiges_ergebnis_ist_still(self, regelordner):
        report = bericht(ergebnis="2 : 1", tore=DREI_TORE)
        assert "ergebnis_widerspricht_toren" not in regeln_von(pruefe(report, regelordner))

    def test_ein_fehlendes_tor_wird_gemeldet(self, regelordner):
        report = bericht(ergebnis="3 : 1", tore=DREI_TORE)
        treffer = befund(pruefe(report, regelordner), "ergebnis_widerspricht_toren")
        assert treffer is not None
        assert "3 : 1" in treffer.message
        assert "4 Tore" in treffer.message

    def test_ein_eigentor_ist_kein_widerspruch(self, regelordner):
        """SG Gittersee – SG Weixdorf 3 vom 30.08.2026, echter Fall.

        Ergebnis 2:0, im Verlauf je ein Treffer pro Seite: das Eigentor führt
        DFBnet bei der Mannschaft des Schützen, gezählt wird es für die
        andere. Verglichen wird deshalb die Gesamtzahl der Tore und nicht die
        Verteilung — sonst meldete jedes Spiel mit einem Eigentor.
        """
        report = bericht(
            ergebnis="2 : 0",
            tore=(tor(9, "away", "G1"), tor(11, "home", "H1")),
        )
        assert "ergebnis_widerspricht_toren" not in regeln_von(pruefe(report, regelordner))

    def test_ohne_torfolge_wird_nichts_behauptet(self, regelordner):
        """Ein Spielverlauf ohne Tore ist ein leerer Bogen, kein 0:0."""
        report = bericht(ergebnis="3 : 1", tore=())
        assert "ergebnis_widerspricht_toren" not in regeln_von(pruefe(report, regelordner))

    def test_nach_einem_abbruch_gilt_die_wertung_nicht_die_torfolge(self, regelordner):
        report = bericht(
            ergebnis="0 : 3",
            tore=DREI_TORE + (tor(85, "home", "H4"),),
            vorkommnisse={"checked_labels": ["Spielabbruch"]},
        )
        assert "ergebnis_widerspricht_toren" not in regeln_von(pruefe(report, regelordner))

    def test_im_pokal_kann_ein_elfmeterschiessen_dazwischenkommen(self, regelordner):
        report = bericht(ergebnis="5 : 4", tore=DREI_TORE, wettbewerb="Kreispokal Herren")
        assert "ergebnis_widerspricht_toren" not in regeln_von(pruefe(report, regelordner))


class TestKarteOhnePerson:
    def test_eine_zugeordnete_karte_ist_still(self, regelordner):
        report = bericht(tore=DREI_TORE, karten=(karte(30, "home", "H3"),))
        assert "karte_ohne_person" not in regeln_von(pruefe(report, regelordner))

    def test_eine_karte_fuer_einen_unbekannten_namen(self, regelordner):
        """Genau hier verschwindet sonst eine Verwarnung: der Zähler hängt an
        der Passnummer, und die kommt aus der Aufstellung."""
        report = bericht(tore=DREI_TORE, karten=(karte(30, "home", "Mueller, Fritz"),))
        treffer = befund(pruefe(report, regelordner), "karte_ohne_person")
        assert treffer is not None
        assert "Mueller, Fritz" in treffer.message
