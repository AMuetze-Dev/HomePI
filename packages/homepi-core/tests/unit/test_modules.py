"""Modulregister: die Grundlage dafuer, dass ein neues Artefakt auf der
Startseite erscheint, ohne dass am Frontend etwas geaendert wird."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from homepi_core import Modul, ServiceSettings, create_service, register_aus
from homepi_core.modules import DefektesModul, Modulregister, entdecke_module


def _modul(kennung: str, titel: str | None = None) -> Modul:
    router = APIRouter()

    @router.get("/")
    async def wurzel() -> dict[str, str]:
        return {"modul": kennung}

    return Modul(id=kennung, titel=titel or kennung.title(), router=router, version="1.0.0")


# --- Modul -----------------------------------------------------------------


@pytest.mark.parametrize("kennung", ["Geraete", "1a", "mit_unterstrich", "mit leer", "-x"])
def test_unbrauchbare_kennung_wird_abgelehnt(kennung: str) -> None:
    """Die Kennung landet in URLs und im Frontend-Router."""
    with pytest.raises(ValueError, match="Modulkennung"):
        Modul(id=kennung, titel="X", router=APIRouter())


def test_modul_ohne_titel_wird_abgelehnt() -> None:
    with pytest.raises(ValueError, match="Titel"):
        Modul(id="x", titel="   ", router=APIRouter())


def test_praefix_folgt_der_kennung() -> None:
    assert _modul("geraete").praefix == "/geraete"


# --- Register --------------------------------------------------------------


def test_doppelte_kennung_faellt_auf() -> None:
    with pytest.raises(ValueError, match="doppelt"):
        register_aus([_modul("geraete"), _modul("geraete")])


def test_manifest_ist_alphabetisch_nach_titel() -> None:
    register = register_aus([_modul("zeit", "Zeit"), _modul("akku", "Akku")])

    assert [e["titel"] for e in register.manifest()] == ["Akku", "Zeit"]


def test_defektes_modul_steht_im_manifest() -> None:
    """Ein Artefakt, das kommentarlos von der Startseite verschwindet, ist
    schwerer zu bemerken als eine Kachel mit 'Fehler'."""
    register = Modulregister(
        module=[_modul("geraete")],
        defekte=[DefektesModul(id="kaputt", grund="ImportError: kein pandas")],
    )

    eintraege = {str(e["id"]): e for e in register.manifest()}

    assert eintraege["geraete"]["status"] == "bereit"
    assert eintraege["kaputt"]["status"] == "fehler"
    assert "pandas" in str(eintraege["kaputt"]["beschreibung"])


# --- Entdeckung ------------------------------------------------------------


class _Punkt:
    def __init__(self, name: str, ergebnis: object) -> None:
        self.name = name
        self._ergebnis = ergebnis

    def load(self) -> object:
        if isinstance(self._ergebnis, Exception):
            raise self._ergebnis
        return self._ergebnis


def _mit_punkten(monkeypatch: pytest.MonkeyPatch, *punkte: _Punkt) -> None:
    monkeypatch.setattr("homepi_core.modules.entry_points", lambda group: list(punkte))


def test_entdeckt_angemeldete_module(monkeypatch: pytest.MonkeyPatch) -> None:
    _mit_punkten(monkeypatch, _Punkt("geraete", _modul("geraete")))

    assert entdecke_module().ids == ["geraete"]


def test_fabrikfunktion_wird_aufgerufen(monkeypatch: pytest.MonkeyPatch) -> None:
    _mit_punkten(monkeypatch, _Punkt("geraete", lambda: _modul("geraete")))

    assert entdecke_module().ids == ["geraete"]


def test_ein_kaputtes_modul_reisst_nicht_alles_mit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sonst blockiert ein einziges fehlerhaftes Artefakt das ganze Gateway."""
    _mit_punkten(
        monkeypatch,
        _Punkt("geraete", _modul("geraete")),
        _Punkt("kaputt", ImportError("kein pandas")),
    )

    register = entdecke_module()

    assert register.ids == ["geraete"]
    assert register.defekte[0].id == "kaputt"
    assert "pandas" in register.defekte[0].grund


def test_falscher_typ_wird_als_defekt_vermerkt(monkeypatch: pytest.MonkeyPatch) -> None:
    _mit_punkten(monkeypatch, _Punkt("murks", "kein Modul, nur ein String"))

    register = entdecke_module()

    assert register.ids == []
    assert "erwartet wird ein Modul" in register.defekte[0].grund


def test_doppelte_kennung_bei_der_entdeckung(monkeypatch: pytest.MonkeyPatch) -> None:
    _mit_punkten(
        monkeypatch,
        _Punkt("a", _modul("geraete")),
        _Punkt("b", _modul("geraete")),
    )

    register = entdecke_module()

    assert register.ids == ["geraete"]
    assert "doppelt" in register.defekte[0].grund


# --- Einbau ins Gateway ----------------------------------------------------


@pytest.fixture
async def gateway() -> AsyncIterator[AsyncClient]:
    register = register_aus([_modul("geraete", "Geräte"), _modul("messwerte", "Messwerte")])
    register.defekte.append(DefektesModul(id="kaputt", grund="ImportError"))
    app = create_service(ServiceSettings(service_name="gateway"), module=register)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_router_haengen_unter_ihrem_praefix(gateway: AsyncClient) -> None:
    assert (await gateway.get("/geraete/")).json() == {"modul": "geraete"}
    assert (await gateway.get("/messwerte/")).json() == {"modul": "messwerte"}


async def test_module_endpunkt_liefert_das_manifest(gateway: AsyncClient) -> None:
    """Genau diese Liste baut die Startseite zu Kacheln."""
    eintraege = (await gateway.get("/module")).json()

    nach_id = {e["id"]: e for e in eintraege}
    assert nach_id["geraete"]["pfad"] == "/geraete"
    assert nach_id["geraete"]["status"] == "bereit"
    assert nach_id["kaputt"]["status"] == "fehler"


async def test_info_nennt_die_geladenen_module(gateway: AsyncClient) -> None:
    koerper = (await gateway.get("/info")).json()

    assert koerper["module"] == ["geraete", "messwerte"]


async def test_service_ohne_module_hat_keinen_modul_endpunkt() -> None:
    app = create_service(ServiceSettings(service_name="einzeln"))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        assert (await c.get("/module")).status_code == 404
        assert (await c.get("/info")).json()["module"] == []
