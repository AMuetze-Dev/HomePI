"""``homepi schema`` - das Startwerkzeug fuer die Tabellen.

Ohne diesen Befehl gaebe es auf dem Pi keinen Weg, das Schema beim ersten
Deploy anzulegen: in Produktion steht DB_SCHEMA_ANLEGEN auf false.

Was hier ohne Datenbank pruefbar ist: die Argumente und dass wirklich alle
Tabellen gefunden werden - auch die der Anmeldung, die kein Artefakt mitbringt.
"""

from __future__ import annotations

import pytest

from homepi_core.cli import schema
from homepi_core.cli.main import _parser
from homepi_core.cli.shell import CliFehler


class TestArgumente:
    def test_unterbefehl_ist_pflicht(self) -> None:
        with pytest.raises(SystemExit):
            _parser().parse_args(["schema"])

    def test_anlegen_kennt_den_trockenlauf(self) -> None:
        # Erst sehen, was entsteht, dann entstehen lassen.
        args = _parser().parse_args(["schema", "anlegen", "--trocken"])

        assert args.unterbefehl == "anlegen"
        assert args.trocken is True

    def test_anlegen_ohne_trockenlauf(self) -> None:
        assert _parser().parse_args(["schema", "anlegen"]).trocken is False

    def test_zeigen_braucht_nichts_weiter(self) -> None:
        assert _parser().parse_args(["schema", "zeigen"]).unterbefehl == "zeigen"


class TestDatenbankUrl:
    def test_fehlende_url_nennt_den_befehl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(CliFehler, match="DATABASE_URL"):
            schema._datenbank_url()


class TestBekannteTabellen:
    def test_die_anmeldung_ist_immer_dabei(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sie kommt aus homepi-core und nicht aus einem Artefakt - ohne den
        ausdruecklichen Import fehlte sie genau dann, wenn kein Artefakt
        installiert ist."""
        monkeypatch.setattr("homepi_core.modules.entry_points", lambda group: [])

        tabellen = schema._bekannte_tabellen()

        assert {"benutzer", "benutzer_rechte", "sitzungen"} <= set(tabellen)

    def test_ein_defektes_artefakt_wird_gemeldet(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Sonst fehlten dessen Tabellen still - und der Fehler faellt erst
        auf, wenn jemand das Artefakt benutzt."""

        class _Kaputt:
            name = "kaputt"

            def load(self) -> object:
                raise ImportError("kein pandas")

        monkeypatch.setattr("homepi_core.modules.entry_points", lambda group: [_Kaputt()])

        schema._bekannte_tabellen()

        assert "kaputt" in capsys.readouterr().out
