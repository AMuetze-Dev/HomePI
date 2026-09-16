"""Einstiegspunkt der ``homepi``-CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import deploy, scaffold
from .project import projekt_ermitteln
from .shell import CliFehler, erfolg, fehler, hinweis, lauf, schritt, warnung

BESCHREIBUNG = """\
Werkzeug für HomePI-Microservices.

  homepi new <name>     neuen Service anlegen
  homepi deploy         über die GitHub-Pipeline auf den Pi bringen
  homepi info           erkanntes Projekt anzeigen
  homepi doctor         Voraussetzungen prüfen
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homepi",
        description=BESCHREIBUNG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    unterbefehle = parser.add_subparsers(dest="befehl", metavar="BEFEHL")

    p_new = unterbefehle.add_parser("new", help="neuen Microservice anlegen")
    scaffold.argumente(p_new)
    p_new.set_defaults(fn=scaffold.ausfuehren)

    p_deploy = unterbefehle.add_parser("deploy", help="Service auf den Pi bringen")
    deploy.argumente(p_deploy)
    p_deploy.set_defaults(fn=deploy.ausfuehren)

    p_info = unterbefehle.add_parser("info", help="erkanntes Projekt anzeigen")
    p_info.add_argument("-s", "--service", help="Servicename überschreiben")
    p_info.set_defaults(fn=_info)

    p_doctor = unterbefehle.add_parser("doctor", help="Voraussetzungen prüfen")
    p_doctor.set_defaults(fn=_doctor)

    p_version = unterbefehle.add_parser("version", help="Version von homepi-core")
    p_version.set_defaults(fn=_version)

    return parser


def _info(args: argparse.Namespace) -> int:
    projekt = projekt_ermitteln(Path.cwd(), service=getattr(args, "service", None))
    schritt("Erkanntes Projekt")
    for bezeichnung, wert in (
        ("Service", projekt.service),
        ("Version", projekt.version),
        ("Stack", projekt.stack),
        ("Verzeichnis", str(projekt.verzeichnis)),
        ("Repo-Wurzel", str(projekt.wurzel)),
        ("GitHub", projekt.repo or "-"),
        ("Image", projekt.image),
    ):
        print(f"    {bezeichnung:<12} {wert}")
    return 0


def _doctor(_: argparse.Namespace) -> int:
    schritt("Voraussetzungen")
    alles_gut = True

    for programm, hinweistext in (
        ("git", "https://git-scm.com"),
        ("gh", "https://cli.github.com"),
    ):
        ergebnis = lauf(programm, "--version", pflicht=False)
        if ergebnis.erfolg:
            erfolg(f"{programm}: {ergebnis.ausgabe.splitlines()[0]}")
        else:
            warnung(f"{programm} fehlt - {hinweistext}")
            alles_gut = False

    if lauf("gh", "auth", "status", pflicht=False).erfolg:
        erfolg("gh ist angemeldet")
    else:
        warnung("gh ist nicht angemeldet - einmalig: gh auth login")
        alles_gut = False

    try:
        projekt = projekt_ermitteln(Path.cwd())
    except CliFehler as problem:
        warnung(str(problem))
        return 1

    if projekt.repo:
        erfolg(f"Remote: {projekt.repo}")
    else:
        warnung("Kein GitHub-Remote 'origin' - homepi deploy funktioniert damit nicht")
        alles_gut = False

    if projekt.service in {"unbenannt", projekt.wurzel.name}:
        warnung(
            f"Servicename '{projekt.service}' stammt nicht aus [tool.homepi]. "
            "Trage ihn in der pyproject.toml ein."
        )

    if alles_gut:
        erfolg("Alles bereit.")
        return 0
    hinweis("Behebe die obigen Punkte, dann funktioniert 'homepi deploy'.")
    return 1


def _version(_: argparse.Namespace) -> int:
    from homepi_core import __version__

    print(__version__)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "fn"):
        parser.print_help()
        return 1

    try:
        return int(args.fn(args))
    except CliFehler as problem:
        fehler(str(problem))
        return 1
    except KeyboardInterrupt:
        fehler("Abgebrochen.")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
