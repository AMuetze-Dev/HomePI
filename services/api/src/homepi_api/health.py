"""Gesundheitsbewertung.

Die Auswertungslogik ist bewusst von I/O getrennt: ``evaluate`` ist eine reine
Funktion und laesst sich ohne Datenbank, ohne Redis und ohne Eventloop testen.
Genau das macht die TDD-Schleife schnell genug, um sie wirklich zu benutzen.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class HealthReport:
    status: Status
    checks: dict[str, bool]

    @property
    def http_status(self) -> int:
        """503, sobald etwas nicht stimmt - damit Uptime-Kuma anschlaegt."""
        return 200 if self.status is Status.OK else 503


#: Ohne diese Abhaengigkeiten kann die API nichts Sinnvolles tun.
ESSENTIAL = frozenset({"database"})


def evaluate(checks: dict[str, bool]) -> HealthReport:
    """Fasst Einzelpruefungen zu einem Gesamtzustand zusammen.

    - alles in Ordnung            -> ok
    - nur Nebensaechliches kaputt -> degraded (die API antwortet weiter)
    - eine essenzielle Abhaengigkeit kaputt -> down
    """
    if not checks:
        raise ValueError("mindestens eine Pruefung erwartet")

    failed = {name for name, healthy in checks.items() if not healthy}

    if not failed:
        status = Status.OK
    elif failed & ESSENTIAL:
        status = Status.DOWN
    else:
        status = Status.DEGRADED

    return HealthReport(status=status, checks=dict(checks))
