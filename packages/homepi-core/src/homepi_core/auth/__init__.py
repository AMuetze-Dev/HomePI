"""Anmeldung, Sitzungen und Rechte je Artefakt.

    from homepi_core.auth import AktuellerBenutzer, Rolle, erfordert

    @router.get("/")
    async def liste(benutzer: AktuellerBenutzer) -> list[X]: ...

Es gibt bewusst keinen globalen Administrator: Rechte gelten immer für genau
ein Artefakt. Wer StaffelPilot verwaltet, hat damit keinerlei Zugriff auf die
Geräte im Haus.

Die Namen werden **lazy** nachgeladen (PEP 562), wie im Paket darüber. Grund
hier: ``modules`` braucht ``Rolle`` für die Sichtbarkeit von Artefakten, und
ein Dienst ohne Anmeldung soll darüber weder argon2 noch die Auth-Tabellen
laden.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .deps import AktuellerBenutzer, MoeglicherBenutzer, erfordert, hole_benutzer
    from .dienst import (
        AnmeldungFehlgeschlagen,
        NichtAngemeldet,
        PasswortUngeeignet,
        Rolle,
        ZugriffVerweigert,
        darf,
    )
    from .modelle import Benutzer, Recht, Sitzung
    from .router import router as anmelde_router

#: Name -> (Untermodul, Name dort). Der Anmelde-Router heißt hier bewusst
#: anders als das Untermodul ``router``: sonst hinge es von der Importreihen-
#: folge ab, ob ``from homepi_core.auth import router`` den APIRouter oder das
#: Modul liefert.
_HERKUNFT: dict[str, tuple[str, str]] = {
    "AktuellerBenutzer": ("deps", "AktuellerBenutzer"),
    "AnmeldungFehlgeschlagen": ("dienst", "AnmeldungFehlgeschlagen"),
    "Benutzer": ("modelle", "Benutzer"),
    "MoeglicherBenutzer": ("deps", "MoeglicherBenutzer"),
    "NichtAngemeldet": ("dienst", "NichtAngemeldet"),
    "PasswortUngeeignet": ("dienst", "PasswortUngeeignet"),
    "Recht": ("modelle", "Recht"),
    "Rolle": ("dienst", "Rolle"),
    "Sitzung": ("modelle", "Sitzung"),
    "ZugriffVerweigert": ("dienst", "ZugriffVerweigert"),
    "anmelde_router": ("router", "router"),
    "darf": ("dienst", "darf"),
    "erfordert": ("deps", "erfordert"),
    "hole_benutzer": ("deps", "hole_benutzer"),
}

#: Ausgeschrieben statt ``sorted(_HERKUNFT)``: nur so sieht ein Linter, dass
#: die Importe oben Exporte sind - und ein Tippfehler faellt hier auf.
__all__ = [
    "AktuellerBenutzer",
    "AnmeldungFehlgeschlagen",
    "Benutzer",
    "MoeglicherBenutzer",
    "NichtAngemeldet",
    "PasswortUngeeignet",
    "Recht",
    "Rolle",
    "Sitzung",
    "ZugriffVerweigert",
    "anmelde_router",
    "darf",
    "erfordert",
    "hole_benutzer",
]


def __getattr__(name: str) -> Any:
    herkunft = _HERKUNFT.get(name)
    if herkunft is None:
        raise AttributeError(f"module 'homepi_core.auth' has no attribute '{name}'")

    from importlib import import_module

    untermodul, attribut = herkunft
    wert = getattr(import_module(f".{untermodul}", __name__), attribut)
    globals()[name] = wert
    return wert


def __dir__() -> list[str]:
    return list(__all__)
