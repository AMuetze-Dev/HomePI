"""Die Entscheidungen dieses Artefakts.

REIN: keine Datenbank, kein await, keine Fixtures. Genau deshalb laufen die
Tests dazu in Millisekunden - und nur deshalb benutzt man die rot-gruen-
Schleife wirklich. Alles, was I/O macht, gehoert in speicher.py.

Faustregel: Entscheidungen sind rein, Seiteneffekte sind dumm.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from homepi_core import ServiceError

from .schemas import Zusammenfassung


class StaffelUnbekannt(ServiceError):
    status = 404
    title = "Staffel unbekannt"


class SpielUnbekannt(ServiceError):
    status = 404
    title = "Spielbericht unbekannt"


class BefundUnbekannt(ServiceError):
    status = 404
    title = "Befund unbekannt"


class StaffelVergeben(ServiceError):
    status = 409
    title = "Staffel bereits angelegt"


class NochOffeneBefunde(ServiceError):
    status = 409
    title = "Es sind noch Befunde offen"


class GrundFehlt(ServiceError):
    status = 422
    title = "Begruendung fehlt"


@dataclass(frozen=True, slots=True)
class BefundSicht:
    """Das Wenige, das die Regeln von einem Befund brauchen.

    Ein eigener Typ und nicht die Tabelle: so bleiben die Entscheidungen ohne
    Datenbank testbar, und eine Spalte mehr in `modelle.py` zwingt niemanden,
    die Tests anzufassen.
    """

    schwere: str
    entscheidung: str
    regel: str = ""
    titel: str = ""


@dataclass(frozen=True, slots=True)
class SpielSicht:
    abgehakt: bool
    befunde: list[BefundSicht] = field(default_factory=list)


# ── Abhaken ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Abhakbar:
    """Als eigener Typ statt als bool, damit der Grund an der Entscheidung
    haengt und der Router ihn weiterreichen kann, ohne ihn zu erraten."""

    erlaubt: bool
    offen: int = 0
    grund: str = ""


def darf_abgehakt_werden(befunde: Iterable[BefundSicht]) -> Abhakbar:
    """Die eine Zusage dieses Artefakts: nichts uebersehen.

    Ein Spielbericht gilt erst als erledigt, wenn zu **jedem** Befund eine
    Entscheidung vorliegt - gleich welcher Schwere. Auch ein Hinweis will
    gesehen worden sein; genau dafuer gibt es 'zur Kenntnis genommen'.
    """
    offen = sum(1 for b in befunde if b.entscheidung == "offen")
    if not offen:
        return Abhakbar(True)
    wort = "Befund braucht" if offen == 1 else "Befunde brauchen"
    return Abhakbar(False, offen, f"{offen} {wort} noch eine Entscheidung")


# ── Entscheidung ──────────────────────────────────────────────────────────


def entscheidung_pruefen(art: str, grund: str) -> str:
    """Gibt den bereinigten Grund zurueck oder wirft.

    'verworfen' heisst: kein Verstoss. Das ist die einzige Entscheidung, die
    einen Befund aus der Bearbeitung nimmt - ohne Begruendung waere sie ein
    halbes Jahr spaeter nicht mehr nachvollziehbar, und genau danach fragt ein
    Verein.
    """
    bereinigt = grund.strip()
    if art == "verworfen" and not bereinigt:
        raise GrundFehlt("Zum Verwerfen eines Befundes gehört eine Begründung")
    return bereinigt


# ── Reihenfolge ───────────────────────────────────────────────────────────

#: Kritisch zuerst. Ein Feldverweis darf nicht unter zwanzig Hinweisen
#: verschwinden - das war der Grund, aus dem es diese Sortierung gibt.
_GEWICHT = {"kritisch": 0, "warnung": 1, "hinweis": 2}


def sortiert(befunde: Iterable[BefundSicht]) -> list[BefundSicht]:
    """Schwere zuerst, offene vor entschiedenen, sonst wie eingegangen.

    Stabil: sonst springen Befunde gleicher Schwere bei jedem Laden umher, und
    man verliert die Stelle, an der man gerade war.
    """
    return sorted(
        befunde,
        key=lambda b: (_GEWICHT.get(b.schwere, 9), 0 if b.entscheidung == "offen" else 1),
    )


# ── Faelligkeit ───────────────────────────────────────────────────────────


def ist_faellig(datum: date, heute: date, tage: int) -> bool:
    """Ob ein Spiel in den Pruefzeitraum faellt.

    Nach vorn ist die Grenze scharf: ein Spiel in der Zukunft ist noch nicht
    gespielt, und ein Befund darauf waere eine Erfindung.
    """
    if datum > heute:
        return False
    return (heute - datum).days <= tage


# ── Zusammenfassung ───────────────────────────────────────────────────────


def zusammenfassen(spiele: Iterable[SpielSicht], staffeln_aktiv: int) -> Zusammenfassung:
    liste = list(spiele)
    offene_befunde = [b for s in liste for b in s.befunde if b.entscheidung == "offen"]
    return Zusammenfassung(
        spiele=len(liste),
        offen=sum(1 for s in liste if not s.abgehakt),
        abgehakt=sum(1 for s in liste if s.abgehakt),
        befunde_offen=len(offene_befunde),
        # Nur was noch offen ist: ein entschiedener Feldverweis ist keine
        # offene Arbeit mehr und darf die Zahl auf der Kachel nicht dauerhaft
        # rot halten.
        befunde_kritisch=sum(1 for b in offene_befunde if b.schwere == "kritisch"),
        staffeln_aktiv=staffeln_aktiv,
    )
