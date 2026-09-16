"""Gesundheitsbewertung.

``evaluate`` ist eine reine Funktion: keine Datenbank, kein Eventloop, keine
Fixtures. Das ist die Bedingung dafür, dass die Tests in Millisekunden laufen
und die rot-grün-Schleife benutzbar bleibt. Alles, was I/O macht, steckt in
den Sonden (``Probe``) und wird beim Testen ersetzt.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

#: Eine Sonde antwortet mit True, wenn ihre Abhängigkeit erreichbar ist.
#: Sie wirft nicht - ein Healthcheck, der eine Exception auslöst, ist kaputt.
ProbeFn = Callable[[], Awaitable[bool]]


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
        """503, sobald etwas nicht stimmt - damit Uptime-Kuma anschlägt und
        Traefik die Instanz aus dem Verkehr nimmt."""
        return 200 if self.status is Status.OK else 503

    def as_dict(self) -> dict[str, object]:
        return {"status": self.status.value, "checks": self.checks}


def evaluate(checks: dict[str, bool], essential: frozenset[str]) -> HealthReport:
    """Fasst Einzelprüfungen zu einem Gesamtzustand zusammen.

    - alles in Ordnung                        -> ok
    - nur Nebensächliches kaputt              -> degraded
    - eine essenzielle Abhängigkeit kaputt    -> down
    """
    if not checks:
        raise ValueError("mindestens eine Prüfung erwartet")

    gescheitert = {name for name, gesund in checks.items() if not gesund}

    if not gescheitert:
        status = Status.OK
    elif gescheitert & essential:
        status = Status.DOWN
    else:
        status = Status.DEGRADED

    return HealthReport(status=status, checks=dict(checks))


@dataclass
class HealthRegistry:
    """Sammelt die Sonden eines Service.

    ``essential=True`` heißt: ohne diese Abhängigkeit kann der Service nichts
    Sinnvolles tun. Die Datenbank ist meist essenziell, ein Cache selten.
    """

    _probes: dict[str, ProbeFn] = field(default_factory=dict)
    _essential: set[str] = field(default_factory=set)

    def register(self, name: str, probe: ProbeFn, *, essential: bool = True) -> None:
        if name in self._probes:
            raise ValueError(f"Sonde '{name}' ist bereits registriert")
        self._probes[name] = probe
        if essential:
            self._essential.add(name)

    def unregister(self, name: str) -> None:
        self._probes.pop(name, None)
        self._essential.discard(name)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._probes)

    async def run(self, *, timeout: float = 5.0) -> HealthReport:
        """Führt alle Sonden nebenläufig aus.

        Nebenläufig, weil sonst die Gesamtdauer die Summe aller Sonden wäre -
        bei drei Abhängigkeiten mit je fünf Sekunden Timeout wären das im
        schlimmsten Fall fünfzehn Sekunden, und der Healthcheck selbst würde
        zum Problem.
        """
        if not self._probes:
            # Ein Service ohne Abhängigkeiten ist gesund, sobald er antwortet.
            return HealthReport(status=Status.OK, checks={"self": True})

        namen = list(self._probes)

        async def sicher(probe: ProbeFn) -> bool:
            try:
                async with asyncio.timeout(timeout):
                    return await probe()
            except Exception:
                # Auch ein Timeout ist nur ein "nein", kein Absturz.
                return False

        ergebnisse = await asyncio.gather(*(sicher(self._probes[n]) for n in namen))
        return evaluate(dict(zip(namen, ergebnisse, strict=True)), frozenset(self._essential))
