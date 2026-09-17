"""``homepi schema`` gegen eine echte Datenbank.

Gegen eine nachgebaute Verbindung wuerde man vor allem den Nachbau testen -
und die Frage, um die es geht, ist gerade: entstehen die Tabellen wirklich?

Ohne diesen Befehl gaebe es auf dem Pi keinen Weg, das Schema beim ersten
Deploy anzulegen: in Produktion steht DB_SCHEMA_ANLEGEN auf false.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from homepi_core.cli.main import main

pytestmark = pytest.mark.integration

URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:15432/test")

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
