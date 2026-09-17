"""``homepi benutzer`` gegen eine echte Datenbank.

Über die Kommandozeile handelt niemand als jemand - der Selbstschutz des
Verwaltungs-Artefakts greift hier also nicht. Übrig bleibt die Zählung, und
genau hier ist sie die einzige Sicherung dagegen, dass sich eine Installation
unverwaltbar macht.
"""

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import Iterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from homepi_core.auth import VERWALTUNG, Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.cli import benutzer as cli_benutzer
from homepi_core.cli.main import main
from homepi_core.modelle import Base

pytestmark = pytest.mark.integration

URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:15432/test")
PASSWORT = "korrekt-pferd-batterie-heftklammer"


def _in_der_datenbank(arbeit):
    """Führt eine Coroutine gegen eine eigene Verbindung aus.

    Eigene Engine je Aufruf: die CLI baut ihre eigene und schließt sie wieder;
    eine geteilte würde zwischen den Aufrufen ins Leere zeigen.
    """

    async def lauf():
        motor = create_async_engine(URL)
        macher = async_sessionmaker(motor, expire_on_commit=False)
        try:
            async with macher() as sitzung:
                ergebnis = await arbeit(sitzung)
                await sitzung.commit()
                return ergebnis
        finally:
            await motor.dispose()

    return asyncio.run(lauf())


