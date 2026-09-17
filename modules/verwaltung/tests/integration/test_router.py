"""Die Verwaltung gegen eine echte Datenbank.

Der ganze Weg: anmelden, Konto anlegen, Rechte vergeben, sperren, löschen -
und an jeder Stelle die Frage, ob die Sperren halten, die einen Verwalter
davor bewahren, sich selbst auszusperren.
"""

from __future__ import annotations

import pytest
from homepi_core.auth import VERWALTUNG
from httpx import AsyncClient

pytestmark = pytest.mark.integration

#: Wie in conftest.py - hier noch einmal, damit dieser Test ohne Import
#: aus dem Testpaket auskommt (tests/ ist keines).
PASSWORT = "korrekt-pferd-batterie-heftklammer"
NEUES_PASSWORT = "ein-anderes-langes-passwort"


async def _anlegen(client: AsyncClient, name: str) -> dict:
    antwort = await client.post(
        "/verwaltung/benutzer",
        json={"name": name, "passwort": "korrekt-pferd-batterie-42", "anzeigename": name.title()},
    )
    assert antwort.status_code == 201, antwort.text
    return antwort.json()


# --- Zugriff ---------------------------------------------------------------


class TestZugriff:
    async def test_ohne_anmeldung_kommt_niemand_hinein(self, anonym: AsyncClient) -> None:
        assert (await anonym.get("/verwaltung/benutzer")).status_code == 401

    async def test_ein_konto_ohne_recht_auch_nicht(
        self, anonym: AsyncClient, gast, app_und_kontext
    ) -> None:
        await anonym.post("/auth/anmelden", json={"name": "gast", "passwort": PASSWORT})

        antwort = await anonym.get("/verwaltung/benutzer")

        assert antwort.status_code == 403
        assert antwort.json()["artefakt"] == VERWALTUNG

    async def test_die_pruefung_haengt_am_ganzen_router(self, anonym: AsyncClient) -> None:
        """Nicht an einzelnen Endpunkten - ein spaeter dazukommender ist damit
        von selbst geschuetzt."""
        for pfad in ("/verwaltung/benutzer", "/verwaltung/artefakte"):
            assert (await anonym.get(pfad)).status_code == 401, pfad


# --- Lesen -----------------------------------------------------------------


class TestLesen:
    async def test_liste_nennt_die_konten(self, client: AsyncClient, gast) -> None:
        namen = [e["name"] for e in (await client.get("/verwaltung/benutzer")).json()]

        assert namen == ["chefin", "gast"]

    async def test_die_liste_enthaelt_keinen_passwort_hash(self, client: AsyncClient) -> None:
        """Der haeufigste Weg, wie so etwas nach draussen gelangt: ein Modell,
        das ungefragt alle Spalten uebernimmt."""
        eintrag = (await client.get("/verwaltung/benutzer")).json()[0]

        assert "passwort_hash" not in eintrag
        assert set(eintrag) == {
            "id",
            "name",
            "anzeigename",
            "aktiv",
            "rechte",
            "angelegt",
            "verwalter",
            "passwort_wechseln",
        }

    async def test_verwalter_wird_ausgewiesen(self, client: AsyncClient, gast) -> None:
        nach_name = {e["name"]: e for e in (await client.get("/verwaltung/benutzer")).json()}

        assert nach_name["chefin"]["verwalter"] is True
        assert nach_name["gast"]["verwalter"] is False

    async def test_einzelnes_konto(self, client: AsyncClient, gast) -> None:
        antwort = await client.get(f"/verwaltung/benutzer/{gast.id}")

        assert antwort.json()["name"] == "gast"

    async def test_unbekannte_kennung_ergibt_404(self, client: AsyncClient) -> None:
        antwort = await client.get("/verwaltung/benutzer/11111111-1111-4111-8111-111111111111")

        assert antwort.status_code == 404
        assert "problem+json" in antwort.headers["content-type"]

    async def test_das_artefakt_antwortet_unter_seinem_praefix(
        self, client: AsyncClient, gast
    ) -> None:
        """Daran erkennt der Rauchtest, dass ein Modul aus dem Manifest
        wirklich eingehaengt ist."""
        antwort = await client.get("/verwaltung/")

        assert antwort.status_code == 200
        assert antwort.json() == {
            "konten": 2,
            "verwalter": 1,
            "gesperrt": 0,
            "artefakte": 1,
        }

    async def test_artefakte_kommen_aus_dem_laufenden_gateway(self, client: AsyncClient) -> None:
        eintraege = (await client.get("/verwaltung/artefakte")).json()

        assert [e["id"] for e in eintraege] == ["verwaltung"]
        assert eintraege[0]["zugang"] == "geschuetzt"


