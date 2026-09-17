"""Der Weg eines neuen Kontos: Startpasswort, erstes Anmelden, eigenes Passwort.

Der Punkt, an dem hier etwas hängt: solange das vergebene Passwort gilt, darf
das Konto an **kein** Artefakt. Dass die Oberfläche eine Maske zeigt, zählt
dabei nicht - jeder Test hier ruft die API direkt auf.
"""

from __future__ import annotations

import pytest
from homepi_core.auth import VERWALTUNG
from httpx import AsyncClient

pytestmark = pytest.mark.integration

EIGENES = "mein-eigenes-langes-passwort"


async def _anlegen(client: AsyncClient, name: str = "neuling") -> dict:
    antwort = await client.post("/verwaltung/benutzer", json={"name": name})
    assert antwort.status_code == 201, antwort.text
    return antwort.json()


async def _anmelden(client: AsyncClient, name: str, passwort: str):
    return await client.post("/auth/anmelden", json={"name": name, "passwort": passwort})


# --- Anlegen ---------------------------------------------------------------


class TestAnlegenOhnePasswort:
    async def test_der_name_genuegt(self, client: AsyncClient) -> None:
        neu = await _anlegen(client)

        assert neu["name"] == "neuling"
        assert neu["aktiv"] is True

    async def test_das_startpasswort_kommt_genau_einmal(self, client: AsyncClient) -> None:
        """In der Antwort aufs Anlegen - und in keiner weiteren Abfrage."""
        neu = await _anlegen(client)

        assert neu["startpasswort"]

        spaeter = (await client.get(f"/verwaltung/benutzer/{neu['id']}")).json()
        assert "startpasswort" not in spaeter

    async def test_es_steht_auch_nicht_in_der_liste(self, client: AsyncClient) -> None:
        await _anlegen(client)

        for eintrag in (await client.get("/verwaltung/benutzer")).json():
            assert "startpasswort" not in eintrag

    async def test_das_konto_ist_auf_wechsel_gestellt(self, client: AsyncClient) -> None:
        neu = await _anlegen(client)

        assert neu["passwort_wechseln"] is True

    async def test_zwei_konten_bekommen_verschiedene(self, client: AsyncClient) -> None:
        # Ein festes Standardpasswort waere nach dem ersten Aushang keines mehr.
        erstes = await _anlegen(client, "eins")
        zweites = await _anlegen(client, "zwei")

        assert erstes["startpasswort"] != zweites["startpasswort"]

    async def test_ein_getipptes_passwort_gibt_es_nicht(self, client: AsyncClient) -> None:
        """Es gibt keinen Weg, eines vorzugeben - auch nicht an der Oberflaeche
        vorbei, direkt gegen die API."""
        antwort = await client.post(
            "/verwaltung/benutzer",
            json={"name": "neuling", "passwort": "vom-verwalter-getippt-lang"},
        )

        assert antwort.status_code == 422


# --- Das erste Anmelden ----------------------------------------------------


