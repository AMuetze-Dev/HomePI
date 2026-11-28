"""Datenbankzugriff. Hier faellt I/O an, hier stehen keine Entscheidungen.

Kein einziges if, das eine Fachregel abbildet - solche gehoeren in dienst.py.
Erlaubt sind nur Pruefungen, die die Datenbank selbst beantwortet: ob ein
Datensatz existiert, ob ein Name in der Runde schon belegt ist.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from . import dienst
from .modelle import (
    Antwort,
    Bild,
    Buzzer,
    Frage,
    Freigabe,
    Katalog,
    Korrektur,
    Medium,
    Moderation,
    Runde,
    Spieler,
    Team,
    Teammitglied,
)
from .schemas import FrageEingabe, KatalogEingabe

# ------------------------------------------------------------- Kataloge


async def kataloge(sitzung: AsyncSession) -> list[tuple[Katalog, int]]:
    anzahl = select(Frage.katalog_id, func.count().label("n")).group_by(Frage.katalog_id).subquery()
    ergebnis = await sitzung.execute(
        select(Katalog, func.coalesce(anzahl.c.n, 0))
        .outerjoin(anzahl, anzahl.c.katalog_id == Katalog.id)
        .where(Katalog.id.not_in(_eigene_kataloge()))
        .order_by(Katalog.titel)
    )
    return [(katalog, int(n)) for katalog, n in ergebnis.all()]


def _eigene_kataloge() -> Select[uuid.UUID]:
    # Ein Quiz, das jemand ohne Konto zu seiner Runde hochgeladen hat, gehoert
    # dieser Runde - nicht in die Liste, aus der alle anderen waehlen.
    return (
        select(Runde.katalog_id)
        .join(Moderation, Moderation.runde_id == Runde.id)
        .where(Moderation.eigener_katalog.is_(True))
    )


async def freie_kataloge(sitzung: AsyncSession) -> list[tuple[Katalog, int]]:
    frei = set(await sitzung.scalars(select(Freigabe.katalog_id)))
    return [(k, n) for k, n in await kataloge(sitzung) if k.id in frei]


async def freigaben(sitzung: AsyncSession) -> set[uuid.UUID]:
    return set(await sitzung.scalars(select(Freigabe.katalog_id)))


async def ist_frei(sitzung: AsyncSession, katalog_id: uuid.UUID) -> bool:
    return await sitzung.get(Freigabe, katalog_id) is not None


async def freigeben(sitzung: AsyncSession, katalog_id: uuid.UUID, frei: bool) -> None:
    await sitzung.execute(delete(Freigabe).where(Freigabe.katalog_id == katalog_id))
    if frei:
        sitzung.add(Freigabe(katalog_id=katalog_id))
    await sitzung.flush()


async def katalog(sitzung: AsyncSession, katalog_id: uuid.UUID) -> Katalog:
    eintrag = await sitzung.get(Katalog, katalog_id)
    if eintrag is None:
        raise dienst.KatalogUnbekannt("Diesen Fragenkatalog gibt es nicht.")
    return eintrag


async def katalog_anlegen(sitzung: AsyncSession, eingabe: KatalogEingabe) -> Katalog:
    eintrag = Katalog(**eingabe.model_dump())
    sitzung.add(eintrag)
    await sitzung.flush()
    await sitzung.refresh(eintrag)
    return eintrag


async def katalog_aendern(sitzung: AsyncSession, eintrag: Katalog, eingabe: KatalogEingabe) -> None:
    eintrag.titel = eingabe.titel
    eintrag.beschreibung = eingabe.beschreibung
    await sitzung.flush()
    await sitzung.refresh(eintrag)


async def katalog_loeschen(sitzung: AsyncSession, eintrag: Katalog) -> None:
    await sitzung.delete(eintrag)
    await sitzung.flush()


async def laufende_runden_mit(sitzung: AsyncSession, katalog_id: uuid.UUID) -> int:
    return int(
        await sitzung.scalar(
            select(func.count())
            .select_from(Runde)
            .where(Runde.katalog_id == katalog_id, Runde.status != "beendet")
        )
        or 0
    )


# ------------------------------------------------------------- Fragen


async def fragen(sitzung: AsyncSession, katalog_id: uuid.UUID) -> list[Frage]:
    ergebnis = await sitzung.execute(
        select(Frage).where(Frage.katalog_id == katalog_id).order_by(Frage.position, Frage.angelegt)
    )
    return list(ergebnis.scalars())


async def mit_bild(sitzung: AsyncSession, frage_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if not frage_ids:
        return set()
    ergebnis = await sitzung.execute(select(Bild.frage_id).where(Bild.frage_id.in_(frage_ids)))
    return set(ergebnis.scalars())


async def frage(sitzung: AsyncSession, frage_id: uuid.UUID) -> Frage:
    eintrag = await sitzung.get(Frage, frage_id)
    if eintrag is None:
        raise dienst.FrageUnbekannt("Diese Frage gibt es nicht.")
    return eintrag


def _felder(eingabe: FrageEingabe) -> dict[str, Any]:
    return {
        "text": eingabe.text,
        "kategorie": eingabe.kategorie,
        "punkte": eingabe.punkte,
        "zeitlimit": eingabe.zeitlimit,
        "daten": eingabe.daten.model_dump(mode="json"),
    }


async def frage_anlegen(
    sitzung: AsyncSession, katalog_id: uuid.UUID, eingabe: FrageEingabe
) -> Frage:
    letzte = await sitzung.scalar(
        select(func.max(Frage.position)).where(Frage.katalog_id == katalog_id)
    )
    eintrag = Frage(katalog_id=katalog_id, position=(letzte or 0) + 1, **_felder(eingabe))
    sitzung.add(eintrag)
    await sitzung.flush()
    await sitzung.refresh(eintrag)
    return eintrag


async def frage_aendern(sitzung: AsyncSession, eintrag: Frage, eingabe: FrageEingabe) -> None:
    for feld, wert in _felder(eingabe).items():
        setattr(eintrag, feld, wert)
    await sitzung.flush()
    await sitzung.refresh(eintrag)


async def frage_loeschen(sitzung: AsyncSession, eintrag: Frage) -> None:
    await sitzung.delete(eintrag)
    await sitzung.flush()


async def reihenfolge_setzen(sitzung: AsyncSession, ids: Sequence[uuid.UUID]) -> None:
    for position, frage_id in enumerate(ids, start=1):
        await sitzung.execute(update(Frage).where(Frage.id == frage_id).values(position=position))
    await sitzung.flush()


async def bild(sitzung: AsyncSession, frage_id: uuid.UUID) -> Bild | None:
    return await sitzung.get(Bild, frage_id)


async def bild_setzen(sitzung: AsyncSession, frage_id: uuid.UUID, mime: str, inhalt: bytes) -> None:
    await sitzung.execute(
        insert(Bild)
        .values(frage_id=frage_id, mime=mime, inhalt=inhalt)
        .on_conflict_do_update(
            index_elements=[Bild.frage_id], set_={"mime": mime, "inhalt": inhalt}
        )
    )


async def bild_loeschen(sitzung: AsyncSession, frage_id: uuid.UUID) -> None:
    await sitzung.execute(delete(Bild).where(Bild.frage_id == frage_id))


# ------------------------------------------------------------- Runden


async def runden(sitzung: AsyncSession) -> list[tuple[Runde, str, int]]:
    anzahl = select(Spieler.runde_id, func.count().label("n")).group_by(Spieler.runde_id).subquery()
    ergebnis = await sitzung.execute(
        select(Runde, Katalog.titel, func.coalesce(anzahl.c.n, 0))
        .join(Katalog, Katalog.id == Runde.katalog_id)
        .outerjoin(anzahl, anzahl.c.runde_id == Runde.id)
        .order_by(Runde.angelegt.desc())
    )
    return [(runde, titel, int(n)) for runde, titel, n in ergebnis.all()]


async def runde_anlegen(sitzung: AsyncSession, katalog_id: uuid.UUID) -> Runde:
    # Ein Zusammenstoss bei 31^6 Codes ist selten, aber nicht unmoeglich. Die
    # Datenbank entscheidet ueber die Eindeutigkeit; hier wird nur neu
    # gewuerfelt. Ein Savepoint, damit ein Fehlschlag nicht die ganze
    # Anfrage mitreisst.
    for _ in range(5):
        eintrag = Runde(code=dienst.neuer_rundencode(), katalog_id=katalog_id, erledigt=[])
        try:
            async with sitzung.begin_nested():
                sitzung.add(eintrag)
                await sitzung.flush()
        except IntegrityError:
            continue
        await sitzung.refresh(eintrag)
        return eintrag
    raise RuntimeError("Kein freier Rundencode gefunden")  # pragma: no cover


async def runde(sitzung: AsyncSession, runde_id: uuid.UUID) -> Runde:
    eintrag = await sitzung.get(Runde, runde_id)
    if eintrag is None:
        raise dienst.RundeUnbekannt("Diese Runde gibt es nicht.")
    return eintrag


async def runde_mit_code(sitzung: AsyncSession, code: str) -> Runde:
    eintrag = await sitzung.scalar(select(Runde).where(Runde.code == code))
    if eintrag is None:
        raise dienst.RundeUnbekannt("Zu diesem Code gibt es keine Runde.")
    return eintrag


async def runde_loeschen(sitzung: AsyncSession, eintrag: Runde) -> None:
    await sitzung.delete(eintrag)
    await sitzung.flush()


async def anzahl_laufend(sitzung: AsyncSession) -> int:
    return int(
        await sitzung.scalar(
            select(func.count()).select_from(Runde).where(Runde.status == "laeuft")
        )
        or 0
    )


async def speichern(sitzung: AsyncSession, eintrag: object) -> None:
    sitzung.add(eintrag)
    await sitzung.flush()


# ------------------------------------------------------------- Spieler


async def spieler_der_runde(sitzung: AsyncSession, runde_id: uuid.UUID) -> list[Spieler]:
    ergebnis = await sitzung.execute(
        select(Spieler).where(Spieler.runde_id == runde_id).order_by(Spieler.beigetreten)
    )
    return list(ergebnis.scalars())


async def anzahl_spieler(sitzung: AsyncSession, runde_id: uuid.UUID) -> int:
    return int(
        await sitzung.scalar(
            select(func.count()).select_from(Spieler).where(Spieler.runde_id == runde_id)
        )
        or 0
    )


async def spieler_anlegen(
    sitzung: AsyncSession, runde_id: uuid.UUID, name: str, schluessel: str, token_hash: str
) -> Spieler:
    eintrag = Spieler(runde_id=runde_id, name=name, schluessel=schluessel, token_hash=token_hash)
    try:
        async with sitzung.begin_nested():
            sitzung.add(eintrag)
            await sitzung.flush()
    except IntegrityError as fehler:
        # Die Datenbank ist die einzige Stelle, die das zuverlaessig weiss -
        # eine Vorabpruefung waere ein Rennen zwischen zwei Beitritten.
        raise dienst.NameVergeben(
            f"„{name}“ spielt in dieser Runde schon mit. Wähle einen anderen Namen."
        ) from fehler
    await sitzung.refresh(eintrag)
    return eintrag


async def spieler_mit_token(
    sitzung: AsyncSession, runde_id: uuid.UUID, token_hash: str
) -> Spieler | None:
    return await sitzung.scalar(
        select(Spieler).where(Spieler.runde_id == runde_id, Spieler.token_hash == token_hash)
    )


async def spieler_mit_name(
    sitzung: AsyncSession, runde_id: uuid.UUID, schluessel: str
) -> Spieler | None:
    return await sitzung.scalar(
        select(Spieler).where(Spieler.runde_id == runde_id, Spieler.schluessel == schluessel)
    )


async def spieler(sitzung: AsyncSession, runde_id: uuid.UUID, spieler_id: uuid.UUID) -> Spieler:
    eintrag = await sitzung.get(Spieler, spieler_id)
    if eintrag is None or eintrag.runde_id != runde_id:
        raise dienst.SpielerUnbekannt("Diesen Spieler gibt es in der Runde nicht.")
    return eintrag


async def spieler_loeschen(sitzung: AsyncSession, eintrag: Spieler) -> None:
    await sitzung.delete(eintrag)
    await sitzung.flush()


# ------------------------------------------------------------- Antworten


async def antworten(
    sitzung: AsyncSession, runde_id: uuid.UUID, frage_id: uuid.UUID
) -> list[Antwort]:
    ergebnis = await sitzung.execute(
        select(Antwort).where(Antwort.runde_id == runde_id, Antwort.frage_id == frage_id)
    )
    return list(ergebnis.scalars())


async def antwort_von(
    sitzung: AsyncSession, spieler_id: uuid.UUID, frage_id: uuid.UUID
) -> Antwort | None:
    return await sitzung.scalar(
        select(Antwort).where(Antwort.spieler_id == spieler_id, Antwort.frage_id == frage_id)
    )


async def antwort_speichern(
    sitzung: AsyncSession,
    runde_id: uuid.UUID,
    frage_id: uuid.UUID,
    spieler_id: uuid.UUID,
    wert: dict[str, object],
    eingeloggt: bool,
) -> None:
    await sitzung.execute(
        insert(Antwort)
        .values(
            id=uuid.uuid4(),
            runde_id=runde_id,
            frage_id=frage_id,
            spieler_id=spieler_id,
            wert=wert,
            eingeloggt=eingeloggt,
        )
        .on_conflict_do_update(
            constraint="uq_quiz_antwort", set_={"wert": wert, "eingeloggt": eingeloggt}
        )
    )


async def antwort(sitzung: AsyncSession, runde_id: uuid.UUID, antwort_id: uuid.UUID) -> Antwort:
    eintrag = await sitzung.get(Antwort, antwort_id)
    if eintrag is None or eintrag.runde_id != runde_id:
        raise dienst.AntwortUnbekannt("Diese Antwort gibt es in der Runde nicht.")
    return eintrag


async def anzahl_antworten(sitzung: AsyncSession, runde_id: uuid.UUID, frage_id: uuid.UUID) -> int:
    return int(
        await sitzung.scalar(
            select(func.count())
            .select_from(Antwort)
            .where(Antwort.runde_id == runde_id, Antwort.frage_id == frage_id)
        )
        or 0
    )


# ------------------------------------------------------------- Buzzer


async def druecke(sitzung: AsyncSession, runde_id: uuid.UUID, frage_id: uuid.UUID) -> list[Buzzer]:
    ergebnis = await sitzung.execute(
        select(Buzzer)
        .where(Buzzer.runde_id == runde_id, Buzzer.frage_id == frage_id)
        .order_by(Buzzer.reihe)
    )
    return list(ergebnis.scalars())


async def druecken(
    sitzung: AsyncSession, runde_id: uuid.UUID, frage_id: uuid.UUID, spieler_id: uuid.UUID
) -> None:
    try:
        async with sitzung.begin_nested():
            sitzung.add(Buzzer(runde_id=runde_id, frage_id=frage_id, spieler_id=spieler_id))
            await sitzung.flush()
    except IntegrityError as fehler:
        raise dienst.AntwortNichtMoeglich("Du hast schon gebuzzert.") from fehler


async def buzzer_loeschen(sitzung: AsyncSession, runde_id: uuid.UUID, frage_id: uuid.UUID) -> None:
    await sitzung.execute(
        delete(Buzzer).where(Buzzer.runde_id == runde_id, Buzzer.frage_id == frage_id)
    )


# ------------------------------------------------------------- Punkte


async def punktestaende(sitzung: AsyncSession, runde_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Summe aus bewerteten Antworten, Buzzer-Urteilen und Korrekturen."""
    staende: dict[uuid.UUID, int] = {}
    for tabelle in (Antwort, Buzzer, Korrektur):
        ergebnis = await sitzung.execute(
            select(tabelle.spieler_id, func.coalesce(func.sum(tabelle.punkte), 0))
            .where(tabelle.runde_id == runde_id)
            .group_by(tabelle.spieler_id)
        )
        for spieler_id, summe in ergebnis.all():
            staende[spieler_id] = staende.get(spieler_id, 0) + int(summe or 0)
    return staende