# --- Anlegen ---------------------------------------------------------------


class TestAnlegen:
    async def test_legt_an_und_gibt_zurueck(self, client: AsyncClient) -> None:
        neu = await _anlegen(client, "neuling")

        assert neu["name"] == "neuling"
        assert neu["aktiv"] is True
        assert neu["rechte"] == {}

    async def test_ein_neues_konto_hat_keine_rechte(self, client: AsyncClient) -> None:
        """Was es darf, wird danach einzeln vergeben - so steht die
        Entscheidung im Log und nicht in einer Voreinstellung."""
        neu = await _anlegen(client, "neuling")

        assert neu["verwalter"] is False

    async def test_doppelter_name_wird_abgelehnt(self, client: AsyncClient) -> None:
        await _anlegen(client, "neuling")

        antwort = await client.post(
            "/verwaltung/benutzer",
            json={"name": "neuling", "passwort": "korrekt-pferd-batterie-42"},
        )

        assert antwort.status_code == 409

    async def test_zu_kurzes_passwort_nennt_den_grund(self, client: AsyncClient) -> None:
        antwort = await client.post(
            "/verwaltung/benutzer", json={"name": "neuling", "passwort": "kurz"}
        )

        assert antwort.status_code == 422
        assert "Zeichen" in antwort.json()["detail"]

    async def test_unbrauchbarer_name_nennt_die_regel(self, client: AsyncClient) -> None:
        antwort = await client.post(
            "/verwaltung/benutzer",
            json={"name": "Mit Leerzeichen", "passwort": "korrekt-pferd-batterie-42"},
        )

        assert antwort.status_code == 422


# --- Aendern ---------------------------------------------------------------


class TestAendern:
    async def test_anzeigename_setzen(self, client: AsyncClient, gast) -> None:
        antwort = await client.patch(
            f"/verwaltung/benutzer/{gast.id}", json={"anzeigename": "Gast im Haus"}
        )

        assert antwort.json()["anzeigename"] == "Gast im Haus"

    async def test_sperren_und_entsperren(self, client: AsyncClient, gast) -> None:
        gesperrt = await client.patch(f"/verwaltung/benutzer/{gast.id}", json={"aktiv": False})
        assert gesperrt.json()["aktiv"] is False

        frei = await client.patch(f"/verwaltung/benutzer/{gast.id}", json={"aktiv": True})
        assert frei.json()["aktiv"] is True

    async def test_ein_gesperrtes_konto_kommt_nicht_mehr_rein(
        self, client: AsyncClient, anonym: AsyncClient, gast
    ) -> None:
        await client.patch(f"/verwaltung/benutzer/{gast.id}", json={"aktiv": False})

        antwort = await anonym.post("/auth/anmelden", json={"name": "gast", "passwort": PASSWORT})

        assert antwort.status_code == 401

    async def test_sich_selbst_sperren_geht_nicht(self, client: AsyncClient, chefin) -> None:
        antwort = await client.patch(f"/verwaltung/benutzer/{chefin.id}", json={"aktiv": False})

        assert antwort.status_code == 409
        assert "eigenen Konto" in antwort.json()["detail"]

    async def test_einen_zweiten_verwalter_sperren_geht(self, client: AsyncClient) -> None:
        """Solange noch einer uebrig bleibt. Dass der letzte bleibt, kann ueber
        diese API gar nicht verletzt werden - wer der letzte ist, ist
        zwangslaeufig der Aufrufer selbst, und den schuetzt die Regel darueber.
        Die Zaehlung greift auf dem Weg ueber die Kommandozeile."""
        zweite = await _anlegen(client, "zweite")
        await client.put(
            f"/verwaltung/benutzer/{zweite['id']}/rechte/{VERWALTUNG}",
            json={"rolle": "verwalter"},
        )

        antwort = await client.patch(f"/verwaltung/benutzer/{zweite['id']}", json={"aktiv": False})

        assert antwort.status_code == 200
        assert antwort.json()["aktiv"] is False


# --- Passwort --------------------------------------------------------------


