"""Die Anmeldung selbst - ohne sie erscheint das Artefakt nirgends.

Dieses Artefakt ist das einzige oeffentliche im Haus. Damit entfaellt die
Pruefung am Router, und die Tests hier sind nicht Formsache, sondern die
Sicherung an ihrer Stelle.
"""

from __future__ import annotations

from fastapi.routing import APIRoute
from homepi_core import Modul, Zugang
from homepi_core.auth import Rolle

#: Was ohne Anmeldung gehen soll - und nur das.
OEFFENTLICH_LESEND = {"GET"}


def test_modul_ist_korrekt_beschrieben(modul: Modul) -> None:
    assert modul.id == "tischtennis"
    assert modul.titel == "Tischtennisturnier"
    assert modul.praefix == "/tischtennis"
    assert modul.version


def test_das_artefakt_ist_mit_absicht_oeffentlich(modul: Modul) -> None:
    """Die Dashboard-Ansicht ist der Grund, warum dieses Artefakt offen ist:
    die Kollegen sollen ohne Konto sehen koennen, wer gerade spielt."""
    assert modul.zugang is Zugang.OEFFENTLICH
    assert modul.sichtbar_fuer(None), "Ein Besucher ohne Konto muss die Kachel sehen"
    assert modul.sichtbar_fuer({"tischtennis": Rolle.LESER})


def test_jeder_schreibende_endpunkt_prueft_selbst(modul: Modul) -> None:
    """Der Test, der dieses Artefakt zusammenhaelt.

    Bei einem geschuetzten Artefakt haengt die Pruefung am Router und gilt
    damit auch fuer Endpunkte, die es heute noch nicht gibt. Dieses ist
    oeffentlich - also gilt sie nur dort, wo sie steht. Ein neuer Endpunkt
    ohne `erfordert` waere ein Formular, das jeder Besucher abschicken kann:
    Ergebnisse aendern, Teilnehmer loeschen, neu auswuerfeln.
    """
    ungeschuetzt = [
        f"{methode} {route.path}"
        for route in modul.router.routes
        if isinstance(route, APIRoute)
        for methode in sorted(route.methods - {"HEAD", "OPTIONS"})
        if methode not in OEFFENTLICH_LESEND and not route.dependencies
    ]

    assert not ungeschuetzt, f"ohne Rechtepruefung: {', '.join(ungeschuetzt)}"


def test_lesende_endpunkte_bleiben_offen(modul: Modul) -> None:
    """Die Gegenprobe: waere das Dashboard versehentlich geschuetzt, waere
    der ganze Zweck dieses Artefakts weg - und zwar unbemerkt, denn der
    Turnierleiter ist angemeldet und saehe es."""
    dashboard = [
        route
        for route in modul.router.routes
        if isinstance(route, APIRoute) and route.path == "/dashboard"
    ]

    assert dashboard, "Der Endpunkt /dashboard fehlt"
    assert not dashboard[0].dependencies


def test_manifest_hat_die_felder_der_kachel(modul: Modul) -> None:
    eintrag = modul.manifest()

    assert eintrag["status"] == "bereit"
    assert eintrag["pfad"] == "/tischtennis"
    assert eintrag["zugang"] == "oeffentlich"


def test_entry_point_zeigt_auf_dieses_modul() -> None:
    """Prueft die Verdrahtung in pyproject.toml - ein Tippfehler dort faellt
    sonst erst auf, wenn die Kachel im Betrieb fehlt."""
    from importlib.metadata import entry_points

    punkte = {p.name: p for p in entry_points(group="homepi.module")}

    assert "tischtennis" in punkte, "Artefakt ist nicht als homepi.module angemeldet"
    assert punkte["tischtennis"].load().id == "tischtennis"


def test_jeder_endpunkt_hat_eine_beschreibung(modul: Modul) -> None:
    """Ohne summary bleibt der Endpunkt in der generischen Ansicht namenlos."""
    ohne = [
        f"{methode.upper()} {route.path}"
        for route in modul.router.routes
        for methode in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}
        if not getattr(route, "summary", None)
    ]

    assert not ohne, f"ohne summary: {', '.join(ohne)}"


def test_kein_endpunkt_steht_vor_einer_parametrisierten_route(modul: Modul) -> None:
    """Feste Pfade vor parametrisierten - sonst liest FastAPI 'dashboard' als
    UUID und antwortet 422. Hier geprueft statt im Betrieb bemerkt."""
    gesehen: list[str] = []
    for route in modul.router.routes:
        if not isinstance(route, APIRoute):
            continue
        teile = route.path.strip("/").split("/")
        for frueher in gesehen:
            frueher_teile = frueher.strip("/").split("/")
            if len(frueher_teile) != len(teile):
                continue
            # Deckt eine frueher angemeldete parametrisierte Route diesen
            # festen Pfad ab?
            verdeckt = all(
                a.startswith("{") or a == b for a, b in zip(frueher_teile, teile, strict=True)
            )
            fest = all(not teil.startswith("{") for teil in teile)
            assert not (verdeckt and fest and frueher != route.path), (
                f"'{route.path}' steht hinter '{frueher}' und ist damit nicht erreichbar"
            )
        gesehen.append(route.path)
