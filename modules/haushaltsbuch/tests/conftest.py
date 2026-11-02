from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from homepi_core import Base, Modul, ServiceSettings, create_service, register_aus
from homepi_core.auth import Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.testing.datenbank import datenbank_fuer_tests
from httpx import ASGITransport, AsyncClient

from homepi_haushaltsbuch import modul as artefakt

# Die Integrationstests laufen gegen "test", nicht gegen "app": sie legen
# Tabellen an und loeschen sie wieder.
#: Nur eine Datenbank, die erkennbar zum Testen da ist - diese Tests
#: rufen drop_all auf.
DATENBANK = datenbank_fuer_tests()

#: Nur fuer Tests. Die Konten werden in der Fixture unten angelegt.
PASSWORT = "korrekt-pferd-batterie-heftklammer"


@pytest.fixture
async def anwendung() -> AsyncIterator[FastAPI]:
    """Echte Datenbank, frische Tabellen, zwei Konten mit verschiedenen Rechten.

    Zwei, weil die halbe Fachlichkeit dieses Artefakts darin besteht, wer was
    darf: die Freundin soll das Flussbild ansehen koennen, ohne dass ihr
    versehentlich eine Miete verrutscht. Ein Test mit nur einem Verwalter
    haette das nie bemerkt.
    """
    settings = ServiceSettings(
        service_name="haushaltsbuch-test", service_version="0.0.1", database_url=DATENBANK
    )
    app = create_service(settings, module=register_aus([artefakt]), anmeldung=True)
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
        await verbindung.run_sync(Base.metadata.create_all)

    async with kontext.db.session() as sitzung:
        for name, rolle in (("pruefer", Rolle.VERWALTER), ("gast", Rolle.LESER)):
            benutzer = await auth_speicher.lege_benutzer_an(sitzung, name, PASSWORT, name)
            await auth_speicher.setze_recht(sitzung, benutzer.id, artefakt.id, rolle)

    yield app

    await kontext.db.dispose()


async def _angemeldet(app: FastAPI, name: str) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        antwort = await client.post("/auth/anmelden", json={"name": name, "passwort": PASSWORT})
        assert antwort.status_code == 200, antwort.text
        yield client


@pytest.fixture
async def client(anwendung: FastAPI) -> AsyncIterator[AsyncClient]:
    """Der Verwalter - darf alles.

    Der Router besteht fast nur aus Datenbankzugriff; ihn gegen eine
    nachgebaute Sitzung zu testen wuerde vor allem den Nachbau testen.
    Deshalb sind die Tests damit als Integration markiert.
    """
    async for c in _angemeldet(anwendung, "pruefer"):
        yield c


@pytest.fixture
async def leser(anwendung: FastAPI) -> AsyncIterator[AsyncClient]:
    """Darf sehen, nicht aendern."""
    async for c in _angemeldet(anwendung, "gast"):
        yield c


@pytest.fixture
def modul() -> Modul:
    return artefakt
