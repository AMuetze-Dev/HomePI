"""Die Benutzer-CLI.

Was hier ohne Datenbank prüfbar ist: die Argumente, die Passwortabfrage und
die Fehlermeldung bei fehlender DATABASE_URL. Alles Weitere prüft
tests/integration/test_auth.py gegen echtes Postgres.
"""

from __future__ import annotations

import io

import pytest

from homepi_core.cli import benutzer
from homepi_core.cli.main import _parser
from homepi_core.cli.shell import CliFehler


class TestArgumente:
    def test_unterbefehl_ist_pflicht(self) -> None:
        # Ohne wüsste die CLI nicht, was sie tun soll - argparse bricht ab.
        with pytest.raises(SystemExit):
            _parser().parse_args(["benutzer"])

    def test_anlegen_mit_recht(self) -> None:
        args = _parser().parse_args(
            ["benutzer", "anlegen", "aaron", "--artefakt", "staffelpilot", "--rolle", "verwalter"]
        )

        assert args.unterbefehl == "anlegen"
        assert args.name == "aaron"
        assert args.artefakt == "staffelpilot"
        assert args.rolle == "verwalter"

    def test_rolle_hat_einen_standard(self) -> None:
        args = _parser().parse_args(["benutzer", "anlegen", "aaron"])

        assert args.rolle == "nutzer"

    def test_erfundene_rolle_wird_abgelehnt(self) -> None:
        with pytest.raises(SystemExit):
            _parser().parse_args(["benutzer", "recht", "aaron", "x", "chefin"])

    def test_passwort_ist_kein_argument(self) -> None:
        """Als Argument landete es in der Shell-Historie und in der
        Prozessliste."""
        with pytest.raises(SystemExit):
            _parser().parse_args(["benutzer", "anlegen", "aaron", "--passwort", "geheim"])


class TestDatenbankUrl:
    def test_fehlende_url_nennt_den_befehl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(CliFehler, match="DATABASE_URL"):
            benutzer._datenbank_url()

    def test_vorhandene_url_wird_genommen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@z/db")

        assert benutzer._datenbank_url() == "postgresql+asyncpg://x:y@z/db"


class TestPasswortabfrage:
    def test_zweimal_gleich_wird_angenommen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(benutzer.getpass, "getpass", lambda _: "korrekt-pferd-batterie")

        assert benutzer._passwort_erfragen("aaron") == "korrekt-pferd-batterie"

    def test_tippfehler_fuehrt_zu_neuem_versuch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eingaben = iter(
            [
                "erstes-langes-passwort",
                "zweites-langes-passwort",
                "gleiches-langes-passwort",
                "gleiches-langes-passwort",
            ]
        )
        monkeypatch.setattr(benutzer.getpass, "getpass", lambda _: next(eingaben))

        assert benutzer._passwort_erfragen("aaron") == "gleiches-langes-passwort"

    def test_untaugliches_passwort_fuehrt_zu_neuem_versuch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        eingaben = iter(["kurz", "kurz", "jetzt-aber-lang-genug", "jetzt-aber-lang-genug"])
        monkeypatch.setattr(benutzer.getpass, "getpass", lambda _: next(eingaben))

        assert benutzer._passwort_erfragen("aaron") == "jetzt-aber-lang-genug"

    def test_nach_drei_versuchen_abbruch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Sonst haengt die CLI in einem Skript endlos.
        monkeypatch.setattr(benutzer.getpass, "getpass", lambda _: "kurz")

        with pytest.raises(CliFehler, match="Dreimal"):
            benutzer._passwort_erfragen("aaron")

    def test_passwort_darf_den_benutzernamen_nicht_enthalten(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        eingaben = iter(
            [
                "aaron-und-noch-mehr",
                "aaron-und-noch-mehr",
                "voellig-anderes-wort",
                "voellig-anderes-wort",
            ]
        )
        monkeypatch.setattr(benutzer.getpass, "getpass", lambda _: next(eingaben))

        assert benutzer._passwort_erfragen("aaron") == "voellig-anderes-wort"


class TestFehlerbehandlung:
    def test_ohne_datenbank_url_meldet_die_cli_verstaendlich(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from homepi_core.cli.main import main

        monkeypatch.delenv("DATABASE_URL", raising=False)

        assert main(["benutzer", "liste"]) == 1
        assert "DATABASE_URL" in capsys.readouterr().err


class TestPasswortVonStdin:
    """Fuer Skripte: die CI kann kein getpass beantworten."""

    def test_wird_von_der_standardeingabe_gelesen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(benutzer.sys, "stdin", io.StringIO("korrekt-pferd-batterie\n"))

        assert benutzer._passwort_erfragen("aaron", True) == "korrekt-pferd-batterie"

    def test_zeilenende_wird_abgeschnitten(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Sonst haengt ein \r am Passwort, wenn das Skript aus Windows kommt.
        monkeypatch.setattr(benutzer.sys, "stdin", io.StringIO("korrekt-pferd-batterie\r\n"))

        assert benutzer._passwort_erfragen("aaron", True) == "korrekt-pferd-batterie"

    def test_leere_eingabe_bricht_ab(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(benutzer.sys, "stdin", io.StringIO(""))

        with pytest.raises(CliFehler, match="Standardeingabe"):
            benutzer._passwort_erfragen("aaron", True)

    def test_untaugliches_passwort_wird_nicht_nachgefragt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Es gibt niemanden, der einen zweiten Versuch tippen koennte."""
        monkeypatch.setattr(benutzer.sys, "stdin", io.StringIO("kurz\n"))

        with pytest.raises(CliFehler, match="Zeichen"):
            benutzer._passwort_erfragen("aaron", True)

    def test_es_gibt_weiterhin_kein_passwort_argument(self) -> None:
        with pytest.raises(SystemExit):
            _parser().parse_args(["benutzer", "anlegen", "aaron", "--passwort", "geheim"])

    def test_der_schalter_ist_vorgesehen(self) -> None:
        args = _parser().parse_args(["benutzer", "anlegen", "aaron", "--passwort-stdin"])

        assert args.passwort_stdin is True


class TestKontenVerwalten:
    """Ohne diese Befehle liesse sich ein Konto nur anlegen, nie wieder
    loswerden - bei einem System ohne Selbstregistrierung eine echte Luecke."""

    def test_sperren_nimmt_einen_namen(self) -> None:
        assert _parser().parse_args(["benutzer", "sperren", "aaron"]).name == "aaron"

    def test_entsperren_nimmt_einen_namen(self) -> None:
        assert _parser().parse_args(["benutzer", "entsperren", "aaron"]).name == "aaron"

    def test_loeschen_fragt_standardmaessig_nach(self) -> None:
        # Ein Tippfehler soll kein Konto kosten.
        assert _parser().parse_args(["benutzer", "loeschen", "aaron"]).ja is False

    def test_loeschen_laesst_sich_fuer_skripte_bestaetigen(self) -> None:
        assert _parser().parse_args(["benutzer", "loeschen", "aaron", "--ja"]).ja is True
