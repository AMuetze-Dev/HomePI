"""``homepi deploy`` - bringt einen Service über die vorhandene Pipeline auf den Pi.

Der Ablauf ist bewusst derselbe, den man auch von Hand über die GitHub-Oberfläche
gehen würde:

    1. prüfen, dass der lokale Stand dem Remote entspricht
    2. images.yml anstoßen  -> baut das arm64-Image und legt es in der GHCR ab
    3. warten, bis der Build durch ist
    4. deploy.yml anstoßen  -> der Pi zieht das Image und startet den Stack neu
    5. warten und das Ergebnis melden

Nichts davon läuft auf deinem Rechner: es gibt keinen lokalen Build, keine
Zugangsdaten zur Registry und keinen SSH-Schlüssel. Wenn die Pipeline es nicht
bauen kann, kommt es auch nicht auf den Pi.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from .project import Projekt, projekt_ermitteln
from .shell import CliFehler, durchreichen, erfolg, hinweis, lauf, schritt, warnung

IMAGES_WORKFLOW = "images.yml"
DEPLOY_WORKFLOW = "deploy.yml"


def argumente(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-s", "--service", help="Servicename (Standard: aus pyproject.toml)")
    parser.add_argument(
        "--ref", default="main", help="Branch, von dem gebaut wird (Standard: main)"
    )
    parser.add_argument("--stack", help="Compose-Stack (Standard: aus pyproject.toml, sonst apps)")
    parser.add_argument(
        "--images-only",
        action="store_true",
        help="nur das Image bauen, nicht ausrollen",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Läufe anstoßen und sofort zurückkehren",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="auch bei ungespeicherten Änderungen fortfahren",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="nur zeigen, was passieren würde",
    )


def ausfuehren(args: argparse.Namespace) -> int:
    projekt = projekt_ermitteln(Path.cwd(), service=args.service)
    stack = args.stack or projekt.stack

    schritt(f"Service '{projekt.service}' -> Stack '{stack}' (ref {args.ref})")
    hinweis(f"Repo:  {projekt.repo or 'kein GitHub-Remote gefunden'}")
    hinweis(f"Image: {projekt.image}")

    if projekt.repo is None:
        raise CliFehler(
            "Kein GitHub-Remote gefunden. homepi deploy steuert GitHub Actions "
            "und braucht deshalb ein Remote namens 'origin'."
        )

    _vorbedingungen(projekt, args.ref, erlaube_aenderungen=args.allow_dirty)

    if args.dry_run:
        warnung("Trockenlauf - es wird nichts angestoßen.")
        hinweis(f"gh workflow run {IMAGES_WORKFLOW} --ref {args.ref} -f service={projekt.service}")
        if not args.images_only:
            hinweis(f"gh workflow run {DEPLOY_WORKFLOW} --ref {args.ref} -f stack={stack}")
        return 0

    schritt("Image bauen")
    lauf_id = _workflow_starten(projekt, IMAGES_WORKFLOW, args.ref, {"service": projekt.service})
    if args.no_wait:
        erfolg(f"Angestoßen: {_lauf_url(projekt, lauf_id)}")
        return 0
    if not _auf_lauf_warten(projekt, lauf_id):
        raise CliFehler(
            f"Der Image-Build ist fehlgeschlagen: {_lauf_url(projekt, lauf_id)}\n"
            "Es wurde nichts ausgerollt."
        )
    erfolg("Image liegt in der Registry.")

    if args.images_only:
        hinweis("--images-only: kein Ausrollen.")
        return 0

    schritt("Auf den Pi ausrollen")
    deploy_id = _workflow_starten(projekt, DEPLOY_WORKFLOW, args.ref, {"stack": stack})
    if not _auf_lauf_warten(projekt, deploy_id):
        raise CliFehler(
            f"Das Ausrollen ist fehlgeschlagen: {_lauf_url(projekt, deploy_id)}\n"
            "Der vorherige Stand läuft weiter - Docker ersetzt einen Container "
            "erst, wenn der neue gestartet ist."
        )

    erfolg(f"{projekt.service} läuft in der neuen Fassung.")
    hinweis("Prüfen mit: curl -s https://api.<domain>/info | jq")
    return 0


# ---------------------------------------------------------------------------


def _vorbedingungen(projekt: Projekt, ref: str, *, erlaube_aenderungen: bool) -> None:
    cwd = str(projekt.wurzel)

    status = lauf("git", "status", "--porcelain", cwd=cwd).ausgabe
    if status and not erlaube_aenderungen:
        raise CliFehler(
            "Es gibt ungespeicherte Änderungen. Gebaut wird der Stand auf GitHub, "
            "nicht dein Arbeitsverzeichnis - das Ergebnis wäre also nicht das, "
            "was du gerade siehst.\n"
            "Erst committen und pushen, oder --allow-dirty setzen.\n\n"
            f"{status}"
        )

    lauf("git", "fetch", "--quiet", "origin", ref, cwd=cwd)
    lokal = lauf("git", "rev-parse", ref, cwd=cwd, pflicht=False)
    entfernt = lauf("git", "rev-parse", f"origin/{ref}", cwd=cwd)

    if lokal.erfolg and lokal.ausgabe != entfernt.ausgabe:
        warnung(
            f"Dein lokaler '{ref}' weicht von 'origin/{ref}' ab. "
            f"Gebaut wird origin/{ref} ({entfernt.ausgabe[:8]})."
        )

    # gh muss da UND angemeldet sein - sonst scheitert es erst nach dem
    # ersten Aufruf mit einer weniger hilfreichen Meldung.
    if not lauf("gh", "auth", "status", pflicht=False).erfolg:
        raise CliFehler(
            "Die GitHub-CLI ist nicht angemeldet. Einmalig: gh auth login\n"
            "Installation: https://cli.github.com"
        )


def _workflow_starten(projekt: Projekt, workflow: str, ref: str, eingaben: dict[str, str]) -> str:
    # Zeitstempel VOR dem Anstoßen merken: 'gh workflow run' liefert keine
    # Lauf-Kennung zurück, also muss der neue Lauf danach identifiziert werden.
    vorher = datetime.now(UTC)

    befehl = ["gh", "workflow", "run", workflow, "--ref", ref, "-R", projekt.repo or ""]
    for schluessel, wert in eingaben.items():
        befehl += ["-f", f"{schluessel}={wert}"]
    lauf(*befehl, cwd=str(projekt.wurzel))

    hinweis(f"{workflow} angestoßen, warte auf die Lauf-Kennung …")
    for _ in range(30):
        time.sleep(2)
        if (lauf_id := _neuester_lauf(projekt, workflow, nach=vorher)) is not None:
            hinweis(f"Lauf {lauf_id}: {_lauf_url(projekt, lauf_id)}")
            return lauf_id

    raise CliFehler(
        f"Nach 60 Sekunden ist kein neuer Lauf von {workflow} aufgetaucht. "
        f"Nachsehen: https://github.com/{projekt.repo}/actions"
    )


def _neuester_lauf(projekt: Projekt, workflow: str, *, nach: datetime) -> str | None:
    ergebnis = lauf(
        "gh",
        "run",
        "list",
        "-R",
        projekt.repo or "",
        "--workflow",
        workflow,
        "--limit",
        "10",
        "--json",
        "databaseId,createdAt",
        cwd=str(projekt.wurzel),
        pflicht=False,
    )
    if not ergebnis.erfolg:
        return None

    for eintrag in json.loads(ergebnis.ausgabe or "[]"):
        erstellt = datetime.fromisoformat(eintrag["createdAt"].replace("Z", "+00:00"))
        if erstellt >= nach.replace(microsecond=0):
            return str(eintrag["databaseId"])
    return None


def _auf_lauf_warten(projekt: Projekt, lauf_id: str) -> bool:
    code = durchreichen(
        "gh",
        "run",
        "watch",
        lauf_id,
        "-R",
        projekt.repo or "",
        "--exit-status",
        cwd=str(projekt.wurzel),
    )
    return code == 0


def _lauf_url(projekt: Projekt, lauf_id: str) -> str:
    return f"https://github.com/{projekt.repo}/actions/runs/{lauf_id}"
