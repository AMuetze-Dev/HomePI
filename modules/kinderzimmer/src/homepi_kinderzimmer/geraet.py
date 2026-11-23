"""Die Anmeldung des Geraets.

Der ESP32 hat kein Benutzerkonto und keine Sitzung. Er schickt bei jeder
Anfrage ``Authorization: Bearer <token>``. Das Token entsteht beim Anlegen des
Geraets und liegt nur als SHA-256 in der Datenbank.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from homepi_core.deps import DbSitzung

from . import speicher
from .dienst import GeraetNichtAngemeldet, token_aus_kopf, token_hash
from .modelle import Geraet


async def aktuelles_geraet(
    sitzung: DbSitzung,
    authorization: Annotated[str | None, Header()] = None,
) -> Geraet:
    token = token_aus_kopf(authorization)
    gefunden = (
        None if token is None else await speicher.geraet_mit_token(sitzung, token_hash(token))
    )
    if gefunden is None:
        raise GeraetNichtAngemeldet(
            "Unbekanntes oder fehlendes Gerätetoken. Ein neues gibt es auf der Website unter "
            "„Geräte“."
        )
    return gefunden


AktuellesGeraet = Annotated[Geraet, Depends(aktuelles_geraet)]
