"""Die Entscheidungen dieses Artefakts.

Reine Funktionen: keine Datenbank, kein await, keine Fixtures. Genau deshalb
laufen ihre Tests in Millisekunden und die rot-gruen-Schleife bleibt benutzbar.
Alles, was I/O macht, steht in speicher.py.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from homepi_core import ServiceError

from .schemas import Zusammenfassung


class GeraetUnbekannt(ServiceError):
    status = 404
    title = "Gerät unbekannt"


class NameVergeben(ServiceError):
    status = 409
    title = "Name bereits vergeben"


class NichtSchaltbar(ServiceError):
    status = 409
    title = "Gerät ist nicht schaltbar"


@dataclass(frozen=True, slots=True)
class Schaltbar:
    """Ein Geraet im Zustand 'wartung' laesst sich nicht schalten.

    Als eigener Typ statt als bool, damit der Grund an der Entscheidung haengt
    und der Aufrufer ihn weiterreichen kann, ohne ihn zu erraten.
    """

    erlaubt: bool
    grund: str = ""


def darf_geschaltet_werden(zustand: str) -> Schaltbar:
    if zustand == "wartung":
        return Schaltbar(False, "Das Gerät steht auf Wartung und lässt sich nicht schalten")
    return Schaltbar(True)


@dataclass(frozen=True, slots=True)
class GeraetSicht:
    """Das Wenige, das die Zusammenfassung braucht - damit sie nicht von der
    Tabelle abhaengt und ohne Datenbank testbar bleibt."""

    raum: str
    zustand: str
    eingeschaltet: bool


def zusammenfassen(geraete: Iterable[GeraetSicht]) -> Zusammenfassung:
    liste = list(geraete)
    return Zusammenfassung(
        anzahl=len(liste),
        eingeschaltet=sum(1 for g in liste if g.eingeschaltet),
        in_wartung=sum(1 for g in liste if g.zustand == "wartung"),
        raeume=dict(sorted(Counter(g.raum for g in liste).items())),
    )
