"""Ermittelt, um welches Projekt es überhaupt geht.

Der Servicename ist der Dreh- und Angelpunkt: er bestimmt den Image-Namen,
den Container, den Traefik-Hostnamen und welchen Teil der Pipeline
``homepi deploy`` anstößt. Deshalb wird er aus der Projektdatei gelesen und
nicht bei jedem Aufruf erneut eingetippt.

    [tool.homepi]
    service = "geraete"
    stack   = "apps"
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .shell import CliFehler, lauf


@dataclass(frozen=True)
class Projekt:
    wurzel: Path
    """Wurzel des Git-Repos."""
    verzeichnis: Path
    """Verzeichnis mit der pyproject.toml."""
    service: str
    stack: str
    version: str
    repo: str | None
    """owner/name des GitHub-Remotes, falls vorhanden."""

    @property
    def image(self) -> str:
        besitzer = self.repo.split("/")[0].lower() if self.repo else "unbekannt"
        return f"ghcr.io/{besitzer}/homepi-{self.service}"


def _repo_wurzel(start: Path) -> Path:
    ergebnis = lauf("git", "rev-parse", "--show-toplevel", cwd=str(start), pflicht=False)
    if not ergebnis.erfolg:
        raise CliFehler(
            f"{start} liegt in keinem Git-Repository. "
            "homepi arbeitet mit der Pipeline und braucht deshalb eines."
        )
    return Path(ergebnis.ausgabe)


def _pyproject_finden(start: Path, wurzel: Path) -> Path | None:
    aktuell = start.resolve()
    while True:
        kandidat = aktuell / "pyproject.toml"
        if kandidat.is_file():
            return kandidat
        if aktuell == wurzel or aktuell == aktuell.parent:
            return None
        aktuell = aktuell.parent


def _remote(wurzel: Path) -> str | None:
    ergebnis = lauf("git", "remote", "get-url", "origin", cwd=str(wurzel), pflicht=False)
    if not ergebnis.erfolg:
        return None
    url = ergebnis.ausgabe
    # https://github.com/Owner/Name.git  oder  git@github.com:Owner/Name.git
    for trenner in ("github.com/", "github.com:"):
        if trenner in url:
            return url.split(trenner, 1)[1].removesuffix(".git")
    return None


def _tabelle(daten: dict[str, object], schluessel: str) -> dict[str, object]:
    """tomllib liefert dict[str, Any]; hier wird daraus etwas, dem mypy traut."""
    wert = daten.get(schluessel)
    return wert if isinstance(wert, dict) else {}


def projekt_ermitteln(start: Path | None = None, *, service: str | None = None) -> Projekt:
    start = (start or Path.cwd()).resolve()
    wurzel = _repo_wurzel(start)
    pyproject = _pyproject_finden(start, wurzel)

    daten: dict[str, object] = {}
    verzeichnis = wurzel
    if pyproject is not None:
        verzeichnis = pyproject.parent
        daten = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    projekt_tabelle = _tabelle(daten, "project")
    homepi_tabelle = _tabelle(_tabelle(daten, "tool"), "homepi")

    name = (
        service
        or homepi_tabelle.get("service")
        # "homepi-geraete" -> "geraete": der Präfix steckt schon im Image-Namen
        or str(projekt_tabelle.get("name", "")).removeprefix("homepi-")
        or verzeichnis.name
    )

    return Projekt(
        wurzel=wurzel,
        verzeichnis=verzeichnis,
        service=str(name),
        stack=str(homepi_tabelle.get("stack", "apps")),
        version=str(projekt_tabelle.get("version", "0.0.0")),
        repo=_remote(wurzel),
    )
