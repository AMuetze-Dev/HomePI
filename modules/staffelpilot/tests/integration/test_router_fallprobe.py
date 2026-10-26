"""Die Fallprobe: denselben Weg gehen und nicht speichern.

**Ein Aktenzeichen ist dauerhaft.** Wer die Fallanlage ausprobieren will, legt
sonst ein Verfahren gegen eine benannte Person an — und löscht es nicht wieder.
Deshalb gibt es einen Auftrag, der bis vor das Speichern geht: Menü, Suche,
Treffer, Formular, Felder. Passt alles, sagt er das. Passt etwas nicht, sagt er
genau, was.

Das ist kein Ersatz für die Anlage, sondern ihre Vorprüfung — und der einzige
ehrliche Weg, die Selektoren am echten DFBnet zu prüfen.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import STAFFEL, befund, einspielen, spiel

pytestmark = pytest.mark.integration


async def _vorgang(
    client: AsyncClient,
    *,
    sportgericht: str = "Sportgericht Stadtverband Fußball Dresden e.V.",
    spielnummer: str = "633203004",
    weg: str = "sportgericht",
    grund: str = "Feldverweis auf Dauer wegen Tätlichkeit",
) -> str:
    antwort = await client.post(
        "/staffelpilot/staffeln", json={**STAFFEL, "sportgericht": sportgericht}
    )
    staffel_id = antwort.json()["id"]
    await einspielen(
        client,
        staffel_id,
        spiel(
            "031DHM03",
            spielnummer=spielnummer,
            anstoss="15:00",
            spielort="Sportplatz Loschwitz",
            mannschaftsart="Herren",
            befunde=[befund(regel="player_eligibility", weg=weg)],
        ),
    )
    spiel_id = (await client.get("/staffelpilot/?nur_faellig=false")).json()[0]["id"]
    befund_id = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"][0]["id"]
    angelegt = await client.post(
        f"/staffelpilot/befunde/{befund_id}/vorgang",
        json={"verein": "SG Gittersee", "grund": grund},
    )
    return str(angelegt.json()["id"])


class TestProbeAnfordern:
    async def test_sie_wird_ein_auftrag(self, client: AsyncClient) -> None:
        """Ein Auftrag und keine Übertragung: die Übertragung ist die Liste
        dessen, was wirklich hinaus soll. Eine Probe gehört nicht hinein."""
        vorgang_id = await _vorgang(client)

        antwort = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallprobe")

        assert antwort.status_code == 201, antwort.text
        assert antwort.json()["art"] == "fallprobe"
        assert antwort.json()["referenz"] == vorgang_id

    async def test_sie_laesst_die_warteschlange_in_ruhe(self, client: AsyncClient) -> None:
        vorgang_id = await _vorgang(client)

        await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallprobe")

        assert (await client.get("/staffelpilot/uebertragungen")).json()["offen"] == 0

    async def test_zweimal_hintereinander_geht_nicht(self, client: AsyncClient) -> None:
        """Es gibt genau eine DFBnet-Sitzung."""
        vorgang_id = await _vorgang(client)
        await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallprobe")

        zweite = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallprobe")

        assert zweite.status_code == 409


class TestWasAbgewiesenWird:
    async def test_eine_mahnung_hat_kein_sportgericht(self, client: AsyncClient) -> None:
        vorgang_id = await _vorgang(client, weg="mahnung")

        antwort = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallprobe")

        assert antwort.status_code == 409
        assert "sportgericht" in antwort.text

    async def test_ohne_gericht_an_der_staffel_gar_nicht(self, client: AsyncClient) -> None:
        """Dieselbe Prüfung wie beim Anlegen. Eine Probe, die mehr durchlässt
        als die Sache selbst, prüft die falsche Sache."""
        vorgang_id = await _vorgang(client, sportgericht="")

        antwort = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallprobe")

        assert antwort.status_code == 409
        assert "Sportgericht" in antwort.text

    async def test_ohne_spielnummer_gar_nicht(self, client: AsyncClient) -> None:
        vorgang_id = await _vorgang(client, spielnummer="")

        antwort = await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallprobe")

        assert antwort.status_code == 409


class TestDasSpielTraegtSeineKopfdaten:
    """Die Spielnummer muss aus der Schnittstelle herauskommen.

    Sie steht im DFBnet-Formular als Suchschlüssel: ohne sie findet die
    Fallanlage kein Spiel. Am 26.10.2026 kam sie nicht heraus -- die Route
    baute ihre Antwort Feld für Feld zusammen und ließ alle sechs Kopfdaten
    weg. In der Datenbank standen sie; über die Schnittstelle waren sie leer,
    und jede Fallanlage wäre mit "Es fehlt noch: Spielkennung" gescheitert,
    obwohl nichts fehlte.

    Gefunden hat es nicht ein Test, sondern `tools/nachsehen.py faelle` --
    also der Blick auf das, was wirklich dasteht.
    """

    async def test_die_spielnummer_kommt_heraus(self, client: AsyncClient) -> None:
        await _vorgang(client, spielnummer="633203004")
        spiel_id = (await client.get("/staffelpilot/?nur_faellig=false")).json()[0]["id"]

        gelesen = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()

        assert gelesen["spielnummer"] == "633203004"

    async def test_und_die_uebrigen_kopfdaten_auch(self, client: AsyncClient) -> None:
        """Sie stehen im Mahnungsformular. Leer heisst dort "nicht bekannt" --
        und das waere hier gelogen."""
        await _vorgang(client)
        spiel_id = (await client.get("/staffelpilot/?nur_faellig=false")).json()[0]["id"]

        gelesen = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()

        assert gelesen["anstoss"] == "15:00"
        assert gelesen["spielort"] == "Sportplatz Loschwitz"
        assert gelesen["mannschaftsart"] == "Herren"
