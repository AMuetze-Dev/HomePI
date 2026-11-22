"""Der Router gegen eine echte Datenbank - Elternseite und Geraeteseite.

    HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
        uv run pytest -m 'not smoke'
"""

from __future__ import annotations

import io
import wave
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

UID = "04A1B2C3D4E5F6"


def wav(sekunden: float = 1.0, rate: int = 22050) -> bytes:
    puffer = io.BytesIO()
    with wave.open(puffer, "wb") as datei:
        datei.setnchannels(1)
        datei.setsampwidth(2)
        datei.setframerate(rate)
        datei.writeframes(b"\x01\x00" * int(sekunden * rate))
    return puffer.getvalue()


async def hochladen(
    client: AsyncClient, titel: str = "Oma sagt Hallo", art: str = "stimme", daten: bytes = b""
) -> Any:
    antwort = await client.post(
        "/kinderzimmer/aufnahmen",
        params={"titel": titel, "art": art},
        content=daten or wav(),
        headers={"Content-Type": "audio/wav"},
    )
    return antwort


async def geraet(client: AsyncClient, name: str = "Spielkiste") -> dict[str, Any]:
    antwort = await client.post("/kinderzimmer/geraete", json={"name": name})
    assert antwort.status_code == 201, antwort.text
    return dict(antwort.json())


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Zugang --------------------------------------------------------------------


async def test_ohne_anmeldung_bleibt_alles_zu(client: AsyncClient) -> None:
    await client.post("/auth/abmelden")

    assert (await client.get("/kinderzimmer/")).status_code == 401
    assert (await client.get("/kinderzimmer/geraet/stand")).status_code == 401


# --- Uebersicht und Einstellungen -------------------------------------------------


async def test_uebersicht_nennt_alle_spiele(client: AsyncClient) -> None:
    antwort = await client.get("/kinderzimmer/")

    assert antwort.status_code == 200
    daten = antwort.json()
    assert len(daten["spiele"]) == 12
    assert [s["id"] for s in daten["spiele"] if s["aktiv"]] == ["licht-und-klang", "stimmen"]
    assert len(daten["phasen"]) == 4
    assert len(daten["stand"]) == 16
    assert daten["zahlen"] == {"figuren": 0, "aufnahmen": 0, "geraete": 0}


async def test_einstellungen_haben_voreinstellungen_und_lassen_sich_aendern(
    client: AsyncClient,
) -> None:
    vorher = (await client.get("/kinderzimmer/einstellungen")).json()
    assert vorher["lautstaerke_max"] == 40

    klang = (await hochladen(client, "Glocke", "klang")).json()
    neu = {
        **vorher,
        "lautstaerke_max": 30,
        "knoepfe": [{"nummer": 1, "farbe": "#00aaff", "klang": klang["id"]}],
    }
    antwort = await client.put("/kinderzimmer/einstellungen", json=neu)

    assert antwort.status_code == 200, antwort.text
    gelesen = (await client.get("/kinderzimmer/einstellungen")).json()
    assert gelesen["lautstaerke_max"] == 30
    assert gelesen["knoepfe"][0] == {"nummer": 1, "farbe": "#00AAFF", "klang": klang["id"]}


async def test_geplantes_spiel_laesst_sich_nicht_einschalten(client: AsyncClient) -> None:
    werte = (await client.get("/kinderzimmer/einstellungen")).json()
    werte["spiele_aktiv"] = ["licht-und-klang", "farben"]

    antwort = await client.put("/kinderzimmer/einstellungen", json=werte)

    assert antwort.status_code == 422
    assert "Finde etwas Rotes" in antwort.json()["detail"]


async def test_knopf_mit_unbekannter_aufnahme_wird_abgelehnt(client: AsyncClient) -> None:
    werte = (await client.get("/kinderzimmer/einstellungen")).json()
    werte["knoepfe"] = [
        {"nummer": 1, "farbe": "#FFB000", "klang": "00000000-0000-0000-0000-000000000000"}
    ]

    antwort = await client.put("/kinderzimmer/einstellungen", json=werte)

    assert antwort.status_code == 422


# --- Aufnahmen -----------------------------------------------------------------


async def test_aufnahme_hochladen_anhoeren_umbenennen(client: AsyncClient) -> None:
    daten = wav(2.0)
    angelegt = await hochladen(client, daten=daten)

    assert angelegt.status_code == 201, angelegt.text
    eintrag = angelegt.json()
    assert eintrag["dauer_ms"] == 2000
    assert eintrag["bytes"] == len(daten)

    datei = await client.get(f"/kinderzimmer/aufnahmen/{eintrag['id']}/datei")
    assert datei.status_code == 200
    assert datei.headers["content-type"] == "audio/wav"
    assert datei.content == daten

    umbenannt = await client.put(
        f"/kinderzimmer/aufnahmen/{eintrag['id']}", json={"titel": "  Oma  ", "art": "stimme"}
    )
    assert umbenannt.json()["titel"] == "Oma"