async def korrektur_anlegen(
    sitzung: AsyncSession, runde_id: uuid.UUID, spieler_id: uuid.UUID, punkte: int, grund: str
) -> None:
    sitzung.add(Korrektur(runde_id=runde_id, spieler_id=spieler_id, punkte=punkte, grund=grund))
    await sitzung.flush()


# ------------------------------------------------------------- Medien


async def medien_von(
    sitzung: AsyncSession, frage_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    if not frage_ids:
        return {}
    ergebnis = await sitzung.execute(
        select(Medium.frage_id, Medium.schluessel)
        .where(Medium.frage_id.in_(frage_ids))
        .order_by(Medium.schluessel)
    )
    medien: dict[uuid.UUID, list[str]] = {}
    for frage_id, schluessel in ergebnis.all():
        medien.setdefault(frage_id, []).append(schluessel)
    return medien


async def medium(sitzung: AsyncSession, frage_id: uuid.UUID, schluessel: str) -> Medium | None:
    return await sitzung.get(Medium, (frage_id, schluessel))


async def medium_setzen(
    sitzung: AsyncSession, frage_id: uuid.UUID, schluessel: str, mime: str, inhalt: bytes
) -> None:
    await sitzung.execute(
        insert(Medium)
        .values(frage_id=frage_id, schluessel=schluessel, mime=mime, inhalt=inhalt)
        .on_conflict_do_update(
            index_elements=[Medium.frage_id, Medium.schluessel],
            set_={"mime": mime, "inhalt": inhalt},
        )
    )


async def medium_loeschen(sitzung: AsyncSession, frage_id: uuid.UUID, schluessel: str) -> None:
    await sitzung.execute(
        delete(Medium).where(Medium.frage_id == frage_id, Medium.schluessel == schluessel)
    )


async def alle_medien(
    sitzung: AsyncSession, frage_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, dict[str, tuple[str, bytes]]]:
    """Fuer den Export: Bild und weitere Medien mit Inhalt."""
    ergebnis: dict[uuid.UUID, dict[str, tuple[str, bytes]]] = {i: {} for i in frage_ids}
    if not frage_ids:
        return ergebnis
    for bild_ in await sitzung.scalars(select(Bild).where(Bild.frage_id.in_(frage_ids))):
        ergebnis[bild_.frage_id]["bild"] = (bild_.mime, bild_.inhalt)
    for eintrag in await sitzung.scalars(select(Medium).where(Medium.frage_id.in_(frage_ids))):
        ergebnis[eintrag.frage_id][eintrag.schluessel] = (eintrag.mime, eintrag.inhalt)
    return ergebnis


# ------------------------------------------------------------- Teams


async def teams(sitzung: AsyncSession, runde_id: uuid.UUID) -> list[Team]:
    ergebnis = await sitzung.execute(
        select(Team).where(Team.runde_id == runde_id).order_by(Team.angelegt, Team.name)
    )
    return list(ergebnis.scalars())


async def team_anlegen(
    sitzung: AsyncSession, runde_id: uuid.UUID, name: str, schluessel: str
) -> Team:
    eintrag = Team(runde_id=runde_id, name=name, schluessel=schluessel)
    try:
        async with sitzung.begin_nested():
            sitzung.add(eintrag)
            await sitzung.flush()
    except IntegrityError as fehler:
        raise dienst.TeamVergeben(f"Ein Team „{name}“ gibt es in dieser Runde schon.") from fehler
    return eintrag


async def team(sitzung: AsyncSession, runde_id: uuid.UUID, team_id: uuid.UUID) -> Team:
    eintrag = await sitzung.get(Team, team_id)
    if eintrag is None or eintrag.runde_id != runde_id:
        raise dienst.TeamUnbekannt("Dieses Team gibt es in der Runde nicht.")
    return eintrag


async def team_loeschen(sitzung: AsyncSession, eintrag: Team) -> None:
    await sitzung.delete(eintrag)
    await sitzung.flush()


async def mitgliedschaften(
    sitzung: AsyncSession, runde_id: uuid.UUID
) -> dict[uuid.UUID, uuid.UUID]:
    ergebnis = await sitzung.execute(
        select(Teammitglied.spieler_id, Teammitglied.team_id)
        .join(Team, Team.id == Teammitglied.team_id)
        .where(Team.runde_id == runde_id)
    )
    return {spieler_id: team_id for spieler_id, team_id in ergebnis.all()}


async def team_setzen(
    sitzung: AsyncSession, spieler_id: uuid.UUID, team_id: uuid.UUID | None
) -> None:
    await sitzung.execute(delete(Teammitglied).where(Teammitglied.spieler_id == spieler_id))
    if team_id is not None:
        sitzung.add(Teammitglied(spieler_id=spieler_id, team_id=team_id))
    await sitzung.flush()


# ------------------------------------------------------------- Auswertung


async def alle_antworten(sitzung: AsyncSession, runde_id: uuid.UUID) -> list[Antwort]:
    return list(await sitzung.scalars(select(Antwort).where(Antwort.runde_id == runde_id)))


async def alle_druecke(sitzung: AsyncSession, runde_id: uuid.UUID) -> list[Buzzer]:
    return list(
        await sitzung.scalars(
            select(Buzzer).where(Buzzer.runde_id == runde_id).order_by(Buzzer.reihe)
        )
    )


# ------------------------------------------------------------- Moderation


async def moderation(sitzung: AsyncSession, runde_id: uuid.UUID) -> Moderation | None:
    return await sitzung.get(Moderation, runde_id)


async def moderation_mit_hash(sitzung: AsyncSession, code_hash: str) -> Moderation | None:
    return await sitzung.scalar(select(Moderation).where(Moderation.code_hash == code_hash))


async def moderation_setzen(
    sitzung: AsyncSession,
    runde_id: uuid.UUID,
    code_hash: str,
    *,
    ohne_konto: bool = False,
    eigener_katalog: bool = False,
) -> None:
    await sitzung.execute(
        insert(Moderation)
        .values(
            runde_id=runde_id,
            code_hash=code_hash,
            ohne_konto=ohne_konto,
            eigener_katalog=eigener_katalog,
        )
        .on_conflict_do_update(index_elements=[Moderation.runde_id], set_={"code_hash": code_hash})
    )


async def offene_ohne_konto(sitzung: AsyncSession) -> int:
    return int(
        await sitzung.scalar(
            select(func.count())
            .select_from(Moderation)
            .join(Runde, Runde.id == Moderation.runde_id)
            .where(Moderation.ohne_konto.is_(True), Runde.status != "beendet")
        )
        or 0
    )


async def abgelaufene(
    sitzung: AsyncSession, grenze: dt.datetime
) -> list[tuple[uuid.UUID, uuid.UUID, bool]]:
    """(runde_id, katalog_id, eigener_katalog) jeder Runde ohne Konto, die
    seit ``grenze`` ruht."""
    ergebnis = await sitzung.execute(
        select(Runde.id, Runde.katalog_id, Moderation.eigener_katalog)
        .join(Moderation, Moderation.runde_id == Runde.id)
        .where(Moderation.ohne_konto.is_(True), Moderation.zuletzt_aktiv < grenze)
    )
    return [(r, k, bool(e)) for r, k, e in ergebnis.all()]


async def runde_und_katalog_loeschen(
    sitzung: AsyncSession, runde_id: uuid.UUID, katalog_id: uuid.UUID | None
) -> None:
    await sitzung.execute(delete(Runde).where(Runde.id == runde_id))
    if katalog_id is not None:
        await sitzung.execute(delete(Katalog).where(Katalog.id == katalog_id))
    await sitzung.flush()
