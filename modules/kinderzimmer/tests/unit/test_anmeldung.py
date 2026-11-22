"""Die Anmeldung selbst - ohne sie erscheint das Artefakt nirgends."""

from __future__ import annotations

from fastapi.routing import APIRoute
from homepi_core import Modul, Zugang
from homepi_core.auth import Rolle

from homepi_kinderzimmer.geraet import aktuelles_geraet


def _aufrufe(route: APIRoute) -> list[object]:
    """Alle Abhaengigkeiten der Route, auch die verschachtelten."""
    gefunden: list[object] = []
    offen = list(route.dependant.dependencies)
    while offen:
        abhaengigkeit = offen.pop()
        gefunden.append(abhaengigkeit.call)
        offen.extend(abhaengigkeit.dependencies)
    return gefunden


def _prueft_rechte(route: APIRoute) -> bool:
    return any(
        getattr(aufruf, "__qualname__", "").startswith("erfordert.") for aufruf in _aufrufe(route)
    )


def test_modul_ist_korrekt_beschrieben(modul: Modul) -> None:
    assert modul.id == "kinderzimmer"
    assert modul.titel == "Kinderzimmer"
    assert modul.praefix == "/kinderzimmer"
    assert modul.version


def test_der_zugang_ist_bewusst_gesetzt(modul: Modul) -> None:
    """SELBST, weil das Geraet kein Konto hat. Sichtbar bleibt das Artefakt
    trotzdem nur fuer Rechteinhaber."""
    assert modul.zugang is Zugang.SELBST
    assert not modul.sichtbar_fuer(None)
    assert modul.sichtbar_fuer({"kinderzimmer": Rolle.LESER})


def test_jede_route_prueft_eltern_oder_geraet(modul: Modul) -> None:
    """Der Test, der dieses Artefakt zusammenhaelt.

    Ohne Pruefung am Modul gilt nur, was am Router haengt. Eine Route ohne
    beides waere fuer jeden Besucher offen - auch aus dem Internet.
    """
    offen = [
        f"{sorted(route.methods)} {route.path}"
        for route in modul.router.routes
        if isinstance(route, APIRoute)
        and not _prueft_rechte(route)
        and aktuelles_geraet not in _aufrufe(route)
    ]

    assert not offen, f"ohne Pruefung: {', '.join(offen)}"


def test_geraetepfade_verlangen_das_token_und_nur_das(modul: Modul) -> None:
    """Das Geraet hat kein Konto - eine Rechtepruefung dort sperrte es aus.
    Und umgekehrt: kein Elternpfad laesst sich mit einem Geraetetoken oeffnen."""
    for route in modul.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path.startswith("/geraet/"):
            assert aktuelles_geraet in _aufrufe(route), route.path
            assert not _prueft_rechte(route), route.path
        else:
            assert aktuelles_geraet not in _aufrufe(route), route.path


def test_schreibende_elternpfade_verlangen_mehr_als_lesen(modul: Modul) -> None:
    """Ein Leser (etwa die Grosseltern) darf schauen, aber nichts aendern."""
    nur_lesend = [
        f"{sorted(route.methods)} {route.path}"
        for route in modul.router.routes
        if isinstance(route, APIRoute)
        and not route.path.startswith("/geraet/")
        and route.methods - {"GET", "HEAD"}
        and sum(getattr(a, "__qualname__", "").startswith("erfordert.") for a in _aufrufe(route))
        < 2
    ]

    assert not nur_lesend, f"nur mit Leserecht: {', '.join(nur_lesend)}"


def test_manifest_hat_die_felder_der_kachel(modul: Modul) -> None:
    eintrag = modul.manifest()

    assert eintrag["status"] == "bereit"
    assert eintrag["pfad"] == "/kinderzimmer"


def test_entry_point_zeigt_auf_dieses_modul() -> None:
    """Prueft die Verdrahtung in pyproject.toml - ein Tippfehler dort faellt
    sonst erst auf, wenn die Kachel im Betrieb fehlt."""
    from importlib.metadata import entry_points

    punkte = {p.name: p for p in entry_points(group="homepi.module")}

    assert "kinderzimmer" in punkte, "Artefakt ist nicht als homepi.module angemeldet"
    assert punkte["kinderzimmer"].load().id == "kinderzimmer"


def test_jeder_endpunkt_hat_eine_beschreibung(modul: Modul) -> None:
    """Ohne summary bleibt der Endpunkt in der generischen Ansicht namenlos."""
    ohne = [
        f"{methode.upper()} {route.path}"
        for route in modul.router.routes
        for methode in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}
        if not getattr(route, "summary", None)
    ]

    assert not ohne, f"ohne summary: {', '.join(ohne)}"
