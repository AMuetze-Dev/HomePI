"""``homepi benutzer`` - Konten und Rechte verwalten.

Es gibt bewusst keinen Endpunkt, der Benutzer anlegt: das erste Konto muss von
jemandem kommen, der ohnehin Zugriff auf die Maschine hat. Ein offener
Registrierungs-Endpunkt wäre auf einem selbst gehosteten Dienst die erste
Tür, die jemand eintritt.

    homepi benutzer anlegen aaron --artefakt staffelpilot --rolle verwalter
    homepi benutzer recht aaron staffelpilot leser
    homepi benutzer liste
    homepi benutzer testkonto            # nur in der Entwicklung
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from typing import TYPE_CHECKING

from .shell import CliFehler, erfolg, hinweis, schritt, warnung

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..auth.modelle import Benutzer


#: Vorgabename des Durchklick-Kontos.
TESTKONTO = "tester"

#: Sein Passwort. Absichtlich fest und absichtlich hier sichtbar: es gilt nur
#: in einer Entwicklungsumgebung, die ohnehin app/app als Datenbankpasswort
#: hat. Ein erzeugtes waere hier sogar schlechter - man will sich damit
#: zwanzigmal am Tag anmelden, nicht es zwanzigmal nachschlagen.
#: Enthaelt den Benutzernamen nicht; das lehnt die Passwortpruefung ab.
TESTPASSWORT = "nur-zum-durchklicken-im-eigenen-netz"


def argumente(parser: argparse.ArgumentParser) -> None:
    unter = parser.add_subparsers(dest="unterbefehl", metavar="BEFEHL", required=True)

    p_neu = unter.add_parser("anlegen", help="Konto anlegen")
    p_neu.add_argument("name", help="Benutzername, klein, 3-32 Zeichen")
    p_neu.add_argument("--anzeigename", help="Name in der Oberfläche")
    p_neu.add_argument("--artefakt", help="gleich ein Recht vergeben")
    p_neu.add_argument("--rolle", default="nutzer", choices=["leser", "nutzer", "verwalter"])
    p_neu.add_argument(
        "--startpasswort",
        action="store_true",
        help="Passwort erzeugen lassen; der Benutzer ersetzt es beim ersten Anmelden",
    )
    _passwort_stdin(p_neu)

    p_recht = unter.add_parser("recht", help="Rolle für ein Artefakt setzen")
    p_recht.add_argument("name")
    p_recht.add_argument("artefakt")
    p_recht.add_argument("rolle", choices=["leser", "nutzer", "verwalter"])

    p_entzug = unter.add_parser("entziehen", help="Rolle für ein Artefakt entfernen")
    p_entzug.add_argument("name")
    p_entzug.add_argument("artefakt")

    unter.add_parser("liste", help="Konten und Rechte anzeigen")

    unter.add_parser(
        "einrichtungstoken",
        help="frisches Token fuer die Ersteinrichtung ausgeben",
    )

    p_sperren = unter.add_parser("sperren", help="Konto stilllegen, ohne es zu löschen")
    p_sperren.add_argument("name")

    p_frei = unter.add_parser("entsperren", help="Gesperrtes Konto wieder freigeben")
    p_frei.add_argument("name")

    p_weg = unter.add_parser("loeschen", help="Konto samt Rechten und Sitzungen entfernen")
    p_weg.add_argument("name")
    p_weg.add_argument(
        "--ja",
        action="store_true",
        help="ohne Rückfrage löschen (für Skripte)",
    )

    p_pw = unter.add_parser("passwort", help="Passwort zurücksetzen")
    p_pw.add_argument("name")
    _passwort_stdin(p_pw)

    p_test = unter.add_parser(
        "testkonto",
        help="Konto zum Durchklicken anlegen - nur in der Entwicklung",
    )
    p_test.add_argument("name", nargs="?", default=TESTKONTO)
    p_test.add_argument(
        "--rolle",
        default="verwalter",
        choices=["leser", "nutzer", "verwalter"],
        help="Rolle auf JEDEM geladenen Artefakt (Vorgabe: verwalter)",
    )
    p_test.add_argument(
        "--passwort-stdin",
        action="store_true",
        dest="passwort_stdin",
        help="eigenes Passwort von der Standardeingabe statt des vorgegebenen",
    )


def _passwort_stdin(parser: argparse.ArgumentParser) -> None:
    """Fuer Skripte: das Passwort kommt von stdin statt aus einer Abfrage.

    Weiterhin **kein** --passwort: ein Argument stuende in der Shell-Historie
    und waere fuer jeden sichtbar, der 'ps' aufruft. Ueber stdin entscheidet
    der Aufrufer, woher der Wert kommt - in der CI aus einem Secret.

        printf '%s' "$PW" | homepi benutzer anlegen rauchtest --passwort-stdin
    """
    parser.add_argument(
        "--passwort-stdin",
        action="store_true",
        dest="passwort_stdin",
        help="Passwort von der Standardeingabe lesen statt abzufragen",
    )


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


def _passwort_erfragen(benutzername: str, von_stdin: bool = False) -> str:
    """Zweimal eingeben lassen. Nie als Argument - das landet in der
    Shell-Historie und in der Prozessliste."""
    from ..auth.dienst import PasswortUngeeignet, pruefe_passwort

    if von_stdin:
        passwort = sys.stdin.readline().rstrip("\r\n")
        if not passwort:
            raise CliFehler("Kein Passwort auf der Standardeingabe")
        try:
            pruefe_passwort(passwort, benutzername)
        except PasswortUngeeignet as problem:
            # Kein zweiter Versuch: es gibt niemanden, der ihn tippen koennte.
            raise CliFehler(str(problem)) from problem
        return passwort

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
        "sperren": _sperren,
        "entsperren": _entsperren,
        "loeschen": _loeschen,
        "einrichtungstoken": _einrichtungstoken,
        "testkonto": _testkonto,
    }
    try:
        async with datenbank.session() as sitzung:
            return await befehle[args.unterbefehl](sitzung, args)
    finally:
        await datenbank.dispose()


async def _anlegen(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    from ..auth import dienst, speicher
    from ..auth.dienst import Rolle

    schritt(f"Konto '{args.name}' anlegen")

    if args.startpasswort:
        # Ein Passwort, das jemand anders kennt, soll nicht das bleibende sein.
        passwort = dienst.neues_startpasswort()
    else:
        passwort = _passwort_erfragen(args.name, args.passwort_stdin)

    benutzer = await speicher.lege_benutzer_an(
        sitzung,
        args.name,
        passwort,
        args.anzeigename,
        wechsel_erzwingen=args.startpasswort,
    )
    if args.artefakt:
        await speicher.setze_recht(sitzung, benutzer.id, args.artefakt, Rolle(args.rolle))
        hinweis(f"{args.artefakt}: {args.rolle}")

    erfolg(f"'{benutzer.name}' angelegt.")
    if args.startpasswort:
        schritt("Startpasswort - jetzt weitergeben, es ist danach nicht mehr abrufbar")
        print(f"    {passwort}")
        hinweis(f"'{benutzer.name}' muss es beim ersten Anmelden ersetzen.")
    if not args.artefakt:
        hinweis("Noch ohne Rechte. Vergeben mit:")
        hinweis(f"  homepi benutzer recht {benutzer.name} <artefakt> <rolle>")
    return 0


async def _recht(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    from ..auth import dienst, speicher
    from ..auth.dienst import Rolle

    benutzer = await _erwarte(sitzung, args.name)
    if args.artefakt == dienst.VERWALTUNG and Rolle(args.rolle) is not Rolle.VERWALTER:
        # Herabstufen ist ein Entzug mit anderem Namen.
        await _pruefe_verwalter_bleibt(sitzung, benutzer, "Die Rolle herabzustufen")
    await speicher.setze_recht(sitzung, benutzer.id, args.artefakt, Rolle(args.rolle))
    erfolg(f"{benutzer.name} -> {args.artefakt}: {args.rolle}")
    return 0


async def _entziehen(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    from ..auth import speicher
    from ..auth.dienst import VERWALTUNG

    benutzer = await _erwarte(sitzung, args.name)
    if args.artefakt == VERWALTUNG:
        await _pruefe_verwalter_bleibt(sitzung, benutzer, "Das Recht zu entziehen")
    await speicher.entziehe_recht(sitzung, benutzer.id, args.artefakt)
    erfolg(f"{benutzer.name} hat für '{args.artefakt}' keine Rolle mehr.")
    return 0


async def _passwort(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    from ..auth import passwoerter, speicher

    benutzer = await _erwarte(sitzung, args.name)
    schritt(f"Neues Passwort für '{benutzer.name}'")
    benutzer.passwort_hash = passwoerter.hashe_passwort(
        _passwort_erfragen(benutzer.name, args.passwort_stdin)
    )

    # Alle Geraete abmelden - wer ein Passwort zuruecksetzt, tut das meist,
    # weil es kompromittiert sein koennte.
    await speicher.melde_ueberall_ab(sitzung, benutzer.id)
    erfolg("Gesetzt. Alle bestehenden Sitzungen wurden beendet.")
    return 0


async def _sperren(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    """Stilllegen statt loeschen.

    Der uebliche Fall: jemand ist ausgeschieden, seine Daten sollen aber
    zuordenbar bleiben. Bestehende Sitzungen fliegen sofort raus - sonst waere
    die Sperre bis zu vierzehn Tage wirkungslos.
    """
    from ..auth import speicher

    benutzer = await _erwarte(sitzung, args.name)
    await _pruefe_verwalter_bleibt(sitzung, benutzer, "Das Konto zu sperren")
    benutzer.aktiv = False
    await speicher.melde_ueberall_ab(sitzung, benutzer.id)
    erfolg(f"'{benutzer.name}' ist gesperrt. Alle Sitzungen wurden beendet.")
    return 0


async def _entsperren(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    benutzer = await _erwarte(sitzung, args.name)
    benutzer.aktiv = True
    erfolg(f"'{benutzer.name}' kann sich wieder anmelden.")
    return 0


async def _loeschen(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    """Endgueltig. Rechte und Sitzungen gehen per Cascade mit."""
    benutzer = await _erwarte(sitzung, args.name)
    await _pruefe_verwalter_bleibt(sitzung, benutzer, "Das Konto zu loeschen")

    if not args.ja:
        warnung(f"'{benutzer.name}' wird samt Rechten und Sitzungen entfernt.")
        hinweis("Zum Bestaetigen den Benutzernamen eingeben, sonst Abbruch:")
        if input("    > ").strip() != benutzer.name:
            raise CliFehler("Abgebrochen - nichts geloescht.")

    await sitzung.delete(benutzer)
    erfolg(f"'{benutzer.name}' ist geloescht.")
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


async def _einrichtungstoken(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    """Gibt ein frisches Einrichtungstoken aus.

    Der Normalfall ist, es beim Start aus dem Log zu lesen. Das hier ist fuer
    den Fall, dass das Log schon weggerollt ist und niemand den Dienst neu
    starten will.
    """
    from ..auth import speicher

    if not await speicher.einrichtung_noetig(sitzung):
        raise CliFehler(
            "Diese Installation hat bereits einen Verwalter - die Einrichtung "
            "ist vorbei. Weitere Konten legt er in der Verwaltung an."
        )

    token = await speicher.setze_einrichtungstoken(sitzung)
    schritt("Einrichtungstoken")
    print(f"    {token}")
    hinweis("Gilt bis zum naechsten Start des Dienstes.")
    return 0


async def _testkonto(sitzung: AsyncSession, args: argparse.Namespace) -> int:
    """Ein Konto zum Durchklicken, mit Rechten auf allem, was geladen ist.

    Warum es das gibt: seit jedes Artefakt ein Recht verlangt, sieht ein
    frisches Konto **nichts**. Wer die Oberfläche prüfen will, müsste also
    erst ein Konto anlegen und dann für jedes Artefakt einzeln ein Recht
    vergeben - jedes Mal neu, nach jedem Zurücksetzen der Datenbank.

    Warum es ein eigener Befehl ist und kein Endpunkt: er legt ein Konto mit
    Rechten auf allem an. So etwas darf nur, wer ohnehin an der Maschine
    sitzt.

    Warum das Passwort fest und sichtbar ist: man meldet sich damit zwanzigmal
    am Tag an. Ein erzeugtes müsste man zwanzigmal nachschlagen, und ein
    erzwungener Wechsel stünde bei jedem Durchlauf im Weg. Es gilt nur in der
    Entwicklung - der Befehl bricht sonst ab.

    Der Befehl ist wiederholbar: gibt es das Konto schon, werden Passwort und
    Rechte neu gesetzt statt zu scheitern.
    """
    from ..auth import passwoerter, speicher
    from ..auth.dienst import Rolle
    from ..modules import entdecke_module
    from ..settings import Umgebung

    # Direkt aus der Umgebung statt ueber die Einstellungen: dieser Riegel
    # soll halten, auch wenn an der Konfiguration sonst etwas fehlt. Ueber
    # get_settings() wuerde eine unbeteiligte Pruefung ihn mit einem
    # Stacktrace ueberspringen, statt ihn zufallen zu lassen.
    #
    # Und er faellt zu, wenn nichts dasteht: ein Konto mit Rechten auf allem
    # soll nur entstehen, wo jemand ausdruecklich "entwicklung" gesagt hat.
    erlaubt = {Umgebung.ENTWICKLUNG.value, Umgebung.TEST.value}
    umgebung = os.environ.get("ENVIRONMENT", "").strip().lower()
    if umgebung not in erlaubt:
        raise CliFehler(
            "'testkonto' legt ein Konto mit Rechten auf JEDEM Artefakt an und "
            "gibt sein Passwort aus.\n"
            f"Das geht nur mit ENVIRONMENT={Umgebung.ENTWICKLUNG.value} "
            f"(hier: {umgebung or 'nicht gesetzt'}).\n"
            "Sonst: homepi benutzer anlegen <name> --startpasswort"
        )

    rolle = Rolle(args.rolle)
    passwort = _passwort_erfragen(args.name, True) if args.passwort_stdin else TESTPASSWORT

    register = entdecke_module()
    artefakte = sorted(register.ids)
    if not artefakte:
        raise CliFehler(
            "Kein Artefakt geladen - ein Konto mit Rechten auf nichts hilft "
            "beim Durchklicken nicht weiter."
        )

    benutzer = await speicher.finde_benutzer(sitzung, args.name)
    if benutzer is None:
        schritt(f"Testkonto '{args.name}' anlegen")
        benutzer = await speicher.lege_benutzer_an(
            sitzung, args.name, passwort, "Testkonto", wechsel_erzwingen=False
        )
    else:
        # Wiederholbar: nach einem misslungenen Versuch will man denselben
        # Befehl noch einmal absetzen und nicht erst aufraeumen.
        schritt(f"Testkonto '{args.name}' auffrischen")
        benutzer.aktiv = True
        benutzer.passwort_wechseln = False
        benutzer.passwort_hash = passwoerter.hashe_passwort(passwort)
        await speicher.melde_ueberall_ab(sitzung, benutzer.id)

    for artefakt in artefakte:
        await speicher.setze_recht(sitzung, benutzer.id, artefakt, rolle)
    hinweis(f"{rolle.value} auf: {', '.join(artefakte)}")

    if register.defekte:
        warnung(
            "Ohne Recht bleiben die Artefakte, die sich nicht laden liessen: "
            + ", ".join(sorted(d.id for d in register.defekte))
        )

    erfolg(f"'{benutzer.name}' kann sich anmelden.")
    schritt("Passwort")
    print(f"    {passwort}")
    hinweis(f"Umgebung: {umgebung}. Kein Wechsel noetig, kein Ablauf.")
    return 0


async def _pruefe_verwalter_bleibt(sitzung: AsyncSession, benutzer: Benutzer, was: str) -> None:
    """Sonst sperrt sich der letzte Verwalter selbst aus."""
    from ..auth import speicher
    from ..auth.dienst import pruefe_letzter_verwalter

    pruefe_letzter_verwalter(
        await speicher.zaehle_verwalter(sitzung),
        await speicher.ist_verwalter(sitzung, benutzer.id),
        was,
    )


async def _erwarte(sitzung: AsyncSession, name: str) -> Benutzer:
    from ..auth import speicher

    benutzer = await speicher.finde_benutzer(sitzung, name)
    if benutzer is None:
        raise CliFehler(f"Kein Konto namens '{name}'")
    return benutzer
