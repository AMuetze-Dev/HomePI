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

from .shell import CliFehler, erfolg, hinweis, schritt, warnung


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


async def _ausfuehren(args: argparse.Namespace) -> int:
    from sqlalchemy import inspect

    from ..db import Database
    from ..modelle import Base

    schritt("Schema")
    bekannt = _bekannte_tabellen()

    datenbank = Database(_datenbank_url())
    try:
        async with datenbank.connection() as verbindung:
            vorhanden = set(await verbindung.run_sync(lambda s: inspect(s).get_table_names()))

        fehlend = [name for name in bekannt if name not in vorhanden]

        if args.unterbefehl == "zeigen":
            for name in bekannt:
                zeichen = "+" if name in vorhanden else "-"
                print(f"    {zeichen} {name}")
            hinweis(f"{len(bekannt) - len(fehlend)} von {len(bekannt)} Tabellen vorhanden.")
            return 0

        if not fehlend:
            erfolg(f"Nichts zu tun - alle {len(bekannt)} Tabellen sind da.")
            return 0

        for name in fehlend:
            hinweis(f"fehlt: {name}")

        if args.trocken:
            warnung("Trockenlauf - nichts geaendert.")
            return 0

        async with datenbank.engine.begin() as verbindung:
            await verbindung.run_sync(Base.metadata.create_all)

        erfolg(f"{len(fehlend)} Tabelle(n) angelegt.")
        hinweis("Aendert sich ein Schema spaeter, gehoert dort eine Migration hin.")
        return 0
    finally:
        await datenbank.dispose()
