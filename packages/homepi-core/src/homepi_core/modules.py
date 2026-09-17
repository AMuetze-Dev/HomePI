"""Module: Artefakte, die sich in einen laufenden Prozess einklinken.

Der Unterschied zum eigenständigen Microservice ist die Betriebsform, nicht
der Code. Ein Modul ist ein Python-Paket mit einem ``APIRouter``, das sich über
einen Entry Point anmeldet:

    # pyproject.toml des Artefakts
    [project.entry-points."homepi.module"]
    geraete = "homepi_geraete:modul"

    # homepi_geraete/__init__.py
    from fastapi import APIRouter
    from homepi_core import Modul

    router = APIRouter()

    @router.get("/")
    async def liste() -> list[str]: ...

    modul = Modul(id="geraete", titel="Geräte", router=router)

Das Gateway findet es beim Start, hängt den Router unter ``/geraete`` ein und
nennt es in ``GET /module``. Die Startseite liest genau diese Liste - ein neues
Artefakt erscheint dort, ohne dass am Frontend etwas geändert wird.

Der Preis gegenüber eigenen Containern: ein Absturz reißt alles mit, und zwei
Module können sich über unverträgliche Abhängigkeiten in die Quere kommen.
Deshalb überlebt das Gateway ein kaputtes Modul und meldet es, statt selbst
nicht zu starten - siehe ``entdecke_module``.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any

from fastapi import APIRouter

log = logging.getLogger(__name__)

GRUPPE = "homepi.module"

#: Beschraenkt die Auswahl beim Entwickeln, z.B. HOMEPI_MODULE=geraete,messwerte
AUSWAHL_VARIABLE = "HOMEPI_MODULE"

#: Die Kennung landet in URLs, im Traefik-Pfad und im Frontend-Router.
ID_MUSTER = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class Modul:
    id: str
    titel: str
    router: APIRouter
    beschreibung: str = ""
    #: Frei wählbarer Bezeichner, den das Frontend auf ein Symbol abbildet.
    icon: str = "kachel"
    version: str = "0.0.0"

    def __post_init__(self) -> None:
        if not ID_MUSTER.match(self.id):
            raise ValueError(
                f"'{self.id}' ist keine gültige Modulkennung. Erlaubt sind "
                "Kleinbuchstaben, Ziffern und Bindestriche - die Kennung "
                "landet in URLs und im Frontend-Router."
            )
        if not self.titel.strip():
            raise ValueError(f"Modul '{self.id}' braucht einen Titel für die Startseite")

    @property
    def praefix(self) -> str:
        return f"/{self.id}"

    def manifest(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "titel": self.titel,
            "pfad": self.praefix,
            "beschreibung": self.beschreibung,
            "icon": self.icon,
            "version": self.version,
            "status": "bereit",
        }


@dataclass(frozen=True, slots=True)
class DefektesModul:
    """Ein Modul, das sich nicht laden ließ.

    Es taucht trotzdem im Manifest auf. Ein Artefakt, das nach einem Deploy
    kommentarlos von der Startseite verschwindet, ist schwerer zu bemerken als
    eine Kachel, die 'Fehler' anzeigt.
    """

    id: str
    grund: str

    def manifest(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "titel": self.id,
            "pfad": "",
            "beschreibung": self.grund,
            "icon": "fehler",
            "version": "",
            "status": "fehler",
        }


@dataclass
class Modulregister:
    module: list[Modul] = field(default_factory=list)
    defekte: list[DefektesModul] = field(default_factory=list)

    @property
    def ids(self) -> list[str]:
        return [m.id for m in self.module]

    def manifest(self) -> list[dict[str, Any]]:
        eintraege = [m.manifest() for m in self.module] + [d.manifest() for d in self.defekte]
        return sorted(eintraege, key=lambda e: str(e["titel"]).casefold())


def gewuenschte_module() -> frozenset[str] | None:
    """Die Auswahl aus HOMEPI_MODULE, oder None für alle.

    Nur zum Entwickeln gedacht: mit zehn Artefakten dauert der Start des
    Gateways spürbar, und beim Arbeiten an einem davon interessieren die
    anderen neun nicht. In Produktion bleibt die Variable leer.
    """
    roh = os.environ.get(AUSWAHL_VARIABLE, "").strip()
    if not roh:
        return None
    return frozenset(teil.strip() for teil in roh.split(",") if teil.strip())


def entdecke_module(gruppe: str = GRUPPE) -> Modulregister:
    """Lädt alle angemeldeten Module.

    Ein Modul, das beim Laden wirft, wird übersprungen und vermerkt - sonst
    würde ein einziges fehlerhaftes Artefakt das gesamte Gateway blockieren.

    ``HOMEPI_MODULE`` beschränkt die Auswahl beim Entwickeln.
    """
    register = Modulregister()
    gesehen: set[str] = set()
    auswahl = gewuenschte_module()

    if auswahl is not None:
        log.warning("HOMEPI_MODULE ist gesetzt - es laufen nur: %s", ", ".join(sorted(auswahl)))

    for punkt in sorted(entry_points(group=gruppe), key=lambda p: p.name):
        # Vor dem Laden filtern: ein uebersprungenes Modul soll auch nicht
        # importiert werden, sonst spart die Auswahl keine Zeit.
        if auswahl is not None and punkt.name not in auswahl:
            continue
        try:
            geladen = punkt.load()
            modul = geladen() if callable(geladen) and not isinstance(geladen, Modul) else geladen
            if not isinstance(modul, Modul):
                raise TypeError(
                    f"Entry Point '{punkt.name}' liefert {type(modul).__name__}, "
                    "erwartet wird ein Modul"
                )
            if modul.id in gesehen:
                raise ValueError(f"Die Modulkennung '{modul.id}' ist doppelt vergeben")
            gesehen.add(modul.id)
            register.module.append(modul)
            log.info("Modul '%s' geladen (%s)", modul.id, modul.version)
        except Exception as problem:
            log.exception("Modul '%s' konnte nicht geladen werden", punkt.name)
            register.defekte.append(DefektesModul(id=punkt.name, grund=str(problem)))

    return register


def register_aus(module: Sequence[Modul]) -> Modulregister:
    """Register aus einer festen Liste - für Tests und für Gateways, die ihre
    Module bewusst aufzählen statt sie zu entdecken."""
    register = Modulregister()
    for modul in module:
        if modul.id in register.ids:
            raise ValueError(f"Die Modulkennung '{modul.id}' ist doppelt vergeben")
        register.module.append(modul)
    return register
