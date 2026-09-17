"""FastAPI-Dependencies, die jedes Modul braucht.

Ein Modul kennt die Anwendung nicht, in die es eingehaengt wird. Es kommt an
Datenbank und Einstellungen deshalb ueber den Request - nicht ueber eine
globale Variable, die es beim Testen wieder zurechtruecken muesste.

    from homepi_core.deps import DbSitzung

    @router.get("/")
    async def liste(sitzung: DbSitzung) -> list[str]:
        ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from .service import ServiceContext
    from .settings import ServiceSettings


def hole_kontext(request: Request) -> ServiceContext:
    kontext = getattr(request.app.state, "homepi", None)
    if kontext is None:
        raise RuntimeError(
            "Diese Anwendung wurde nicht mit create_service gebaut - es gibt keinen HomePI-Kontext."
        )
    return kontext  # type: ignore[no-any-return]


def hole_einstellungen(request: Request) -> ServiceSettings:
    return hole_kontext(request).settings


async def hole_sitzung(request: Request) -> AsyncIterator[AsyncSession]:
    """Eine Transaktion je Anfrage: Commit am Ende, Rollback bei Fehler."""
    async with hole_kontext(request).require_db().session() as sitzung:
        yield sitzung


Kontext = Annotated["ServiceContext", Depends(hole_kontext)]
Einstellungen = Annotated["ServiceSettings", Depends(hole_einstellungen)]
# scope="function" ist hier kein Feinschliff, sondern die halbe Miete.
#
# Voreingestellt ist "request": FastAPI beendet eine yield-Dependency erst,
# NACHDEM die Antwort beim Aufrufer ist. Der Commit liefe damit hinter dem
# Statuscode her, und beides ginge schief:
#
#   * Der Aufrufer bekommt 204, fragt sofort nach - und liest den Stand von
#     vorher. Genau so ist ein Oberflaechentest hier ins Leere gelaufen:
#     Passwort gesetzt, Antwort da, naechste Abfrage sagt "noch nicht".
#   * Scheitert der Commit, ist die Erfolgsmeldung schon raus. Die Aenderung
#     ist weg, und niemand erfaehrt es.
#
# Mit "function" endet die Sitzung zwischen Endpunkt und Antwort: erst
# committen, dann antworten. Scheitert der Commit, wird daraus ein Fehler,
# den der Aufrufer sieht.
DbSitzung = Annotated[AsyncSession, Depends(hole_sitzung, scope="function")]