@pytest.fixture
def datenbank(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", URL)

    async def frisch(_):
        motor = create_async_engine(URL)
        async with motor.begin() as verbindung:
            await verbindung.run_sync(Base.metadata.drop_all)
            await verbindung.run_sync(Base.metadata.create_all)
        await motor.dispose()

    _in_der_datenbank(frisch)
    yield


def _anlege_befehl(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(cli_benutzer.sys, "stdin", io.StringIO(f"{PASSWORT}\n"))
    return main([*args, "--passwort-stdin"])


def _zum_verwalter(name: str) -> None:
    async def arbeit(sitzung):
        person = await auth_speicher.finde_benutzer(sitzung, name)
        assert person is not None
        await auth_speicher.setze_recht(sitzung, person.id, VERWALTUNG, Rolle.VERWALTER)

    _in_der_datenbank(arbeit)


def _anzahl_verwalter() -> int:
    return _in_der_datenbank(auth_speicher.zaehle_verwalter)


# --- Anlegen ---------------------------------------------------------------


def test_anlegen_mit_recht(datenbank: None, monkeypatch: pytest.MonkeyPatch) -> None:
    code = _anlege_befehl(
        monkeypatch,
        "benutzer",
        "anlegen",
        "chefin",
        "--artefakt",
        VERWALTUNG,
        "--rolle",
        "verwalter",
    )

    assert code == 0
    assert _anzahl_verwalter() == 1


def test_die_einrichtung_ist_danach_zu(datenbank: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Weg ueber die Kommandozeile schliesst die Ersteinrichtung genauso
    wie der ueber die Maske."""
    _anlege_befehl(
        monkeypatch,
        "benutzer",
        "anlegen",
        "chefin",
        "--artefakt",
        VERWALTUNG,
        "--rolle",
        "verwalter",
    )

    assert not _in_der_datenbank(auth_speicher.einrichtung_noetig)


# --- Der letzte Verwalter --------------------------------------------------


class TestLetzterVerwalter:
    @pytest.fixture(autouse=True)
    def eine_chefin(self, datenbank: None, monkeypatch: pytest.MonkeyPatch) -> None:
        _anlege_befehl(monkeypatch, "benutzer", "anlegen", "chefin")
        _zum_verwalter("chefin")

    def test_recht_entziehen_wird_abgelehnt(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["benutzer", "entziehen", "chefin", VERWALTUNG])

        assert code == 1
        assert "letzten Verwalter" in capsys.readouterr().err
        assert _anzahl_verwalter() == 1

    def test_herabstufen_wird_abgelehnt(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Herabstufen ist ein Entzug mit anderem Namen."""
        code = main(["benutzer", "recht", "chefin", VERWALTUNG, "leser"])

        assert code == 1
        assert "letzten Verwalter" in capsys.readouterr().err

    def test_sperren_wird_abgelehnt(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["benutzer", "sperren", "chefin"])

        assert code == 1
        assert "letzten Verwalter" in capsys.readouterr().err

    def test_loeschen_wird_abgelehnt(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["benutzer", "loeschen", "chefin", "--ja"])

        assert code == 1
        assert "letzten Verwalter" in capsys.readouterr().err

    def test_mit_einer_zweiten_geht_alles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _anlege_befehl(monkeypatch, "benutzer", "anlegen", "zweite")
        _zum_verwalter("zweite")

        assert main(["benutzer", "entziehen", "chefin", VERWALTUNG]) == 0
        assert _anzahl_verwalter() == 1

    def test_ein_gewoehnliches_konto_faellt_nicht_darunter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _anlege_befehl(monkeypatch, "benutzer", "anlegen", "gast")

        assert main(["benutzer", "loeschen", "gast", "--ja"]) == 0

    def test_ein_anderes_artefakt_ist_frei(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert main(["benutzer", "recht", "chefin", "geraete", "nutzer"]) == 0
        assert main(["benutzer", "entziehen", "chefin", "geraete"]) == 0


# --- Einrichtungstoken -----------------------------------------------------


class TestEinrichtungstoken:
    def test_solange_niemand_verwaltet_gibt_es_eines(
        self, datenbank: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["benutzer", "einrichtungstoken"]) == 0

        ausgabe = capsys.readouterr().out
        assert "Einrichtungstoken" in ausgabe
        # 32 Byte urlsafe-base64 -> mindestens 43 Zeichen
        assert any(len(z.strip()) >= 43 for z in ausgabe.splitlines())

    def test_mit_verwalter_wird_es_verweigert(
        self, datenbank: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Sonst waere es ein Zweitschluessel, der nie ungueltig wird."""
        _anlege_befehl(monkeypatch, "benutzer", "anlegen", "chefin")
        _zum_verwalter("chefin")
        capsys.readouterr()

        assert main(["benutzer", "einrichtungstoken"]) == 1
        assert "bereits einen Verwalter" in capsys.readouterr().err


# --- Sperren und Loeschen --------------------------------------------------


class TestKontenVerwalten:
    def test_sperren_entsperren_loeschen(
        self, datenbank: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _anlege_befehl(monkeypatch, "benutzer", "anlegen", "gast")

        assert main(["benutzer", "sperren", "gast"]) == 0
        assert main(["benutzer", "entsperren", "gast"]) == 0
        assert main(["benutzer", "liste"]) == 0
        assert main(["benutzer", "loeschen", "gast", "--ja"]) == 0
        assert main(["benutzer", "liste"]) == 0

    def test_loeschen_fragt_ohne_ja_nach(
        self, datenbank: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Ein Tippfehler soll kein Konto kosten."""
        _anlege_befehl(monkeypatch, "benutzer", "anlegen", "gast")
        monkeypatch.setattr("builtins.input", lambda *_: "etwas anderes")

        assert main(["benutzer", "loeschen", "gast"]) == 1
        assert "Abgebrochen" in capsys.readouterr().err

    def test_ein_unbekanntes_konto_meldet_sich_verstaendlich(
        self, datenbank: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["benutzer", "sperren", "gibtsnicht"]) == 1
        assert "Kein Konto" in capsys.readouterr().err


class TestStartpasswortAufDerKommandozeile:
    """Derselbe Gedanke wie in der Oberflaeche: was der Dienst erzeugt, muss
    der Benutzer ersetzen."""

    def test_wird_ausgegeben(self, datenbank: None, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["benutzer", "anlegen", "neuling", "--startpasswort"])

        ausgabe = capsys.readouterr().out
        assert code == 0
        assert "Startpasswort" in ausgabe
        # Vier Gruppen zu vier Zeichen.
        assert any(z.strip().count("-") == 3 for z in ausgabe.splitlines())

    def test_das_konto_muss_wechseln(self, datenbank: None) -> None:
        main(["benutzer", "anlegen", "neuling", "--startpasswort"])

        async def nachsehen(sitzung):
            person = await auth_speicher.finde_benutzer(sitzung, "neuling")
            assert person is not None
            return person.passwort_wechseln

        assert _in_der_datenbank(nachsehen) is True

    def test_ein_selbst_getipptes_nicht(
        self, datenbank: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Wer es selbst tippt, hat es selbst gewaehlt."""
        _anlege_befehl(monkeypatch, "benutzer", "anlegen", "neuling")

        async def nachsehen(sitzung):
            person = await auth_speicher.finde_benutzer(sitzung, "neuling")
            assert person is not None
            return person.passwort_wechseln

        assert _in_der_datenbank(nachsehen) is False

    def test_es_wird_nicht_abgefragt(
        self, datenbank: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sonst haenge das Skript an einer getpass-Abfrage, die niemand
        beantwortet."""

        def nicht_fragen(_: str) -> str:
            raise AssertionError("getpass wurde aufgerufen")

        monkeypatch.setattr(cli_benutzer.getpass, "getpass", nicht_fragen)

        assert main(["benutzer", "anlegen", "neuling", "--startpasswort"]) == 0
