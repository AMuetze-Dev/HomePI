"""``homepi new <name>`` - legt ein neues Artefakt an.

Zwei Betriebsformen, dieselbe ``homepi-core``:

- ``modul`` (Standard): ein Paket unter ``modules/``, das sich per Entry Point
  im Gateway anmeldet. Zehn Artefakte sind damit ein Prozess statt zehn
  Container. Begründung in docs/06-artefakte.md.
- ``service``: ein eigenständiger Dienst mit eigenem Container. Für Artefakte,
  die dauerhaft rechnen, exotische Abhängigkeiten mitbringen oder wirklich
  unabhängig laufen müssen.

Erzeugt wird die Verdrahtung, nicht die Fachlichkeit: Projektdatei, Router,
Schichten, Tests, Oberfläche - und eine AGENTS.md, die beschreibt, was noch
zu tun ist.
"""

from __future__ import annotations

import argparse
import re
from importlib import resources
from pathlib import Path

from .project import Projekt, projekt_ermitteln
from .shell import CliFehler, erfolg, hinweis, schritt, warnung

NAME_MUSTER = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

#: Vorlage -> Zielpfad unterhalb des Artefaktverzeichnisses.
MODUL_DATEIEN = {
    "pyproject.toml.tmpl": "pyproject.toml",
    "init.py.tmpl": "src/homepi_{modul}/__init__.py",
    "schemas.py.tmpl": "src/homepi_{modul}/schemas.py",
    "modelle.py.tmpl": "src/homepi_{modul}/modelle.py",
    "dienst.py.tmpl": "src/homepi_{modul}/dienst.py",
    "speicher.py.tmpl": "src/homepi_{modul}/speicher.py",
    "router.py.tmpl": "src/homepi_{modul}/router.py",
    "conftest.py.tmpl": "tests/conftest.py",
    "test_dienst.py.tmpl": "tests/unit/test_dienst.py",
    "test_anmeldung.py.tmpl": "tests/unit/test_anmeldung.py",
    "test_router.py.tmpl": "tests/integration/test_router.py",
    "README.md.tmpl": "README.md",
    "AGENTS.md.tmpl": "AGENTS.md",
}

#: Vorlage -> Zielpfad unterhalb von services/web/src/module/<name>/.
WEB_DATEIEN = {
    "web_api.ts.tmpl": "api.ts",
    "web_seite.tsx.tmpl": "{Klasse}Seite.tsx",
    "web_seite.module.css.tmpl": "{Klasse}Seite.module.css",
    "web_test.tsx.tmpl": "{Klasse}Seite.test.tsx",
}

SERVICE_DATEIEN = {
    "pyproject.toml.tmpl": "pyproject.toml",
    "main.py.tmpl": "src/homepi_{modul}/main.py",
    "settings.py.tmpl": "src/homepi_{modul}/settings.py",
    "init.py.tmpl": "src/homepi_{modul}/__init__.py",
    "conftest.py.tmpl": "tests/conftest.py",
    "test_service.py.tmpl": "tests/unit/test_service.py",
    "Dockerfile.tmpl": "Dockerfile",
    "README.md.tmpl": "README.md",
}


