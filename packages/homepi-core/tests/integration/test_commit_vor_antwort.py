"""Wird committet, bevor die Antwort rausgeht?

Die Frage klingt nach Feinheit und ist keine. FastAPI beendet eine
yield-Dependency voreingestellt erst, **nachdem** die Antwort beim Aufrufer
ist. Mit dem Commit in ebendieser Dependency heisst das:

* Wer auf ein ``204`` sofort nachfragt, kann den Stand von vorher lesen.
* Scheitert der Commit, ist die Erfolgsmeldung schon draussen. Die Aenderung
  ist weg, und niemand erfaehrt es.

Gefunden hat das ein Oberflaechentest, und zwar als Flackern: Passwort
gesetzt, 204 zurueck, naechste Abfrage sagt "noch nicht gewechselt" - mal so,
mal so. Ein Test, der zweimal hintereinander ueber HTTP fragt, faenge das
nicht zuverlaessig; er waere meistens gruen.

Deshalb zwei Kunstgriffe, die zusammen aus der Wahrscheinlichkeit eine
Gewissheit machen:

1. **Hinsehen statt warten.** Eine ASGI-Schicht ganz aussen haelt den Moment
   fest, in dem die Antwortkoepfe losgehen, und zaehlt ueber eine *eigene*
   Verbindung nach, was dann schon in der Datenbank steht. Was eine fremde
   Verbindung sieht, ist committet - alles andere nicht.
2. **Den Commit bremsen.** Ohne das entscheidet die Ablaufplanung, wer
   zuerst fertig ist, und der Test faellt mal so, mal so aus. Eine Zehntel-
   sekunde Verzoegerung aendert nichts an der Reihenfolge - sie macht sie
   nur sichtbar. Ohne ``scope="function"`` in deps.py zaehlt dieser Test
   dann 0 statt 1.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from homepi_core import Base, Modul, ServiceSettings, Zugang, create_service, register_aus
from homepi_core.auth import VERWALTUNG, Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.testing import datenbank as td

pytestmark = pytest.mark.integration

URL = td.datenbank_fuer_tests()
PASSWORT = "korrekt-pferd-batterie-heftklammer"

#: Lang genug, dass die Reihenfolge sichtbar wird, kurz genug, dass es nicht
#: auffaellt. Gemessen: ohne die Bremse entscheidet der Zufall.
BREMSE = 0.1


@pytest.fixture(autouse=True)
def langsamer_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verzoegert jeden Commit - und macht damit die Reihenfolge messbar."""
    echt = AsyncSession.commit

    async def gebremst(selbst: AsyncSession) -> None:
        await asyncio.sleep(BREMSE)
        await echt(selbst)

    monkeypatch.setattr(AsyncSession, "commit", gebremst)


async def _konten() -> int:
    """Zaehlt ueber eine eigene Verbindung - sieht also nur Committetes."""
    import asyncpg

    verbindung = await asyncpg.connect(td.dsn(URL))
    try:
        return int(await verbindung.fetchval("SELECT count(*) FROM benutzer"))
    finally:
        await verbindung.close()


class Mitschnitt:
    """Haelt fest, was beim Absenden der Antwortkoepfe schon committet war."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.beim_absenden: int | None = None

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        async def mitsehen(nachricht: Any) -> None:
            if nachricht["type"] == "http.response.start" and self.beim_absenden is None:
                self.beim_absenden = await _konten()
            await send(nachricht)

        await self.app(scope, receive, mitsehen)


def _modul() -> Modul:
    router = APIRouter()

    @router.get("/", summary="Wurzel")
    async def wurzel() -> dict[str, bool]:
        return {"da": True}

    return Modul(
        id=VERWALTUNG,
        titel="Verwaltung",
        router=router,
        zugang=Zugang.GESCHUETZT,
        mindestrolle=Rolle.VERWALTER,
    )


@pytest.fixture
async def app_und_kontext():
    app = create_service(
        ServiceSettings(service_name="commit-test", database_url=URL),
        module=register_aus([_modul()]),
        anmeldung=True,
    )
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
        await verbindung.run_sync(Base.metadata.create_all)

    yield app, kontext
    await kontext.db.dispose()


@pytest.fixture
async def token(app_und_kontext) -> str:
    _, kontext = app_und_kontext
    async with kontext.db.session() as sitzung:
        return await auth_speicher.setze_einrichtungstoken(sitzung)


@pytest.fixture
async def mitschnitt(app_und_kontext) -> Mitschnitt:
    app, _ = app_und_kontext
    return Mitschnitt(app)


@pytest.fixture
async def client(mitschnitt: Mitschnitt) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=mitschnitt), base_url="http://test") as c:
        yield c


async def test_die_schreibende_anfrage_committet_vor_der_antwort(
    client: AsyncClient, token: str, mitschnitt: Mitschnitt
) -> None:
    assert await _konten() == 0

    antwort = await client.post(
        "/auth/einrichtung",
        json={
            "token": token,
            "name": "chefin",
            "anzeigename": "Die Chefin",
            "passwort": PASSWORT,
        },
    )
    assert antwort.status_code == 200, antwort.text

    # Der eigentliche Punkt: schon beim ersten Byte der Antwort stand das Konto
    # in der Datenbank. Waere die Sitzung an den Request gebunden statt an die
    # Funktion, stuende hier 0 - und ein Aufrufer, der sofort nachfragt, bekaeme
    # den Stand von vorher.
    assert mitschnitt.beim_absenden == 1


async def test_und_danach_ist_es_natuerlich_erst_recht_da(client: AsyncClient, token: str) -> None:
    await client.post(
        "/auth/einrichtung",
        json={
            "token": token,
            "name": "chefin",
            "anzeigename": "Die Chefin",
            "passwort": PASSWORT,
        },
    )

    assert await _konten() == 1


async def test_eine_lesende_anfrage_schreibt_nichts(
    client: AsyncClient, mitschnitt: Mitschnitt
) -> None:
    # Gegenprobe: der Mitschnitt haengt an jeder Antwort, nicht nur an der
    # einen, die gerade passt.
    await client.get("/auth/einrichtung")

    assert mitschnitt.beim_absenden == 0
