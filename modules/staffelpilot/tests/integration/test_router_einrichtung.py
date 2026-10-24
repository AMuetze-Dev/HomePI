"""Der Einrichtungsstand: was fehlt, bevor dieses Artefakt etwas kann.

Ohne DFBnet-Zugang und ohne Staffel bleibt jede Liste leer. Ohne diesen Ruf
stünde dort „keine Spielberichte" statt „hier fehlt noch etwas" — und der
Unterschied ist der zwischen einer Anwendung, die nichts zu tun hat, und
einer, die nicht eingerichtet ist.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from homepi_staffelpilot.dienst import SCHLUESSEL_VARIABLE

from .hilfen import staffel_anlegen

pytestmark = pytest.mark.integration


@pytest.fixture
def mit_schluessel(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Ohne Schluessel in der Umgebung legt das Artefakt kein Passwort ab --
    und sagt das mit 503 statt es stumm zu verlieren."""
    schluessel = Fernet.generate_key().decode()
    monkeypatch.setenv(SCHLUESSEL_VARIABLE, schluessel)
    yield schluessel


async def stand(client: AsyncClient) -> dict:
    antwort = await client.get("/staffelpilot/einrichtung")
    assert antwort.status_code == 200, antwort.text
    return dict(antwort.json())


class TestEinrichtung:
    async def test_frisch_fehlt_der_zugang(self, client: AsyncClient) -> None:
        assert (await stand(client))["schritt"] == "zugang"

    async def test_mit_zugang_fehlen_die_staffeln(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        await client.put(
            "/staffelpilot/zugang",
            json={"benutzer": "staffelleiter", "passwort": "geheim-und-lang"},
        )

        gelesen = await stand(client)

        assert gelesen["zugang"] is True
        assert gelesen["schritt"] == "staffeln"

    async def test_mit_beidem_ist_sie_fertig(
        self, client: AsyncClient, mit_schluessel: str
    ) -> None:
        await client.put(
            "/staffelpilot/zugang",
            json={"benutzer": "staffelleiter", "passwort": "geheim-und-lang"},
        )
        await staffel_anlegen(client)

        gelesen = await stand(client)

        assert gelesen["staffeln"] == 1
        assert gelesen["schritt"] == "fertig"

    async def test_abgehakt_bleibt_abgehakt(self, client: AsyncClient) -> None:
        """Ein Weg, der sich nicht schließen lässt, ist eine Sackgasse."""
        await client.put("/staffelpilot/einstellungen", json={"einrichtung_erledigt": True})

        gelesen = await stand(client)

        assert gelesen["erledigt"] is True
        assert gelesen["schritt"] == "fertig"
        # Was fehlt, steht trotzdem da -- die Oberflaeche soll daraus einen
        # Hinweis machen koennen, nur keinen Zwang.
        assert gelesen["zugang"] is False

    async def test_sie_laesst_sich_wieder_aufmachen(self, client: AsyncClient) -> None:
        await client.put("/staffelpilot/einstellungen", json={"einrichtung_erledigt": True})
        await client.put("/staffelpilot/einstellungen", json={"einrichtung_erledigt": False})

        assert (await stand(client))["schritt"] == "zugang"

    async def test_eine_anmeldeprobe_laesst_sich_anfordern(self, client: AsyncClient) -> None:
        """Der kürzeste Auftrag von allen: anmelden und sonst nichts.

        Ein eigener, damit ein falsches Passwort als falsches Passwort
        dasteht und nicht als „Staffeln ließen sich nicht holen".
        """
        antwort = await client.post("/staffelpilot/auftraege", json={"art": "anmeldeprobe"})

        assert antwort.status_code == 201, antwort.text
        assert antwort.json()["art"] == "anmeldeprobe"
