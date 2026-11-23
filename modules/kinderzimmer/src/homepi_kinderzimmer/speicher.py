"""Datenbankzugriff. Hier faellt I/O an, hier stehen keine Entscheidungen."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .dienst import NameVergeben, Unbekannt, WavInfo, konfliktmeldung
from .modelle import Aufnahme, EinstellungenZeile, Ereignis, Figur, Geraet, Tagebucheintrag
from .schemas import (
    AufnahmeAendern,
    AufnahmeAusgabe,
    Einstellungen,
    FigurAusgabe,
    FigurEingabe,
    TagebuchEingabe,
    Zahlen,
)

# --- Einstellungen -------------------------------------------------------------


async def einstellungen(sitzung: AsyncSession) -> Einstellungen:
    zeile = await sitzung.get(EinstellungenZeile, 1)
    return Einstellungen() if zeile is None else Einstellungen.model_validate(zeile.werte)


async def speichere_einstellungen(sitzung: AsyncSession, werte: Einstellungen) -> None:
    daten = werte.model_dump(mode="json")
    await sitzung.execute(
        insert(EinstellungenZeile)
        .values(id=1, werte=daten)
        .on_conflict_do_update(index_elements=["id"], set_={"werte": daten})
    )


# --- Aufnahmen -----------------------------------------------------------------


def _aufnahme_ausgabe(aufnahme: Aufnahme) -> AufnahmeAusgabe:
    return AufnahmeAusgabe(
        id=aufnahme.id,
        titel=aufnahme.titel,
        art=aufnahme.art,  # type: ignore[arg-type]
        dauer_ms=aufnahme.dauer_ms,
        bytes=aufnahme.groesse,
        sha256=aufnahme.sha256,
        angelegt=aufnahme.angelegt,
    )


async def aufnahmen(sitzung: AsyncSession) -> list[AufnahmeAusgabe]:
    ergebnis = await sitzung.execute(select(Aufnahme).order_by(Aufnahme.titel))
    return [_aufnahme_ausgabe(a) for a in ergebnis.scalars()]


async def _aufnahme(sitzung: AsyncSession, aufnahme_id: uuid.UUID) -> Aufnahme:
    aufnahme = await sitzung.get(Aufnahme, aufnahme_id)
    if aufnahme is None:
        raise Unbekannt("Diese Aufnahme gibt es nicht (mehr).")
    return aufnahme


async def aufnahme_daten(sitzung: AsyncSession, aufnahme_id: uuid.UUID) -> tuple[bytes, str]:
    ergebnis = await sitzung.execute(
        select(Aufnahme.daten, Aufnahme.sha256).where(Aufnahme.id == aufnahme_id)
    )
    zeile = ergebnis.one_or_none()
    if zeile is None:
        raise Unbekannt("Diese Aufnahme gibt es nicht (mehr).")
    return zeile.daten, zeile.sha256


async def _flush(sitzung: AsyncSession, meldung: str) -> None:
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        # Die Datenbank ist die einzige Stelle, die das zuverlaessig weiss -
        # eine Vorabpruefung waere ein Rennen zwischen zwei Anfragen.
        raise NameVergeben(konfliktmeldung(str(fehler.orig), meldung)) from fehler


async def lege_aufnahme_an(
    sitzung: AsyncSession, titel: str, art: str, daten: bytes, info: WavInfo
) -> AufnahmeAusgabe:
    aufnahme = Aufnahme(
        titel=titel,
        art=art,
        daten=daten,
        sha256=info.sha256,
        dauer_ms=info.dauer_ms,
        groesse=info.bytes,
    )
    sitzung.add(aufnahme)
    await _flush(sitzung, f"Eine Aufnahme „{titel}“ gibt es schon.")
    await sitzung.refresh(aufnahme)
    return _aufnahme_ausgabe(aufnahme)


async def aendere_aufnahme(
    sitzung: AsyncSession, aufnahme_id: uuid.UUID, werte: AufnahmeAendern
) -> AufnahmeAusgabe:
    aufnahme = await _aufnahme(sitzung, aufnahme_id)
    aufnahme.titel = werte.titel
    aufnahme.art = werte.art
    await _flush(sitzung, f"Eine Aufnahme „{werte.titel}“ gibt es schon.")
    await sitzung.refresh(aufnahme)
    return _aufnahme_ausgabe(aufnahme)


async def loesche_aufnahme(sitzung: AsyncSession, aufnahme_id: uuid.UUID) -> None:
    await sitzung.delete(await _aufnahme(sitzung, aufnahme_id))


# --- Figuren -------------------------------------------------------------------


def _figur_ausgabe(figur: Figur) -> FigurAusgabe:
    return FigurAusgabe.model_validate(
        {
            "id": figur.id,
            "uid": figur.uid,
            "name": figur.name,
            "art": figur.art,
            "farbe": figur.farbe,
            "form": figur.form,
            "menge": figur.menge,
            "stimme": figur.stimme_id,
            "klang": figur.klang_id,
        }
    )


async def figuren(sitzung: AsyncSession) -> list[FigurAusgabe]:
    ergebnis = await sitzung.execute(select(Figur).order_by(Figur.name))
    return [_figur_ausgabe(f) for f in ergebnis.scalars()]


def _uebertrage(figur: Figur, werte: FigurEingabe) -> None:
    figur.uid = werte.uid
    figur.name = werte.name
    figur.art = werte.art
    figur.farbe = werte.farbe
    figur.form = werte.form
    figur.menge = werte.menge
    figur.stimme_id = werte.stimme
    figur.klang_id = werte.klang


async def lege_figur_an(sitzung: AsyncSession, werte: FigurEingabe) -> FigurAusgabe:
    figur = Figur()
    _uebertrage(figur, werte)
    sitzung.add(figur)
    await _flush(sitzung, "Diese UID oder dieser Name gehört schon zu einer anderen Figur.")
    return _figur_ausgabe(figur)


async def _figur(sitzung: AsyncSession, figur_id: uuid.UUID) -> Figur:
    figur = await sitzung.get(Figur, figur_id)
    if figur is None:
        raise Unbekannt("Diese Figur gibt es nicht (mehr).")
    return figur


async def aendere_figur(
    sitzung: AsyncSession, figur_id: uuid.UUID, werte: FigurEingabe
) -> FigurAusgabe:
    figur = await _figur(sitzung, figur_id)
    _uebertrage(figur, werte)
    await _flush(sitzung, "Diese UID oder dieser Name gehört schon zu einer anderen Figur.")
    return _figur_ausgabe(figur)


async def loesche_figur(sitzung: AsyncSession, figur_id: uuid.UUID) -> None:
    await sitzung.delete(await _figur(sitzung, figur_id))


# --- Geraete -------------------------------------------------------------------


async def geraete(sitzung: AsyncSession) -> list[Geraet]:
    ergebnis = await sitzung.execute(select(Geraet).order_by(Geraet.name))
    return list(ergebnis.scalars())


async def lege_geraet_an(sitzung: AsyncSession, name: str, token_hash: str) -> Geraet:
    geraet = Geraet(name=name, token_hash=token_hash)
    sitzung.add(geraet)
    await _flush(sitzung, f"Ein Gerät „{name}“ gibt es schon.")
    await sitzung.refresh(geraet)
    return geraet


async def geraet(sitzung: AsyncSession, geraet_id: uuid.UUID) -> Geraet:
    gefunden = await sitzung.get(Geraet, geraet_id)
    if gefunden is None:
        raise Unbekannt("Dieses Gerät gibt es nicht (mehr).")
    return gefunden


async def setze_token(sitzung: AsyncSession, geraet_id: uuid.UUID, token_hash: str) -> Geraet:
    gefunden = await geraet(sitzung, geraet_id)
    gefunden.token_hash = token_hash
    await sitzung.flush()
    await sitzung.refresh(gefunden)
    return gefunden


async def loesche_geraet(sitzung: AsyncSession, geraet_id: uuid.UUID) -> None:
    await sitzung.delete(await geraet(sitzung, geraet_id))


async def geraet_mit_token(sitzung: AsyncSession, token_hash: str) -> Geraet | None:
    ergebnis = await sitzung.execute(select(Geraet).where(Geraet.token_hash == token_hash))
    return ergebnis.scalar_one_or_none()


def melde(geraet: Geraet, zeit: dt.datetime, firmware: str | None, stand: str | None) -> None:
    geraet.zuletzt_gesehen = zeit
    if firmware:
        geraet.firmware = firmware
    if stand is not None:
        geraet.stand = stand


# --- Ereignisse ----------------------------------------------------------------


async def speichere_ereignisse(sitzung: AsyncSession, zeilen: Sequence[dict[str, Any]]) -> int:
    """Neu angelegte zaehlen. Doppelte gehen ohne Fehler unter."""
    if not zeilen:
        return 0
    ergebnis = await sitzung.execute(
        insert(Ereignis)
        .values(list(zeilen))
        .on_conflict_do_nothing(index_elements=["geraet_id", "start", "nr"])
        .returning(Ereignis.id)
    )
    return len(ergebnis.all())


async def ereignisse(sitzung: AsyncSession, anzahl: int) -> list[tuple[Ereignis, str]]:
    ergebnis = await sitzung.execute(
        select(Ereignis, Geraet.name)
        .join(Geraet, Geraet.id == Ereignis.geraet_id)
        .order_by(Ereignis.empfangen.desc(), Ereignis.id.desc())
        .limit(anzahl)
    )
    return [(e, name) for e, name in ergebnis.tuples()]


async def gesehene_uids(
    sitzung: AsyncSession, seit: dt.datetime
) -> list[tuple[str, dt.datetime | None]]:
    ergebnis = await sitzung.execute(
        select(Ereignis.uid, func.coalesce(Ereignis.zeitpunkt, Ereignis.empfangen))
        .where(Ereignis.art == "figur_auf", Ereignis.uid.is_not(None), Ereignis.empfangen >= seit)
        .order_by(Ereignis.empfangen.desc())
        .limit(500)
    )
    return [(uid, wann) for uid, wann in ergebnis.tuples() if uid is not None]


# --- Tagebuch ------------------------------------------------------------------


async def tagebuch(sitzung: AsyncSession) -> list[Tagebucheintrag]:
    ergebnis = await sitzung.execute(
        select(Tagebucheintrag).order_by(Tagebucheintrag.datum.desc(), Tagebucheintrag.angelegt)
    )
    return list(ergebnis.scalars())


async def lege_tagebuch_an(sitzung: AsyncSession, werte: TagebuchEingabe) -> Tagebucheintrag:
    eintrag = Tagebucheintrag(datum=werte.datum, text=werte.text)
    sitzung.add(eintrag)
    await sitzung.flush()
    await sitzung.refresh(eintrag)
    return eintrag


async def loesche_tagebuch(sitzung: AsyncSession, eintrag_id: uuid.UUID) -> None:
    eintrag = await sitzung.get(Tagebucheintrag, eintrag_id)
    if eintrag is None:
        raise Unbekannt("Diesen Tagebucheintrag gibt es nicht (mehr).")
    await sitzung.delete(eintrag)


# --- Zahlen --------------------------------------------------------------------


async def zahlen(sitzung: AsyncSession) -> Zahlen:
    async def anzahl(spalte: Any) -> int:
        return int((await sitzung.execute(select(func.count(spalte)))).scalar_one())

    return Zahlen(
        figuren=await anzahl(Figur.id),
        aufnahmen=await anzahl(Aufnahme.id),
        geraete=await anzahl(Geraet.id),
    )
