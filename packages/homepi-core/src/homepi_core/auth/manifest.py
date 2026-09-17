"""Der gefilterte Modulkatalog.

Dass ``GET /module`` je nach Aufrufer verschieden antwortet, ist der Punkt, an
dem aus einem Artefakt eine eigenständige Website wird: wer StaffelPilot
benutzt, bekommt die Geräte im Haus nicht genannt - auch nicht als gesperrte
Kachel.

Warum das hier liegt und nicht in ``service``: der Endpunkt braucht die
Anmeldung, und ein Dienst ohne Anmeldung soll weder argon2 noch die
Auth-Tabellen laden. ``service`` importiert dieses Modul deshalb erst, wenn
``anmeldung=True`` ist.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..modules import Modulregister
from .deps import MoeglicherBenutzer
from .speicher import rechte_von

BESCHREIBUNG = (
    "Die Startseite baut ihre Kacheln aus genau dieser Liste. Ein neues Artefakt "
    "erscheint dort, sobald das Gateway es geladen hat - ohne Änderung am "
    "Frontend. Defekte Module stehen mit status='fehler' drin, damit sie nicht "
    "stillschweigend fehlen. Aufgeführt ist nur, was der Aufrufer sehen darf."
)


def manifest_router(register: Modulregister) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/module",
        tags=["betrieb"],
        summary="Welche Artefakte hier laufen",
        description=BESCHREIBUNG,
    )
    async def module(benutzer: MoeglicherBenutzer) -> list[dict[str, Any]]:
        # Ohne Anmeldung beantwortbar, sonst sähe ein Besucher der öffentlichen
        # Seite einen 401 statt der Seite, für die er gekommen ist.
        return register.manifest_fuer(rechte_von(benutzer) if benutzer else None)

    return router
