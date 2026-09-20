"""Das Mahnungsformular und der Mailentwurf.

Zwei Zusicherungen, und beide betreffen ein Schriftstück, das an einen Verein
geht:

* Was nicht bekannt ist, bleibt **leer** und wird benannt. Ein Formular mit
  erfundenen Angaben ist schlimmer als eines mit einer Lücke.
* Ein Kreuz wird nur gesetzt, wo der Verband einen Tatbestand vorsieht. Die
  Liste ist geschlossen; ein geratenes Kreuz behauptet etwas, das niemand
  geprüft hat.

Und die dritte, die für alles gilt, was hier hinausgeht: **abgeschickt wird
nichts.**
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from .hilfen import STAFFEL

pytestmark = pytest.mark.integration


async def vorgang_mit_befund(
    client: AsyncClient,
    regel: str = "confirmation_missing",
    weg: str = "mahnung",
    einzelheiten: dict[str, str] | None = None,
    **spielfelder: object,
) -> tuple[str, str]:
    """Eine Staffel, ein Spiel, ein Befund, ein Vorgang. Gibt (vorgang_id, spiel_id)."""
    antwort = await client.post("/staffelpilot/staffeln", json=STAFFEL)
    staffel_id = antwort.json()["id"]

    spiel = {
        "dfbnet_id": "031DHM04",
        "datum": "2026-09-05",
        "heim": "SV Loschwitz",
        "gast": "SG Gittersee",
        "ergebnis": "1 : 2",
        "spielnummer": "633203177",
        "anstoss": "15:00",
        "spielort": "Sportplatz Loschwitz",
        "spieltag": "5",
        "mannschaftsart": "Herren",
        "wettbewerb": "Meisterschaft",
        "befunde": [
            {
                "regel": regel,
                "schwere": "kritisch",
                "titel": "Bestätigung fehlt",
                "text": "Die Heimmannschaft hat nicht bestätigt.",
                "mannschaft": "SV Loschwitz",
                "weg": weg,
                "einzelheiten": einzelheiten or {},
            }
        ],
        **spielfelder,
    }
    await client.post("/staffelpilot/import", json={"staffel_id": staffel_id, "spiele": [spiel]})

    warteschlange = (await client.get("/staffelpilot/?nur_faellig=false")).json()
    spiel_id = warteschlange[0]["id"]
    befund_id = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"][0]["id"]
    vorgang = await client.post(
        f"/staffelpilot/befunde/{befund_id}/vorgang", json={"verein": "SV Loschwitz"}
    )
    assert vorgang.status_code in (200, 201), vorgang.text
    return vorgang.json()["id"], spiel_id


class TestFormular:
    async def test_es_kommt_ein_pdf(self, client: AsyncClient) -> None:
        vorgang_id, _ = await vorgang_mit_befund(client)

        antwort = await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mahnung.pdf")

        assert antwort.status_code == 200
        assert antwort.headers["content-type"] == "application/pdf"
        assert antwort.content.startswith(b"%PDF")

    async def test_es_heisst_nach_dem_aktenzeichen(self, client: AsyncClient) -> None:
        """Daran findet der Staffelleiter es wieder, wenn zwanzig davon im
        Ordner liegen."""
        vorgang_id, _ = await vorgang_mit_befund(client)

        antwort = await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mahnung.pdf")

        assert "Mahnung_" in antwort.headers["content-disposition"]

    async def test_was_fehlt_wird_benannt(self, client: AsyncClient) -> None:
        """Und nicht mit einem Platzhalter gefüllt."""
        vorgang_id, _ = await vorgang_mit_befund(client, spielort="", spieltag="", spielnummer="")

        antwort = await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mahnung.pdf")
        fehlt = antwort.headers["x-fehlende-felder"]

        assert "Spielort" in fehlt
        assert "Spieltag" in fehlt
        assert "Spielnummer" in fehlt

    async def test_mit_allen_angaben_fehlt_nur_der_staffelleiter(self, client: AsyncClient) -> None:
        """Er steht in den Einstellungen; eine frische Installation hat ihn
        noch nicht."""
        vorgang_id, _ = await vorgang_mit_befund(client)

        antwort = await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mahnung.pdf")

        assert antwort.headers["x-fehlende-felder"] == "Staffelleiter"

    async def test_der_staffelleiter_kommt_aus_den_einstellungen(self, client: AsyncClient) -> None:
        await client.put("/staffelpilot/einstellungen", json={"staffelleiter": "Aaron Mütze"})
        vorgang_id, _ = await vorgang_mit_befund(client)

        antwort = await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mahnung.pdf")

        assert antwort.headers["x-fehlende-felder"] == ""

    async def test_einen_unbekannten_vorgang_gibt_es_nicht(self, client: AsyncClient) -> None:
        antwort = await client.get(f"/staffelpilot/vorgaenge/{uuid.uuid4()}/mahnung.pdf")

        assert antwort.status_code == 404


class TestMailentwurf:
    async def test_betreff_und_text_stehen_bereit(self, client: AsyncClient) -> None:
        vorgang_id, _ = await vorgang_mit_befund(client)

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert entwurf["betreff"]
        assert entwurf["text"]

    async def test_der_empfaenger_ist_ein_vorschlag_und_keine_vorgabe(
        self, client: AsyncClient
    ) -> None:
        """Wer die Mail bekommt, entscheidet der Staffelleiter."""
        vorgang_id, _ = await vorgang_mit_befund(client)

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert entwurf["empfaenger"] == ""

    async def test_die_mahnung_haengt_an(self, client: AsyncClient) -> None:
        vorgang_id, _ = await vorgang_mit_befund(client)

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert entwurf["anhang"].endswith("/mahnung.pdf")

    async def test_ein_sportgerichtsfall_hat_kein_formular(self, client: AsyncClient) -> None:
        """Er läuft über das Verbandspostfach, nicht über den Vordruck für
        Bagatellsachen."""
        vorgang_id, _ = await vorgang_mit_befund(
            client, regel="player_eligibility", weg="sportgericht"
        )

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert entwurf["anhang"] == ""


class TestDerSatzZumVergehen:
    """Der Weg vom Befund bis in den Brief -- ueber Schema, Spalte und Vorlage.

    Die Einzelheiten reisen weit: der Prueflauf legt sie an, das Artefakt legt
    sie in eine JSONB-Spalte, und aus ihr wird ein Satz in einem Schreiben an
    einen Verein. Bricht der Weg an einer Stelle, faellt das erst dort auf --
    wenn niemand hinschaut, erst im Briefkasten.
    """

    async def test_der_paragraf_steht_im_text(self, client: AsyncClient) -> None:
        vorgang_id, _ = await vorgang_mit_befund(client, regel="order_manager_missing")

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert "kein Leiter Ordnungsdienst" in entwurf["text"]
        assert "§ 53" in entwurf["text"]

    async def test_die_einzelheiten_ueberleben_die_datenbank(self, client: AsyncClient) -> None:
        vorgang_id, _ = await vorgang_mit_befund(
            client,
            regel="confirmation_late",
            einzelheiten={"signed_at": "22:35", "deadline": "20:14"},
        )

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert "erst am 22:35" in entwurf["text"]
        assert "(20:14)" in entwurf["text"]

    async def test_ohne_einzelheiten_bleibt_kein_satz_angefangen(self, client: AsyncClient) -> None:
        vorgang_id, _ = await vorgang_mit_befund(client, regel="confirmation_late")

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert "erst am" not in entwurf["text"]
        assert "nach Ablauf der Frist bestätigt" in entwurf["text"]

    async def test_eine_regel_ohne_vorlage_behaelt_den_befundtext(self, client: AsyncClient) -> None:
        vorgang_id, _ = await vorgang_mit_befund(client, regel="dfbnet_warning")

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert "Die Heimmannschaft hat nicht bestätigt." in entwurf["text"]
