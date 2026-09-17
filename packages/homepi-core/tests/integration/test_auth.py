"""Anmeldung gegen eine echte Datenbank.

Als Integration markiert: Benutzer, Sitzungen und Rechte liegen in Postgres,
und gegen eine nachgebaute Sitzung würde man vor allem den Nachbau testen.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from homepi_core import Base, Modul, ServiceSettings, Zugang, create_service, register_aus
from homepi_core.auth import AktuellerBenutzer, Rolle, erfordert
from homepi_core.auth import speicher as auth_speicher
from homepi_core.auth.cookies import NAME as COOKIE
from homepi_core.auth.modelle import Sitzung

pytestmark = pytest.mark.integration

URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:15432/test")
PASSWORT = "korrekt-pferd-batterie-heftklammer"


def _geschuetztes_modul() -> Modul:
    router = APIRouter()

    @router.get("/offen", summary="Ohne Anmeldung")
    async def offen() -> dict[str, bool]:
        return {"offen": True}

    @router.get("/meins", summary="Nur angemeldet")
    async def meins(benutzer: AktuellerBenutzer) -> dict[str, str]:
        return {"benutzer": benutzer.name}

    @router.get(
        "/verwaltung",
        summary="Nur für Verwalter",
        dependencies=[erfordert("probe", Rolle.VERWALTER)],
    )
    async def verwaltung() -> dict[str, bool]:
        return {"ok": True}

    @router.get(
        "/lesen",
        summary="Ab Leser",
        dependencies=[erfordert("probe", Rolle.LESER)],
    )
    async def lesen() -> dict[str, bool]:
        return {"ok": True}

    # Zugang.SELBST: das Modul prueft Endpunkt fuer Endpunkt, damit
    # '/offen' auch ohne Anmeldung erreichbar bleibt.
    return Modul(id="probe", titel="Probe", router=router, zugang=Zugang.SELBST)


@pytest.fixture
async def app_und_kontext():
    einstellungen = ServiceSettings(
        service_name="auth-test", service_version="0.0.1", database_url=URL
    )
    app = create_service(
        einstellungen, module=register_aus([_geschuetztes_modul()]), anmeldung=True
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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def benutzer(app_und_kontext):
    """Ein Benutzer mit der Rolle 'nutzer' für das Artefakt 'probe'."""
    _, kontext = app_und_kontext
    async with kontext.db.session() as sitzung:
        angelegt = await auth_speicher.lege_benutzer_an(sitzung, "aaron", PASSWORT, "Aaron M.")
        await auth_speicher.setze_recht(sitzung, angelegt.id, "probe", Rolle.NUTZER)
        return angelegt


async def _anmelden(client: AsyncClient, name: str = "aaron", passwort: str = PASSWORT):
    return await client.post("/auth/anmelden", json={"name": name, "passwort": passwort})


# --- Anmelden --------------------------------------------------------------


class TestAnmelden:
    async def test_richtige_daten_setzen_ein_cookie(self, client: AsyncClient, benutzer) -> None:
        antwort = await _anmelden(client)

        assert antwort.status_code == 200
        assert antwort.json()["name"] == "aaron"
        assert COOKIE in antwort.cookies

    async def test_cookie_ist_httponly_und_lax(self, client: AsyncClient, benutzer) -> None:
        # httponly: ein XSS-Fund im Frontend liefert damit kein Token.
        antwort = await _anmelden(client)

        gesetzt = antwort.headers["set-cookie"].lower()
        assert "httponly" in gesetzt
        assert "samesite=lax" in gesetzt

    async def test_cookie_ist_lokal_nicht_secure(self, client: AsyncClient, benutzer) -> None:
        """In der Entwicklung läuft alles über http - secure=True wäre ein
        Cookie, das der Browser nie sendet."""
        antwort = await _anmelden(client)

        assert "secure" not in antwort.headers["set-cookie"].lower()

    async def test_falsches_passwort_wird_abgelehnt(self, client: AsyncClient, benutzer) -> None:
        antwort = await _anmelden(client, passwort="falsch-aber-lang-genug")

        assert antwort.status_code == 401
        assert COOKIE not in antwort.cookies

    async def test_unbekannter_benutzer_klingt_genauso(self, client: AsyncClient, benutzer) -> None:
        # Sonst liesse sich herausfinden, wer ein Konto hat.
        unbekannt = await _anmelden(client, name="gibtsnicht")
        falsch = await _anmelden(client, passwort="falsch-aber-lang-genug")

        assert unbekannt.status_code == falsch.status_code == 401
        assert unbekannt.json()["detail"] == falsch.json()["detail"]

    async def test_antwort_enthaelt_die_rechte(self, client: AsyncClient, benutzer) -> None:
        koerper = (await _anmelden(client)).json()

        assert koerper["rechte"] == {"probe": "nutzer"}

    async def test_passwort_steht_nirgends_in_der_antwort(
        self, client: AsyncClient, benutzer
    ) -> None:
        antwort = await _anmelden(client)

        assert PASSWORT not in antwort.text
        assert "passwort_hash" not in antwort.text


# --- Geschützte Endpunkte --------------------------------------------------


class TestZugriff:
    async def test_offener_endpunkt_braucht_nichts(self, client: AsyncClient) -> None:
        assert (await client.get("/probe/offen")).status_code == 200

    async def test_ohne_anmeldung_401(self, client: AsyncClient) -> None:
        antwort = await client.get("/probe/meins")

        assert antwort.status_code == 401
        assert "problem+json" in antwort.headers["content-type"]

    async def test_mit_anmeldung_erlaubt(self, client: AsyncClient, benutzer) -> None:
        await _anmelden(client)

        antwort = await client.get("/probe/meins")

        assert antwort.status_code == 200
        assert antwort.json()["benutzer"] == "aaron"

    async def test_zu_niedrige_rolle_ergibt_403(self, client: AsyncClient, benutzer) -> None:
        # Angemeldet ja, aber nur 'nutzer' statt 'verwalter'.
        await _anmelden(client)

        antwort = await client.get("/probe/verwaltung")

        assert antwort.status_code == 403
        assert antwort.json()["benoetigt"] == "verwalter"

    async def test_hoehere_rolle_deckt_die_niedrigere(self, client: AsyncClient, benutzer) -> None:
        await _anmelden(client)

        assert (await client.get("/probe/lesen")).status_code == 200

    async def test_recht_fuer_ein_anderes_artefakt_hilft_nicht(
        self, client: AsyncClient, benutzer, app_und_kontext
    ) -> None:
        """Der Kern des Modells: wer StaffelPilot verwaltet, kommt damit nicht
        an die Geräte im Haus."""
        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            await auth_speicher.entziehe_recht(sitzung, benutzer.id, "probe")
            await auth_speicher.setze_recht(sitzung, benutzer.id, "woanders", Rolle.VERWALTER)

        await _anmelden(client)

        assert (await client.get("/probe/lesen")).status_code == 403

    async def test_erfundenes_cookie_wird_abgelehnt(self, client: AsyncClient) -> None:
        client.cookies.set(COOKIE, "ausgedacht")

        assert (await client.get("/probe/meins")).status_code == 401


# --- Sitzungen -------------------------------------------------------------


class TestSitzungen:
    async def test_token_liegt_nur_gehasht_in_der_datenbank(
        self, client: AsyncClient, benutzer, app_und_kontext
    ) -> None:
        # Ein Datenbankabzug soll keine lebenden Sitzungen enthalten.
        antwort = await _anmelden(client)
        token = antwort.cookies[COOKIE]

        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            eintraege = (await sitzung.execute(select(Sitzung))).scalars().all()

        assert len(eintraege) == 1
        assert eintraege[0].token_hash != token
        assert token not in eintraege[0].token_hash

    async def test_abmelden_loescht_die_sitzung(
        self, client: AsyncClient, benutzer, app_und_kontext
    ) -> None:
        await _anmelden(client)

        antwort = await client.post("/auth/abmelden")

        assert antwort.status_code == 204
        assert (await client.get("/probe/meins")).status_code == 401

        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            assert (await sitzung.execute(select(Sitzung))).scalars().all() == []

    async def test_abgelaufene_sitzung_wird_abgewiesen(
        self, client: AsyncClient, benutzer, app_und_kontext
    ) -> None:
        await _anmelden(client)

        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            eintrag = (await sitzung.execute(select(Sitzung))).scalar_one()
            eintrag.laeuft_ab = datetime.now(UTC) - timedelta(minutes=1)

        assert (await client.get("/probe/meins")).status_code == 401

    async def test_aufraeumen_entfernt_nur_abgelaufene(
        self, client: AsyncClient, benutzer, app_und_kontext
    ) -> None:
        await _anmelden(client)
        _, kontext = app_und_kontext

        async with kontext.db.session() as sitzung:
            assert await auth_speicher.raeume_abgelaufene_auf(sitzung) == 0
            eintrag = (await sitzung.execute(select(Sitzung))).scalar_one()
            eintrag.laeuft_ab = datetime.now(UTC) - timedelta(minutes=1)

        async with kontext.db.session() as sitzung:
            assert await auth_speicher.raeume_abgelaufene_auf(sitzung) == 1

    async def test_ich_nennt_benutzer_und_rechte(self, client: AsyncClient, benutzer) -> None:
        await _anmelden(client)

        koerper = (await client.get("/auth/ich")).json()

        assert koerper["anzeigename"] == "Aaron M."
        assert koerper["rechte"] == {"probe": "nutzer"}


# --- Passwort ändern -------------------------------------------------------


class TestPasswortAendern:
    async def test_aendert_und_meldet_ueberall_ab(
        self, client: AsyncClient, benutzer, app_und_kontext
    ) -> None:
        """Wer das Passwort ändert, tut das häufig genau deshalb - eine
        weiterlaufende fremde Sitzung wäre dann fatal."""
        await _anmelden(client)
        neu = "ganz-anderes-langes-passwort"

        antwort = await client.post(
            "/auth/passwort", json={"altes_passwort": PASSWORT, "neues_passwort": neu}
        )

        assert antwort.status_code == 204
        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            assert (await sitzung.execute(select(Sitzung))).scalars().all() == []

        client.cookies.clear()
        assert (await _anmelden(client, passwort=neu)).status_code == 200
        assert (await _anmelden(client, passwort=PASSWORT)).status_code == 401

    async def test_falsches_altes_passwort_aendert_nichts(
        self, client: AsyncClient, benutzer
    ) -> None:
        await _anmelden(client)

        antwort = await client.post(
            "/auth/passwort",
            json={"altes_passwort": "stimmt-nicht-ganz", "neues_passwort": "neues-langes-passwort"},
        )

        assert antwort.status_code == 401
        assert (await _anmelden(client)).status_code == 200

    async def test_untaugliches_neues_passwort_wird_abgelehnt(
        self, client: AsyncClient, benutzer
    ) -> None:
        await _anmelden(client)

        antwort = await client.post(
            "/auth/passwort", json={"altes_passwort": PASSWORT, "neues_passwort": "kurz"}
        )

        assert antwort.status_code == 422


# --- Benutzerverwaltung ----------------------------------------------------


class TestBenutzer:
    async def test_doppelter_name_wird_abgelehnt(self, benutzer, app_und_kontext) -> None:
        _, kontext = app_und_kontext

        with pytest.raises(Exception, match="vergeben"):
            async with kontext.db.session() as sitzung:
                await auth_speicher.lege_benutzer_an(sitzung, "AARON", PASSWORT)

    async def test_deaktiviertes_konto_kommt_nicht_rein(
        self, client: AsyncClient, benutzer, app_und_kontext
    ) -> None:
        _, kontext = app_und_kontext
        async with kontext.db.session() as sitzung:
            geladen = await auth_speicher.finde_benutzer(sitzung, "aaron")
            geladen.aktiv = False

        assert (await _anmelden(client)).status_code == 401

    async def test_sperren_beendet_die_laufende_sitzung(
        self, client: AsyncClient, benutzer, app_und_kontext
    ) -> None:
        """Ohne das Beenden waere die Sperre bis zum Ablauf der Sitzung
        wirkungslos - bis zu vierzehn Tage."""
        _, kontext = app_und_kontext
        await _anmelden(client)
        assert (await client.get("/auth/ich")).status_code == 200

        async with kontext.db.session() as sitzung:
            geladen = await auth_speicher.finde_benutzer(sitzung, "aaron")
            geladen.aktiv = False
            await auth_speicher.melde_ueberall_ab(sitzung, geladen.id)

        assert (await client.get("/auth/ich")).status_code == 401

    async def test_loeschen_nimmt_rechte_und_sitzungen_mit(
        self, client: AsyncClient, benutzer, app_und_kontext
    ) -> None:
        """Cascade, nicht Handarbeit: eine verwaiste Sitzung waere ein
        gueltiges Token ohne Konto dahinter."""
        _, kontext = app_und_kontext
        await _anmelden(client)

        async with kontext.db.session() as sitzung:
            geladen = await auth_speicher.finde_benutzer(sitzung, "aaron")
            await sitzung.delete(geladen)

        async with kontext.db.session() as sitzung:
            assert await auth_speicher.finde_benutzer(sitzung, "aaron") is None
            uebrig = await sitzung.execute(select(Sitzung))
            assert uebrig.scalars().all() == []

        assert (await client.get("/auth/ich")).status_code == 401

    async def test_recht_setzen_ist_idempotent(self, benutzer, app_und_kontext) -> None:
        _, kontext = app_und_kontext

        async with kontext.db.session() as sitzung:
            await auth_speicher.setze_recht(sitzung, benutzer.id, "probe", Rolle.VERWALTER)
            await auth_speicher.setze_recht(sitzung, benutzer.id, "probe", Rolle.LESER)

        async with kontext.db.session() as sitzung:
            geladen = await auth_speicher.finde_benutzer(sitzung, "aaron")
            assert auth_speicher.rechte_von(geladen) == {"probe": Rolle.LESER}
