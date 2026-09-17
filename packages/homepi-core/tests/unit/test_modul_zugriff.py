"""Was ein Aufruf tatsaechlich zu sehen bekommt.

Die reine Entscheidung steht in test_modules.py. Hier geht es um die
Verdrahtung: haengt die Pruefung wirklich am Router, und liefert ``GET /module``
wirklich nur das, was dieser Benutzer sehen darf?

Die Anmeldung selbst wird ersetzt statt nachgebaut - der vollstaendige Ablauf
mit Cookie und Datenbank steht in tests/integration/test_auth.py.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from homepi_core import Modul, ServiceSettings, Umgebung, Zugang, create_service, register_aus
from homepi_core.auth import AktuellerBenutzer
from homepi_core.auth.deps import (
    hole_benutzer,
    hole_benutzer_optional,
    hole_sitzungsbenutzer,
)
from homepi_core.auth.dienst import Rolle
from homepi_core.auth.modelle import Benutzer, Recht

#: Es wird nie verbunden: jeder Test ersetzt die Dependencies, die eine
#: Datenbanksitzung braeuchten. Die URL muss nur da sein, damit create_service
#: die Anmeldung ueberhaupt zulaesst.
TOTE_DB = "postgresql+asyncpg://app:app@127.0.0.1:59999/nix"

Anmelden = Callable[[Benutzer | None], None]


def _benutzer(*, wechsel: bool = False, **rechte: Rolle) -> Benutzer:
    kennung = uuid.uuid4()
    return Benutzer(
        id=kennung,
        name="probe",
        anzeigename="Probe",
        passwort_hash="egal",
        aktiv=True,
        passwort_wechseln=wechsel,
        rechte=[
            Recht(benutzer_id=kennung, artefakt=artefakt, rolle=rolle.value)
            for artefakt, rolle in rechte.items()
        ],
    )


def _modul(kennung: str, zugang: Zugang, mindestrolle: Rolle = Rolle.LESER) -> Modul:
    router = APIRouter()

    @router.get("/")
    async def wurzel() -> dict[str, str]:
        return {"modul": kennung}

    @router.get("/geschuetzt")
    async def geschuetzt(benutzer: AktuellerBenutzer) -> dict[str, str]:
        """Ein Endpunkt, der seinen Benutzer selbst holt - ohne erfordert."""
        return {"benutzer": benutzer.name}

    return Modul(
        id=kennung,
        titel=kennung.title(),
        router=router,
        zugang=zugang,
        mindestrolle=mindestrolle,
    )


def _dienst(umgebung: Umgebung = Umgebung.ENTWICKLUNG) -> FastAPI:
    register = register_aus(
        [
            _modul("info", Zugang.OEFFENTLICH),
            _modul("geraete", Zugang.GESCHUETZT),
            _modul("kasse", Zugang.GESCHUETZT, mindestrolle=Rolle.VERWALTER),
            _modul("verein", Zugang.SELBST),
        ]
    )
    return create_service(
        ServiceSettings(service_name="gateway", database_url=TOTE_DB, environment=umgebung),
        module=register,
        anmeldung=True,
    )


@pytest.fixture
async def dienst() -> AsyncIterator[FastAPI]:
    app = _dienst()
    yield app
    await app.state.homepi.require_db().dispose()


@pytest.fixture
async def client(dienst: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=dienst), base_url="http://test") as c:
        yield c


@pytest.fixture
def als(dienst: FastAPI) -> Anmelden:
    """Setzt, wer gerade anfragt - oder ``None`` fuer niemanden."""

    def anmelden(benutzer: Benutzer | None) -> None:
        dienst.dependency_overrides[hole_benutzer_optional] = lambda: benutzer
        if benutzer is None:
            dienst.dependency_overrides.pop(hole_benutzer, None)
        else:
            dienst.dependency_overrides[hole_benutzer] = lambda: benutzer

    return anmelden


def _ids(koerper: object) -> set[str]:
    assert isinstance(koerper, list)
    return {str(eintrag["id"]) for eintrag in koerper}


# --- Der Router ------------------------------------------------------------


class TestZugriffAufDenRouter:
    async def test_oeffentliches_artefakt_braucht_keine_anmeldung(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        als(None)

        assert (await client.get("/info/")).json() == {"modul": "info"}

    async def test_geschuetztes_artefakt_weist_anonyme_ab(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        als(None)

        assert (await client.get("/geraete/")).status_code == 401

    async def test_mit_recht_geht_es_durch(self, client: AsyncClient, als: Anmelden) -> None:
        als(_benutzer(geraete=Rolle.LESER))

        assert (await client.get("/geraete/")).json() == {"modul": "geraete"}

    async def test_das_recht_gilt_nur_fuer_sein_artefakt(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        """Der Kern des Modells: wer StaffelPilot verwaltet, kommt damit nicht
        an die Geraete im Haus."""
        als(_benutzer(verein=Rolle.VERWALTER))

        antwort = await client.get("/geraete/")

        assert antwort.status_code == 403
        assert antwort.json()["artefakt"] == "geraete"

    async def test_die_mindestrolle_wird_durchgesetzt(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        als(_benutzer(kasse=Rolle.NUTZER))

        antwort = await client.get("/kasse/")

        assert antwort.status_code == 403
        assert antwort.json()["benoetigt"] == "verwalter"

    async def test_selbstpruefendes_artefakt_bekommt_keine_pauschale_sperre(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        """Es soll ja gerade einen oeffentlichen Teil haben duerfen. Sichtbar
        ist es trotzdem nur fuer Rechteinhaber - siehe unten."""
        als(None)

        assert (await client.get("/verein/")).json() == {"modul": "verein"}

    async def test_der_fehler_kommt_im_problem_format(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        als(None)

        antwort = await client.get("/geraete/")

        assert antwort.headers["content-type"].startswith("application/problem+json")


# --- Das Manifest ----------------------------------------------------------


class TestGefiltertesManifest:
    async def test_ohne_anmeldung_nur_das_oeffentliche(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        als(None)

        antwort = await client.get("/module")

        assert antwort.status_code == 200
        assert _ids(antwort.json()) == {"info"}

    async def test_ein_benutzer_sieht_nur_seine_artefakte(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        als(_benutzer(verein=Rolle.LESER))

        assert _ids((await client.get("/module")).json()) == {"info", "verein"}

    async def test_eine_zu_niedrige_rolle_blendet_das_artefakt_aus(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        als(_benutzer(kasse=Rolle.NUTZER))

        assert _ids((await client.get("/module")).json()) == {"info"}

    async def test_das_manifest_verlangt_keine_anmeldung(
        self, client: AsyncClient, als: Anmelden
    ) -> None:
        """Sonst saehe ein Besucher der oeffentlichen Seite einen 401, statt
        der Seite, fuer die er gekommen ist."""
        als(None)

        assert (await client.get("/module")).status_code == 200


# --- Ausstehender Passwortwechsel ------------------------------------------


class TestPasswortwechsel:
    """Solange das vergebene Startpasswort gilt, kommt das Konto an kein
    Artefakt. Die Pruefung sitzt in hole_benutzer - also an der Stelle, an der
    **jedes** Artefakt seinen Benutzer bekommt, auch ein selbstpruefendes."""

    @pytest.fixture
    def mit_wechsel(self, dienst: FastAPI) -> Benutzer:
        benutzer = _benutzer(wechsel=True, geraete=Rolle.VERWALTER, verein=Rolle.VERWALTER)
        dienst.dependency_overrides[hole_sitzungsbenutzer] = lambda: benutzer
        return benutzer

    async def test_ein_geschuetztes_artefakt_bleibt_zu(
        self, client: AsyncClient, mit_wechsel: Benutzer
    ) -> None:
        antwort = await client.get("/geraete/")

        assert antwort.status_code == 403
        assert "Startpasswort" in antwort.json()["detail"]

    async def test_auch_ein_selbstpruefendes(
        self, client: AsyncClient, mit_wechsel: Benutzer
    ) -> None:
        """Es benutzt AktuellerBenutzer und nicht erfordert - eine Pruefung in
        erfordert allein waere hier vorbeigelaufen."""
        assert (await client.get("/verein/geschuetzt")).status_code == 403

    async def test_das_oeffentliche_bleibt_offen(
        self, client: AsyncClient, mit_wechsel: Benutzer
    ) -> None:
        assert (await client.get("/info/")).json() == {"modul": "info"}

    async def test_das_manifest_zeigt_nur_oeffentliches(
        self, client: AsyncClient, mit_wechsel: Benutzer
    ) -> None:
        antwort = await client.get("/module")

        assert antwort.status_code == 200
        assert _ids(antwort.json()) == {"info"}


# --- Das OpenAPI-Schema ----------------------------------------------------


async def test_schema_ist_in_der_entwicklung_offen(client: AsyncClient) -> None:
    assert (await client.get("/openapi.json")).status_code == 200


async def test_schema_ist_in_produktion_zu() -> None:
    """Es listet jeden Pfad jedes Artefakts - auch die, die der Aufrufer nicht
    sehen darf. Das waere ein Verzeichnis der internen Artefakte."""
    app = _dienst(Umgebung.PRODUKTION)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/openapi.json")).status_code == 404

    await app.state.homepi.require_db().dispose()
