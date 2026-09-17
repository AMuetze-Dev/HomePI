"""``homepi benutzer testkonto`` gegen eine echte Datenbank.

Der Befehl gibt es, weil jedes Artefakt ein Recht verlangt: ein frisches Konto
sieht **nichts**. Wer die Oberfläche durchklicken will, müsste nach jedem
Zurücksetzen erst ein Konto anlegen und dann für jedes Artefakt einzeln ein
Recht vergeben - und würde beim vierten Mal eines vergessen.

Er legt damit ein Konto mit Rechten auf allem an und schreibt sein Passwort in
die Ausgabe. Deshalb hängt hier mehr dran als an einer Bequemlichkeit, und
deshalb steht der Riegel gegen Produktion in einem eigenen Test.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from homepi_core.auth import VERWALTUNG, Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.cli import benutzer as cli_benutzer
from homepi_core.cli.main import main
from homepi_core.modelle import Base
from homepi_core.modules import Modul, register_aus
from homepi_core.testing.datenbank import datenbank_fuer_tests

pytestmark = pytest.mark.integration

URL = datenbank_fuer_tests()

#: Was der Befehl in dieser Installation vorfinden soll. Die echte Entdeckung
#: über Entry Points haengt davon ab, welche Artefakte gerade installiert
#: sind - hier waere das eine Wette auf die Umgebung.
ARTEFAKTE = ["geraete", VERWALTUNG]


def _in_der_datenbank(arbeit):
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
    monkeypatch.setenv("ENVIRONMENT", "entwicklung")

    async def frisch(_):
        motor = create_async_engine(URL)
        async with motor.begin() as verbindung:
            await verbindung.run_sync(Base.metadata.drop_all)
            await verbindung.run_sync(Base.metadata.create_all)
        await motor.dispose()

    _in_der_datenbank(frisch)
    yield


@pytest.fixture(autouse=True)
def geladene_artefakte(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ersetzt die Entdeckung - sonst haengt der Test an der Installation.

    Die Liste wird bei jedem Aufruf neu gelesen: ein Test darf ein Artefakt
    dazulegen und den Befehl noch einmal rufen.
    """

    def entdecken(*_, **__):
        return register_aus(
            [Modul(id=kennung, titel=kennung.title(), router=APIRouter()) for kennung in ARTEFAKTE]
        )

    monkeypatch.setattr("homepi_core.modules.entdecke_module", entdecken)


def _konto(name: str = cli_benutzer.TESTKONTO):
    async def arbeit(sitzung):
        return await auth_speicher.finde_benutzer(sitzung, name)

    return _in_der_datenbank(arbeit)


def _rechte(name: str = cli_benutzer.TESTKONTO) -> dict[str, Rolle]:
    benutzer = _konto(name)
    assert benutzer is not None
    return auth_speicher.rechte_von(benutzer)


