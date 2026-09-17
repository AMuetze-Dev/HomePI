"""Datenbankzugriff der Anmeldung. Hier faellt I/O an, hier stehen keine
sicherheitsrelevanten Entscheidungen - die stehen in dienst.py."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from . import dienst, passwoerter
from .modelle import Benutzer, Einrichtung, Recht, Sitzung

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult


async def finde_benutzer(sitzung: AsyncSession, name: str) -> Benutzer | None:
    ergebnis = await sitzung.execute(select(Benutzer).where(Benutzer.name == name.strip().lower()))
    return ergebnis.scalar_one_or_none()


async def lege_benutzer_an(
    sitzung: AsyncSession, name: str, passwort: str, anzeigename: str | None = None
) -> Benutzer:
    sauber = dienst.pruefe_benutzername(name)
    dienst.pruefe_passwort(passwort, sauber)

    benutzer = Benutzer(
        name=sauber,
        anzeigename=(anzeigename or name).strip(),
        passwort_hash=passwoerter.hashe_passwort(passwort),
    )
    sitzung.add(benutzer)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        raise dienst.BenutzerVergeben(f"'{sauber}' ist schon vergeben") from fehler
    await sitzung.refresh(benutzer)
    return benutzer


async def setze_recht(
    sitzung: AsyncSession, benutzer_id: uuid.UUID, artefakt: str, rolle: dienst.Rolle
) -> None:
    vorhanden = await sitzung.execute(
        select(Recht).where(Recht.benutzer_id == benutzer_id, Recht.artefakt == artefakt)
    )
    recht = vorhanden.scalar_one_or_none()
    if recht is None:
        sitzung.add(Recht(benutzer_id=benutzer_id, artefakt=artefakt, rolle=rolle.value))
    else:
        recht.rolle = rolle.value
    await sitzung.flush()


async def entziehe_recht(sitzung: AsyncSession, benutzer_id: uuid.UUID, artefakt: str) -> None:
    await sitzung.execute(
        delete(Recht).where(Recht.benutzer_id == benutzer_id, Recht.artefakt == artefakt)
    )


def rechte_von(benutzer: Benutzer) -> dict[str, dienst.Rolle]:
    return {r.artefakt: dienst.Rolle(r.rolle) for r in benutzer.rechte}


# --- Anmelden --------------------------------------------------------------


async def melde_an(sitzung: AsyncSession, name: str, passwort: str) -> tuple[Benutzer, str]:
    """Prueft und legt eine Sitzung an. Gibt Benutzer und Klartext-Token zurueck.

    Der Ablauf ist absichtlich fuer jeden Fehlerfall gleich lang und gleich
    formuliert: ein unbekannter Benutzer und ein falsches Passwort duerfen von
    aussen nicht unterscheidbar sein, sonst laesst sich herausfinden, wer ein
    Konto hat.
    """
    benutzer = await finde_benutzer(sitzung, name)

    if benutzer is None:
        # Trotzdem einmal hashen, damit die Antwortzeit nicht verraet, dass es
        # den Benutzer nicht gibt.
        passwoerter.passwort_stimmt(
            "$argon2id$v=19$m=65536,t=2,p=1$" + "A" * 22 + "$" + "B" * 43, passwort
        )
        raise dienst.AnmeldungFehlgeschlagen("Benutzername oder Passwort stimmt nicht")

    if not passwoerter.passwort_stimmt(benutzer.passwort_hash, passwort):
        raise dienst.AnmeldungFehlgeschlagen("Benutzername oder Passwort stimmt nicht")

    if not benutzer.aktiv:
        raise dienst.AnmeldungFehlgeschlagen("Dieses Konto ist deaktiviert")

    # Bei strengeren Parametern still nachziehen - der Benutzer merkt nichts.
    if passwoerter.muss_neu_gehasht_werden(benutzer.passwort_hash):
        benutzer.passwort_hash = passwoerter.hashe_passwort(passwort)

    token = dienst.neues_token()
    jetzt = datetime.now(UTC)
    sitzung.add(
        Sitzung(
            token_hash=passwoerter.hashe_token(token),
            benutzer_id=benutzer.id,
            laeuft_ab=dienst.laeuft_ab_am(jetzt),
            angelegt=jetzt,
        )
    )
    await sitzung.flush()
    return benutzer, token


async def finde_sitzung(sitzung: AsyncSession, token: str) -> Sitzung | None:
    ergebnis = await sitzung.execute(
        select(Sitzung).where(Sitzung.token_hash == passwoerter.hashe_token(token))
    )
    return ergebnis.scalar_one_or_none()


async def verlaengere(sitzung: AsyncSession, eintrag: Sitzung) -> None:
    eintrag.laeuft_ab = dienst.laeuft_ab_am()
    await sitzung.flush()


async def melde_ab(sitzung: AsyncSession, token: str) -> None:
    await sitzung.execute(
        delete(Sitzung).where(Sitzung.token_hash == passwoerter.hashe_token(token))
    )


async def melde_ueberall_ab(sitzung: AsyncSession, benutzer_id: uuid.UUID) -> None:
    """Nach einer Passwortaenderung: alle anderen Geraete fliegen raus."""
    await sitzung.execute(delete(Sitzung).where(Sitzung.benutzer_id == benutzer_id))


async def raeume_abgelaufene_auf(sitzung: AsyncSession) -> int:
    """Loescht abgelaufene Sitzungen und meldet, wie viele es waren."""
    ergebnis = await sitzung.execute(delete(Sitzung).where(Sitzung.laeuft_ab <= datetime.now(UTC)))
    # CursorResult.rowcount gibt es, der Rueckgabetyp von execute() ist nur
    # allgemeiner deklariert.
    return int(cast("CursorResult[Any]", ergebnis).rowcount or 0)


# --- Verwalter -------------------------------------------------------------


async def zaehle_verwalter(sitzung: AsyncSession) -> int:
    """Wie viele Konten duerfen die Verwaltung?

    Absichtlich **ohne** Ruecksicht auf ``aktiv``: zaehlte ein gesperrtes Konto
    nicht mit, liesse sich die Einrichtung wieder oeffnen, indem man den
    letzten Verwalter sperrt. Ein gesperrter Verwalter ist ein Fall fuer die
    Kommandozeile, kein Grund, die Tuer erneut aufzumachen.
    """
    ergebnis = await sitzung.execute(
        select(func.count())
        .select_from(Recht)
        .where(Recht.artefakt == dienst.VERWALTUNG, Recht.rolle == dienst.Rolle.VERWALTER.value)
    )
    return int(ergebnis.scalar_one())


async def ist_verwalter(sitzung: AsyncSession, benutzer_id: uuid.UUID) -> bool:
    ergebnis = await sitzung.execute(
        select(Recht.id).where(
            Recht.benutzer_id == benutzer_id,
            Recht.artefakt == dienst.VERWALTUNG,
            Recht.rolle == dienst.Rolle.VERWALTER.value,
        )
    )
    return ergebnis.scalar_one_or_none() is not None


# --- Einrichtung -----------------------------------------------------------


async def einrichtung_noetig(sitzung: AsyncSession) -> bool:
    return await zaehle_verwalter(sitzung) == 0


async def setze_einrichtungstoken(sitzung: AsyncSession) -> str:
    """Legt ein frisches Token an und gibt den Klartext zurueck.

    Bei jedem Start ein neues: so steht im Log immer das gueltige, und ein
    Token, das jemand vor drei Wochen mitgelesen hat, ist wertlos.
    """
    await sitzung.execute(delete(Einrichtung))
    token = dienst.neues_einrichtungstoken()
    sitzung.add(Einrichtung(token_hash=passwoerter.hashe_token(token), angelegt=datetime.now(UTC)))
    await sitzung.flush()
    return token


async def einrichtungstoken_stimmt(sitzung: AsyncSession, token: str) -> bool:
    ergebnis = await sitzung.execute(select(Einrichtung))
    eintrag = ergebnis.scalars().first()
    if eintrag is None:
        return False
    return passwoerter.token_stimmt(eintrag.token_hash, token)


async def schliesse_einrichtung(sitzung: AsyncSession) -> None:
    """Nach dem ersten Verwalter ist das Token wertlos - und weg."""
    await sitzung.execute(delete(Einrichtung))
