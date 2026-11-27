"""Datenbankzugriff. Hier fällt I/O an, hier stehen keine Entscheidungen.

Erlaubt sind nur Prüfungen, die die Datenbank selbst beantwortet - etwa ob
ein Datensatz existiert.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from .dienst import DokumentUnbekannt, PrueflingUnbekannt, TagUnbekannt
from .modelle import Dokument, Pruefling, Pruefungstag

# ── Prüfungstage ─────────────────────────────────────────────────────────────


async def tage_mit_anzahl(sitzung: AsyncSession) -> list[tuple[Pruefungstag, int]]:
    anzahl = select(Pruefling.tag_id, func.count().label("n")).group_by(Pruefling.tag_id).subquery()
    ergebnis = await sitzung.execute(
        select(Pruefungstag, func.coalesce(anzahl.c.n, 0))
        .outerjoin(anzahl, anzahl.c.tag_id == Pruefungstag.id)
        .order_by(Pruefungstag.datum.desc(), Pruefungstag.angelegt.desc())
    )
    return [(tag, int(n)) for tag, n in ergebnis.all()]


async def tag(sitzung: AsyncSession, tag_id: uuid.UUID) -> Pruefungstag:
    gefunden = await sitzung.get(Pruefungstag, tag_id)
    if gefunden is None:
        raise TagUnbekannt(f"Es gibt keinen Prüfungstag mit der Kennung {tag_id}")
    return gefunden


async def tag_anlegen(sitzung: AsyncSession, felder: dict[str, Any]) -> Pruefungstag:
    neu = Pruefungstag(**felder)
    sitzung.add(neu)
    await sitzung.flush()
    await sitzung.refresh(neu)
    return neu


async def tag_loeschen(sitzung: AsyncSession, tag_id: uuid.UUID) -> None:
    # Prüflinge und Dokumente gehen per ON DELETE CASCADE mit.
    await sitzung.delete(await tag(sitzung, tag_id))
    await sitzung.flush()


# ── Prüflinge ────────────────────────────────────────────────────────────────


async def prueflinge_von(sitzung: AsyncSession, tag_id: uuid.UUID) -> list[Pruefling]:
    ergebnis = await sitzung.execute(
        select(Pruefling).where(Pruefling.tag_id == tag_id).order_by(Pruefling.reihenfolge)
    )
    return list(ergebnis.scalars())


async def alle_prueflinge(sitzung: AsyncSession) -> list[Pruefling]:
    ergebnis = await sitzung.execute(select(Pruefling).order_by(Pruefling.reihenfolge))
    return list(ergebnis.scalars())


async def dokumente_je_pruefling(sitzung: AsyncSession) -> dict[uuid.UUID, int]:
    ergebnis = await sitzung.execute(
        select(Dokument.pruefling_id, func.count()).group_by(Dokument.pruefling_id)
    )
    return {pruefling_id: int(n) for pruefling_id, n in ergebnis.all()}


async def anzahl_prueflinge(sitzung: AsyncSession, tag_id: uuid.UUID) -> int:
    ergebnis = await sitzung.execute(
        select(func.count()).select_from(Pruefling).where(Pruefling.tag_id == tag_id)
    )
    return int(ergebnis.scalar_one())


async def pruefling_anlegen(sitzung: AsyncSession, tag_id: uuid.UUID, name: str) -> Pruefling:
    hoechste = await sitzung.execute(
        select(func.coalesce(func.max(Pruefling.reihenfolge), 0)).where(Pruefling.tag_id == tag_id)
    )
    neu = Pruefling(tag_id=tag_id, name=name, reihenfolge=int(hoechste.scalar_one()) + 1)
    sitzung.add(neu)
    await sitzung.flush()
    await sitzung.refresh(neu)
    return neu


async def pruefling(sitzung: AsyncSession, pruefling_id: uuid.UUID) -> Pruefling:
    gefunden = await sitzung.get(Pruefling, pruefling_id)
    if gefunden is None:
        raise PrueflingUnbekannt(f"Es gibt keinen Prüfling mit der Kennung {pruefling_id}")
    return gefunden


async def speichern(sitzung: AsyncSession, eintrag: Pruefling | Pruefungstag) -> None:
    await sitzung.flush()
    await sitzung.refresh(eintrag)


async def pruefling_loeschen(sitzung: AsyncSession, pruefling_id: uuid.UUID) -> None:
    await sitzung.delete(await pruefling(sitzung, pruefling_id))
    await sitzung.flush()


# ── Dokumente ────────────────────────────────────────────────────────────────


async def dokumente_von(sitzung: AsyncSession, pruefling_id: uuid.UUID) -> list[Dokument]:
    ergebnis = await sitzung.execute(
        select(Dokument).where(Dokument.pruefling_id == pruefling_id).order_by(Dokument.angelegt)
    )
    return list(ergebnis.scalars())


async def dokument_anlegen(
    sitzung: AsyncSession, pruefling_id: uuid.UUID, art: str, dateiname: str, daten: bytes
) -> Dokument:
    neu = Dokument(
        pruefling_id=pruefling_id, art=art, dateiname=dateiname, groesse=len(daten), daten=daten
    )
    sitzung.add(neu)
    await sitzung.flush()
    await sitzung.refresh(neu)
    return neu


async def dokument_mit_daten(
    sitzung: AsyncSession, pruefling_id: uuid.UUID, dokument_id: uuid.UUID
) -> Dokument:
    ergebnis = await sitzung.execute(
        select(Dokument)
        .options(undefer(Dokument.daten))
        .where(Dokument.id == dokument_id, Dokument.pruefling_id == pruefling_id)
    )
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        raise DokumentUnbekannt("Dieses Dokument gibt es zu diesem Prüfling nicht")
    return gefunden


async def dokument_loeschen(
    sitzung: AsyncSession, pruefling_id: uuid.UUID, dokument_id: uuid.UUID
) -> None:
    ergebnis = await sitzung.execute(
        delete(Dokument).where(Dokument.id == dokument_id, Dokument.pruefling_id == pruefling_id)
    )
    if getattr(ergebnis, "rowcount", 0) == 0:
        raise DokumentUnbekannt("Dieses Dokument gibt es zu diesem Prüfling nicht")
