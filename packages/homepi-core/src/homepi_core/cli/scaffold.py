"""``homepi new <name>`` - legt einen neuen Microservice an.

Erzeugt wird nur, was ohne Nachdenken gleich aussehen soll: Projektdatei,
Einstiegspunkt, Einstellungen, ein erster Test, Dockerfile und das
Compose-Fragment für den apps-Stack. Die Fachlichkeit schreibst du selbst -
dafür gibt es keine Vorlage.
"""

from __future__ import annotations

import argparse
import re
from importlib import resources
from pathlib import Path

from .project import projekt_ermitteln
from .shell import CliFehler, erfolg, hinweis, schritt, warnung

NAME_MUSTER = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

VORLAGEN = {
    "pyproject.toml.tmpl": "pyproject.toml",
    "main.py.tmpl": "src/homepi_{modul}/main.py",
    "settings.py.tmpl": "src/homepi_{modul}/settings.py",
    "init.py.tmpl": "src/homepi_{modul}/__init__.py",
    "conftest.py.tmpl": "tests/conftest.py",
    "test_service.py.tmpl": "tests/unit/test_service.py",
    "Dockerfile.tmpl": "Dockerfile",
    "README.md.tmpl": "README.md",
}

COMPOSE_VORLAGE = "compose.yml.tmpl"


def argumente(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name", help="Servicename, klein und mit Bindestrichen, z.B. 'geraete'")
    parser.add_argument(
        "--dir",
        dest="ziel",
        help="Zielverzeichnis (Standard: services/<name> im Repo)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Port im Container")
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="ohne Datenbankanbindung erzeugen",
    )
    parser.add_argument("--force", action="store_true", help="vorhandene Dateien überschreiben")


def ausfuehren(args: argparse.Namespace) -> int:
    name: str = args.name
    if not NAME_MUSTER.match(name):
        raise CliFehler(
            f"'{name}' ist kein gültiger Servicename. Erlaubt sind Kleinbuchstaben, "
            "Ziffern und Bindestriche, beginnend mit einem Buchstaben - der Name "
            "landet in Hostnamen, Image-Namen und Python-Modulen."
        )

    projekt = projekt_ermitteln(Path.cwd())
    ziel = Path(args.ziel) if args.ziel else projekt.wurzel / "services" / name
    modul = name.replace("-", "_")
    besitzer = projekt.repo.split("/")[0].lower() if projekt.repo else "aendere-mich"

    ersetzungen = {
        "{{service}}": name,
        "{{modul}}": modul,
        "{{MODUL}}": modul.upper(),
        "{{port}}": str(args.port),
        "{{besitzer}}": besitzer,
        "{{repo}}": projekt.repo or "AMuetze-Dev/HomePI",
        "{{db_zeile}}": (
            "# ohne Datenbank - dieser Service braucht keine"
            if args.no_db
            else "DATABASE_URL: postgresql+asyncpg://app:${APP_DB_PASSWORD}@postgres:5432/app"
        ),
    }

    schritt(f"Neuer Service '{name}' in {ziel.relative_to(projekt.wurzel)}")

    geschrieben = 0
    for vorlage, zielpfad in VORLAGEN.items():
        datei = ziel / zielpfad.format(modul=modul)
        if datei.exists() and not args.force:
            warnung(f"übersprungen (existiert): {datei.relative_to(projekt.wurzel)}")
            continue
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(_rendern(vorlage, ersetzungen), encoding="utf-8", newline="\n")
        hinweis(f"{datei.relative_to(projekt.wurzel)}")
        geschrieben += 1

    # Compose-Fragment in den apps-Stack
    fragment = projekt.wurzel / "stacks" / "apps" / "services" / f"{name}.yml"
    if fragment.exists() and not args.force:
        warnung(f"übersprungen (existiert): {fragment.relative_to(projekt.wurzel)}")
    else:
        fragment.parent.mkdir(parents=True, exist_ok=True)
        fragment.write_text(_rendern(COMPOSE_VORLAGE, ersetzungen), encoding="utf-8", newline="\n")
        hinweis(f"{fragment.relative_to(projekt.wurzel)}")
        geschrieben += 1

    _im_stack_eintragen(projekt.wurzel, name)

    erfolg(f"{geschrieben} Dateien angelegt.")
    print()
    hinweis("Weiter:")
    hinweis(f"  cd services/{name} && uv sync && uv run pytest")
    hinweis(f"  .env ergänzen:  {modul.upper()}_IMAGE='ghcr.io/{besitzer}/homepi-{name}:latest'")
    hinweis(f"  danach:  homepi deploy -s {name}")
    return 0


def _rendern(vorlage: str, ersetzungen: dict[str, str]) -> str:
    quelle = resources.files("homepi_core.templates.service").joinpath(vorlage)
    text = quelle.read_text(encoding="utf-8")
    for platzhalter, wert in ersetzungen.items():
        text = text.replace(platzhalter, wert)
    return text


def _im_stack_eintragen(wurzel: Path, name: str) -> None:
    """Trägt das Fragment in die include-Liste des apps-Stacks ein."""
    stack = wurzel / "stacks" / "apps" / "docker-compose.yml"
    if not stack.is_file():
        warnung(f"{stack} nicht gefunden - Fragment bitte von Hand eintragen.")
        return

    inhalt = stack.read_text(encoding="utf-8")
    zeile = f"  - services/{name}.yml"
    if zeile in inhalt:
        return

    if "include:" not in inhalt:
        warnung("Der apps-Stack benutzt kein 'include:'. Trage das Fragment von Hand ein.")
        return

    zeilen = inhalt.splitlines()
    index = next(i for i, z in enumerate(zeilen) if z.strip() == "include:")
    letzte = index
    for i in range(index + 1, len(zeilen)):
        if zeilen[i].startswith("  - "):
            letzte = i
        elif zeilen[i].strip():
            break
    zeilen.insert(letzte + 1, zeile)
    stack.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
    hinweis(f"in stacks/apps/docker-compose.yml eingetragen: services/{name}.yml")
