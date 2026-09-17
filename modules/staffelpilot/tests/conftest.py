from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from homepi_core import Base, Modul, ServiceSettings, create_service, register_aus
from homepi_core.auth import Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.testing.datenbank import datenbank_fuer_tests
from httpx import ASGITransport, AsyncClient

from homepi_staffelpilot import modul as artefakt

#: Nur eine Datenbank, die erkennbar zum Testen da ist - diese Tests
#: rufen drop_all auf.
DATENBANK = datenbank_fuer_tests()

#: Nur hier, nur fuer Tests. Angelegt wird das Konto in der Fixture unten.
PASSWORT = "korrekt-pferd-batterie-heftklammer"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Echte Datenbank, frische Tabellen, angemeldeter Staffelleiter.

    Der Router besteht fast nur aus Datenbankzugriff - ihn gegen eine
    nachgebaute Sitzung zu testen wuerde vor allem den Nachbau testen.
    Deshalb sind die Tests damit als Integration markiert.

    Angemeldet, weil das Artefakt geschuetzt ist: die Tests gehen damit durch
    denselben Weg wie ein echter Aufruf und nicht an der Pruefung vorbei.
    """
    settings = ServiceSettings(
        service_name="staffelpilot-test", service_version="0.0.1", database_url=DATENBANK
    )
    app = create_service(settings, module=register_aus([artefakt]), anmeldung=True)
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
        await verbindung.run_sync(Base.metadata.create_all)

    async with kontext.db.session() as sitzung:
        benutzer = await auth_speicher.lege_benutzer_an(
            sitzung, "staffelleiter", PASSWORT, "Staffelleiter"
        )
        await auth_speicher.setze_recht(sitzung, benutzer.id, artefakt.id, Rolle.VERWALTER)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        antwort = await c.post(
            "/auth/anmelden", json={"name": "staffelleiter", "passwort": PASSWORT}
        )
        assert antwort.status_code == 200, antwort.text
        yield c

    await kontext.db.dispose()


@pytest.fixture
def modul() -> Modul:
    return artefakt
