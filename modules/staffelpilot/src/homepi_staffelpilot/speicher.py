"""Datenbankzugriff. Hier faellt I/O an, hier stehen keine Entscheidungen."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .dienst import BefundUnbekannt, SpielUnbekannt, StaffelUnbekannt, StaffelVergeben
from .modelle import Befund, Spielbericht, Staffel
from .schemas import ImportAuftrag, StaffelAnlegen

# ── Staffeln ──────────────────────────────────────────────────────────────


async def staffeln(sitzung: AsyncSession) -> list[Staffel]:
    ergebnis = await sitzung.execute(select(Staffel).order_by(Staffel.name))
    return list(ergebnis.scalars())


async def staffel(sitzung: AsyncSession, staffel_id: uuid.UUID) -> Staffel:
    gefunden = await sitzung.get(Staffel, staffel_id)
    if gefunden is None:
        raise StaffelUnbekannt(f"Es gibt keine Staffel mit der Kennung {staffel_id}")
    return gefunden


async def staffel_anlegen(sitzung: AsyncSession, daten: StaffelAnlegen) -> Staffel:
    neue = Staffel(**daten.model_dump())
    sitzung.add(neue)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        # Die Datenbank ist die einzige Stelle, die das zuverlaessig weiss.
        raise StaffelVergeben(f"Eine Staffel namens '{daten.name}' gibt es bereits") from fehler
    await sitzung.refresh(neue)
    return neue


async def staffel_loeschen(sitzung: AsyncSession, staffel_id: uuid.UUID) -> None:
    await sitzung.delete(await staffel(sitzung, staffel_id))


async def anzahl_aktiver_staffeln(sitzung: AsyncSession) -> int:
    ergebnis = await sitzung.execute(
        select(func.count()).select_from(Staffel).where(Staffel.aktiv.is_(True))
    )
    return int(ergebnis.scalar_one())


# ── Spielberichte ─────────────────────────────────────────────────────────


async def spiele(sitzung: AsyncSession, staffel_id: uuid.UUID | None = None) -> list[Spielbericht]:
    """Immer mit Befunden.

    Der Aufrufer zaehlt sie -- ohne `selectinload` waere das ein Nachladen
    mitten in der Antwort, und unter async ist das ein `MissingGreenlet`.
    """
    frage = (
        select(Spielbericht)
        .options(selectinload(Spielbericht.befunde))
        .order_by(Spielbericht.datum.desc(), Spielbericht.heim)
    )
    if staffel_id is not None:
        frage = frage.where(Spielbericht.staffel_id == staffel_id)
    ergebnis = await sitzung.execute(frage)
    return list(ergebnis.scalars())


async def spiel(sitzung: AsyncSession, spiel_id: uuid.UUID) -> Spielbericht:
    ergebnis = await sitzung.execute(
        select(Spielbericht)
        .options(selectinload(Spielbericht.befunde))
        .where(Spielbericht.id == spiel_id)
    )
    gefunden = ergebnis.scalar_one_or_none()
    if gefunden is None:
        raise SpielUnbekannt(f"Es gibt keinen Spielbericht mit der Kennung {spiel_id}")
    return gefunden


async def befund(sitzung: AsyncSession, befund_id: uuid.UUID) -> Befund:
    gefunden = await sitzung.get(Befund, befund_id)
    if gefunden is None:
        raise BefundUnbekannt(f"Es gibt keinen Befund mit der Kennung {befund_id}")
    return gefunden


async def einspielen(sitzung: AsyncSession, auftrag: ImportAuftrag) -> tuple[int, int, int]:
    """Spielberichte anlegen oder auffrischen. Gibt (angelegt, aktualisiert,
    Befunde) zurueck.

    Ein erneuter Import desselben Spiels ersetzt seine Befunde vollstaendig -
    ein Prueflauf ist die vollstaendige Aussage ueber einen Bericht, nicht ein
    Nachtrag. Getroffene Entscheidungen zu bereits bekannten Befunden bleiben
    dabei erhalten; sie an derselben Regel und derselben Person wiederzufinden
    ist das, was den zweiten Prueflauf ertraeglich macht.
    """
    await staffel(sitzung, auftrag.staffel_id)
    angelegt = aktualisiert = befunde_gesamt = 0

    for eingang in auftrag.spiele:
        vorhanden = await sitzung.execute(
            select(Spielbericht)
            .options(selectinload(Spielbericht.befunde))
            .where(
                Spielbericht.staffel_id == auftrag.staffel_id,
                Spielbericht.dfbnet_id == eingang.dfbnet_id,
            )
        )
        bericht = vorhanden.scalar_one_or_none()
        # Was der Staffelleiter zu einem Befund schon entschieden hat, nach
        # Regel und Person. Genau das wiederzufinden macht den zweiten
        # Prueflauf ertraeglich.
        frueher: dict[tuple[str, str], Befund] = {}

        if bericht is None:
            bericht = Spielbericht(
                staffel_id=auftrag.staffel_id,
                dfbnet_id=eingang.dfbnet_id,
                datum=eingang.datum,
                heim=eingang.heim,
                gast=eingang.gast,
                ergebnis=eingang.ergebnis,
            )
            sitzung.add(bericht)
            await sitzung.flush()
            angelegt += 1
        else:
            bericht.datum = eingang.datum
            bericht.heim = eingang.heim
            bericht.gast = eingang.gast
            bericht.ergebnis = eingang.ergebnis
            frueher = {(b.regel, b.person): b for b in bericht.befunde}
            # Ein Prueflauf ist die vollstaendige Aussage ueber einen Bericht:
            # was er nicht mehr meldet, ist keine offene Arbeit mehr.
            await sitzung.execute(delete(Befund).where(Befund.spiel_id == bericht.id))
            aktualisiert += 1

        for rang, b in enumerate(eingang.befunde):
            alt = frueher.get((b.regel, b.person))
            # Ueber die Fremdschluesselspalte und nicht ueber die Beziehung:
            # `bericht.befunde` waere unter async ein Nachladen an einer
            # Stelle, an der nicht await gesagt werden kann.
            sitzung.add(
                Befund(
                    spiel_id=bericht.id,
                    regel=b.regel,
                    schwere=b.schwere,
                    titel=b.titel,
                    text=b.text,
                    person=b.person,
                    mannschaft=b.mannschaft,
                    rang=rang,
                    entscheidung=alt.entscheidung if alt else "offen",
                    grund=alt.grund if alt else "",
                    entschieden_am=alt.entschieden_am if alt else None,
                )
            )
            befunde_gesamt += 1
        await sitzung.flush()
        # Die Beziehung haelt sonst den Stand von vor dem Loeschen.
        await sitzung.refresh(bericht, ["befunde"])

    return angelegt, aktualisiert, befunde_gesamt


async def entscheidung_setzen(
    sitzung: AsyncSession, befund_id: uuid.UUID, art: str, grund: str
) -> Befund:
    gefunden = await befund(sitzung, befund_id)
    gefunden.entscheidung = art
    gefunden.grund = grund
    gefunden.entschieden_am = dt.datetime.now(dt.UTC)
    await sitzung.flush()
    return gefunden


async def haken_setzen(sitzung: AsyncSession, spiel_id: uuid.UUID, gesetzt: bool) -> Spielbericht:
    bericht = await spiel(sitzung, spiel_id)
    bericht.abgehakt = gesetzt
    bericht.abgehakt_am = dt.datetime.now(dt.UTC) if gesetzt else None
    await sitzung.flush()
    return bericht
