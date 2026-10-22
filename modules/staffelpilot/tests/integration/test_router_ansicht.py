"""Das Vorschaufenster: ein Abbild der Seite am Auftrag.

Warum es das gibt: der Prüfdienst fährt einen Browser in einem Container ohne
Bildschirm. Ein sichtbares Chromium kann es dort nie geben — `Missing X server`
—, und auf Windows soll dieser Dienst nicht laufen müssen, damit jemand
zusehen kann. Also wird die Seite fotografiert statt gezeigt.

Warum ein Bild und kein HTML: gemessen am 22.10.2026 wiegt die
Spielberichtssuche als JPEG 85 KiB, ihr rohes HTML 203 KiB — und das HTML wäre
in unserer Oberfläche unbrauchbar (fremdes CSS hinter derselben Sitzung,
relative Verweise, XSS). Vor allem sind die Comboboxen JS-getrieben: genau
das, was man sehen will, stünde im DOM nicht drin.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

#: Ein winziges, gültiges JPEG. Kein echtes Bild — geprüft wird der Weg.
BILD = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300"
    + "08060607060508070707090908"
    + "0a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c3033"
    + "3435311f27393d38323c2e333431ffc9000b080001000101011100ffcc000600101005ffda"
    + "0008010100003f00d2cf20ffd9"
)


async def auftrag_anfordern(client: AsyncClient) -> str:
    antwort = await client.post("/staffelpilot/auftraege", json={"art": "pruflauf"})
    assert antwort.status_code in (200, 201), antwort.text
    return str(antwort.json()["id"])


async def ablegen(client: AsyncClient, auftrag_id: str, art: str = "aktuell", **kopf: str):
    return await client.put(
        f"/staffelpilot/auftraege/{auftrag_id}/ansicht/{art}",
        content=BILD,
        headers={"Content-Type": "image/jpeg", **kopf},
    )


class TestAblegenUndHolen:
    async def test_das_abbild_kommt_zurueck_wie_es_kam(self, client: AsyncClient) -> None:
        auftrag_id = await auftrag_anfordern(client)
        assert (await ablegen(client, auftrag_id)).status_code == 204

        antwort = await client.get(f"/staffelpilot/auftraege/{auftrag_id}/ansicht/aktuell")

        assert antwort.status_code == 200
        assert antwort.headers["content-type"] == "image/jpeg"
        assert antwort.content == BILD

    async def test_der_schritt_steht_dabei(self, client: AsyncClient) -> None:
        """Ohne ihn ist ein Bild nur ein Bild."""
        auftrag_id = await auftrag_anfordern(client)
        await ablegen(client, auftrag_id, **{"X-Schritt": "Trefferliste Stadtliga C"})

        antwort = await client.get(f"/staffelpilot/auftraege/{auftrag_id}/ansicht/aktuell")

        assert antwort.headers["x-schritt"] == "Trefferliste Stadtliga C"

    async def test_es_wird_nicht_zwischengespeichert(self, client: AsyncClient) -> None:
        """Dasselbe Bild unter derselben Adresse ändert sich im Sekundentakt.
        Ein Browser, der es behält, zeigt eine Ansicht von vor zwei Minuten —
        und sieht dabei aus wie eine aktuelle."""
        auftrag_id = await auftrag_anfordern(client)
        await ablegen(client, auftrag_id)

        antwort = await client.get(f"/staffelpilot/auftraege/{auftrag_id}/ansicht/aktuell")

        assert antwort.headers["cache-control"] == "no-store"

    async def test_das_zweite_ersetzt_das_erste(self, client: AsyncClient) -> None:
        """Höchstens zwei Zeilen je Auftrag. Ein Band aus Bildern wäre nach
        drei Prüfläufen größer als die ganze übrige Datenbank."""
        auftrag_id = await auftrag_anfordern(client)
        await ablegen(client, auftrag_id, **{"X-Schritt": "erstes"})
        await ablegen(client, auftrag_id, **{"X-Schritt": "zweites"})

        antwort = await client.get(f"/staffelpilot/auftraege/{auftrag_id}/ansicht/aktuell")

        assert antwort.headers["x-schritt"] == "zweites"

    async def test_das_fehlerbild_steht_neben_dem_laufenden(self, client: AsyncClient) -> None:
        """Zwei verschiedene Aussagen: das eine veraltet, das andere ist der
        Beweis — und wird vom nächsten Schritt nicht überschrieben."""
        auftrag_id = await auftrag_anfordern(client)
        await ablegen(client, auftrag_id, "fehler", **{"X-Schritt": "Staffel nicht gefunden"})
        await ablegen(client, auftrag_id, "aktuell", **{"X-Schritt": "weiter"})

        fehler = await client.get(f"/staffelpilot/auftraege/{auftrag_id}/ansicht/fehler")

        assert fehler.headers["x-schritt"] == "Staffel nicht gefunden"


class TestWelcheEsGibt:
    async def test_am_anfang_keine(self, client: AsyncClient) -> None:
        auftrag_id = await auftrag_anfordern(client)

        antwort = await client.get(f"/staffelpilot/auftraege/{auftrag_id}/ansichten")

        assert antwort.json()["arten"] == []

    async def test_danach_beide(self, client: AsyncClient) -> None:
        """Damit die Oberfläche nicht auf zwei Adressen raten muss, von denen
        eine 404 gibt."""
        auftrag_id = await auftrag_anfordern(client)
        await ablegen(client, auftrag_id, "aktuell")
        await ablegen(client, auftrag_id, "fehler")

        antwort = await client.get(f"/staffelpilot/auftraege/{auftrag_id}/ansichten")

        assert antwort.json()["arten"] == ["aktuell", "fehler"]


class TestAbgewiesen:
    async def test_eine_erfundene_art_gibt_es_nicht(self, client: AsyncClient) -> None:
        auftrag_id = await auftrag_anfordern(client)

        antwort = await ablegen(client, auftrag_id, "irgendwas")

        assert antwort.status_code == 404

    async def test_ein_leeres_abbild_wird_nicht_abgelegt(self, client: AsyncClient) -> None:
        auftrag_id = await auftrag_anfordern(client)

        antwort = await client.put(
            f"/staffelpilot/auftraege/{auftrag_id}/ansicht/aktuell",
            content=b"",
            headers={"Content-Type": "image/jpeg"},
        )

        assert antwort.status_code == 413

    async def test_ein_zu_grosses_wird_abgewiesen(self, client: AsyncClient) -> None:
        """Ohne Grenze legte ein Dienst, der versehentlich ein PNG in voller
        Höhe schickt, die Datenbank mit Bildern zu, die niemand ansieht."""
        auftrag_id = await auftrag_anfordern(client)

        antwort = await client.put(
            f"/staffelpilot/auftraege/{auftrag_id}/ansicht/aktuell",
            content=b"x" * (2 * 1024 * 1024 + 1),
            headers={"Content-Type": "image/jpeg"},
        )

        assert antwort.status_code == 413

    async def test_zu_einem_unbekannten_auftrag_geht_es_nicht(self, client: AsyncClient) -> None:
        antwort = await ablegen(client, str(uuid.uuid4()))

        assert antwort.status_code == 404

    async def test_ohne_abbild_gibt_es_keines(self, client: AsyncClient) -> None:
        """Kein leeres Bild und kein Platzhalter: die Oberfläche soll
        unterscheiden können, ob nichts da ist oder nichts zu sehen war."""
        auftrag_id = await auftrag_anfordern(client)

        antwort = await client.get(f"/staffelpilot/auftraege/{auftrag_id}/ansicht/aktuell")

        assert antwort.status_code == 404
