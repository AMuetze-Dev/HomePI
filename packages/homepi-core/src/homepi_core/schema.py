"""Was die Anwendung erwartet, und was die Datenbank tatsächlich hat.

Der Grund für dieses Modul ist ein Fehler, der genau einmal passiert ist und
danach nie wieder passieren soll:

``Base.metadata.create_all`` legt **fehlende Tabellen** an und rührt
vorhandene nicht an. Kommt in einer Tabelle eine Spalte dazu, fehlt sie nach
dem Deploy — und zwar lautlos. Die Tabelle ist ja da. Erst die nächste Abfrage
scheitert mit ``column ... does not exist``, und weil das jede Abfrage auf
diese Tabelle betrifft, sieht es aus, als wären die Daten weg.

Deshalb vergleicht ``stand()`` Tabellen **und** Spalten. Migrieren kann es
nicht und soll es nicht - dafür gibt es Alembic. Es soll nur dafür sorgen,
dass niemand eine halbe Datenbank für eine ganze hält.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import inspect

if TYPE_CHECKING:
    from sqlalchemy.engine import Inspector

    from .db import Database


@dataclass(frozen=True, slots=True)
class Schemastand:
    """Der Unterschied zwischen Erwartung und Wirklichkeit."""

    fehlende_tabellen: list[str] = field(default_factory=list)
    #: Tabelle -> fehlende Spalten. Nur für Tabellen, die es schon gibt.
    fehlende_spalten: dict[str, list[str]] = field(default_factory=dict)

    @property
    def vollstaendig(self) -> bool:
        return not self.fehlende_tabellen and not self.fehlende_spalten

    @property
    def nur_tabellen_fehlen(self) -> bool:
        """Der harmlose Fall: eine frische Datenbank, die sich anlegen lässt."""
        return not self.fehlende_spalten

    def als_meldung(self) -> str:
        """Eine Zeile, die sagt, was zu tun ist - für Log und Kommandozeile."""
        if self.vollstaendig:
            return "Schema vollständig."

        teile = []
        if self.fehlende_tabellen:
            teile.append(f"fehlende Tabellen: {', '.join(self.fehlende_tabellen)}")
        for tabelle, spalten in sorted(self.fehlende_spalten.items()):
            teile.append(f"{tabelle} ohne {', '.join(spalten)}")
        return "; ".join(teile)


def erwartet() -> dict[str, set[str]]:
    """Tabelle -> Spaltennamen, so wie die Modelle sie beschreiben.

    Die Artefakte müssen vorher importiert sein, sonst kennt ``Base.metadata``
    ihre Tabellen nicht. Im Gateway erledigt das die Modulentdeckung.
    """
    from .modelle import Base

    return {
        name: {spalte.name for spalte in tabelle.columns}
        for name, tabelle in Base.metadata.tables.items()
    }


def _vergleiche(erwartung: dict[str, set[str]], pruefer: Inspector) -> Schemastand:
    vorhandene = set(pruefer.get_table_names())

    fehlende_tabellen = sorted(name for name in erwartung if name not in vorhandene)
    fehlende_spalten: dict[str, list[str]] = {}

    for name, spalten in erwartung.items():
        if name not in vorhandene:
            continue
        da = {s["name"] for s in pruefer.get_columns(name)}
        fehlt = sorted(spalten - da)
        if fehlt:
            fehlende_spalten[name] = fehlt

    return Schemastand(fehlende_tabellen=fehlende_tabellen, fehlende_spalten=fehlende_spalten)


async def stand(datenbank: Database) -> Schemastand:
    """Vergleicht die Modelle mit der laufenden Datenbank."""
    erwartung = erwartet()
    async with datenbank.connection() as verbindung:
        return await verbindung.run_sync(lambda s: _vergleiche(erwartung, inspect(s)))


def probe(datenbank: Database) -> Callable[[], Awaitable[bool]]:
    """Eine Sonde für die HealthRegistry.

    Sie meldet ``False``, sobald eine Spalte fehlt - dann steht ``/health`` auf
    ``degraded``, der Rauchtest wird nach dem Deploy rot, und niemand muss erst
    durch Zufall auf die kaputte Abfrage stoßen.

    Eine fehlende **Tabelle** zählt genauso: ohne sie scheitert jede Abfrage
    darauf ebenso.
    """
    import logging

    log = logging.getLogger(__name__)

    async def pruefen() -> bool:
        try:
            ergebnis = await stand(datenbank)
        except Exception:
            # Ist die Datenbank weg, meldet das der Datenbank-Check. Hier
            # waere ein zweites "down" nur Rauschen.
            return True
        if not ergebnis.vollstaendig:
            log.error("Schema unvollständig: %s", ergebnis.als_meldung())
        return ergebnis.vollstaendig

    return pruefen