async def test_falsches_format_wird_mit_grund_abgelehnt(client: AsyncClient) -> None:
    antwort = await hochladen(client, daten=wav(rate=44100))

    assert antwort.status_code == 422
    assert "22050" in antwort.json()["detail"]


async def test_doppelter_titel_wird_abgelehnt(client: AsyncClient) -> None:
    await hochladen(client, "Oma")

    antwort = await hochladen(client, "Oma")

    assert antwort.status_code == 409
    assert "Namen" in antwort.json()["detail"]


async def test_benutzte_aufnahme_bleibt(client: AsyncClient) -> None:
    aufnahme = (await hochladen(client)).json()
    await client.post(
        "/kinderzimmer/figuren", json={"uid": UID, "name": "Oma", "stimme": aufnahme["id"]}
    )

    antwort = await client.delete(f"/kinderzimmer/aufnahmen/{aufnahme['id']}")

    assert antwort.status_code == 409
    assert "Figur „Oma“" in antwort.json()["detail"]


async def test_unbenutzte_aufnahme_geht(client: AsyncClient) -> None:
    aufnahme = (await hochladen(client)).json()

    assert (await client.delete(f"/kinderzimmer/aufnahmen/{aufnahme['id']}")).status_code == 204
    assert (await client.get(f"/kinderzimmer/aufnahmen/{aufnahme['id']}/datei")).status_code == 404


# --- Figuren -------------------------------------------------------------------


async def test_figur_anlegen_aendern_loeschen(client: AsyncClient) -> None:
    angelegt = await client.post(
        "/kinderzimmer/figuren",
        json={"uid": "04:a1:b2:c3:d4:e5:f6", "name": "Kuh", "art": "tier", "farbe": "rot"},
    )
    assert angelegt.status_code == 201, angelegt.text
    figur = angelegt.json()
    assert figur["uid"] == UID

    geaendert = await client.put(
        f"/kinderzimmer/figuren/{figur['id']}",
        json={"uid": UID, "name": "Rote Kuh", "art": "tier", "farbe": "rot"},
    )
    assert geaendert.json()["name"] == "Rote Kuh"

    assert (await client.delete(f"/kinderzimmer/figuren/{figur['id']}")).status_code == 204
    assert (await client.get("/kinderzimmer/figuren")).json() == []


async def test_doppelte_uid_wird_beim_namen_genannt(client: AsyncClient) -> None:
    await client.post("/kinderzimmer/figuren", json={"uid": UID, "name": "Kuh"})

    antwort = await client.post("/kinderzimmer/figuren", json={"uid": UID, "name": "Schaf"})

    assert antwort.status_code == 409
    assert "UID" in antwort.json()["detail"]


async def test_falsche_uid_nennt_das_problem(client: AsyncClient) -> None:
    antwort = await client.post("/kinderzimmer/figuren", json={"uid": "123", "name": "Kuh"})

    assert antwort.status_code == 422


async def test_unbekannte_figur_ergibt_404(client: AsyncClient) -> None:
    antwort = await client.delete("/kinderzimmer/figuren/00000000-0000-0000-0000-000000000000")

    assert antwort.status_code == 404


# --- Geraet --------------------------------------------------------------------


async def test_geraet_holt_manifest_und_dateien(client: AsyncClient) -> None:
    aufnahme = (await hochladen(client)).json()
    await hochladen(client, "Unbenutzt")
    await client.post(
        "/kinderzimmer/figuren", json={"uid": UID, "name": "Oma", "stimme": aufnahme["id"]}
    )
    token = (await geraet(client))["token"]

    manifest = await client.get("/kinderzimmer/geraet/stand", headers=bearer(token))

    assert manifest.status_code == 200, manifest.text
    daten = manifest.json()
    assert daten["format"] == 1
    assert daten["figuren"][0]["stimme"] == aufnahme["id"]
    assert [d["id"] for d in daten["dateien"]] == [aufnahme["id"]]
    assert daten["stand"] == (await client.get("/kinderzimmer/")).json()["stand"]

    datei = await client.get(
        f"/kinderzimmer/geraet/dateien/{aufnahme['id']}", headers=bearer(token)
    )
    assert datei.status_code == 200
    assert datei.headers["etag"] == f'"{aufnahme["sha256"]}"'


