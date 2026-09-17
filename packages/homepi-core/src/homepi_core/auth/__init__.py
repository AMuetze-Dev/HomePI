"""Anmeldung, Sitzungen und Rechte je Artefakt.

    from homepi_core.auth import AktuellerBenutzer, Rolle, erfordert

    @router.get("/")
    async def liste(benutzer: AktuellerBenutzer) -> list[X]: ...

Es gibt bewusst keinen globalen Administrator: Rechte gelten immer fuer genau
ein Artefakt. Wer StaffelPilot verwaltet, hat damit keinerlei Zugriff auf die
Geraete im Haus.
"""

from .deps import AktuellerBenutzer, erfordert, hole_benutzer
from .dienst import (
    AnmeldungFehlgeschlagen,
    NichtAngemeldet,
    PasswortUngeeignet,
    Rolle,
    ZugriffVerweigert,
    darf,
)
from .modelle import Benutzer, Recht, Sitzung
from .router import router

__all__ = [
    "AktuellerBenutzer",
    "AnmeldungFehlgeschlagen",
    "Benutzer",
    "NichtAngemeldet",
    "PasswortUngeeignet",
    "Recht",
    "Rolle",
    "Sitzung",
    "ZugriffVerweigert",
    "darf",
    "erfordert",
    "hole_benutzer",
    "router",
]
