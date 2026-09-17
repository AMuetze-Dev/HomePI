"""Was beide Integrationsdateien brauchen.

Eigene Datei und nicht die eine oder andere Testdatei: ein Test, der
Helfer aus einer anderen Testdatei holt, laeuft nur so lange, wie beide
im selben Verzeichnis liegen -- und sagt beim Umziehen nicht Bescheid.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

UNBEKANNT = "11111111-1111-1111-1111-111111111111"

STAFFEL = {
    "name": "Stadtliga C",
    "altersklasse": "maenner",
    "spielklasse": "3.Kreisliga (C)",
    "saison": "26/27",
}


async def staffel_anlegen(client: AsyncClient, **abweichend: Any) -> str:
    antwort = await client.post("/staffelpilot/staffeln", json={**STAFFEL, **abweichend})
    assert antwort.status_code == 201, antwort.text
    return str(antwort.json()["id"])


def spiel(dfbnet_id: str = "M-1", **abweichend: Any) -> dict[str, Any]:
    return {
        "dfbnet_id": dfbnet_id,
        "datum": "2026-09-13",
        "heim": "SG Gittersee",
        "gast": "SV Fortschritt",
        "ergebnis": "2 : 1",
        "befunde": [],
        **abweichend,
    }


def befund(**abweichend: Any) -> dict[str, Any]:
    return {
        "regel": "rote_karte",
        "schwere": "kritisch",
        "titel": "Feldverweis auf Dauer",
        "text": "Feldverweis in Minute 71.",
        "person": "Max Müller",
        "mannschaft": "SG Gittersee",
        **abweichend,
    }


async def einspielen(client: AsyncClient, staffel_id: str, *spiele: dict[str, Any]) -> Any:
    return await client.post(
        "/staffelpilot/import", json={"staffel_id": staffel_id, "spiele": list(spiele)}
    )


async def erste_zeile(client: AsyncClient) -> dict[str, Any]:
    zeilen = (await client.get("/staffelpilot/")).json()
    assert zeilen, "die Warteschlange ist leer"
    return dict(zeilen[0])


async def erster_befund(client: AsyncClient, spiel_id: str) -> dict[str, Any]:
    befunde = (await client.get(f"/staffelpilot/spiele/{spiel_id}")).json()["befunde"]
    assert befunde, "das Spiel hat keine Befunde"
    return dict(befunde[0])
