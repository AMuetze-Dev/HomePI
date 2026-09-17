"""Einstellungen, Mannschaften und Vorgaenge gegen eine echte Datenbank.

    make dev
    HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
      uv run pytest -m 'not smoke'
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from .hilfen import UNBEKANNT, befund, einspielen, spiel, staffel_anlegen

pytestmark = pytest.mark.integration


async def befund_mit_weg(client: AsyncClient, weg: str = "mahnung") -> dict[str, Any]:
    """Ein eingespielter Befund, aus dem ein Vorgang werden darf."""
    staffel_id = await staffel_anlegen(client)
    antwort = await einspielen(client, staffel_id, spiel(befunde=[befund(weg=weg)]))
    assert antwort.status_code == 200, antwort.text
    spiel_id = (await client.get("/staffelpilot/")).json()[0]["id"]
    return dict((await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"][0])


async def vorgang_anlegen(
    client: AsyncClient, weg: str = "mahnung", **daten: Any
) -> dict[str, Any]:
    b = await befund_mit_weg(client, weg)
    antwort = await client.post(f"/staffelpilot/befunde/{b['id']}/vorgang", json=daten)
    assert antwort.status_code == 201, antwort.text
    return dict(antwort.json())


# ── Einstellungen ─────────────────────────────────────────────────────────


class TestEinstellungen:
    async def test_eine_frische_installation_ist_benutzbar(self, client: AsyncClient) -> None:
        werte = (await client.get("/staffelpilot/einstellungen")).json()

        assert werte["pruefzeitraum_tage"] == 30
        assert werte["staffelleiter"] == ""

    async def test_setzen_und_wiederlesen(self, client: AsyncClient) -> None:
        await client.put(
            "/staffelpilot/einstellungen",
            json={"staffelleiter": "Aaron Mütze", "frist_tage": 21},
        )
        werte = (await client.get("/staffelpilot/einstellungen")).json()

        assert werte["staffelleiter"] == "Aaron Mütze"
        assert werte["frist_tage"] == 21

    async def test_ein_ausgelassenes_feld_bleibt_stehen(self, client: AsyncClient) -> None:
        """Ein Dialog, der offen stand, waehrend woanders geschrieben wurde,
        schreibt sonst einen alten Wert zurueck."""
        await client.put("/staffelpilot/einstellungen", json={"staffelleiter": "Aaron"})
        await client.put("/staffelpilot/einstellungen", json={"frist_tage": 7})
        werte = (await client.get("/staffelpilot/einstellungen")).json()

        assert werte["staffelleiter"] == "Aaron"
        assert werte["frist_tage"] == 7

    async def test_derselbe_schluessel_zweimal_ueberschreibt(self, client: AsyncClient) -> None:
        """Sonst stuenden zwei Zeilen fuer denselben Schluessel da, und welche
        gilt, entschiede die Reihenfolge der Abfrage."""
        await client.put("/staffelpilot/einstellungen", json={"staffelleiter": "Erste"})
        await client.put("/staffelpilot/einstellungen", json={"staffelleiter": "Zweite"})

        assert (await client.get("/staffelpilot/einstellungen")).json()["staffelleiter"] == "Zweite"

    async def test_eine_zahl_ausserhalb_der_grenzen_wird_abgelehnt(
        self, client: AsyncClient
    ) -> None:
        antwort = await client.put("/staffelpilot/einstellungen", json={"frist_tage": 0})

        assert antwort.status_code == 422


# ── Mannschaften ──────────────────────────────────────────────────────────


class TestMannschaften:
    async def test_ohne_meldung_ist_die_liste_leer(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)

        assert (await client.get(f"/staffelpilot/staffeln/{staffel_id}/mannschaften")).json() == []

    async def test_die_hoeheren_werden_geraten(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        antwort = await client.put(
            f"/staffelpilot/staffeln/{staffel_id}/mannschaften",
            json={
                "mannschaften": [
                    {"name": "SV Loschwitz 2"},
                    {"name": "SV Loschwitz"},
                    {"name": "SG Weixdorf"},
                ]
            },
        )
        assert antwort.status_code == 200, antwort.text
        nach_namen = {m["name"]: m for m in antwort.json()}

        assert nach_namen["SV Loschwitz 2"]["hoehere"] == ["SV Loschwitz"]
        assert nach_namen["SV Loschwitz 2"]["nummer"] == 2
        assert nach_namen["SG Weixdorf"]["hoehere"] == []

    async def test_eine_spielgemeinschaft_faellt_als_unsicher_auf(
        self, client: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)
        antwort = await client.put(
            f"/staffelpilot/staffeln/{staffel_id}/mannschaften",
            json={"mannschaften": [{"name": "SG Gittersee/Coschütz", "ist_sg": True}]},
        )

        assert antwort.json()[0]["unsicher"] is True

    async def test_eine_handkorrektur_ueberlebt_das_naechste_einspielen(
        self, client: AsyncClient
    ) -> None:
        """Sonst waere jede Korrektur bis zum naechsten DFBnet-Abgleich haltbar
        - und genau davor soll die Zuordnung schuetzen."""
        staffel_id = await staffel_anlegen(client)
        pfad = f"/staffelpilot/staffeln/{staffel_id}/mannschaften"
        await client.put(
            pfad,
            json={
                "mannschaften": [
                    {"name": "SG Gittersee", "ist_sg": True, "hoehere": ["SV Coschütz"]},
                    {"name": "SV Coschütz"},
                ]
            },
        )

        # Wie es aus DFBnet wiederkaeme: ohne die Zuordnung.
        antwort = await client.put(
            pfad, json={"mannschaften": [{"name": "SG Gittersee"}, {"name": "SV Coschütz"}]}
        )
        nach_namen = {m["name"]: m for m in antwort.json()}

        assert nach_namen["SG Gittersee"]["hoehere"] == ["SV Coschütz"]
        assert nach_namen["SG Gittersee"]["bestaetigt"] is True

    async def test_was_nicht_mehr_gemeldet_wird_verschwindet(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        pfad = f"/staffelpilot/staffeln/{staffel_id}/mannschaften"
        await client.put(pfad, json={"mannschaften": [{"name": "A"}, {"name": "B"}]})

        antwort = await client.put(pfad, json={"mannschaften": [{"name": "A"}]})

        assert [m["name"] for m in antwort.json()] == ["A"]

    async def test_unbekannte_staffel_gibt_404(self, client: AsyncClient) -> None:
        antwort = await client.get(f"/staffelpilot/staffeln/{UNBEKANNT}/mannschaften")

        assert antwort.status_code == 404


# ── Vorgänge ──────────────────────────────────────────────────────────────


class TestVorgangAnlegen:
    async def test_aus_einem_befund_wird_ein_entwurf(self, client: AsyncClient) -> None:
        vorgang = await vorgang_anlegen(client)

        assert vorgang["art"] == "mahnung"
        assert vorgang["zustand"] == "entwurf"
        assert vorgang["aktenzeichen"] == "26-27-0001"
        assert "Feldverweis auf Dauer" in vorgang["text"]
        assert vorgang["versandt_am"] is None

    async def test_der_befund_liefert_verein_und_person(self, client: AsyncClient) -> None:
        vorgang = await vorgang_anlegen(client)

        assert vorgang["verein"] == "SG Gittersee"
        assert vorgang["betroffener"] == "Max Müller"

    async def test_angaben_des_staffelleiters_gehen_vor(self, client: AsyncClient) -> None:
        vorgang = await vorgang_anlegen(client, betroffener="Erika Beispiel", grund="Tätlichkeit")

        assert vorgang["betroffener"] == "Erika Beispiel"
        assert "Tätlichkeit" in vorgang["text"]

    async def test_ein_befund_ohne_weg_bekommt_keinen_vorgang(self, client: AsyncClient) -> None:
        b = await befund_mit_weg(client, weg="kein")
        antwort = await client.post(f"/staffelpilot/befunde/{b['id']}/vorgang", json={})

        assert antwort.status_code == 422

    async def test_zweimal_derselbe_befund_gibt_409(self, client: AsyncClient) -> None:
        """Zwei Mahnungen zu demselben Vorfall sind fuer den Verein nicht
        unterscheidbar."""
        b = await befund_mit_weg(client)
        await client.post(f"/staffelpilot/befunde/{b['id']}/vorgang", json={})
        zweiter = await client.post(f"/staffelpilot/befunde/{b['id']}/vorgang", json={})

        assert zweiter.status_code == 409

    async def test_unbekannter_befund_gibt_404(self, client: AsyncClient) -> None:
        antwort = await client.post(f"/staffelpilot/befunde/{UNBEKANNT}/vorgang", json={})

        assert antwort.status_code == 404

    async def test_der_sportgerichtsfall_ist_ein_antrag(self, client: AsyncClient) -> None:
        vorgang = await vorgang_anlegen(client, weg="sportgericht")

        assert vorgang["art"] == "sportgericht"
        assert "Antrag auf Eröffnung" in vorgang["text"]

    async def test_die_einstellungen_stehen_im_text(self, client: AsyncClient) -> None:
        await client.put("/staffelpilot/einstellungen", json={"staffelleiter": "Aaron Mütze"})
        vorgang = await vorgang_anlegen(client)

        assert "Aaron Mütze" in vorgang["text"]

    async def test_aktenzeichen_zaehlen_je_saison_hoch(self, client: AsyncClient) -> None:
        staffel_id = await staffel_anlegen(client)
        await einspielen(
            client,
            staffel_id,
            spiel("M-1", befunde=[befund(weg="mahnung")]),
            spiel("M-2", befunde=[befund(weg="mahnung")]),
        )
        nummern = []
        for zeile in (await client.get("/staffelpilot/")).json():
            b = (await client.get(f"/staffelpilot/spiele/{zeile['id']}")).json()["befunde"][0]
            antwort = await client.post(f"/staffelpilot/befunde/{b['id']}/vorgang", json={})
            nummern.append(antwort.json()["aktenzeichen"])

        assert sorted(nummern) == ["26-27-0001", "26-27-0002"]


class TestVorgangBearbeiten:
    async def test_der_text_gehoert_dem_staffelleiter(self, client: AsyncClient) -> None:
        vorgang = await vorgang_anlegen(client)
        antwort = await client.patch(
            f"/staffelpilot/vorgaenge/{vorgang['id']}", json={"text": "Eigene Fassung."}
        )

        assert antwort.json()["text"] == "Eigene Fassung."

    async def test_der_empfaenger_laesst_sich_nachtragen(self, client: AsyncClient) -> None:
        vorgang = await vorgang_anlegen(client)
        antwort = await client.patch(
            f"/staffelpilot/vorgaenge/{vorgang['id']}", json={"empfaenger": "verein@example.org"}
        )

        assert antwort.json()["empfaenger"] == "verein@example.org"

    async def test_ausgelassene_felder_bleiben_stehen(self, client: AsyncClient) -> None:
        vorgang = await vorgang_anlegen(client)
        await client.patch(
            f"/staffelpilot/vorgaenge/{vorgang['id']}", json={"betreff": "Neuer Betreff"}
        )
        danach = (await client.get(f"/staffelpilot/vorgaenge/{vorgang['id']}")).json()

        assert danach["betreff"] == "Neuer Betreff"
        assert danach["text"] == vorgang["text"]

    async def test_unbekannter_vorgang_gibt_404(self, client: AsyncClient) -> None:
        assert (await client.get(f"/staffelpilot/vorgaenge/{UNBEKANNT}")).status_code == 404


class TestVorgangZustand:
    async def test_versandt_haelt_den_tag_fest(self, client: AsyncClient) -> None:
        """'versandt' heisst: ein Mensch hat es abgeschickt. Dieses Programm
        verschickt nichts."""
        vorgang = await vorgang_anlegen(client)
        antwort = await client.post(
            f"/staffelpilot/vorgaenge/{vorgang['id']}/zustand", json={"zustand": "versandt"}
        )

        assert antwort.json()["zustand"] == "versandt"
        assert antwort.json()["versandt_am"] is not None

    async def test_ein_sprung_ueber_versandt_hinweg_wird_abgelehnt(
        self, client: AsyncClient
    ) -> None:
        vorgang = await vorgang_anlegen(client)
        antwort = await client.post(
            f"/staffelpilot/vorgaenge/{vorgang['id']}/zustand", json={"zustand": "erledigt"}
        )

        assert antwort.status_code == 409

    async def test_der_versandtag_bleibt_beim_zweiten_mal(self, client: AsyncClient) -> None:
        """Wer ein Schreiben zurueckholt und erneut abschickt, hat es trotzdem
        an dem Tag versandt, an dem es beim Verein ankam."""
        vorgang = await vorgang_anlegen(client)
        pfad = f"/staffelpilot/vorgaenge/{vorgang['id']}/zustand"
        erst = (await client.post(pfad, json={"zustand": "versandt"})).json()["versandt_am"]
        await client.post(pfad, json={"zustand": "entwurf"})
        wieder = (await client.post(pfad, json={"zustand": "versandt"})).json()["versandt_am"]

        assert wieder == erst


class TestVorgangListe:
    async def test_die_liste_traegt_keinen_text(self, client: AsyncClient) -> None:
        """Der Text ist lang und wird erst beim Oeffnen gebraucht."""
        await vorgang_anlegen(client)
        zeilen = (await client.get("/staffelpilot/vorgaenge")).json()

        assert len(zeilen) == 1
        assert "text" not in zeilen[0]

    async def test_nach_zustand_filtern(self, client: AsyncClient) -> None:
        vorgang = await vorgang_anlegen(client)
        await client.post(
            f"/staffelpilot/vorgaenge/{vorgang['id']}/zustand", json={"zustand": "versandt"}
        )

        assert (await client.get("/staffelpilot/vorgaenge?zustand=entwurf")).json() == []
        assert len((await client.get("/staffelpilot/vorgaenge?zustand=versandt")).json()) == 1

    async def test_verwerfen(self, client: AsyncClient) -> None:
        vorgang = await vorgang_anlegen(client)
        antwort = await client.delete(f"/staffelpilot/vorgaenge/{vorgang['id']}")

        assert antwort.status_code == 204
        assert (await client.get("/staffelpilot/vorgaenge")).json() == []

    async def test_der_befund_kennt_seinen_vorgang(self, client: AsyncClient) -> None:
        """Ohne das muesste die Oberflaeche je Befund einmal nachfragen, um zu
        wissen, ob der Knopf 'Entwurf' noch anzubieten ist."""
        vorgang = await vorgang_anlegen(client)
        spiel_id = (await client.get("/staffelpilot/")).json()[0]["id"]
        b = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"][0]

        assert b["vorgang_id"] == vorgang["id"]
        assert b["weg"] == "mahnung"

    async def test_entwuerfe_stehen_in_der_zusammenfassung(self, client: AsyncClient) -> None:
        await vorgang_anlegen(client)
        werte = (await client.get("/staffelpilot/zusammenfassung")).json()

        assert werte["vorgaenge_entwurf"] == 1


# ── Der Fehler, der zwei Befunde verschluckt hat ──────────────────────────


class TestGleicheRegelZweimal:
    async def test_zwei_spieler_ohne_foto_bleiben_zwei(self, client: AsyncClient) -> None:
        """Dieselbe Regel mit demselben Titel gibt es wirklich - zwei Spieler
        ohne Foto in einem Spiel. Ueber (regel, titel) zurueckgesucht wurde
        einer verschluckt und der andere doppelt gezeigt."""
        staffel_id = await staffel_anlegen(client)
        gleich = {
            "regel": "spielerfoto_fehlt",
            "schwere": "hinweis",
            "titel": "Spielerfoto fehlt",
        }
        await einspielen(
            client,
            staffel_id,
            spiel(
                befunde=[
                    befund(**gleich, person="Jan Klein"),
                    befund(**gleich, person="Tim Groß"),
                ]
            ),
        )
        spiel_id = (await client.get("/staffelpilot/")).json()[0]["id"]
        befunde = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"]

        assert sorted(b["person"] for b in befunde) == ["Jan Klein", "Tim Groß"]