def argumente(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name", help="Kennung, klein und mit Bindestrichen, z.B. 'messwerte'")
    parser.add_argument(
        "--modus",
        choices=["modul", "service"],
        default="modul",
        help="modul: läuft im Gateway (Standard). service: eigener Container.",
    )
    parser.add_argument("--titel", help="Beschriftung der Kachel (Standard: aus dem Namen)")
    parser.add_argument("--beschreibung", default="", help="eine Zeile unter der Kachel")
    parser.add_argument("--dir", dest="ziel", help="Zielverzeichnis überschreiben")
    parser.add_argument("--port", type=int, default=8000, help="nur bei --modus service")
    parser.add_argument("--no-db", action="store_true", help="ohne Datenbankanbindung")
    parser.add_argument("--no-web", action="store_true", help="ohne eigene Oberfläche")
    parser.add_argument("--force", action="store_true", help="vorhandene Dateien überschreiben")


def ausfuehren(args: argparse.Namespace) -> int:
    name: str = args.name
    if not NAME_MUSTER.match(name):
        raise CliFehler(
            f"'{name}' ist keine gültige Kennung. Erlaubt sind Kleinbuchstaben, "
            "Ziffern und Bindestriche, beginnend mit einem Buchstaben - die "
            "Kennung landet in URLs, Image-Namen und Python-Modulen."
        )

    projekt = projekt_ermitteln(Path.cwd())
    modul = name.replace("-", "_")
    klasse = "".join(teil.capitalize() for teil in name.split("-"))
    titel = args.titel or name.replace("-", " ").capitalize()
    besitzer = projekt.repo.split("/")[0].lower() if projekt.repo else "aendere-mich"

    ersetzungen = {
        "{{service}}": name,
        "{{modul}}": modul,
        "{{MODUL}}": modul.upper(),
        "{{Klasse}}": klasse,
        "{{titel}}": titel,
        "{{beschreibung}}": args.beschreibung or f"Artefakt {titel}",
        "{{port}}": str(args.port),
        "{{besitzer}}": besitzer,
        "{{repo}}": projekt.repo or "AMuetze-Dev/HomePI",
        "{{db_zeile}}": (
            "# ohne Datenbank - dieser Service braucht keine"
            if args.no_db
            else "DATABASE_URL: postgresql+asyncpg://app:${APP_DB_PASSWORD}@postgres:5432/app"
        ),
    }

    if args.modus == "modul":
        return _modul_anlegen(args, projekt, name, modul, klasse, ersetzungen)
    return _service_anlegen(args, projekt, name, modul, ersetzungen)


# --------------------------------------------------------------------- Modul


def _modul_anlegen(
    args: argparse.Namespace,
    projekt: Projekt,
    name: str,
    modul: str,
    klasse: str,
    ersetzungen: dict[str, str],
) -> int:
    ziel = Path(args.ziel) if args.ziel else projekt.wurzel / "modules" / name
    schritt(f"Artefakt '{name}' als Modul in {_kurz(ziel, projekt)}")

    vorlagen = dict(MODUL_DATEIEN)
    if args.no_db:
        for entfernen in ("modelle.py.tmpl", "speicher.py.tmpl", "test_router.py.tmpl"):
            vorlagen.pop(entfernen, None)

    geschrieben = _schreiben("modul", vorlagen, ziel, modul, klasse, ersetzungen, projekt, args)

    if not args.no_web:
        web_ziel = projekt.wurzel / "services" / "web" / "src" / "module" / name
        geschrieben += _schreiben(
            "modul", WEB_DATEIEN, web_ziel, modul, klasse, ersetzungen, projekt, args
        )
        _im_register_eintragen(projekt.wurzel, name, klasse)

    _im_gateway_eintragen(projekt.wurzel, name)

    erfolg(f"{geschrieben} Dateien angelegt.")
    print()
    hinweis("Weiter:")
    hinweis("  cd services/gateway && uv sync     # Modul in die Umgebung holen")
    hinweis("  make dev                           # Kachel erscheint auf der Startseite")
    hinweis(f"  cd modules/{name} && uv run ptw . --now")
    print()
    hinweis(f"Was zu tun ist, steht in modules/{name}/AGENTS.md")
    return 0


def _im_gateway_eintragen(wurzel: Path, name: str) -> None:
    """Traegt das Modul als Abhaengigkeit des Gateways ein.

    Ohne diesen Eintrag findet der Entry Point niemanden, der ihn laedt - das
    Artefakt existiert dann zwar, taucht aber nirgends auf.
    """
    datei = wurzel / "services" / "gateway" / "pyproject.toml"
    if not datei.is_file():
        warnung(f"{datei} nicht gefunden - Abhängigkeit bitte von Hand eintragen.")
        return

    inhalt = datei.read_text(encoding="utf-8")
    paket = f"homepi-{name}"
    if f'"{paket}"' in inhalt:
        return

    inhalt = inhalt.replace(
        '    "homepi-core",\n',
        f'    "homepi-core",\n    "{paket}",\n',
        1,
    )
    inhalt = inhalt.replace(
        'homepi-core = { path = "../../packages/homepi-core", editable = true }\n',
        'homepi-core = { path = "../../packages/homepi-core", editable = true }\n'
        f'{paket} = {{ path = "../../modules/{name}", editable = true }}\n',
        1,
    )
    datei.write_text(inhalt, encoding="utf-8", newline="\n")
    hinweis(f"in services/gateway/pyproject.toml eingetragen: {paket}")


def _im_register_eintragen(wurzel: Path, name: str, klasse: str) -> None:
    """Traegt die Oberflaeche in services/web/src/module/register.ts ein."""
    datei = wurzel / "services" / "web" / "src" / "module" / "register.ts"
    if not datei.is_file():
        warnung(f"{datei} nicht gefunden - Oberfläche bitte von Hand eintragen.")
        return

    inhalt = datei.read_text(encoding="utf-8")
    eintrag = f'  {{ id: "{name}", Komponente: {klasse}Seite }},'
    if eintrag in inhalt:
        return

    if "export const OBERFLAECHEN" not in inhalt:
        warnung("register.ts hat kein OBERFLAECHEN - Eintrag bitte von Hand ergänzen.")
        return

    zeilen = inhalt.splitlines()

    importzeile = f'import {{ {klasse}Seite }} from "./{name}/{klasse}Seite";'
    if importzeile not in zeilen:
        # Hinter den letzten vorhandenen Import, nicht an den Dateianfang:
        # sonst steht der neue vor allen anderen und die Reihenfolge zerfaellt
        # mit jedem Artefakt weiter.
        letzter = max((i for i, z in enumerate(zeilen) if z.startswith("import ")), default=-1)
        zeilen.insert(letzter + 1, importzeile)

    index = next(i for i, z in enumerate(zeilen) if z.startswith("export const OBERFLAECHEN"))
    zeilen.insert(index + 1, eintrag)
    datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
    hinweis(f"in services/web/src/module/register.ts eingetragen: {name}")


# ------------------------------------------------------------------- Service


def _service_anlegen(
    args: argparse.Namespace,
    projekt: Projekt,
    name: str,
    modul: str,
    ersetzungen: dict[str, str],
) -> int:
    ziel = Path(args.ziel) if args.ziel else projekt.wurzel / "services" / name
    schritt(f"Artefakt '{name}' als eigener Service in {_kurz(ziel, projekt)}")

    geschrieben = _schreiben(
        "service", SERVICE_DATEIEN, ziel, modul, "", ersetzungen, projekt, args
    )

    fragment = projekt.wurzel / "stacks" / "apps" / "services" / f"{name}.yml"
    if fragment.exists() and not args.force:
        warnung(f"übersprungen (existiert): {_kurz(fragment, projekt)}")
    else:
        fragment.parent.mkdir(parents=True, exist_ok=True)
        fragment.write_text(
            _rendern("service", "compose.yml.tmpl", ersetzungen), encoding="utf-8", newline="\n"
        )
        hinweis(_kurz(fragment, projekt))
        geschrieben += 1

    _im_stack_eintragen(projekt.wurzel, name)

    erfolg(f"{geschrieben} Dateien angelegt.")
    print()
    hinweis("Weiter:")
    hinweis(f"  cd services/{name} && uv sync && uv run pytest")
    hinweis(f"  .env ergänzen:  {modul.upper()}_IMAGE='...'")
    hinweis(f"  danach:  homepi deploy -s {name}")
    return 0


def _im_stack_eintragen(wurzel: Path, name: str) -> None:
    """Traegt das Compose-Fragment in die include-Liste des apps-Stacks ein."""
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


# -------------------------------------------------------------------- Hilfen


def _schreiben(
    satz: str,
    vorlagen: dict[str, str],
    ziel: Path,
    modul: str,
    klasse: str,
    ersetzungen: dict[str, str],
    projekt: Projekt,
    args: argparse.Namespace,
) -> int:
    geschrieben = 0
    for vorlage, zielpfad in vorlagen.items():
        datei = ziel / zielpfad.format(modul=modul, Klasse=klasse)
        if datei.exists() and not args.force:
            warnung(f"übersprungen (existiert): {_kurz(datei, projekt)}")
            continue
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(_rendern(satz, vorlage, ersetzungen), encoding="utf-8", newline="\n")
        hinweis(_kurz(datei, projekt))
        geschrieben += 1
    return geschrieben


def _rendern(satz: str, vorlage: str, ersetzungen: dict[str, str]) -> str:
    quelle = resources.files(f"homepi_core.templates.{satz}").joinpath(vorlage)
    text = quelle.read_text(encoding="utf-8")
    for platzhalter, wert in ersetzungen.items():
        text = text.replace(platzhalter, wert)
    return text


def _kurz(pfad: Path, projekt: Projekt) -> str:
    try:
        return str(pfad.relative_to(projekt.wurzel))
    except ValueError:
        return str(pfad)
