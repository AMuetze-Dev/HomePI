from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import pytest
from fastapi import FastAPI
from homepi_core import Base, Modul, ServiceSettings, create_service, register_aus
from homepi_core.auth import Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.testing.datenbank import datenbank_fuer_tests
from httpx import ASGITransport, AsyncClient

from homepi_quiz import modul as artefakt

#: Nur fuer Tests. Die Konten werden in der Fixture unten angelegt.
PASSWORT = "korrekt-pferd-batterie-heftklammer"

#: Leitet die Runden: Rechte auf diesem Artefakt.
LEITUNG = "pruefer"
#: Angemeldet, aber ohne Recht auf diesem Artefakt.
OHNE_RECHT = "fremder"
#: Darf ansehen, aber nicht leiten.
LESER = "zuschauer"

Spielerfabrik = Callable[[], AbstractAsyncContextManager[AsyncClient]]


@pytest.fixture
async def anwendung() -> AsyncIterator[FastAPI]:
    """Der Dienst mit diesem Artefakt, frische Tabellen, drei Konten.

    Weil dieses Artefakt oeffentlich ist, sind die Spieler ohne Konto kein
    Randfall, sondern die haeufigsten Aufrufer.
    """
    # Erst hier lesen, nicht als Konstante oben in der Datei: pytest laedt
    # diese conftest, bevor das Plugin in pytest_configure die eigene
    # Datenbank dieses Laufs anlegt.
    datenbank = datenbank_fuer_tests()
    settings = ServiceSettings(
        service_name="quiz-test", service_version="0.0.1", database_url=datenbank
    )
    app = create_service(settings, module=register_aus([artefakt]), anmeldung=True)
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
        await verbindung.run_sync(Base.metadata.create_all)

    async with kontext.db.session() as sitzung:
        leitung = await auth_speicher.lege_benutzer_an(sitzung, LEITUNG, PASSWORT, "Quizleitung")
        await auth_speicher.setze_recht(sitzung, leitung.id, artefakt.id, Rolle.VERWALTER)
        await auth_speicher.lege_benutzer_an(sitzung, OHNE_RECHT, PASSWORT, "Kollege")
        leser = await auth_speicher.lege_benutzer_an(sitzung, LESER, PASSWORT, "Zuschauer")
        await auth_speicher.setze_recht(sitzung, leser.id, artefakt.id, Rolle.LESER)

    yield app

    await kontext.db.dispose()


@asynccontextmanager
async def _client(app: FastAPI, anmeldung: str | None) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        if anmeldung is not None:
            antwort = await client.post(
                "/auth/anmelden", json={"name": anmeldung, "passwort": PASSWORT}
            )
            assert antwort.status_code == 200, antwort.text
        yield client


@pytest.fixture
async def client(anwendung: FastAPI) -> AsyncIterator[AsyncClient]:
    """Die Quizleitung - alles, was steuert, laeuft ueber sie."""
    async with _client(anwendung, LEITUNG) as c:
        yield c


@pytest.fixture
async def fremder(anwendung: FastAPI) -> AsyncIterator[AsyncClient]:
    async with _client(anwendung, OHNE_RECHT) as c:
        yield c


@pytest.fixture
async def leser(anwendung: FastAPI) -> AsyncIterator[AsyncClient]:
    async with _client(anwendung, LESER) as c:
        yield c


@pytest.fixture
async def besucher(anwendung: FastAPI) -> AsyncIterator[AsyncClient]:
    """Kein Konto, kein Cookie - die Anzeigetafel am Beamer."""
    async with _client(anwendung, None) as c:
        yield c


@pytest.fixture
def spieler(anwendung: FastAPI) -> Spielerfabrik:
    """Je Aufruf ein eigenes Handy: eigener Client, eigene Cookies."""
    return lambda: _client(anwendung, None)


@pytest.fixture
def modul() -> Modul:
    return artefakt