class TestPasswort:
    async def test_setzen_und_anmelden(
        self, client: AsyncClient, anonym: AsyncClient, gast
    ) -> None:
        antwort = await client.put(
            f"/verwaltung/benutzer/{gast.id}/passwort", json={"passwort": NEUES_PASSWORT}
        )
        assert antwort.status_code == 200

        neu = await anonym.post("/auth/anmelden", json={"name": "gast", "passwort": NEUES_PASSWORT})
        assert neu.status_code == 200

    async def test_ohne_angabe_entsteht_ein_startpasswort(
        self, client: AsyncClient, anonym: AsyncClient, gast
    ) -> None:
        antwort = await client.put(f"/verwaltung/benutzer/{gast.id}/passwort", json={})

        start = antwort.json()["startpasswort"]
        assert start
        neu = await anonym.post("/auth/anmelden", json={"name": "gast", "passwort": start})
        assert neu.status_code == 200
        assert neu.json()["passwort_wechseln"] is True

    async def test_ein_selbst_getipptes_kommt_nicht_zurueck(
        self, client: AsyncClient, gast
    ) -> None:
        """Der Verwalter kennt es - zurueck kommt nur, was der Dienst erzeugt hat."""
        antwort = await client.put(
            f"/verwaltung/benutzer/{gast.id}/passwort", json={"passwort": NEUES_PASSWORT}
        )

        assert antwort.json()["startpasswort"] is None

    async def test_am_fremden_konto_muss_gewechselt_werden(self, client: AsyncClient, gast) -> None:
        """Ein Passwort, das ein Verwalter kennt, soll nicht das bleibende sein."""
        await client.put(
            f"/verwaltung/benutzer/{gast.id}/passwort", json={"passwort": NEUES_PASSWORT}
        )

        eintrag = (await client.get(f"/verwaltung/benutzer/{gast.id}")).json()
        assert eintrag["passwort_wechseln"] is True

    async def test_am_eigenen_konto_nicht(self, client: AsyncClient, chefin) -> None:
        await client.put(
            f"/verwaltung/benutzer/{chefin.id}/passwort", json={"passwort": NEUES_PASSWORT}
        )

        eintrag = (await client.get(f"/verwaltung/benutzer/{chefin.id}")).json()
        assert eintrag["passwort_wechseln"] is False

    async def test_zu_kurzes_passwort_wird_abgelehnt(self, client: AsyncClient, gast) -> None:
        antwort = await client.put(
            f"/verwaltung/benutzer/{gast.id}/passwort", json={"passwort": "kurz"}
        )

        assert antwort.status_code == 422

    async def test_alle_sitzungen_des_kontos_enden(
        self, client: AsyncClient, anonym: AsyncClient, gast
    ) -> None:
        """Wer ein Passwort zuruecksetzt, tut das meist, weil etwas schiefging.
        Eine weiterlaufende fremde Sitzung waere dann fatal."""
        await anonym.post("/auth/anmelden", json={"name": "gast", "passwort": PASSWORT})
        assert (await anonym.get("/auth/ich")).status_code == 200

        await client.put(
            f"/verwaltung/benutzer/{gast.id}/passwort", json={"passwort": NEUES_PASSWORT}
        )

        assert (await anonym.get("/auth/ich")).status_code == 401


# --- Rechte ----------------------------------------------------------------


