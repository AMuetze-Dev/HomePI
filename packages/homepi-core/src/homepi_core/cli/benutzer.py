"""``homepi benutzer`` - Konten und Rechte verwalten.

Es gibt bewusst keinen Endpunkt, der Benutzer anlegt: das erste Konto muss von
jemandem kommen, der ohnehin Zugriff auf die Maschine hat. Ein offener
Registrierungs-Endpunkt wäre auf einem selbst gehosteten Dienst die erste
Tür, die jemand eintritt.

    homepi benutzer anlegen aaron --artefakt staffelpilot --rolle verwalter
    homepi benutzer recht aaron staffelpilot leser
    homepi benutzer liste
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
from typing import TYPE_CHECKING

from .shell import CliFehler, erfolg, hinweis, schritt, warnung

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..auth.modelle import Benutzer


def argumente(parser: argparse.ArgumentParser) -> None:
    unter = parser.add_subparsers(dest="unterbefehl", metavar="BEFEHL", required=True)

    p_neu = unter.add_parser("anlegen", help="Konto anlegen")
    p_neu.add_argument("name", help="Benutzername, klein, 3-32 Zeichen")
    p_neu.add_argument("--anzeigename", help="Name in der Oberfläche")
    p_neu.add_argument("--artefakt", help="gleich ein Recht vergeben")
    p_neu.add_argument("--rolle", default="nutzer", choices=["leser", "nutzer", "verwalter"])

    p_recht = unter.add_parser("recht", help="Rolle für ein Artefakt setzen")
    p_recht.add_argument("name")
    p_recht.add_argument("artefakt")
    p_recht.add_argument("rolle", choices=["leser", "nutzer", "verwalter"])

    p_entzug = unter.add_parser("entziehen", help="Rolle für ein Artefakt entfernen")
    p_entzug.add_argument("name")
    p_entzug.add_argument("artefakt")

    unter.add_parser("liste", help="Konten und Rechte anzeigen")

    p_pw = unter.add_parser("passwort", help="Passwort zurücksetzen")
    p_pw.add_argument("name")


def ausfuehren(args: argparse.Namespace) -> int:
    return asyncio.run(_ausfuehren(args))


def _datenbank_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise CliFehler(
            "DATABASE_URL fehlt. Gegen die Entwicklungsumgebung:\n"
            "  export DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/app'"
        )
    return url


def _passwort_erfragen(benutzername: str) -> str:
    """Zweimal eingeben lassen. Nie als Argument - das landet in der
    Shell-Historie und in der Prozessliste."""
    from ..auth.dienst import PasswortUngeeignet, pruefe_passwort

    for _ in range(3):
        erste = getpass.getpass("Passwort: ")
        zweite = getpass.getpass("Wiederholen: ")
        if erste != zweite:
            warnung("Die Eingaben stimmen nicht überein.")
            continue
        try:
            pruefe_passwort(erste, benutzername)
        except PasswortUngeeignet as problem:
            warnung(str(problem))
            continue
        return erste

    raise CliFehler("Dreimal daneben - abgebrochen.")


async def _ausfuehren(args: argparse.Namespace) -> int:
    # Erst hier importieren: "homepi deploy" soll kein SQLAlchemy laden.
    from ..db import Database

    datenbank = Database(_datenbank_url())
    befehle = {
        "anlegen": _anlegen,
        "recht": _recht,
        "entziehen": _entziehen,
        "passwort": _passwort,
        "liste": _liste,
    }
    try:
        async with datenbank.session() as sitzung:
            return await befehle[args.unterbefehl](sitzung, args)
    finally:
        await datenbank.dispose()


async def _anlegen(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    from ..auth import speicher
    from ..auth.dienst import Rolle

    schritt(f"Konto '{args.name}' anlegen")
    passwort = _passwort_erfragen(args.name)

    benutzer = await speicher.lege_benutzer_an(sitzung, args.name, passwort, args.anzeigename)
    if args.artefakt:
        await speicher.setze_recht(sitzung, benutzer.id, args.artefakt, Rolle(args.rolle))
        hinweis(f"{args.artefakt}: {args.rolle}")

    erfolg(f"'{benutzer.name}' angelegt.")
    if not args.artefakt:
        hinweis("Noch ohne Rechte. Vergeben mit:")
        hinweis(f"  homepi benutzer recht {benutzer.name} <artefakt> <rolle>")
    return 0


async def _recht(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    from ..auth import speicher
    from ..auth.dienst import Rolle

    benutzer = await _erwarte(sitzung, args.name)
    await speicher.setze_recht(sitzung, benutzer.id, args.artefakt, Rolle(args.rolle))
    erfolg(f"{benutzer.name} -> {args.artefakt}: {args.rolle}")
    return 0


async def _entziehen(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    from ..auth import speicher

    benutzer = await _erwarte(sitzung, args.name)
    await speicher.entziehe_recht(sitzung, benutzer.id, args.artefakt)
    erfolg(f"{benutzer.name} hat für '{args.artefakt}' keine Rolle mehr.")
    return 0


async def _passwort(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    from ..auth import passwoerter, speicher

    benutzer = await _erwarte(sitzung, args.name)
    schritt(f"Neues Passwort für '{benutzer.name}'")
    benutzer.passwort_hash = passwoerter.hashe_passwort(_passwort_erfragen(benutzer.name))

    # Alle Geraete abmelden - wer ein Passwort zuruecksetzt, tut das meist,
    # weil es kompromittiert sein koennte.
    await speicher.melde_ueberall_ab(sitzung, benutzer.id)
    erfolg("Gesetzt. Alle bestehenden Sitzungen wurden beendet.")
    return 0


async def _liste(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from ..auth import speicher
    from ..auth.modelle import Benutzer

    ergebnis = await sitzung.execute(select(Benutzer).order_by(Benutzer.name))
    konten = list(ergebnis.scalars())

    if not konten:
        hinweis("Noch kein Konto. Anlegen mit: homepi benutzer anlegen <name>")
        return 0

    schritt(f"{len(konten)} Konten")
    for benutzer in konten:
        zustand = "" if benutzer.aktiv else "  (deaktiviert)"
        rechte = speicher.rechte_von(benutzer)
        beschriftung = ", ".join(f"{a}={r.value}" for a, r in sorted(rechte.items())) or "-"
        print(f"    {benutzer.name:<20} {beschriftung}{zustand}")
    return 0


async def _erwarte(sitzung: AsyncSession, name: str) -> Benutzer:
    from ..auth import speicher

    benutzer = await speicher.finde_benutzer(sitzung, name)
    if benutzer is None:
        raise CliFehler(f"Kein Konto namens '{name}'")
    return benutzer
