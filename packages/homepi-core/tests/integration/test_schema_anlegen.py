"""``homepi schema`` gegen eine echte Datenbank.

Gegen eine nachgebaute Verbindung wuerde man vor allem den Nachbau testen -
und die Frage, um die es geht, ist gerade: entstehen die Tabellen wirklich?

Ohne diesen Befehl gaebe es auf dem Pi keinen Weg, das Schema beim ersten
Deploy anzulegen: in Produktion steht DB_SCHEMA_ANLEGEN auf false.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from homepi_core.cli.main import main
from homepi_core.testing.datenbank import datenbank_fuer_tests

pytestmark = pytest.mark.integration

#: Nur eine Datenbank, die erkennbar zum Testen da ist - diese Tests
#: rufen drop_all auf.
URL = datenbank_fuer_tests()

#: Sie kommen aus homepi-core selbst, nicht aus einem Artefakt - sie muessen
#: also auch dann entstehen, wenn kein Artefakt installiert ist.
ANMELDUNG = {"benutzer", "benutzer_rechte", "sitzungen"}


def _tabellen() -> set[str]:
    async def lesen() -> set[str]:
        motor = create_async_engine(URL)
        try:
            async with motor.connect() as verbindung:
                namen = await verbindung.run_sync(lambda s: inspect(s).get_table_names())
            return set(namen)
        finally:
            await motor.dispose()

    return asyncio.run(lesen())


def _leeren() -> None:
    async def weg() -> None:
        from homepi_core.auth import modelle as auth_modelle  # noqa: F401
        from homepi_core.modelle import Base

        motor = create_async_engine(URL)
        try:
            async with motor.begin() as verbindung:
                await verbindung.run_sync(Base.metadata.drop_all)
        finally:
            await motor.dispose()

    asyncio.run(weg())


@pytest.fixture
def leere_datenbank(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", URL)
    _leeren()
    yield
    _leeren()


def test_trockenlauf_aendert_nichts(leere_datenbank: None) -> None:
    """Erst sehen, was entsteht - dann entstehen lassen."""
    assert main(["schema", "anlegen", "--trocken"]) == 0

    assert _tabellen() & ANMELDUNG == set()


def test_anlegen_erzeugt_die_tabellen(leere_datenbank: None) -> None:
    assert main(["schema", "anlegen"]) == 0

    assert _tabellen() >= ANMELDUNG


def test_zweiter_aufruf_ist_unschaedlich(leere_datenbank: None) -> None:
    """Ein Startwerkzeug muss man zweimal aufrufen duerfen, ohne nachzudenken."""
    assert main(["schema", "anlegen"]) == 0
    assert main(["schema", "anlegen"]) == 0

    assert _tabellen() >= ANMELDUNG


def test_zeigen_nennt_vorhandene_und_fehlende(
    leere_datenbank: None, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["schema", "zeigen"])
    fehlend = capsys.readouterr().out

    main(["schema", "anlegen"])
    capsys.readouterr()

    main(["schema", "zeigen"])
    vorhanden = capsys.readouterr().out

    assert "- benutzer" in fehlend
    assert "+ benutzer" in vorhanden


def test_ohne_datenbank_url_meldet_es_sich_verstaendlich(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert main(["schema", "zeigen"]) == 1
    assert "DATABASE_URL" in capsys.readouterr().err


# --- Eine Tabelle, der eine Spalte fehlt ------------------------------------


def _benutzer_ohne_spalte() -> None:
    """Legt die Tabelle 'benutzer' an, wie sie vor passwort_wechseln aussah."""

    async def arbeit() -> None:
        motor = create_async_engine(URL)
        async with motor.begin() as verbindung:
            await verbindung.execute(
                text(
                    "CREATE TABLE benutzer ("
                    " id uuid PRIMARY KEY,"
                    " name varchar(32) NOT NULL,"
                    " anzeigename varchar(100) NOT NULL,"
                    " passwort_hash varchar(255) NOT NULL,"
                    " aktiv boolean NOT NULL,"
                    " angelegt timestamptz NOT NULL DEFAULT now(),"
                    " geaendert timestamptz NOT NULL DEFAULT now())"
                )
            )
        await motor.dispose()

    asyncio.run(arbeit())


class TestFehlendeSpalte:
    """Der Fall, der einmal lautlos durchging: die Tabelle ist da, eine Spalte
    fehlt - und jede Abfrage darauf scheitert."""

    @pytest.fixture(autouse=True)
    def alte_tabelle(self, leere_datenbank: None) -> None:
        _benutzer_ohne_spalte()

    def test_anlegen_meldet_sie_und_scheitert(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Sonst faehrt ein Deploy mit 'alles gut' weiter und die Anwendung
        ist trotzdem kaputt."""
        code = main(["schema", "anlegen"])

        ausgabe = capsys.readouterr().out
        assert code == 1
        assert "passwort_wechseln" in ausgabe
        assert "Migration" in ausgabe

    def test_zeigen_meldet_sie_ebenfalls(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["schema", "zeigen"])

        assert code == 1
        assert "passwort_wechseln" in capsys.readouterr().out

    def test_die_fehlenden_tabellen_entstehen_trotzdem(self) -> None:
        """Was sich anlegen laesst, wird angelegt - nur das Ergebnis ist kein
        Erfolg."""
        main(["schema", "anlegen"])

        assert ANMELDUNG - {"benutzer"} <= _tabellen()

    def test_der_gesundheitscheck_schlaegt_an(self) -> None:
        """Damit es nach einem Deploy auffaellt und nicht erst, wenn jemand
        die betroffene Seite aufruft."""
        from homepi_core.db import Database
        from homepi_core.schema import probe

        async def pruefen() -> bool:
            datenbank = Database(URL)
            try:
                return await probe(datenbank)()
            finally:
                await datenbank.dispose()

        assert asyncio.run(pruefen()) is False

    def test_nach_der_migration_ist_er_wieder_gruen(self) -> None:
        from homepi_core.db import Database
        from homepi_core.schema import probe

        main(["schema", "anlegen"])

        async def migrieren_und_pruefen() -> bool:
            motor = create_async_engine(URL)
            async with motor.begin() as verbindung:
                await verbindung.execute(
                    text(
                        "ALTER TABLE benutzer ADD COLUMN passwort_wechseln "
                        "boolean NOT NULL DEFAULT false"
                    )
                )
            await motor.dispose()

            datenbank = Database(URL)
            try:
                return await probe(datenbank)()
            finally:
                await datenbank.dispose()

        assert asyncio.run(migrieren_und_pruefen()) is True