class TestAnlegen:
    def test_das_konto_entsteht_mit_recht_auf_jedem_artefakt(self, datenbank: None) -> None:
        # Der Kern: nicht "ein Recht", sondern jedes - ein Konto, das nur die
        # Haelfte sieht, taugt zum Durchklicken nicht.
        code = main(["benutzer", "testkonto"])

        assert code == 0
        assert _rechte() == dict.fromkeys(ARTEFAKTE, Rolle.VERWALTER)

    def test_es_darf_sich_sofort_anmelden(self, datenbank: None) -> None:
        """Kein erzwungener Wechsel: man meldet sich damit zwanzigmal am Tag
        an, nicht einmal."""
        main(["benutzer", "testkonto"])

        benutzer = _konto()
        assert benutzer is not None
        assert benutzer.aktiv is True
        assert benutzer.passwort_wechseln is False

    def test_das_ausgegebene_passwort_passt(
        self, datenbank: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from homepi_core.auth.passwoerter import passwort_stimmt

        main(["benutzer", "testkonto"])

        benutzer = _konto()
        assert benutzer is not None
        assert passwort_stimmt(benutzer.passwort_hash, cli_benutzer.TESTPASSWORT)
        # Es steht in der Ausgabe - sonst muesste man es im Quelltext suchen.
        assert cli_benutzer.TESTPASSWORT in capsys.readouterr().out

    def test_ein_eigener_name_geht_auch(self, datenbank: None) -> None:
        main(["benutzer", "testkonto", "klickkonto"])

        assert _rechte("klickkonto") == dict.fromkeys(ARTEFAKTE, Rolle.VERWALTER)

    def test_eine_andere_rolle_geht_auch(self, datenbank: None) -> None:
        main(["benutzer", "testkonto", "--rolle", "leser"])

        assert _rechte() == dict.fromkeys(ARTEFAKTE, Rolle.LESER)


class TestWiederholbar:
    def test_ein_zweiter_lauf_scheitert_nicht(self, datenbank: None) -> None:
        """Nach einem misslungenen Versuch will man denselben Befehl noch
        einmal absetzen und nicht erst aufraeumen."""
        main(["benutzer", "testkonto"])

        assert main(["benutzer", "testkonto"]) == 0

    def test_er_holt_ein_gesperrtes_konto_zurueck(self, datenbank: None) -> None:
        main(["benutzer", "testkonto"])

        async def sperren(sitzung):
            benutzer = await auth_speicher.finde_benutzer(sitzung, cli_benutzer.TESTKONTO)
            assert benutzer is not None
            benutzer.aktiv = False

        _in_der_datenbank(sperren)
        main(["benutzer", "testkonto"])

        benutzer = _konto()
        assert benutzer is not None
        assert benutzer.aktiv is True

    def test_er_holt_ein_geaendertes_passwort_zurueck(self, datenbank: None) -> None:
        # Sonst muesste man sich merken, was man beim letzten Durchklicken
        # gesetzt hat.
        from homepi_core.auth.passwoerter import hashe_passwort, passwort_stimmt

        main(["benutzer", "testkonto"])

        async def umstellen(sitzung):
            benutzer = await auth_speicher.finde_benutzer(sitzung, cli_benutzer.TESTKONTO)
            assert benutzer is not None
            benutzer.passwort_hash = hashe_passwort("etwas-ganz-anderes-langes")

        _in_der_datenbank(umstellen)
        main(["benutzer", "testkonto"])

        benutzer = _konto()
        assert benutzer is not None
        assert passwort_stimmt(benutzer.passwort_hash, cli_benutzer.TESTPASSWORT)

    def test_ein_neues_artefakt_bekommt_sein_recht(self, datenbank: None) -> None:
        """Der haeufigste Grund, den Befehl noch einmal zu rufen."""
        main(["benutzer", "testkonto"])
        ARTEFAKTE.append("messwerte")
        try:
            main(["benutzer", "testkonto"])
            assert "messwerte" in _rechte()
        finally:
            ARTEFAKTE.remove("messwerte")


class TestRiegel:
    def test_in_produktion_bricht_er_ab(
        self, datenbank: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Ein Konto mit Rechten auf allem, dessen Passwort in der Ausgabe
        steht - das ist in Produktion kein Werkzeug, sondern eine offene Tuer."""
        monkeypatch.setenv("ENVIRONMENT", "produktion")

        code = main(["benutzer", "testkonto"])

        assert code == 1
        assert "entwicklung" in capsys.readouterr().err
        assert _konto() is None

    def test_ohne_angabe_faellt_er_ebenfalls_zu(
        self, datenbank: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Fail-closed. Ein vergessenes ENVIRONMENT auf dem Pi darf nicht
        dazu fuehren, dass der Befehl dort klaglos durchlaeuft."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        assert main(["benutzer", "testkonto"]) == 1
        assert "nicht gesetzt" in capsys.readouterr().err
        assert _konto() is None

    def test_die_meldung_nennt_den_weg_dorthin(
        self, datenbank: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "produktion")

        main(["benutzer", "testkonto"])

        assert "--startpasswort" in capsys.readouterr().err

    def test_ohne_artefakt_bricht_er_ab(
        self, datenbank: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Ein Konto mit Rechten auf nichts hilft beim Durchklicken nicht.
        monkeypatch.setattr(
            "homepi_core.modules.entdecke_module", lambda *_, **__: register_aus([])
        )

        code = main(["benutzer", "testkonto"])

        assert code == 1
        assert "Kein Artefakt" in capsys.readouterr().err