async def test_falsches_token_kommt_nicht_hinein(client: AsyncClient) -> None:
    await geraet(client)

    antwort = await client.get("/kinderzimmer/geraet/stand", headers=bearer("geraten"))

    assert antwort.status_code == 401
    assert "Gerätetoken" in antwort.json()["detail"]


async def test_ereignisse_kommen_an_und_doppeltes_geht_unter(client: AsyncClient) -> None:
    await client.post("/kinderzimmer/figuren", json={"uid": UID, "name": "Oma"})
    token = (await geraet(client))["token"]
    sendung = {
        "start": 3,
        "jetzt_ms": 10000,
        "firmware": "0.1.0",
        "stand": "alt",
        "ereignisse": [
            {"nr": 1, "ms": 1000, "art": "start"},
            {"nr": 2, "ms": 4000, "art": "knopf", "knopf": 1},
            {"nr": 3, "ms": 5000, "art": "figur_auf", "uid": "04:a1:b2:c3:d4:e5:f6"},
            {"nr": 4, "ms": 6000, "art": "figur_auf", "uid": "04FFFFFF"},
        ],
    }

    erste = await client.post(
        "/kinderzimmer/geraet/ereignisse", json=sendung, headers=bearer(token)
    )
    zweite = await client.post(
        "/kinderzimmer/geraet/ereignisse", json=sendung, headers=bearer(token)
    )

    assert erste.status_code == 200, erste.text
    assert erste.json()["neu"] == 4
    assert zweite.json() == {"neu": 0, "doppelt": 4, "stand": erste.json()["stand"]}

    texte = [e["text"] for e in (await client.get("/kinderzimmer/protokoll")).json()]
    assert "„Oma“ aufgelegt" in texte
    assert "Knopf 1 gedrückt" in texte
    assert "Unbekannte Figur 04FFFFFF aufgelegt" in texte

    unbekannt = (await client.get("/kinderzimmer/figuren/unbekannt")).json()
    assert [u["uid"] for u in unbekannt] == ["04FFFFFF"]

    eintrag = (await client.get("/kinderzimmer/geraete")).json()[0]
    assert eintrag["firmware"] == "0.1.0"
    assert eintrag["stand_aktuell"] is False
    assert eintrag["zuletzt_gesehen"] is not None


async def test_neues_token_sperrt_das_alte_aus(client: AsyncClient) -> None:
    angelegt = await geraet(client)

    neu = await client.post(f"/kinderzimmer/geraete/{angelegt['id']}/token")

    assert neu.status_code == 200
    alt = await client.get("/kinderzimmer/geraet/stand", headers=bearer(angelegt["token"]))
    assert alt.status_code == 401
    jetzt = await client.get("/kinderzimmer/geraet/stand", headers=bearer(neu.json()["token"]))
    assert jetzt.status_code == 200


async def test_geraet_entfernen(client: AsyncClient) -> None:
    angelegt = await geraet(client)

    assert (await client.delete(f"/kinderzimmer/geraete/{angelegt['id']}")).status_code == 204
    assert (await client.get("/kinderzimmer/geraete")).json() == []
    weg = await client.delete(f"/kinderzimmer/geraete/{angelegt['id']}")
    assert weg.status_code == 404


async def test_doppelter_geraetename(client: AsyncClient) -> None:
    await geraet(client)

    antwort = await client.post("/kinderzimmer/geraete", json={"name": "Spielkiste"})

    assert antwort.status_code == 409


# --- Tagebuch ------------------------------------------------------------------


async def test_tagebuch(client: AsyncClient) -> None:
    angelegt = await client.post(
        "/kinderzimmer/tagebuch",
        json={"datum": "2026-11-20", "text": "  Hat zum ersten Mal den Knopf selbst gedrückt. "},
    )
    assert angelegt.status_code == 201
    assert angelegt.json()["text"] == "Hat zum ersten Mal den Knopf selbst gedrückt."

    liste = (await client.get("/kinderzimmer/tagebuch")).json()
    assert len(liste) == 1

    entfernt = await client.delete(f"/kinderzimmer/tagebuch/{liste[0]['id']}")
    assert entfernt.status_code == 204
    weg = await client.delete(f"/kinderzimmer/tagebuch/{liste[0]['id']}")
    assert weg.status_code == 404


async def test_leerer_tagebucheintrag_wird_abgelehnt(client: AsyncClient) -> None:
    antwort = await client.post(
        "/kinderzimmer/tagebuch", json={"datum": "2026-11-20", "text": "  "}
    )

    assert antwort.status_code == 422
