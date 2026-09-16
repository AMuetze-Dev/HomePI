"""Datenbankzugriff. Hier faellt I/O an, hier stehen keine Entscheidungen."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .dienst import GeraetUnbekannt, NameVergeben
from .modelle import Geraet
from .schemas import GeraetAnlegen


async def alle(sitzung: AsyncSession) -> list[Geraet]:
    ergebnis = await sitzung.execute(select(Geraet).order_by(Geraet.raum, Geraet.name))
    return list(ergebnis.scalars())


async def eines(sitzung: AsyncSession, geraet_id: uuid.UUID) -> Geraet:
    geraet = await sitzung.get(Geraet, geraet_id)
    if geraet is None:
        raise GeraetUnbekannt(f"Es gibt kein Gerät mit der Kennung {geraet_id}")
    return geraet


async def anlegen(sitzung: AsyncSession, daten: GeraetAnlegen) -> Geraet:
    geraet = Geraet(**daten.model_dump())
    sitzung.add(geraet)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        # Die Datenbank ist die einzige Stelle, die das zuverlaessig weiss -
        # eine Vorabpruefung waere ein Rennen zwischen zwei Anfragen.
        raise NameVergeben(f"Ein Gerät namens '{daten.name}' existiert bereits") from fehler
    await sitzung.refresh(geraet)
    return geraet


async def loeschen(sitzung: AsyncSession, geraet_id: uuid.UUID) -> None:
    await sitzung.delete(await eines(sitzung, geraet_id))
