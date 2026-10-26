"""Das Aktenzeichen aus DFBnet — und die Mail, die sich darauf beruft.

Der Prüfdienst legt den Fall an, DFBnet vergibt eine Nummer, und **aus dieser
Nummer entsteht die Mail an den Sportrichter.** Bis hierher endete die Nummer
in einer Meldungszeile: der Fall war angelegt, aber das Schreiben dazu ließ
sich nicht vorbereiten, weil niemand mehr wusste, wie die Akte heißt.

**Abgeschickt wird nichts** — siehe `test_kein_mailversand.py`.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .hilfen import STAFFEL, befund, einspielen, spiel

pytestmark = pytest.mark.integration

AKTENZEICHEN = "00042-26/27-SPG_DD"


async def _vorgang(client: AsyncClient, weg: str = "sportgericht") -> tuple[str, str]:
    """Eine Staffel, ein Spiel, ein Befund, ein Vorgang. Gibt (vorgang_id, spiel_id)."""
    antwort = await client.post(
        "/staffelpilot/staffeln",
        json={**STAFFEL, "sportgericht": "Sportgericht Stadtverband Fußball Dresden e.V."},
    )
    staffel_id = antwort.json()["id"]
    await einspielen(
        client,
        staffel_id,
        spiel(
            "031DHM03",
            spielnummer="633203004",
            befunde=[befund(regel="player_eligibility", weg=weg)],
        ),
    )
    spiel_id = (await client.get("/staffelpilot/?nur_faellig=false")).json()[0]["id"]
    befund_id = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"][0]["id"]
    angelegt = await client.post(
        f"/staffelpilot/befunde/{befund_id}/vorgang",
        json={
            "verein": "SG Gittersee",
            "betroffener": "Redlingshöfer, Tom",
            "grund": "Feldverweis aufgrund Beleidigung",
        },
    )
    assert angelegt.status_code in (200, 201), angelegt.text
    return str(angelegt.json()["id"]), str(spiel_id)


async def _vorgemerkt_und_erledigt(
    client: AsyncClient, vorgang_id: str, **abschluss: object
) -> dict:
    """Vormerken, die Zeile übernehmen und sie abschließen -- wie der Dienst."""
    await client.post(f"/staffelpilot/vorgaenge/{vorgang_id}/fallanlage")
    offen = await client.post("/staffelpilot/uebertragungen/naechste")
    assert offen.status_code == 200, offen.text
    zeile = offen.json()
    antwort = await client.post(
        f"/staffelpilot/uebertragungen/{zeile['id']}/abschluss",
        json={"zustand": "fertig", **abschluss},
    )
    assert antwort.status_code == 200, antwort.text
    return dict(antwort.json())


class TestAktenzeichenKommtAn:
    async def test_der_dienst_kann_es_zurueckmelden(self, client: AsyncClient) -> None:
        vorgang_id, _ = await _vorgang(client)

        await _vorgemerkt_und_erledigt(client, vorgang_id, aktenzeichen=AKTENZEICHEN)

        vorgang = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}")).json()
        assert vorgang["dfbnet_aktenzeichen"] == AKTENZEICHEN

    async def test_ohne_nummer_bleibt_es_leer(self, client: AsyncClient) -> None:
        """DFBnet zeigt die Nummer nicht immer. Dann steht dort nichts --
        und nicht etwas Erfundenes."""
        vorgang_id, _ = await _vorgang(client)

        await _vorgemerkt_und_erledigt(client, vorgang_id)

        vorgang = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}")).json()
        assert vorgang["dfbnet_aktenzeichen"] == ""

    async def test_von_hand_laesst_es_sich_nachtragen(self, client: AsyncClient) -> None:
        """Wenn die Nummer auf der Seite nicht stand, steht sie in DFBnet.
        Abtippen muss möglich sein, sonst ist der Fall unbrauchbar."""
        vorgang_id, _ = await _vorgang(client)
        await _vorgemerkt_und_erledigt(client, vorgang_id)

        geaendert = await client.patch(
            f"/staffelpilot/vorgaenge/{vorgang_id}",
            json={"dfbnet_aktenzeichen": AKTENZEICHEN},
        )

        assert geaendert.status_code == 200, geaendert.text
        assert geaendert.json()["dfbnet_aktenzeichen"] == AKTENZEICHEN


class TestDieMailAnDenSportrichter:
    async def test_vor_der_anlage_steht_der_antrag(self, client: AsyncClient) -> None:
        """Ohne Aktenzeichen gibt es keine Akte, auf die man sich beruft."""
        vorgang_id, _ = await _vorgang(client)

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert "Antrag" in entwurf["betreff"]
        assert "Aktenzeichen:" not in entwurf["text"]
        assert "Aktenzeichen" in entwurf["fehlende_felder"]

    async def test_mit_aktenzeichen_wird_daraus_die_mail(self, client: AsyncClient) -> None:
        vorgang_id, _ = await _vorgang(client)
        await _vorgemerkt_und_erledigt(client, vorgang_id, aktenzeichen=AKTENZEICHEN)

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        # Der Betreff ist der des Staffelleiters: Klammern, Verein, Person.
        assert entwurf["betreff"] == f"[{AKTENZEICHEN}], SG Gittersee, Redlingshöfer, Tom"
        assert entwurf["text"].startswith("Guten Tag,")
        assert f"Aktenzeichen: {AKTENZEICHEN}" in entwurf["text"]
        assert "Spieler: Redlingshöfer, Tom" in entwurf["text"]
        assert entwurf["fehlende_felder"] == []

    async def test_eine_mahnung_bleibt_eine_mahnung(self, client: AsyncClient) -> None:
        """Nur Sportgerichtsfälle bekommen dieses Schreiben. Eine Mahnung geht
        an den Verein und hat mit dem Sportrichter nichts zu tun."""
        vorgang_id, _ = await _vorgang(client, weg="mahnung")

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert "Mahnung" in entwurf["betreff"]
        assert entwurf["anhang"].endswith("/mahnung.pdf")

    async def test_es_gibt_keinen_anhang(self, client: AsyncClient) -> None:
        """Der Sonderbericht des Schiedsrichters liegt in DFBnet, nicht hier.
        Ein Vordruck für Bagatellsachen wäre hier das falsche Papier."""
        vorgang_id, _ = await _vorgang(client)
        await _vorgemerkt_und_erledigt(client, vorgang_id, aktenzeichen=AKTENZEICHEN)

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert entwurf["anhang"] == ""

    @pytest.mark.parametrize(
        "feld,erwartet",
        [("verein", "Verein"), ("betroffener", "Angeklagter")],
    )
    async def test_was_fehlt_wird_benannt(
        self, client: AsyncClient, feld: str, erwartet: str
    ) -> None:
        """Ein Schreiben mit Lücke ist besser als eines mit erfundener Angabe
        — aber nur, wenn die Lücke auffällt."""
        vorgang_id, _ = await _vorgang(client)
        await _vorgemerkt_und_erledigt(client, vorgang_id, aktenzeichen=AKTENZEICHEN)
        await client.patch(f"/staffelpilot/vorgaenge/{vorgang_id}", json={feld: " "})

        entwurf = (await client.get(f"/staffelpilot/vorgaenge/{vorgang_id}/mail")).json()

        assert erwartet in entwurf["fehlende_felder"]
