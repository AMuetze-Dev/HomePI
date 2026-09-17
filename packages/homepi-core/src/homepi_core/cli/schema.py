"""``homepi schema`` - Tabellen anlegen und nachsehen, was da ist.

Ein Startwerkzeug, **kein Migrationssystem**: es legt Fehlendes an und ändert
nichts Vorhandenes. In Produktion steht ``DB_SCHEMA_ANLEGEN`` deshalb auf
``false`` - ein Schema ändert man mit einer Migration. Beim allerersten Deploy
gibt es aber noch nichts zu migrieren, und genau dafür ist dieser Befehl da.

    homepi schema anlegen
    homepi schema zeigen
"""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import TYPE_CHECKING

from .shell import CliFehler, erfolg, hinweis, schritt, warnung

if TYPE_CHECKING:
    from ..schema import Schemastand


def argumente(parser: argparse.ArgumentParser) -> None:
    unter = parser.add_subparsers(dest="unterbefehl", metavar="BEFEHL", required=True)

    p_neu = unter.add_parser("anlegen", help="fehlende Tabellen anlegen")
    p_neu.add_argument(
        "--trocken",
        action="store_true",
        help="nur zeigen, was fehlt, ohne etwas zu ändern",
    )

    unter.add_parser("zeigen", help="bekannte und vorhandene Tabellen vergleichen")


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


def _bekannte_tabellen() -> list[str]:
    """Laedt alles, was Tabellen mitbringt, und gibt ihre Namen zurueck.

    Die Artefakte werden ueber dieselbe Entdeckung geladen wie im Gateway -
    sonst fehlten genau die Tabellen, die man anlegen wollte. Die Anmeldung
    kommt aus homepi-core selbst und wird deshalb ausdruecklich importiert.
    """
    from ..auth import modelle as auth_modelle  # noqa: F401  (registriert die Tabellen)
    from ..modelle import Base
    from ..modules import entdecke_module

    register = entdecke_module()
    if register.defekte:
        for defekt in register.defekte:
            warnung(f"Artefakt '{defekt.id}' laesst sich nicht laden: {defekt.grund}")
        warnung("Seine Tabellen fehlen entsprechend.")

    if register.ids:
        hinweis(f"Artefakte geladen: {', '.join(register.ids)}")
    else:
        warnung("Kein Artefakt gefunden - es entstehen nur die Tabellen der Anmeldung.")

    return sorted(Base.metadata.tables)


def _fehlende_spalten_melden(stand: Schemastand) -> None:
    """Der Fall, der frueher lautlos durchging.

    create_all legt fehlende Tabellen an und ruehrt vorhandene nicht an. Eine
    neue Spalte fehlt danach - und jede Abfrage auf diese Tabelle scheitert.
    """
    for tabelle, spalten in sorted(stand.fehlende_spalten.items()):
        warnung(f"{tabelle}: Spalte(n) {', '.join(spalten)} fehlen")
    hinweis("create_all legt nur fehlende Tabellen an und aendert keine vorhandene.")
    hinweis("Hier gehoert eine Migration hin - von Hand oder mit Alembic.")


async def _ausfuehren(args: argparse.Namespace) -> int:
    from ..db import Database
    from ..modelle import Base
    from ..schema import erwartet, stand

    schritt("Schema")
    bekannt = _bekannte_tabellen()

    datenbank = Database(_datenbank_url())
    try:
        ergebnis = await stand(datenbank)
        fehlende_tabellen = set(ergebnis.fehlende_tabellen)

        if args.unterbefehl == "zeigen":
            for name in bekannt:
                if name in fehlende_tabellen:
                    zeichen = "-"
                elif name in ergebnis.fehlende_spalten:
                    zeichen = "!"
                else:
                    zeichen = "+"
                print(f"    {zeichen} {name}")
            vorhanden = len(bekannt) - len(fehlende_tabellen)
            hinweis(f"{vorhanden} von {len(bekannt)} Tabellen vorhanden.")
            if ergebnis.fehlende_spalten:
                _fehlende_spalten_melden(ergebnis)
                return 1
            return 0

        if ergebnis.vollstaendig:
            erfolg(f"Nichts zu tun - alle {len(erwartet())} Tabellen sind vollstaendig.")
            return 0

        for name in ergebnis.fehlende_tabellen:
            hinweis(f"fehlt: {name}")

        if args.trocken:
            if ergebnis.fehlende_spalten:
                _fehlende_spalten_melden(ergebnis)
            warnung("Trockenlauf - nichts geaendert.")
            return 1 if ergebnis.fehlende_spalten else 0

        if ergebnis.fehlende_tabellen:
            async with datenbank.engine.begin() as verbindung:
                await verbindung.run_sync(Base.metadata.create_all)
            erfolg(f"{len(ergebnis.fehlende_tabellen)} Tabelle(n) angelegt.")

        if ergebnis.fehlende_spalten:
            # Bewusst ein Fehlschlag: sonst faehrt ein Deploy mit "alles gut"
            # weiter und die Anwendung ist trotzdem kaputt.
            _fehlende_spalten_melden(ergebnis)
            return 1

        hinweis("Aendert sich ein Schema spaeter, gehoert dort eine Migration hin.")
        return 0
    finally:
        await datenbank.dispose()
