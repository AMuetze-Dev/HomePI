"""Die Ersteinrichtung gegen eine echte Datenbank.

Hier hängt mehr dran als an den meisten Tests: der Endpunkt legt ein Konto an,
das alles verwalten darf, und er ist naturgemäß **ohne Anmeldung** erreichbar.
Zwei Bedingungen müssen ihn zumachen, und beide werden hier einzeln geprüft:

1. Es gibt noch keinen Verwalter.
2. Der Aufrufer legt das Token vor, das beim Start im Log stand.

Dass die Oberfläche die Maske nicht anzeigt, zählt ausdrücklich nicht. Jeder
Test hier ruft die API direkt auf - genau wie jemand, der ``/einrichtung`` von
Hand eintippt.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from homepi_core import Base, Modul, ServiceSettings, Zugang, create_service, register_aus
from homepi_core.auth import VERWALTUNG, Rolle
from homepi_core.auth import speicher as auth_speicher
from homepi_core.auth.cookies import NAME as COOKIE
from homepi_core.testing.datenbank import datenbank_fuer_tests

pytestmark = pytest.mark.integration

#: Nur eine Datenbank, die erkennbar zum Testen da ist - diese Tests
#: rufen drop_all auf.
URL = datenbank_fuer_tests()
PASSWORT = "korrekt-pferd-batterie-heftklammer"


def _modul() -> Modul:
    router = APIRouter()

    @router.get("/", summary="Wurzel")
    async def wurzel() -> dict[str, bool]:
        return {"da": True}

    return Modul(
        id=VERWALTUNG,
        titel="Verwaltung",
        router=router,
        zugang=Zugang.GESCHUETZT,
        mindestrolle=Rolle.VERWALTER,
    )


@pytest.fixture
async def app_und_kontext():
    app = create_service(
        ServiceSettings(service_name="einrichtung-test", database_url=URL),
        module=register_aus([_modul()]),
        anmeldung=True,
    )
    kontext = app.state.homepi

    async with kontext.db.engine.begin() as verbindung:
        await verbindung.run_sync(Base.metadata.drop_all)
        await verbindung.run_sync(Base.metadata.create_all)

    yield app, kontext
    await kontext.db.dispose()


@pytest.fixture
async def client(app_und_kontext) -> AsyncIterator[AsyncClient]:
    app, _ = app_und_kontext
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def token(app_und_kontext) -> str:
    """Das Token, das der Dienst beim Start ins Log schreibt."""
    _, kontext = app_und_kontext
    async with kontext.db.session() as sitzung:
        return await auth_speicher.setze_einrichtungstoken(sitzung)


@pytest.fixture
async def verwalterin(app_und_kontext):
    _, kontext = app_und_kontext
    async with kontext.db.session() as sitzung:
        benutzer = await auth_speicher.lege_benutzer_an(sitzung, "chefin", PASSWORT, "Chefin")
        await auth_speicher.setze_recht(sitzung, benutzer.id, VERWALTUNG, Rolle.VERWALTER)
        return benutzer


def _daten(token: str, **rest: object) -> dict[str, object]:
    return {
        "token": token,
        "name": "aaron",
        "passwort": "ein-hinreichend-langes-passwort",
        **rest,
    }


# --- Der Stand ------------------------------------------------------------


class TestStand:
    async def test_frisch_ist_die_einrichtung_noetig(self, client: AsyncClient) -> None:
        assert (await client.get("/auth/einrichtung")).json() == {"noetig": True}

    async def test_mit_verwalter_nicht_mehr(self, client: AsyncClient, verwalterin) -> None:
        assert (await client.get("/auth/einrichtung")).json() == {"noetig": False}

    async def test_der_stand_braucht_keine_anmeldung(self, client: AsyncClient) -> None:
        """Die Oberflaeche muss beim ersten Aufruf entscheiden, ob sie die
        Maske oder die Anmeldung zeigt."""
        assert (await client.get("/auth/einrichtung")).status_code == 200

    async def test_der_stand_verraet_sonst_nichts(self, client: AsyncClient, verwalterin) -> None:
        assert set((await client.get("/auth/einrichtung")).json()) == {"noetig"}


# --- Einrichten -----------------------------------------------------------


class TestEinrichten:
    async def test_mit_token_entsteht_ein_verwalter(self, client: AsyncClient, token: str) -> None:
        antwort = await client.post("/auth/einrichtung", json=_daten(token))

        assert antwort.status_code == 200, antwort.text
        assert antwort.json()["name"] == "aaron"
        assert antwort.json()["rechte"] == {VERWALTUNG: "verwalter"}

    async def test_der_erste_verwalter_ist_gleich_angemeldet(
        self, client: AsyncClient, token: str
    ) -> None:
        """Sonst muesste man sich unmittelbar nach dem Anlegen noch einmal
        anmelden - fuer nichts."""
        antwort = await client.post("/auth/einrichtung", json=_daten(token))

        assert COOKIE in antwort.cookies
        assert (await client.get("/auth/ich")).json()["name"] == "aaron"

    async def test_er_kommt_sofort_in_die_verwaltung(self, client: AsyncClient, token: str) -> None:
        await client.post("/auth/einrichtung", json=_daten(token))

        assert (await client.get(f"/{VERWALTUNG}/")).status_code == 200

    async def test_der_anzeigename_ist_optional(self, client: AsyncClient, token: str) -> None:
        antwort = await client.post("/auth/einrichtung", json=_daten(token))

        assert antwort.json()["anzeigename"] == "aaron"

    async def test_danach_ist_die_einrichtung_zu(self, client: AsyncClient, token: str) -> None:
        await client.post("/auth/einrichtung", json=_daten(token))

        assert (await client.get("/auth/einrichtung")).json() == {"noetig": False}


# --- Was den Endpunkt zumacht ---------------------------------------------


class TestAbwehr:
    async def test_ohne_token_geht_nichts(self, client: AsyncClient, token: str) -> None:
        """Der Kern: 'es gibt noch keinen Verwalter' allein genuegt nicht. Wer
        als Erster an die frische Adresse kommt, wuerde sonst die Installation
        uebernehmen."""
        antwort = await client.post("/auth/einrichtung", json=_daten("falsches-token"))

        assert antwort.status_code == 401
        assert (await client.get("/auth/einrichtung")).json() == {"noetig": True}

    async def test_ein_falsches_token_legt_kein_konto_an(
        self, client: AsyncClient, token: str, app_und_kontext
    ) -> None:
        _, kontext = app_und_kontext
        await client.post("/auth/einrichtung", json=_daten("falsches-token"))

        async with kontext.db.session() as sitzung:
            assert await auth_speicher.finde_benutzer(sitzung, "aaron") is None

    async def test_mit_vorhandenem_verwalter_ist_zu(
        self, client: AsyncClient, token: str, verwalterin
    ) -> None:
        """Auch mit gueltigem Token. Sonst waere ein einmal mitgelesenes Token
        ein dauerhafter Zweitschluessel."""
        antwort = await client.post("/auth/einrichtung", json=_daten(token))

        assert antwort.status_code == 409

    async def test_das_token_gilt_nur_einmal(self, client: AsyncClient, token: str) -> None:
        await client.post("/auth/einrichtung", json=_daten(token))

        zweite = await client.post("/auth/einrichtung", json=_daten(token, name="zweiter"))

        assert zweite.status_code == 409

    async def test_ein_gesperrter_verwalter_oeffnet_die_tuer_nicht_wieder(
        self, client: AsyncClient, token: str, verwalterin, app_und_kontext
    ) -> None:
        """Sonst liesse sich die Einrichtung erneut oeffnen, indem man den
        letzten Verwalter sperrt."""
        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            geladen = await auth_speicher.finde_benutzer(sitzung, "chefin")
            assert geladen is not None
            geladen.aktiv = False

        assert (await client.get("/auth/einrichtung")).json() == {"noetig": False}
        assert (await client.post("/auth/einrichtung", json=_daten(token))).status_code == 409

    async def test_ein_verwalter_fuer_ein_anderes_artefakt_zaehlt_nicht(
        self, client: AsyncClient, app_und_kontext
    ) -> None:
        """Rechte gelten je Artefakt - wer die Geraete verwaltet, ist damit
        kein Verwalter dieser Installation."""
        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            benutzer = await auth_speicher.lege_benutzer_an(sitzung, "gast", PASSWORT)
            await auth_speicher.setze_recht(sitzung, benutzer.id, "geraete", Rolle.VERWALTER)

        assert (await client.get("/auth/einrichtung")).json() == {"noetig": True}

    async def test_ein_zu_kurzes_passwort_wird_abgelehnt(
        self, client: AsyncClient, token: str
    ) -> None:
        antwort = await client.post("/auth/einrichtung", json=_daten(token, passwort="kurz"))

        assert antwort.status_code == 422

    async def test_nach_einem_abgelehnten_passwort_gilt_das_token_weiter(
        self, client: AsyncClient, token: str
    ) -> None:
        """Sonst braeuchte es fuer jeden Tippfehler einen Neustart."""
        await client.post("/auth/einrichtung", json=_daten(token, passwort="kurz"))

        antwort = await client.post("/auth/einrichtung", json=_daten(token))

        assert antwort.status_code == 200


# --- Das Token selbst -----------------------------------------------------


class TestToken:
    async def test_jeder_start_erzeugt_ein_neues(self, app_und_kontext) -> None:
        """Damit im Log immer das gueltige steht - und ein mitgelesenes von
        vorgestern wertlos ist."""
        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            erstes = await auth_speicher.setze_einrichtungstoken(sitzung)
        async with kontext.db.session() as sitzung:
            zweites = await auth_speicher.setze_einrichtungstoken(sitzung)

        assert erstes != zweites

    async def test_das_alte_gilt_danach_nicht_mehr(
        self, client: AsyncClient, app_und_kontext
    ) -> None:
        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            altes = await auth_speicher.setze_einrichtungstoken(sitzung)
        async with kontext.db.session() as sitzung:
            await auth_speicher.setze_einrichtungstoken(sitzung)

        assert (await client.post("/auth/einrichtung", json=_daten(altes))).status_code == 401

    async def test_in_der_datenbank_steht_nur_der_hash(self, app_und_kontext) -> None:
        """Ein Datenbankabzug soll keinen Zweitschluessel enthalten."""
        from sqlalchemy import select

        from homepi_core.auth import Einrichtung

        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            token = await auth_speicher.setze_einrichtungstoken(sitzung)

        async with kontext.db.session() as sitzung:
            eintrag = (await sitzung.execute(select(Einrichtung))).scalar_one()

        assert eintrag.token_hash != token
        assert len(eintrag.token_hash) == 64

    async def test_ohne_zeile_stimmt_kein_token(self, app_und_kontext) -> None:
        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            await auth_speicher.schliesse_einrichtung(sitzung)
            assert not await auth_speicher.einrichtungstoken_stimmt(sitzung, "irgendwas")
