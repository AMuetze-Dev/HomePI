"""Der DFBnet-Zugang: verschlüsselt abgelegt, nie zurückgegeben.

Der Schlüssel steht in der Umgebung, nicht in der Datenbank. Diese Tests
setzen ihn selbst und stellen ihn hinterher zurück.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from homepi_staffelpilot.dienst import SCHLUESSEL_VARIABLE

pytestmark = pytest.mark.integration

ZUGANG = {"benutzer": "staffelleiter42", "passwort": "geheim-und-lang-genug"}


@pytest.fixture
def mit_schluessel(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    schluessel = Fernet.generate_key().decode()
    monkeypatch.setenv(SCHLUESSEL_VARIABLE, schluessel)
    yield schluessel


@pytest.fixture
def ohne_schluessel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SCHLUESSEL_VARIABLE, raising=False)


class TestOhneSchluessel:
    async def test_die_oberflaeche_erfaehrt_es_vorher(
        self, client: AsyncClient, ohne_schluessel: None
    ) -> None:
        """Bevor jemand ein Passwort tippt, soll dastehen, dass es nicht
        abgelegt werden kann."""
        stand = (await client.get("/staffelpilot/zugang")).json()

        assert stand["schluessel_vorhanden"] is False
        assert stand["gespeichert"] is False

    async def test_es_wird_nichts_abgelegt(
        self, client: AsyncClient, ohne_schluessel: None
    ) -> None:
        """Lieber gar nicht speichern als ein Passwort im Klartext."""
        antwort = await client.put("/staffelpilot/zugang", json=ZUGANG)

        assert antwort.status_code == 503
        assert SCHLUESSEL_VARIABLE in antwort.text
        assert (await client.get("/staffelpilot/zugang")).json()["gespeichert"] is False


class TestMitSchluessel:
    async def test_hinterlegen_und_nachsehen(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        antwort = await client.put("/staffelpilot/zugang", json=ZUGANG)

        assert antwort.status_code == 204, antwort.text
        stand = (await client.get("/staffelpilot/zugang")).json()
        assert stand["gespeichert"] is True
        assert stand["benutzer"] == "staffelleiter42"
        assert stand["schluessel_vorhanden"] is True

    async def test_das_passwort_kommt_nicht_zurueck(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        """Die Statusantwort ist ein Ja oder Nein und ein Benutzername."""
        await client.put("/staffelpilot/zugang", json=ZUGANG)

        antwort = await client.get("/staffelpilot/zugang")

        assert "geheim-und-lang-genug" not in antwort.text
        assert "passwort" not in antwort.json()

    async def test_es_steht_auch_nicht_im_klartext_in_der_datenbank(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        """Ein Datenbankabzug allein soll wertlos sein."""
        from sqlalchemy import select

        from homepi_staffelpilot.modelle import Zugang

        await client.put("/staffelpilot/zugang", json=ZUGANG)

        # Über denselben Weg lesen, den ein Abzug nähme: roh.
        app = client._transport.app  # type: ignore[attr-defined]
        async with app.state.homepi.db.session() as sitzung:
            zeile = (await sitzung.execute(select(Zugang))).scalar_one()

        assert "geheim-und-lang-genug" not in zeile.geheimnis
        assert zeile.benutzer == "staffelleiter42"

    async def test_der_pruefdienst_holt_es_ab(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        await client.put("/staffelpilot/zugang", json=ZUGANG)

        antwort = await client.post("/staffelpilot/zugang/abholen")

        assert antwort.json() == ZUGANG

    async def test_zweimal_hinterlegen_ersetzt(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        await client.put("/staffelpilot/zugang", json=ZUGANG)
        await client.put(
            "/staffelpilot/zugang", json={"benutzer": "anderer", "passwort": "neues-passwort-hier"}
        )

        antwort = await client.post("/staffelpilot/zugang/abholen")

        assert antwort.json()["benutzer"] == "anderer"
        assert antwort.json()["passwort"] == "neues-passwort-hier"

    async def test_entfernen(self, client: AsyncClient, mit_schluessel: str) -> None:
        await client.put("/staffelpilot/zugang", json=ZUGANG)

        assert (await client.delete("/staffelpilot/zugang")).status_code == 204
        assert (await client.get("/staffelpilot/zugang")).json()["gespeichert"] is False

    async def test_entfernen_ohne_zugang_geht_auch(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        """Wer auf 'Entfernen' klickt, will danach keinen Zugang haben - ob
        vorher einer da war, ist seine Sache und kein Fehler."""
        assert (await client.delete("/staffelpilot/zugang")).status_code == 204

    async def test_abholen_ohne_zugang_gibt_404(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        assert (await client.post("/staffelpilot/zugang/abholen")).status_code == 404

    async def test_ein_leeres_passwort_wird_abgelehnt(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        antwort = await client.put("/staffelpilot/zugang", json={"benutzer": "wer", "passwort": ""})

        assert antwort.status_code == 422


class TestSchluesselGetauscht:
    async def test_die_meldung_zeigt_auf_den_schluessel(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ein vertauschter Schluessel darf nicht wie ein falsches Passwort
        aussehen - sonst sucht jemand stundenlang bei DFBnet nach einem
        Fehler, der in der Umgebung steht."""
        monkeypatch.setenv(SCHLUESSEL_VARIABLE, Fernet.generate_key().decode())
        await client.put("/staffelpilot/zugang", json=ZUGANG)

        monkeypatch.setenv(SCHLUESSEL_VARIABLE, Fernet.generate_key().decode())
        antwort = await client.post("/staffelpilot/zugang/abholen")

        assert antwort.status_code == 503
        assert SCHLUESSEL_VARIABLE in antwort.text
        assert "neu eintragen" in antwort.text

    async def test_ein_unbrauchbarer_schluessel_wird_gesagt(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(SCHLUESSEL_VARIABLE, "kein-fernet-schluessel")

        antwort = await client.put("/staffelpilot/zugang", json=ZUGANG)

        assert antwort.status_code == 503
        assert "Fernet" in antwort.text


class TestNurVerwalter:
    def test_schreiben_und_abholen_haengen_an_der_rolle(self) -> None:
        """Ein Leser sieht Spielberichte. Er meldet sich nicht fuer die ganze
        Installation bei DFBnet an -- und holt ihr Passwort schon gar nicht ab.

        Geprueft wird an der Route und nicht an der Konstanten: eine Liste, die
        niemand einhaengt, ist keine Pruefung.
        """
        from homepi_staffelpilot.router import router

        geschuetzt = {
            (r.path, methode)
            for r in router.routes
            for methode in getattr(r, "methods", set())
            if getattr(r, "dependencies", None)
        }

        assert ("/zugang", "PUT") in geschuetzt
        assert ("/zugang", "DELETE") in geschuetzt
        assert ("/zugang/abholen", "POST") in geschuetzt

    async def test_der_stand_ist_fuer_jeden_leser_sichtbar(
        self, client: AsyncClient, ohne_schluessel: None
    ) -> None:
        """Dass ein Zugang fehlt, erklaert eine leere Warteschlange - das darf
        auch jemand sehen, der ihn nicht eintragen darf."""
        from homepi_staffelpilot.router import router

        lesen = next(
            r
            for r in router.routes
            if getattr(r, "path", "") == "/zugang" and "GET" in getattr(r, "methods", set())
        )

        assert not lesen.dependencies
        assert (await client.get("/staffelpilot/zugang")).status_code == 200
