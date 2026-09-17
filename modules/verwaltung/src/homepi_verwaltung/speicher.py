"""Datenbankzugriff der Verwaltung.

Hier fällt I/O an, hier stehen keine Entscheidungen - die stehen in dienst.py.
Die Tabellen selbst kommen aus ``homepi_core.auth``: dieses Artefakt bringt
keine eigenen mit, es verwaltet die vorhandenen.
"""

from __future__ import annotations

import uuid

from homepi_core.auth import Benutzer
from homepi_core.auth import speicher as kern
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .dienst import BenutzerUnbekannt


async def alle(sitzung: AsyncSession) -> list[Benutzer]:
    ergebnis = await sitzung.execute(select(Benutzer).order_by(Benutzer.name))
    return list(ergebnis.scalars())


async def finde(sitzung: AsyncSession, benutzer_id: uuid.UUID) -> Benutzer:
    ergebnis = await sitzung.execute(select(Benutzer).where(Benutzer.id == benutzer_id))
    benutzer = ergebnis.scalar_one_or_none()
    if benutzer is None:
        raise BenutzerUnbekannt(f"Kein Konto mit der Kennung {benutzer_id}")
    return benutzer


async def loesche(sitzung: AsyncSession, benutzer: Benutzer) -> None:
    """Rechte und Sitzungen gehen per Cascade mit.

    Eine verwaiste Sitzung wäre ein gültiges Token ohne Konto dahinter.
    """
    await sitzung.delete(benutzer)


async def setze_aktiv(sitzung: AsyncSession, benutzer: Benutzer, aktiv: bool) -> None:
    benutzer.aktiv = aktiv
    if not aktiv:
        # Ohne das bliebe die Sperre bis zum Ablauf der Sitzung wirkungslos -
        # bis zu vierzehn Tage.
        await kern.melde_ueberall_ab(sitzung, benutzer.id)


async def setze_passwort(sitzung: AsyncSession, benutzer: Benutzer, passwort: str) -> None:
    """Setzt ein neues Passwort und beendet alle Sitzungen des Kontos.

    Ein Verwalter setzt ein Passwort meist dann zurück, wenn etwas schiefging.
    Eine weiterlaufende fremde Sitzung wäre genau dann fatal.
    """
    from homepi_core.auth import dienst, passwoerter

    dienst.pruefe_passwort(passwort, benutzer.name)
    benutzer.passwort_hash = passwoerter.hashe_passwort(passwort)
    await kern.melde_ueberall_ab(sitzung, benutzer.id)