class TestRechte:
    async def test_recht_setzen(self, client: AsyncClient, gast) -> None:
        antwort = await client.put(
            f"/verwaltung/benutzer/{gast.id}/rechte/geraete", json={"rolle": "nutzer"}
        )

        assert antwort.json()["rechte"] == {"geraete": "nutzer"}

    async def test_recht_aendern_ist_idempotent(self, client: AsyncClient, gast) -> None:
        await client.put(f"/verwaltung/benutzer/{gast.id}/rechte/geraete", json={"rolle": "nutzer"})
        antwort = await client.put(
            f"/verwaltung/benutzer/{gast.id}/rechte/geraete", json={"rolle": "leser"}
        )

        assert antwort.json()["rechte"] == {"geraete": "leser"}

    async def test_recht_entziehen(self, client: AsyncClient, gast) -> None:
        await client.put(f"/verwaltung/benutzer/{gast.id}/rechte/geraete", json={"rolle": "nutzer"})

        antwort = await client.delete(f"/verwaltung/benutzer/{gast.id}/rechte/geraete")

        assert antwort.json()["rechte"] == {}

    async def test_ein_recht_wirkt_sofort(
        self, client: AsyncClient, anonym: AsyncClient, gast
    ) -> None:
        await anonym.post("/auth/anmelden", json={"name": "gast", "passwort": PASSWORT})
        assert (await anonym.get("/verwaltung/benutzer")).status_code == 403

        await client.put(
            f"/verwaltung/benutzer/{gast.id}/rechte/{VERWALTUNG}", json={"rolle": "verwalter"}
        )

        assert (await anonym.get("/verwaltung/benutzer")).status_code == 200

    async def test_sich_selbst_die_verwaltung_nehmen_geht_nicht(
        self, client: AsyncClient, chefin
    ) -> None:
        """Sie koennte es nicht zuruecknehmen - und saesse vor einer
        Oberflaeche, die sie nicht mehr hineinlaesst."""
        antwort = await client.delete(f"/verwaltung/benutzer/{chefin.id}/rechte/{VERWALTUNG}")

        assert antwort.status_code == 409
        assert "Verwaltung abzugeben" in antwort.json()["detail"]

    async def test_sich_selbst_herabstufen_auch_nicht(self, client: AsyncClient, chefin) -> None:
        antwort = await client.put(
            f"/verwaltung/benutzer/{chefin.id}/rechte/{VERWALTUNG}", json={"rolle": "leser"}
        )

        assert antwort.status_code == 409

    async def test_ein_anderes_artefakt_darf_sie_sich_selbst_nehmen(
        self, client: AsyncClient, chefin
    ) -> None:
        """Nur die Verwaltung ist heikel - die Geraete kann sie sich
        anschliessend wiedergeben."""
        await client.put(
            f"/verwaltung/benutzer/{chefin.id}/rechte/geraete", json={"rolle": "nutzer"}
        )

        antwort = await client.delete(f"/verwaltung/benutzer/{chefin.id}/rechte/geraete")

        assert antwort.status_code == 200

    async def test_einem_zweiten_verwalter_das_recht_nehmen_geht(self, client: AsyncClient) -> None:
        zweite = await _anlegen(client, "zweite")
        await client.put(
            f"/verwaltung/benutzer/{zweite['id']}/rechte/{VERWALTUNG}",
            json={"rolle": "verwalter"},
        )

        antwort = await client.delete(f"/verwaltung/benutzer/{zweite['id']}/rechte/{VERWALTUNG}")

        assert antwort.status_code == 200
        assert antwort.json()["rechte"] == {}

    async def test_der_letzte_verwalter_ist_immer_man_selbst(
        self, client: AsyncClient, chefin
    ) -> None:
        """Deshalb faengt der Selbstschutz diesen Fall ab, bevor die Zaehlung
        ueberhaupt drankommt - und die Installation bleibt verwaltbar."""
        antwort = await client.delete(f"/verwaltung/benutzer/{chefin.id}/rechte/{VERWALTUNG}")

        assert antwort.status_code == 409
        assert "Verwaltung abzugeben" in antwort.json()["detail"]


# --- Loeschen --------------------------------------------------------------


class TestLoeschen:
    async def test_loescht(self, client: AsyncClient, gast) -> None:
        antwort = await client.delete(f"/verwaltung/benutzer/{gast.id}")

        assert antwort.status_code == 204
        assert (await client.get(f"/verwaltung/benutzer/{gast.id}")).status_code == 404

    async def test_rechte_und_sitzungen_gehen_mit(
        self, client: AsyncClient, anonym: AsyncClient, gast, app_und_kontext
    ) -> None:
        """Eine verwaiste Sitzung waere ein gueltiges Token ohne Konto."""
        from sqlalchemy import select

        _, kontext = app_und_kontext
        await anonym.post("/auth/anmelden", json={"name": "gast", "passwort": PASSWORT})

        await client.delete(f"/verwaltung/benutzer/{gast.id}")

        assert (await anonym.get("/auth/ich")).status_code == 401
        async with kontext.db.session() as sitzung:
            from homepi_core.auth import Sitzung

            uebrig = await sitzung.execute(select(Sitzung).where(Sitzung.benutzer_id == gast.id))
            assert uebrig.scalars().all() == []

    async def test_das_eigene_konto_nicht(self, client: AsyncClient, chefin) -> None:
        antwort = await client.delete(f"/verwaltung/benutzer/{chefin.id}")

        assert antwort.status_code == 409

    async def test_unbekannte_kennung_ergibt_404(self, client: AsyncClient) -> None:
        antwort = await client.delete("/verwaltung/benutzer/11111111-1111-4111-8111-111111111111")

        assert antwort.status_code == 404