class TestErstesAnmelden:
    async def test_mit_dem_startpasswort_kommt_man_rein(
        self, client: AsyncClient, anonym: AsyncClient
    ) -> None:
        neu = await _anlegen(client)

        antwort = await _anmelden(anonym, "neuling", neu["startpasswort"])

        assert antwort.status_code == 200
        assert antwort.json()["passwort_wechseln"] is True

    async def test_aber_an_kein_artefakt(self, client: AsyncClient, anonym: AsyncClient) -> None:
        """Der Kern. Selbst mit Recht kommt das Konto nicht durch, solange das
        vergebene Passwort gilt."""
        neu = await _anlegen(client)
        await client.put(
            f"/verwaltung/benutzer/{neu['id']}/rechte/{VERWALTUNG}", json={"rolle": "verwalter"}
        )
        await _anmelden(anonym, "neuling", neu["startpasswort"])

        antwort = await anonym.get("/verwaltung/benutzer")

        assert antwort.status_code == 403
        assert "Startpasswort" in antwort.json()["detail"]

    async def test_das_manifest_zeigt_nichts(
        self, client: AsyncClient, anonym: AsyncClient
    ) -> None:
        """So viel wie einem Besucher - an die Artefakte kaeme es ohnehin nicht."""
        neu = await _anlegen(client)
        await client.put(
            f"/verwaltung/benutzer/{neu['id']}/rechte/{VERWALTUNG}", json={"rolle": "verwalter"}
        )
        await _anmelden(anonym, "neuling", neu["startpasswort"])

        assert (await anonym.get("/module")).json() == []

    async def test_wer_bin_ich_geht_trotzdem(
        self, client: AsyncClient, anonym: AsyncClient
    ) -> None:
        """Sonst wuesste die Oberflaeche nicht, warum sie abgewiesen wird."""
        neu = await _anlegen(client)
        await _anmelden(anonym, "neuling", neu["startpasswort"])

        antwort = await anonym.get("/auth/ich")

        assert antwort.status_code == 200
        assert antwort.json()["passwort_wechseln"] is True

    async def test_abmelden_geht_trotzdem(self, client: AsyncClient, anonym: AsyncClient) -> None:
        neu = await _anlegen(client)
        await _anmelden(anonym, "neuling", neu["startpasswort"])

        assert (await anonym.post("/auth/abmelden")).status_code == 204


# --- Der Wechsel -----------------------------------------------------------


class TestWechsel:
    async def test_danach_ist_der_weg_frei(self, client: AsyncClient, anonym: AsyncClient) -> None:
        neu = await _anlegen(client)
        await client.put(
            f"/verwaltung/benutzer/{neu['id']}/rechte/{VERWALTUNG}", json={"rolle": "verwalter"}
        )
        await _anmelden(anonym, "neuling", neu["startpasswort"])

        wechsel = await anonym.post(
            "/auth/passwort",
            json={"altes_passwort": neu["startpasswort"], "neues_passwort": EIGENES},
        )

        assert wechsel.status_code == 204
        assert (await anonym.get("/verwaltung/benutzer")).status_code == 200

    async def test_die_sitzung_bleibt(self, client: AsyncClient, anonym: AsyncClient) -> None:
        """Sonst landet man nach einem erzwungenen Erstwechsel auf der
        Anmeldeseite - fuer nichts."""
        neu = await _anlegen(client)
        await _anmelden(anonym, "neuling", neu["startpasswort"])

        await anonym.post(
            "/auth/passwort",
            json={"altes_passwort": neu["startpasswort"], "neues_passwort": EIGENES},
        )

        assert (await anonym.get("/auth/ich")).json()["passwort_wechseln"] is False

    async def test_das_startpasswort_gilt_danach_nicht_mehr(
        self, client: AsyncClient, anonym: AsyncClient
    ) -> None:
        neu = await _anlegen(client)
        await _anmelden(anonym, "neuling", neu["startpasswort"])
        await anonym.post(
            "/auth/passwort",
            json={"altes_passwort": neu["startpasswort"], "neues_passwort": EIGENES},
        )
        await anonym.post("/auth/abmelden")

        assert (await _anmelden(anonym, "neuling", neu["startpasswort"])).status_code == 401
        assert (await _anmelden(anonym, "neuling", EIGENES)).status_code == 200

    async def test_ein_zuruecksetzen_stellt_den_wechsel_wieder(
        self, client: AsyncClient, anonym: AsyncClient
    ) -> None:
        """Auch ein spaeter gesetztes Passwort kennt jemand anders."""
        neu = await _anlegen(client)
        await _anmelden(anonym, "neuling", neu["startpasswort"])
        await anonym.post(
            "/auth/passwort",
            json={"altes_passwort": neu["startpasswort"], "neues_passwort": EIGENES},
        )

        zurueck = await client.put(f"/verwaltung/benutzer/{neu['id']}/passwort")

        assert (await client.get(f"/verwaltung/benutzer/{neu['id']}")).json()[
            "passwort_wechseln"
        ] is True
        assert zurueck.json()["startpasswort"]
