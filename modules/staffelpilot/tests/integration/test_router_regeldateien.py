"""Die Regeldateien: Quelltext im Artefakt, Kopie im Prüfdienst.

Bisher lagen die dreißig Prüfungen der Spielordnung nur in einem Band am
Prüfdienst. Wer eine ändern wollte, brauchte eine Konsole auf dem Pi.

**Das hier ist ausführbarer Code.** Er läuft im Prüfdienst, in dessen
Container, mit dessen Rechten. Deshalb steht in dieser Datei mehr über das
Abweisen als über das Speichern — und deshalb prüft sie zuerst, dass ein
Dateiname kein Pfad sein kann.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

REGEL = {
    "name": "90_eigene.py",
    "inhalt": '@regel("eigene", "Eine eigene Prüfung")\ndef pruefe(spiel, melde):\n    pass\n',
}


async def ablegen(client: AsyncClient, **abweichend: object):
    return await client.put("/staffelpilot/regeldateien", json={**REGEL, **abweichend})


class TestAblegen:
    async def test_eine_datei_kommt_an(self, client: AsyncClient) -> None:
        antwort = await ablegen(client)

        assert antwort.status_code == 200, antwort.text
        assert antwort.json()["name"] == "90_eigene.py"
        assert antwort.json()["aktiv"] is True

    async def test_die_liste_kommt_ohne_quelltext(self, client: AsyncClient) -> None:
        """Dreißig Dateien mit je zweihundert Zeilen wären ein
        Viertelmegabyte für eine Liste."""
        await ablegen(client)

        liste = (await client.get("/staffelpilot/regeldateien")).json()

        assert liste[0]["zeilen"] == 4
        assert "inhalt" not in liste[0]

    async def test_der_quelltext_kommt_beim_oeffnen(self, client: AsyncClient) -> None:
        kennung = (await ablegen(client)).json()["id"]

        datei = (await client.get(f"/staffelpilot/regeldateien/{kennung}")).json()

        assert datei["inhalt"] == REGEL["inhalt"]

    async def test_derselbe_name_ueberschreibt(self, client: AsyncClient) -> None:
        """Zwei Dateien desselben Namens gäbe es im Ordner des Prüfdienstes
        ohnehin nicht — welche gewänne, hinge an der Reihenfolge des
        Schreibens."""
        erste = (await ablegen(client)).json()["id"]

        zweite = await ablegen(client, inhalt="# anders\n")

        assert zweite.json()["id"] == erste
        assert len((await client.get("/staffelpilot/regeldateien")).json()) == 1

    async def test_nach_namen_sortiert(self, client: AsyncClient) -> None:
        """Das ist die Ladereihenfolge: `10_` vor `20_`, und eine
        `90_eigene.py` kann am Ende gezielt etwas ersetzen."""
        await ablegen(client, name="90_eigene.py")
        await ablegen(client, name="10_zuerst.py")

        namen = [d["name"] for d in (await client.get("/staffelpilot/regeldateien")).json()]

        assert namen == ["10_zuerst.py", "90_eigene.py"]


class TestAendern:
    async def test_der_quelltext_laesst_sich_ersetzen(self, client: AsyncClient) -> None:
        kennung = (await ablegen(client)).json()["id"]

        await client.patch(f"/staffelpilot/regeldateien/{kennung}", json={"inhalt": "# ganz neu\n"})

        datei = (await client.get(f"/staffelpilot/regeldateien/{kennung}")).json()
        assert datei["inhalt"] == "# ganz neu\n"

    async def test_stilllegen_laesst_sie_liegen(self, client: AsyncClient) -> None:
        """Aus heißt: liegt hier, läuft nicht. Besser als gelöscht, wenn
        jemand sie nur vorübergehend stilllegen will."""
        kennung = (await ablegen(client)).json()["id"]

        await client.patch(f"/staffelpilot/regeldateien/{kennung}", json={"aktiv": False})

        liste = (await client.get("/staffelpilot/regeldateien")).json()
        assert len(liste) == 1
        assert liste[0]["aktiv"] is False

    async def test_ausgelassene_felder_bleiben_stehen(self, client: AsyncClient) -> None:
        kennung = (await ablegen(client)).json()["id"]

        await client.patch(f"/staffelpilot/regeldateien/{kennung}", json={"aktiv": False})

        datei = (await client.get(f"/staffelpilot/regeldateien/{kennung}")).json()
        assert datei["inhalt"] == REGEL["inhalt"]


class TestLoeschen:
    async def test_sie_ist_danach_weg(self, client: AsyncClient) -> None:
        kennung = (await ablegen(client)).json()["id"]

        antwort = await client.delete(f"/staffelpilot/regeldateien/{kennung}")

        assert antwort.status_code == 204
        assert (await client.get("/staffelpilot/regeldateien")).json() == []

    async def test_eine_unbekannte_gibt_es_nicht(self, client: AsyncClient) -> None:
        antwort = await client.delete(f"/staffelpilot/regeldateien/{uuid.uuid4()}")

        assert antwort.status_code == 404


class TestAbgewiesen:
    @pytest.mark.parametrize(
        "name",
        [
            "../draussen.py",
            "unter/ordner.py",
            "mit leerzeichen.py",
            "ohne_endung",
            "umlaut_ä.py",
            ".py",
        ],
    )
    async def test_ein_name_der_ein_pfad_sein_koennte(self, client: AsyncClient, name: str) -> None:
        """Der Name wird zu einem Pfad im Ordner des Prüfdienstes.

        Ein `../` darin wäre ein Weg aus dem Ordner heraus, ein Leerzeichen
        eine Datei, die der Lader übersieht — beides wäre still.
        """
        antwort = await ablegen(client, name=name)

        assert antwort.status_code == 422, f"{name!r} wurde angenommen"

    async def test_ein_unbekanntes_oeffnen_gibt_404(self, client: AsyncClient) -> None:
        antwort = await client.get(f"/staffelpilot/regeldateien/{uuid.uuid4()}")

        assert antwort.status_code == 404
