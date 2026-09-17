"""Das Gateway.

Es hat selbst keine Fachlichkeit. Seine Aufgabe ist, die angemeldeten Artefakte
zu finden und unter einer gemeinsamen API bereitzustellen - damit zehn Artefakte
ein Prozess sind und nicht zehn Container.

Welche Artefakte mitkommen, steht in den Abhaengigkeiten der pyproject.toml.
Eingehaengt werden sie ueber ihren Entry Point, nicht ueber einen Import hier:
so muss diese Datei nicht angefasst werden, wenn ein Artefakt dazukommt.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from homepi_core import Base, ServiceContext, create_service, entdecke_module

from .settings import Settings

log = logging.getLogger(__name__)


async def beim_start(kontext: ServiceContext) -> AsyncIterator[None]:
    einstellungen = kontext.settings
    anlegen = getattr(einstellungen, "db_schema_anlegen", False)

    if anlegen and kontext.db is not None:
        # Alle Module erben von derselben Base, deshalb genuegt ein Durchgang.
        async with kontext.db.engine.begin() as verbindung:
            await verbindung.run_sync(Base.metadata.create_all)
        log.info("Schema geprueft: %d Tabellen bekannt", len(Base.metadata.tables))

    yield


settings = Settings()
app = create_service(
    settings,
    module=entdecke_module(),
    # Artefakte sind per Voreinstellung verschlossen. Ohne Anmeldung gaebe
    # es niemanden, der pruefen koennte, wer sie sehen darf - create_service
    # laesst sich dann gar nicht erst starten.
    anmeldung=True,
    on_startup=beim_start,
)
