"""Welche Regeln abgeschaltet sind.

Der Schalter steht in einer eigenen Datei neben den Regeln und **nicht** in
der Regeldatei selbst: die gehört dem Staffelleiter, und ein Programm, das
darin herumschreibt, zerstört früher oder später eine Anpassung.

Die Zusicherung, auf die es hier ankommt: eine abgeschaltete Regel ist nicht
dasselbe wie eine gelöschte. Sie bleibt zählbar, und eine kaputte Schalterdatei
schaltet **nichts** ab — lieber eine Regel zu viel prüfen als eine zu wenig.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homepi_pruefdienst.regelwerk import schalter


@pytest.fixture
def datei(tmp_path: Path) -> Path:
    return tmp_path / "abgeschaltet.yaml"


class TestUmschalten:
    def test_abschalten_und_wieder_an(self, datei: Path) -> None:
        stand = schalter.umschalten("ue32_limit", aktiv=False, pfad=datei)
        assert "ue32_limit" in stand
        assert "ue32_limit" in schalter.laden(datei)

        stand = schalter.umschalten("ue32_limit", aktiv=True, pfad=datei)
        assert stand == {}
        assert schalter.laden(datei) == {}

    def test_das_datum_der_abschaltung_steht_dabei(self, datei: Path) -> None:
        """Damit in der Übersicht steht, seit wann hier nichts mehr geprüft
        wird."""
        stand = schalter.umschalten("red_card", aktiv=False, pfad=datei)

        assert stand["red_card"]


class TestLaden:
    def test_ohne_datei_ist_nichts_abgeschaltet(self, datei: Path) -> None:
        assert schalter.laden(datei) == {}

    def test_eine_liste_von_hand_ist_auch_gueltig(self, datei: Path) -> None:
        """Ohne Datum, je Zeile eine Kennung — so schreibt es ein Mensch."""
        datei.write_text("- red_card\n- ue32_limit\n", encoding="utf-8")

        assert schalter.laden(datei) == {"red_card": "", "ue32_limit": ""}

    def test_kaputtes_yaml_schaltet_nichts_ab(self, datei: Path) -> None:
        """Lieber eine Regel zu viel prüfen als eine zu wenig."""
        datei.write_text("dies: [ist: kein\n  gueltiges yaml\n", encoding="utf-8")

        assert schalter.laden(datei) == {}

    def test_etwas_ganz_anderes_ebenso(self, datei: Path) -> None:
        datei.write_text("42\n", encoding="utf-8")

        assert schalter.laden(datei) == {}

    def test_leere_kennungen_fallen_weg(self, datei: Path) -> None:
        datei.write_text("'': 2026-09-01\nred_card: 2026-09-01\n", encoding="utf-8")

        assert schalter.laden(datei) == {"red_card": "2026-09-01"}


class TestSpeichern:
    def test_der_kopf_erklaert_die_datei(self, datei: Path) -> None:
        """Wer sie von Hand aufmacht, soll nicht raten müssen."""
        schalter.speichern({"red_card": "2026-09-01"}, datei)

        text = datei.read_text(encoding="utf-8")
        assert text.startswith("# Abgeschaltete Regeln")
        assert "red_card" in text

    def test_leer_bleibt_lesbar(self, datei: Path) -> None:
        schalter.speichern({}, datei)

        assert schalter.laden(datei) == {}

    def test_der_ordner_wird_angelegt(self, tmp_path: Path) -> None:
        ziel = tmp_path / "gibt" / "es" / "noch" / "nicht" / "abgeschaltet.yaml"

        schalter.speichern({"red_card": "2026-09-01"}, ziel)

        assert ziel.is_file()


def test_ohne_pfad_liegt_sie_beim_regelordner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUEFDIENST_REGELN", "/tmp/regeln")

    assert schalter.datei().name == "abgeschaltet.yaml"
    assert schalter.datei().parent.name == "regeln"
