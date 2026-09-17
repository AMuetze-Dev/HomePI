"""Modulregister: die Grundlage dafuer, dass ein neues Artefakt auf der
Startseite erscheint, ohne dass am Frontend etwas geaendert wird.

Wer welches Artefakt sehen darf, steht in test_modul_zugriff.py.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from homepi_core import Modul, ServiceSettings, Zugang, create_service, register_aus
from homepi_core.auth.dienst import Rolle
from homepi_core.modules import (
    DefektesModul,
    Modulregister,
    entdecke_module,
    gewuenschte_module,
)


def _modul(
    kennung: str,
    titel: str | None = None,
    zugang: Zugang = Zugang.OEFFENTLICH,
    mindestrolle: Rolle = Rolle.LESER,
) -> Modul:
    router = APIRouter()

    @router.get("/")
    async def wurzel() -> dict[str, str]:
        return {"modul": kennung}

    return Modul(
        id=kennung,
        titel=titel or kennung.title(),
        router=router,
        version="1.0.0",
        zugang=zugang,
        mindestrolle=mindestrolle,
    )


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


# --- Zugang ----------------------------------------------------------------


def test_ohne_angabe_ist_ein_artefakt_verschlossen() -> None:
    """Wer beim Bauen nicht ueber Zugriff nachdenkt, soll ein verschlossenes
    Artefakt bekommen und kein offenes."""
    assert Modul(id="neu", titel="Neu", router=APIRouter()).zugang is Zugang.GESCHUETZT


def test_mindestrolle_ohne_pruefung_ist_ein_fehler() -> None:
    """Sonst stuende im Code eine Rolle, die niemand prueft - und der naechste
    Leser hielte das Artefakt fuer abgesichert."""
    with pytest.raises(ValueError, match="mindestrolle"):
        Modul(
            id="offen",
            titel="Offen",
            router=APIRouter(),
            zugang=Zugang.OEFFENTLICH,
            mindestrolle=Rolle.VERWALTER,
        )


def test_manifest_nennt_den_zugang() -> None:
    """Das Frontend muss wissen, ob es eine Anmeldung anbieten soll."""
    assert _modul("geraete", zugang=Zugang.GESCHUETZT).manifest()["zugang"] == "geschuetzt"


class TestSichtbarkeit:
    def test_oeffentliches_sieht_auch_wer_nicht_angemeldet_ist(self) -> None:
        assert _modul("info", zugang=Zugang.OEFFENTLICH).sichtbar_fuer(None)

    def test_geschuetztes_sieht_ohne_anmeldung_niemand(self) -> None:
        assert not _modul("geraete", zugang=Zugang.GESCHUETZT).sichtbar_fuer(None)

    def test_geschuetztes_sieht_nur_wer_ein_recht_hat(self) -> None:
        modul = _modul("geraete", zugang=Zugang.GESCHUETZT)

        assert modul.sichtbar_fuer({"geraete": Rolle.LESER})
        assert not modul.sichtbar_fuer({"staffelpilot": Rolle.VERWALTER})

    def test_die_mindestrolle_zaehlt(self) -> None:
        modul = _modul("kasse", zugang=Zugang.GESCHUETZT, mindestrolle=Rolle.VERWALTER)

        assert not modul.sichtbar_fuer({"kasse": Rolle.LESER})
        assert modul.sichtbar_fuer({"kasse": Rolle.VERWALTER})

    def test_selbstpruefendes_bleibt_im_manifest_verborgen(self) -> None:
        """Sonst waere es ueber die Kachelliste doch wieder sichtbar."""
        modul = _modul("verein", zugang=Zugang.SELBST)

        assert not modul.sichtbar_fuer(None)
        assert modul.sichtbar_fuer({"verein": Rolle.LESER})

    def test_defektes_sieht_nur_wer_ein_recht_hat(self) -> None:
        """Sein Zugang stand in dem Modul, das sich nicht laden liess - im
        Zweifel gilt die strengere Annahme."""
        defekt = DefektesModul(id="kaputt", grund="ImportError")

        assert not defekt.sichtbar_fuer(None)
        assert not defekt.sichtbar_fuer({"geraete": Rolle.VERWALTER})
        assert defekt.sichtbar_fuer({"kaputt": Rolle.LESER})


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


def test_braucht_anmeldung_sobald_ein_artefakt_verschlossen_ist() -> None:
    offen = register_aus([_modul("info", zugang=Zugang.OEFFENTLICH)])
    gemischt = register_aus(
        [_modul("info", zugang=Zugang.OEFFENTLICH), _modul("geraete", zugang=Zugang.GESCHUETZT)]
    )

    assert not offen.braucht_anmeldung
    assert gemischt.braucht_anmeldung


class TestGefiltertesManifest:
    @pytest.fixture
    def register(self) -> Modulregister:
        register = register_aus(
            [
                _modul("info", "Info", zugang=Zugang.OEFFENTLICH),
                _modul("geraete", "Geräte", zugang=Zugang.GESCHUETZT),
                _modul("staffelpilot", "StaffelPilot", zugang=Zugang.GESCHUETZT),
            ]
        )
        register.defekte.append(DefektesModul(id="kaputt", grund="ImportError"))
        return register

    def _ids(self, eintraege: list[dict[str, object]]) -> set[str]:
        return {str(e["id"]) for e in eintraege}

    def test_ohne_anmeldung_nur_das_oeffentliche(self, register: Modulregister) -> None:
        assert self._ids(register.manifest_fuer(None)) == {"info"}

    def test_ein_staffelleiter_sieht_die_geraete_im_haus_nicht(
        self, register: Modulregister
    ) -> None:
        """Der Kern der Sache: ein Artefakt ist eine eigenstaendige Website.
        Die uebrigen sollen fuer seine Besucher nicht existieren - auch nicht
        als graue Kachel."""
        sichtbar = self._ids(register.manifest_fuer({"staffelpilot": Rolle.VERWALTER}))

        assert sichtbar == {"info", "staffelpilot"}

    def test_wer_alles_darf_sieht_alles(self, register: Modulregister) -> None:
        sichtbar = self._ids(
            register.manifest_fuer(
                {"geraete": Rolle.LESER, "staffelpilot": Rolle.LESER, "kaputt": Rolle.LESER}
            )
        )

        assert sichtbar == {"info", "geraete", "staffelpilot", "kaputt"}

    def test_auch_gefiltert_bleibt_es_alphabetisch(self, register: Modulregister) -> None:
        eintraege = register.manifest_fuer({"geraete": Rolle.LESER})

        assert [e["titel"] for e in eintraege] == ["Geräte", "Info"]


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


async def test_info_nennt_nur_die_anzahl_der_module(gateway: AsyncClient) -> None:
    """Die Namen der Artefakte gehen nur den etwas an, der sie sehen darf -
    und /info braucht keine Anmeldung."""
    koerper = (await gateway.get("/info")).json()

    assert koerper["module"] == 2


async def test_service_ohne_module_hat_keinen_modul_endpunkt() -> None:
    app = create_service(ServiceSettings(service_name="einzeln"))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        assert (await c.get("/module")).status_code == 404
        assert (await c.get("/info")).json()["module"] == 0


async def test_verschlossenes_artefakt_ohne_anmeldung_startet_nicht() -> None:
    """Lieber gar nicht starten als offen stehen: ohne Anmeldung gaebe es
    niemanden, der die Rechte pruefen koennte."""
    register = register_aus([_modul("geraete", zugang=Zugang.GESCHUETZT)])

    with pytest.raises(RuntimeError, match="geraete"):
        create_service(ServiceSettings(service_name="gateway"), module=register)


# --- Auswahl beim Entwickeln ----------------------------------------------


class TestAuswahl:
    def test_ohne_variable_gilt_keine_einschraenkung(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HOMEPI_MODULE", raising=False)

        assert gewuenschte_module() is None

    def test_leere_variable_zaehlt_wie_nicht_gesetzt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Sonst wuerde ein versehentliches HOMEPI_MODULE= alle Module abschalten.
        monkeypatch.setenv("HOMEPI_MODULE", "   ")

        assert gewuenschte_module() is None

    def test_liste_wird_zerlegt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOMEPI_MODULE", " geraete , messwerte ,")

        assert gewuenschte_module() == frozenset({"geraete", "messwerte"})

    def test_nur_ausgewaehlte_werden_geladen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOMEPI_MODULE", "geraete")
        _mit_punkten(
            monkeypatch,
            _Punkt("geraete", _modul("geraete")),
            _Punkt("messwerte", _modul("messwerte")),
        )

        assert entdecke_module().ids == ["geraete"]

    def test_uebersprungene_werden_nicht_einmal_importiert(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sonst spart die Auswahl keine Startzeit - genau dafuer ist sie da."""
        geladen: list[str] = []

        class _Zaehlend(_Punkt):
            def load(self) -> object:
                geladen.append(self.name)
                return super().load()

        monkeypatch.setenv("HOMEPI_MODULE", "geraete")
        _mit_punkten(
            monkeypatch,
            _Zaehlend("geraete", _modul("geraete")),
            _Zaehlend("messwerte", _modul("messwerte")),
        )

        entdecke_module()

        assert geladen == ["geraete"]

    def test_ein_kaputtes_modul_laesst_sich_ausblenden(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Der praktische Fall: ein Artefakt ist gerade kaputt und soll beim
        Arbeiten am naechsten nicht im Weg stehen."""
        monkeypatch.setenv("HOMEPI_MODULE", "geraete")
        _mit_punkten(
            monkeypatch,
            _Punkt("geraete", _modul("geraete")),
            _Punkt("kaputt", ImportError("kein pandas")),
        )

        register = entdecke_module()

        assert register.ids == ["geraete"]
        assert register.defekte == []
