"""Das Sitzungscookie.

Warum Cookie und nicht ein Token im localStorage: ein httponly-Cookie ist fuer
JavaScript unlesbar, also nutzt ein XSS-Fund im Frontend dem Angreifer nichts.
Der Preis ist CSRF - dagegen steht SameSite=Lax.
"""

from __future__ import annotations

from fastapi import Response

from ..settings import ServiceSettings
from .dienst import SITZUNGSDAUER

NAME = "homepi_sitzung"


def setze(antwort: Response, token: str, einstellungen: ServiceSettings) -> None:
    antwort.set_cookie(
        NAME,
        token,
        max_age=int(SITZUNGSDAUER.total_seconds()),
        # Kein Zugriff aus JavaScript - ein XSS-Fund liefert damit kein Token.
        httponly=True,
        # Lokal laeuft die Entwicklung ueber http, dort waere secure=True ein
        # Cookie, das der Browser nie sendet. In Produktion ist es Pflicht.
        secure=einstellungen.ist_produktion,
        # Lax statt Strict: Strict wuerde bedeuten, dass ein Link aus einer
        # Mail auf der Anmeldeseite landet, obwohl die Sitzung laeuft.
        samesite="lax",
        path="/",
    )


def loesche(antwort: Response) -> None:
    antwort.delete_cookie(NAME, path="/")
