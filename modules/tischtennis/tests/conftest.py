from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from homepi_core import Base, Modul, ServiceSettings, create_service, register_aus
from homepi_core.auth import Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.testing.datenbank import datenbank_fuer_tests
from httpx import ASGITransport, AsyncClient

from homepi_tischtennis import modul as artefakt

# Die Integrationstests laufen gegen "test", nicht gegen "app": sie legen
# Tabellen an und loeschen sie wieder.
#: Nur eine Datenbank, die erkennbar zum Testen da ist - diese Tests
#: rufen drop_all auf.
DATENBANK = datenbank_fuer_tests()

#: Nur fuer Tests. Die Konten werden in der Fixture unten angelegt.
PASSWORT = "korrekt-pferd-batterie-heftklammer"

#: Fuehrt das Turnier: Rechte auf diesem Artefakt.
LEITER = "pruefer"
#: Angemeldet, aber ohne Recht auf diesem Artefakt. Fuer die Gegenprobe:
#: 403 und nicht 401 - der Unterschied zwischen "wer bist du" und "du
#: darfst das nicht".
OHNE_RECHT = "fremder"


@pytest.fixture
async def anwendung() -> AsyncIterator[FastAPI]:
    """Der Dienst mit diesem Artefakt, frische Tabellen, zwei Konten.

    Drei Clients greifen darauf zu: der Turnierleiter, ein Angemeldeter ohne
    Recht und ein Besucher ohne Konto. Weil dieses Artefakt oeffentlich ist,
    ist der dritte kein Randfall, sondern der haeufigste Aufrufer.
    """
    settings = ServiceSettings(
        service_name="tischtennis-test", service_version="0.0.1", database_url=DATENBANK
    )
    app = create_service(settings, module=register_aus([artefakt]), anmeldung=True)
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
        await verbindung.run_sync(Base.metadata.create_all)

    async with kontext.db.session() as sitzung:
        leiter = await auth_speicher.lege_benutzer_an(sitzung, LEITER, PASSWORT, "Turnierleiter")
        await auth_speicher.setze_recht(sitzung, leiter.id, artefakt.id, Rolle.VERWALTER)
        await auth_speicher.lege_benutzer_an(sitzung, OHNE_RECHT, PASSWORT, "Kollege")

    yield app

    await kontext.db.dispose()


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
    """Der Turnierleiter - alles, was schreibt, laeuft ueber ihn."""
    async for client in _client(anwendung, LEITER):
        yield client


@pytest.fixture
async def fremder(anwendung: FastAPI) -> AsyncIterator[AsyncClient]:
    """Angemeldet, aber ohne Recht auf diesem Artefakt."""
    async for client in _client(anwendung, OHNE_RECHT):
        yield client


@pytest.fixture
async def besucher(anwendung: FastAPI) -> AsyncIterator[AsyncClient]:
    """Kein Konto, kein Cookie - der Kollege mit dem Link."""
    async for client in _client(anwendung, None):
        yield client


@pytest.fixture
def modul() -> Modul:
    return artefakt
