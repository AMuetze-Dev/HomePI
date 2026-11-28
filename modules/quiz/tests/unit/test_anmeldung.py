"""Die Anmeldung selbst - und die Sicherung an Stelle der Pruefung am Router.

Dieses Artefakt ist oeffentlich wie das Tischtennisturnier: Mitspieler
brauchen kein Konto. Damit haengt die Rechtepruefung nicht mehr am Router,
und die Tests hier sind nicht Formsache. Sie halten fest, welche Endpunkte
ohne Konto gehen - namentlich - und dass die Spieler-Endpunkte darunter das
Spielertoken verlangen.
"""

from __future__ import annotations

from fastapi.routing import APIRoute
from homepi_core import Modul, Zugang
from homepi_core.auth import Rolle

from homepi_quiz.router import hole_spieler

#: Was ohne Konto geht, mit Grund. Ein neuer Endpunkt ohne `erfordert` macht
#: den Test rot, bis er hier mit Begruendung steht.
OHNE_KONTO = {
    "GET /": "Kachel und Rauchtest - nur die Zahl laufender Runden",
    "GET /runden/{code}": "Stand fuer Spieler und Anzeigetafel, ohne Loesung bis zum Aufloesen",
    "GET /runden/{code}/bild": "Bild der gezeigten Frage, erst wenn die Leitung es freigibt",
    "GET /runden/{code}/medien/{schluessel}": "Ton und Antwortbilder, erst mit der Frage",
    "PUT /runden/{code}/team": "nur mit Spielertoken, nur vor dem Start",
    "POST /runden/{code}/beitreten": "Name waehlen - das Einzige, was ohne Token gehen muss",
    "PUT /runden/{code}/antwort": "nur mit Spielertoken",
    "POST /runden/{code}/buzzer": "nur mit Spielertoken",
}
#: Diese verlangen das Token im Cookie, ohne geht nichts.
MIT_SPIELERTOKEN = {
    "PUT /runden/{code}/antwort",
    "POST /runden/{code}/buzzer",
    "PUT /runden/{code}/team",
}


def _routen(modul: Modul) -> list[tuple[str, APIRoute]]:
    return [
        (f"{methode} {route.path}", route)
        for route in modul.router.routes
        if isinstance(route, APIRoute)
        for methode in sorted(route.methods - {"HEAD", "OPTIONS"})
    ]


def _haengt_an(route: APIRoute, funktion: object) -> bool:
    offen = list(route.dependant.dependencies)
    while offen:
        abhaengigkeit = offen.pop()
        if abhaengigkeit.call is funktion:
            return True
        offen.extend(abhaengigkeit.dependencies)
    return False


def test_modul_ist_korrekt_beschrieben(modul: Modul) -> None:
    assert modul.id == "quiz"
    assert modul.titel == "Quiz"
    assert modul.praefix == "/quiz"
    assert modul.version


def test_das_artefakt_ist_mit_absicht_oeffentlich(modul: Modul) -> None:
    """Mitspieler sollen ohne Konto beitreten koennen, ueber die Kachel und
    nicht nur ueber einen weitergegebenen Link - wie beim Tischtennis."""
    assert modul.zugang is Zugang.OEFFENTLICH
    assert modul.sichtbar_fuer(None), "Ein Besucher ohne Konto muss die Kachel sehen"
    assert modul.sichtbar_fuer({"quiz": Rolle.LESER})


def test_ohne_konto_geht_genau_die_liste(modul: Modul) -> None:
    """Der Test, der dieses Artefakt zusammenhaelt.

    Ein neuer Endpunkt ohne `erfordert` waere ein Formular, das jeder
    Besucher abschicken kann: Fragen samt Loesung lesen, Punkte verteilen,
    Spieler hinauswerfen.
    """
    ungeschuetzt = {name for name, route in _routen(modul) if not route.dependencies}

    assert ungeschuetzt == set(OHNE_KONTO), (
        f"neu ohne Pruefung: {sorted(ungeschuetzt - set(OHNE_KONTO))}, "
        f"nicht mehr offen: {sorted(set(OHNE_KONTO) - ungeschuetzt)}"
    )


def test_spieler_endpunkte_verlangen_das_token(modul: Modul) -> None:
    routen = dict(_routen(modul))
    for name in MIT_SPIELERTOKEN:
        assert _haengt_an(routen[name], hole_spieler), f"{name} prueft das Spielertoken nicht"


def test_fragen_und_loesungen_nur_mit_konto(modul: Modul) -> None:
    """Die Gegenprobe zur offenen Liste: wer ohne Konto die Kataloge lesen
    koennte, kennte alle Loesungen vor der Runde."""
    for name, route in _routen(modul):
        if name.split(" ")[1].startswith(("/kataloge", "/fragen", "/leitung")):
            assert route.dependencies, f"{name} ist ohne Konto erreichbar"


def test_manifest_hat_die_felder_der_kachel(modul: Modul) -> None:
    eintrag = modul.manifest()

    assert eintrag["status"] == "bereit"
    assert eintrag["pfad"] == "/quiz"
    assert eintrag["zugang"] == "oeffentlich"


def test_entry_point_zeigt_auf_dieses_modul() -> None:
    """Prueft die Verdrahtung in pyproject.toml - ein Tippfehler dort faellt
    sonst erst auf, wenn die Kachel im Betrieb fehlt."""
    from importlib.metadata import entry_points

    punkte = {p.name: p for p in entry_points(group="homepi.module")}

    assert "quiz" in punkte, "Artefakt ist nicht als homepi.module angemeldet"
    assert punkte["quiz"].load().id == "quiz"


def test_jeder_endpunkt_hat_eine_beschreibung(modul: Modul) -> None:
    """Ohne summary bleibt der Endpunkt in der generischen Ansicht namenlos."""
    ohne = [name for name, route in _routen(modul) if not route.summary]

    assert not ohne, f"ohne summary: {', '.join(ohne)}"


def test_kein_fester_pfad_hinter_einer_parametrisierten_route(modul: Modul) -> None:
    """Feste Pfade vor parametrisierten - sonst liest FastAPI 'reihenfolge'
    als UUID und antwortet 422."""
    gesehen: list[tuple[str, str]] = []
    for name, route in _routen(modul):
        methode = name.split(" ")[0]
        teile = route.path.strip("/").split("/")
        for frueher_methode, frueher in gesehen:
            frueher_teile = frueher.strip("/").split("/")
            if frueher_methode != methode or len(frueher_teile) != len(teile):
                continue
            verdeckt = all(
                a.startswith("{") or a == b for a, b in zip(frueher_teile, teile, strict=True)
            )
            assert not (verdeckt and frueher != route.path and not teile[-1].startswith("{")), (
                f"'{route.path}' steht hinter '{frueher}' und ist damit nicht erreichbar"
            )
        gesehen.append((methode, route.path))
