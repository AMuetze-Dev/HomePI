"""Die Brücke: Regeldateien hinein, Befunde in unserer Form heraus.

Die Zusicherungen hier sind alle von derselben Sorte: **ein Ausfall muss
lauter sein als ein Fund.** Ein Spiel ohne Befunde sieht in der Warteschlange
aus wie ein sauberes — und genau so verschwindet eine Prüfung, ohne dass es
jemand merkt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homepi_pruefdienst import katalog
from homepi_pruefdienst.bericht import MatchMeta, MatchReport, Player, TeamSquad
from homepi_pruefdienst.regelwerk import auskunft


@pytest.fixture(autouse=True)
def frisch() -> None:
    """Der Zwischenspeicher ist prozessweit — sonst sieht ein Test die Regeln
    des vorigen."""
    katalog.zuruecksetzen()


def elf(name: str) -> TeamSquad:
    """Elf Spieler ohne Spielfuehrer -- damit ueberhaupt eine Regel anspricht.

    Ein leerer Kader waere fuer die Regeln *unbekannt*, und dann faende auch
    eine heile Regel nichts: der Test wuerde gruen, ohne etwas zu zeigen.
    """
    return TeamSquad(
        team_name=name,
        starting_eleven=[
            Player(name=f"S{i}", pass_number=f"P{i}", jersey_number=str(i + 1)) for i in range(11)
        ],
    )


def bericht() -> MatchReport:
    return MatchReport(
        meta=MatchMeta(
            match_id="M-1",
            home_team="SV Loschwitz 2",
            away_team="SV Blasewitz",
            match_date="13.06.2026",
        ),
        home_squad=elf("SV Loschwitz 2"),
        away_squad=elf("SV Blasewitz"),
    )


class TestOhneRegeln:
    def test_wenn_nichts_geladen_wurde_ist_das_ein_lauter_befund(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Kein Schreibrecht, nichts ausgerollt: dreißig Regeln sind weg, und
        der Bericht sähe geprüft aus."""
        leer = tmp_path / "leer"
        leer.mkdir()
        monkeypatch.setattr(katalog, "laden", lambda ordner: katalog.Ladung(ordner=ordner))

        verstoesse = katalog.pruefen(bericht(), ordner=leer)

        assert [v.rule for v in verstoesse] == ["regel_fehlerhaft"]
        assert verstoesse[0].severity.value == "critical"
        assert "keine einzige Regel" in verstoesse[0].message

    def test_ein_leerer_ordner_bekommt_die_vorlagen(self, tmp_path: Path) -> None:
        """Er ist der Normalfall beim ersten Start und darf kein Fehler sein."""
        leer = tmp_path / "leer"
        leer.mkdir()

        verstoesse = katalog.pruefen(bericht(), ordner=leer)

        assert "regel_fehlerhaft" not in {v.rule for v in verstoesse}
        assert len(list(leer.glob("*.py"))) >= 9


class TestMitRegeln:
    def test_die_vorlagen_werden_ausgerollt_und_laufen(self, tmp_path: Path) -> None:
        ordner = tmp_path / "regeln"

        katalog.pruefen(bericht(), ordner=ordner)

        assert len(list(ordner.glob("*.py"))) >= 9
        assert katalog.regeln(ordner).anzahl >= 30

    def test_eine_abgeschaltete_regel_laeuft_nicht(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ordner = tmp_path / "regeln"
        monkeypatch.setenv("PRUEFDIENST_REGELN", str(ordner))
        vorher = {v.rule for v in katalog.pruefen(bericht(), ordner=ordner)}
        assert "spielfuehrer_fehlt" in vorher

        from homepi_pruefdienst.regelwerk import schalter

        schalter.umschalten("spielfuehrer_fehlt", aktiv=False)

        nachher = {v.rule for v in katalog.pruefen(bericht(), ordner=ordner)}
        assert "spielfuehrer_fehlt" not in nachher

    def test_eine_kaputte_datei_meldet_sich_und_die_anderen_laufen(self, tmp_path: Path) -> None:
        ordner = tmp_path / "regeln"
        katalog.pruefen(bericht(), ordner=ordner)
        (ordner / "99_kaputt.py").write_text("das ist kein Python", encoding="utf-8")
        katalog.zuruecksetzen()

        verstoesse = katalog.pruefen(bericht(), ordner=ordner)

        fehler = [v for v in verstoesse if v.rule == "regel_fehlerhaft"]
        assert fehler and "99_kaputt.py" in fehler[0].details["quelle"]
        assert len(verstoesse) > len(fehler)


class TestUebersetzung:
    def test_ein_bericht_der_sich_nicht_aufbereiten_laesst(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ohne Spiel läuft keine Regel — dann muss das dastehen und nicht
        eine leere Liste."""
        ordner = tmp_path / "regeln"
        katalog.pruefen(bericht(), ordner=ordner)

        def kaputt(*_: object, **__: object) -> None:
            raise RuntimeError("so nicht")

        monkeypatch.setattr(katalog, "uebersetzen", kaputt)
        verstoesse = katalog.pruefen(bericht(), ordner=ordner)

        assert [v.rule for v in verstoesse] == ["regel_fehlerhaft"]
        assert "so nicht" in verstoesse[0].message


class TestZwischenspeicher:
    def test_ohne_ordner_gibt_es_keinen_fingerabdruck(self, tmp_path: Path) -> None:
        assert katalog._fingerabdruck(tmp_path / "nichts") == ()

    def test_zwei_ordner_teilen_sich_nichts(self, tmp_path: Path) -> None:
        """Nur der Fingerabdruck als Schlüssel reichte nicht: zwei leere Ordner
        haben denselben (nämlich keinen), und der zweite bekam die Regeln des
        ersten."""
        eins = tmp_path / "eins"
        zwei = tmp_path / "zwei"

        assert katalog.regeln(eins).ordner == eins
        assert katalog.regeln(zwei).ordner == zwei


class TestAuskunft:
    def test_ohne_speicher_heisst_es_weiss_ich_nicht(self) -> None:
        """Eine 0 wäre eine Behauptung — „diese Person hat keine
        Verwarnungen" —, und eine Regel, die daraufhin schweigt, sähe aus, als
        hätte sie geprüft."""
        stumm = auskunft.Auskunft()

        assert stumm.verwarnungen("P1", "Meisterschaft") is None
        assert stumm.letzte_sperre("P1", "Meisterschaft") is None
