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
DbSitzung = Annotated[AsyncSession, Depends(hole_sitzung)]
