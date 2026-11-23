"""Die Anmeldung selbst - ohne sie erscheint das Artefakt nirgends."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from fastapi.routing import APIRoute
from homepi_core import Modul, Zugang
from homepi_core.auth import Rolle

#: Das Modul. `homepi_staffelpilot.router` ist der APIRouter darin.
router_modul = import_module("homepi_staffelpilot.router")


def test_modul_ist_korrekt_beschrieben(modul: Modul) -> None:
    assert modul.id == "staffelpilot"
    assert modul.titel == "StaffelPilot"
    assert modul.praefix == "/staffelpilot"
    assert modul.version


def test_spielberichte_sind_nicht_oeffentlich(modul: Modul) -> None:
    """In einem Spielbericht stehen Namen und Entscheidungen ueber Personen.
    Waere das Artefakt oeffentlich, laege es auf jeder Seite offen, die dieses
    Gateway ausliefert."""
    assert modul.zugang is Zugang.GESCHUETZT
    assert not modul.sichtbar_fuer(None)
    assert not modul.sichtbar_fuer({"geraete": Rolle.VERWALTER})
    assert modul.sichtbar_fuer({"staffelpilot": Rolle.LESER})


def test_manifest_hat_die_felder_der_kachel(modul: Modul) -> None:
    eintrag = modul.manifest()

    assert eintrag["status"] == "bereit"
    assert eintrag["pfad"] == "/staffelpilot"


def test_entry_point_zeigt_auf_dieses_modul() -> None:
    """Prueft die Verdrahtung in pyproject.toml - ein Tippfehler dort faellt
    sonst erst auf, wenn die Kachel im Betrieb fehlt."""
    from importlib.metadata import entry_points

    punkte = {p.name: p for p in entry_points(group="homepi.module")}

    assert "staffelpilot" in punkte, "Artefakt ist nicht als homepi.module angemeldet"
    assert punkte["staffelpilot"].load().id == "staffelpilot"


def test_jeder_endpunkt_hat_eine_beschreibung(modul: Modul) -> None:
    """Ohne summary bleibt der Endpunkt in der generischen Ansicht namenlos."""
    ohne = [
        f"{methode.upper()} {route.path}"
        for route in modul.router.routes
        for methode in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}
        if not getattr(route, "summary", None)
    ]

    assert not ohne, f"ohne summary: {', '.join(ohne)}"


#: Was niemandem gehoert: die Regeldateien sind Programm und kein Inhalt.
OHNE_BLICK = {
    "regeldateien",
    "regeldatei",
    "regeldatei_setzen",
    "vorlagen_uebernehmen",
    "regeldatei_aendern",
    "regeldatei_loeschen",
}


def _haengt_am_blick(dependant: Any) -> bool:
    return any(d.call is router_modul._blick or _haengt_am_blick(d) for d in dependant.dependencies)


def test_jede_route_weiss_fuer_wen_sie_antwortet() -> None:
    """Eine neue Route, die den Blick vergisst, liest die Berichte aller."""
    ohne = {
        r.name
        for r in router_modul.router.routes
        if isinstance(r, APIRoute) and not _haengt_am_blick(r.dependant)
    }

    assert ohne == OHNE_BLICK
