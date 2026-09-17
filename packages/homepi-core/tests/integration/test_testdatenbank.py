"""Die Datenbank, in die dieser Lauf schreibt.

Zwei Fragen, die nur eine echte Postgres beantworten kann:

1. Landet dieser Lauf wirklich in einer eigenen, frisch angelegten Datenbank -
   oder doch in der vorgegebenen? Das ist der Teil, der still danebengehen
   koennte: eine falsche Weiche faellt nirgends auf, bis Reste aus einem
   Vorlauf einen Test gruen machen.
2. Legt ``anlegen`` wirklich neu an, statt Vorhandenes weiterzubenutzen?
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator

import pytest

from homepi_core.testing import datenbank as td

pytestmark = pytest.mark.integration


async def _abfrage(url: str, sql: str):
    import asyncpg

    verbindung = await asyncpg.connect(td.dsn(url))
    try:
        return await verbindung.fetchval(sql)
    finally:
        await verbindung.close()


async def _gibt_es(vorlage: str, name: str) -> bool:
    gefunden = await _abfrage(vorlage, f"SELECT 1 FROM pg_database WHERE datname = '{name}'")
    return bool(gefunden)


@pytest.fixture
def vorlage() -> str:
    """Die Datenbank, ueber die angelegt und weggeworfen wird."""
    return td.datenbank_fuer_tests()


@pytest.fixture
async def probe(vorlage: str) -> AsyncIterator[str]:
    """Ein Name, unter dem dieser Test anlegen darf - und der danach weg ist."""
    name = f"probe_{secrets.token_hex(4)}_test"
    yield name
    await td.wegwerfen(vorlage, name)


@pytest.mark.skipif(
    td.abgeschaltet(),
    reason=f"{td.SCHALTER} ist aus - dieser Lauf benutzt absichtlich die vorgegebene Datenbank",
)
class TestEigeneDatenbank:
    async def test_dieser_lauf_schreibt_in_die_angelegte(
        self, request: pytest.FixtureRequest, vorlage: str
    ) -> None:
        # Genau die Weiche, um die es geht: das Plugin hat zu Beginn eine
        # Datenbank angelegt und die Umgebung darauf gestellt.
        erwartet = td.name_fuer(request.config.rootpath.name)

        assert await _abfrage(vorlage, "SELECT current_database()") == erwartet

    async def test_und_nicht_in_die_gemeinsame(self, vorlage: str) -> None:
        assert td.datenbankname(vorlage) != "test"


class TestAnlegenUndWegwerfen:
    async def test_die_datenbank_entsteht_und_verschwindet(self, vorlage: str, probe: str) -> None:
        url = await td.anlegen(vorlage, probe)

        assert await _gibt_es(vorlage, probe)
        assert await _abfrage(url, "SELECT current_database()") == probe

        await td.wegwerfen(vorlage, probe)

        assert not await _gibt_es(vorlage, probe)

    async def test_anlegen_wirft_weg_was_der_vorlauf_hinterliess(
        self, vorlage: str, probe: str
    ) -> None:
        url = await td.anlegen(vorlage, probe)
        await td._kommando(url, "CREATE TABLE rest (x int)")

        await td.anlegen(vorlage, probe)

        # Waere sie nur wiederverwendet worden, stuende die Tabelle noch da -
        # und ein Test koennte auf Resten des Vorlaufs gruen werden.
        assert await _abfrage(url, "SELECT to_regclass('public.rest')") is None

    async def test_wegwerfen_vertraegt_eine_offene_verbindung(
        self, vorlage: str, probe: str
    ) -> None:
        import asyncpg

        url = await td.anlegen(vorlage, probe)
        # Genau der Fall, an dem ein DROP ohne FORCE scheitert: jemand hat
        # noch ein psql offen, oder ein Pool haengt an der letzten Sitzung.
        haengt = await asyncpg.connect(td.dsn(url))
        try:
            await td.wegwerfen(vorlage, probe)
            assert not await _gibt_es(vorlage, probe)
        finally:
            await haengt.close()

    async def test_wegwerfen_stoert_sich_nicht_an_nichts(self, vorlage: str, probe: str) -> None:
        # Der Fall nach einem hart abgebrochenen Lauf: es ist schon weg.
        await td.wegwerfen(vorlage, probe)
        await td.wegwerfen(vorlage, probe)
