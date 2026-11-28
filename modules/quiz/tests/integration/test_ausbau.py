"""Import/Export, Medien, neue Fragetypen, Teams, Beitrittssperre, Auswertung."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

Spielerfabrik = Callable[[], AbstractAsyncContextManager[AsyncClient]]

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MP3 = b"ID3\x03" + b"\x00" * 64


def _frage(daten: dict[str, Any], **mehr: Any) -> dict[str, Any]:
    return {"text": "Frage?", "punkte": 2, **mehr, "daten": daten}


FREITEXT = _frage({"typ": "freitext", "loesungen": ["Berlin"]})
BUZZER = _frage({"typ": "buzzer", "loesung": "Zugspitze"}, punkte=3)
ZUORDNEN = _frage(
    {"typ": "zuordnen", "paare": [{"links": "A", "rechts": "1"}, {"links": "B", "rechts": "2"}]}
)
BILDAUSWAHL = _frage(
    {"typ": "bildauswahl", "optionen": [{"text": "Karte A", "richtig": True}, {"text": "B"}]}
)


async def _katalog(client: AsyncClient, *fragen: dict[str, Any]) -> tuple[str, list[str]]:
    katalog_id: str = (await client.post("/quiz/kataloge", json={"titel": "Abend"})).json()["id"]
    ids = []
    for frage in fragen:
        antwort = await client.post(f"/quiz/kataloge/{katalog_id}/fragen", json=frage)
        assert antwort.status_code == 201, antwort.text
        ids.append(antwort.json()["id"])
    return katalog_id, ids


async def _runde(client: AsyncClient, katalog_id: str) -> dict[str, Any]:
    antwort = await client.post("/quiz/leitung", json={"katalog_id": katalog_id})
    assert antwort.status_code == 201, antwort.text
    return dict(antwort.json())


async def _steuern(client: AsyncClient, rid: str, aktion: str, **daten: Any) -> dict[str, Any]:
    antwort = await client.post(f"/quiz/leitung/{rid}/{aktion}", json=daten or None)
    assert antwort.status_code == 200, antwort.text
    return dict(antwort.json())


async def _oeffnen(client: AsyncClient, rid: str, frage_id: str) -> dict[str, Any]:
    await _steuern(client, rid, "frage", frage_id=frage_id)
    return await _steuern(client, rid, "zeigen", timer=False)


async def _beitreten(handy: AsyncClient, code: str, name: str, **mehr: Any) -> Any:
    return await handy.post(f"/quiz/runden/{code}/beitreten", json={"name": name, **mehr})


def _battlenet_zip() -> bytes:
    bild = "data:image/png;base64," + base64.b64encode(PNG).decode()
    quiz = {
        "title": "Allgemeinwissen",
        "questions": [
            {"type": "text", "question": "Hauptstadt?", "correctAnswerText": "Paris", "points": 2},
            {
                "type": "image-choice",
                "question": "Welche Karte?",
                "imageOptions": [
                    {"alt": "A", "correct": True, "imageData": bild},
                    {"alt": "B", "correct": False, "imageData": bild},
                ],
            },
            {"type": "tanzen", "question": "?"},
        ],
    }
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as paket:
        paket.writestr("quiz.json", json.dumps(quiz))
    return puffer.getvalue()


# ------------------------------------------------------------- Import / Export


async def test_battlenet_quiz_importieren(client: AsyncClient) -> None:
    antwort = await client.post(
        "/quiz/kataloge/import",
        content=_battlenet_zip(),
        headers={"content-type": "application/zip"},
    )
    assert antwort.status_code == 201, antwort.text
    ergebnis = antwort.json()
    assert ergebnis["katalog"]["titel"] == "Allgemeinwissen"
    assert [f["daten"]["typ"] for f in ergebnis["katalog"]["fragen"]] == ["freitext", "bildauswahl"]
    assert ergebnis["katalog"]["fragen"][1]["medien"] == ["option-0", "option-1"]
    assert any("tanzen" in h for h in ergebnis["hinweise"])


async def test_export_und_wieder_import_ohne_verlust(client: AsyncClient) -> None:
    katalog_id, ids = await _katalog(client, FREITEXT, BILDAUSWAHL)
    await client.put(
        f"/quiz/fragen/{ids[0]}/bild", content=PNG, headers={"content-type": "image/png"}
    )
    await client.put(
        f"/quiz/fragen/{ids[0]}/medien/ton", content=MP3, headers={"content-type": "audio/mpeg"}
    )

    paket = await client.get(f"/quiz/kataloge/{katalog_id}/export")
    assert paket.status_code == 200
    assert paket.headers["content-type"] == "application/zip"
    assert "attachment" in paket.headers["content-disposition"]

    wieder = await client.post("/quiz/kataloge/import", content=paket.content)
    fragen = wieder.json()["katalog"]["fragen"]
    assert [f["text"] for f in fragen] == ["Frage?", "Frage?"]
    assert fragen[0]["hat_bild"] and fragen[0]["medien"] == ["ton"]
    assert wieder.json()["hinweise"] == []


async def test_import_kaputter_datei(client: AsyncClient) -> None:
    antwort = await client.post("/quiz/kataloge/import", content=b"kaputt")
    assert antwort.status_code == 422
    assert "ZIP" in antwort.json()["detail"]


async def test_import_und_export_nur_mit_recht(
    client: AsyncClient, leser: AsyncClient, besucher: AsyncClient
) -> None:
    katalog_id, _ = await _katalog(client, FREITEXT)
    assert (await leser.post("/quiz/kataloge/import", content=_battlenet_zip())).status_code == 403
    assert (await leser.get(f"/quiz/kataloge/{katalog_id}/export")).status_code == 200
    assert (await besucher.get(f"/quiz/kataloge/{katalog_id}/export")).status_code == 401


# ------------------------------------------------------------- Medien


async def test_medien_einer_frage(client: AsyncClient) -> None:
    _, ids = await _katalog(client, BILDAUSWAHL)
    frage = ids[0]

    hoch = await client.put(
        f"/quiz/fragen/{frage}/medien/option-1", content=PNG, headers={"content-type": "image/png"}
    )
    assert hoch.status_code == 200 and hoch.json()["medien"] == ["option-1"]
    assert (await client.get(f"/quiz/fragen/{frage}/medien/option-1")).content == PNG

    falsch = await client.put(
        f"/quiz/fragen/{frage}/medien/option-5", content=PNG, headers={"content-type": "image/png"}
    )
    assert falsch.status_code == 422
    ton_als_bild = await client.put(
        f"/quiz/fragen/{frage}/medien/ton", content=PNG, headers={"content-type": "image/png"}
    )
    assert ton_als_bild.status_code == 422

    assert (await client.delete(f"/quiz/fragen/{frage}/medien/option-1")).status_code == 204
    assert (await client.get(f"/quiz/fragen/{frage}/medien/option-1")).status_code == 404


async def test_bildauswahl_braucht_alle_bilder_und_zeigt_sie_erst_mit_der_frage(
    client: AsyncClient, besucher: AsyncClient
) -> None:
    katalog_id, ids = await _katalog(client, BILDAUSWAHL)
    runde = await _runde(client, katalog_id)
    await _steuern(client, runde["id"], "frage", frage_id=ids[0])

    fehlt = await client.post(f"/quiz/leitung/{runde['id']}/zeigen", json={})
    assert fehlt.status_code == 409
    assert "Bild" in fehlt.json()["detail"]

    for i in (0, 1):
        await client.put(
            f"/quiz/fragen/{ids[0]}/medien/option-{i}",
            content=PNG,
            headers={"content-type": "image/png"},
        )
    medium = f"/quiz/runden/{runde['code']}/medien/option-0"
    assert (await besucher.get(medium)).status_code == 404, "vor dem Zeigen verborgen"
    await _steuern(client, runde["id"], "zeigen", timer=False)
    assert (await besucher.get(medium)).content == PNG
    assert (await besucher.get(f"/quiz/runden/{runde['code']}/medien/ton")).status_code == 404


async def test_zuordnen_ueber_die_oeffentliche_schnittstelle(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    katalog_id, ids = await _katalog(client, ZUORDNEN)
    runde = await _runde(client, katalog_id)
    async with spieler() as anna:
        await _beitreten(anna, runde["code"], "Anna")
        await _oeffnen(client, runde["id"], ids[0])
        frage = (await anna.get(f"/quiz/runden/{runde['code']}")).json()["frage"]
        assert frage["links"] == ["A", "B"]
        rechts = {e["text"]: e["kennung"] for e in frage["rechts"]}
        antwort = await anna.put(
            f"/quiz/runden/{runde['code']}/antwort",
            json={"zuordnung": {"0": rechts["1"], "1": rechts["2"]}, "eingeloggt": True},
        )
        assert antwort.status_code == 200, antwort.text
        await _steuern(client, runde["id"], "aufloesen")
        assert (await anna.get(f"/quiz/runden/{runde['code']}")).json()["ich"]["punkte"] == 2


# ------------------------------------------------------------- Teams


async def test_teams_vom_anlegen_bis_zur_rangliste(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    katalog_id, ids = await _katalog(client, FREITEXT)
    runde = await _runde(client, katalog_id)
    rot = (await client.post(f"/quiz/leitung/{runde['id']}/teams", json={"name": "Rot"})).json()
    blau = (await client.post(f"/quiz/leitung/{runde['id']}/teams", json={"name": "Blau"})).json()
    doppelt = await client.post(f"/quiz/leitung/{runde['id']}/teams", json={"name": "rot"})
    assert doppelt.status_code == 409

    rot_id = next(t["id"] for t in rot["teams"] if t["name"] == "Rot")
    blau_id = next(t["id"] for t in blau["teams"] if t["name"] == "Blau")

    async with spieler() as anna, spieler() as ben:
        ohne = await _beitreten(anna, runde["code"], "Anna")
        assert ohne.status_code == 422
        assert "Team" in ohne.json()["detail"]

        stand = (await _beitreten(anna, runde["code"], "Anna", team_id=rot_id)).json()
        assert stand["ich"]["team"] == "Rot"
        await _beitreten(ben, runde["code"], "Ben", team_id=rot_id)

        wechsel = await ben.put(f"/quiz/runden/{runde['code']}/team", json={"team_id": blau_id})
        assert wechsel.status_code == 200
        assert wechsel.json()["ich"]["team"] == "Blau"

        await _oeffnen(client, runde["id"], ids[0])
        await anna.put(f"/quiz/runden/{runde['code']}/antwort", json={"text": "Berlin"})
        await _steuern(client, runde["id"], "aufloesen")

        spaeter = await ben.put(f"/quiz/runden/{runde['code']}/team", json={"team_id": rot_id})
        assert spaeter.status_code == 409

        tafel = (await ben.get(f"/quiz/runden/{runde['code']}")).json()
        assert [(t["name"], t["punkte"], t["mitglieder"]) for t in tafel["teams"]] == [
            ("Rot", 2, 1),
            ("Blau", 0, 1),
        ]
        assert {p["name"]: p["team"] for p in tafel["rangliste"]} == {"Anna": "Rot", "Ben": "Blau"}

        # Die Leitung darf auch waehrend der Runde umsetzen.
        ben_id = next(
            s["id"]
            for s in stand_spieler(await client.get(f"/quiz/leitung/{runde['id']}"))
            if s["name"] == "Ben"
        )
        umgesetzt = await client.put(
            f"/quiz/leitung/{runde['id']}/spieler/{ben_id}/team", json={"team_id": rot_id}
        )
        assert umgesetzt.status_code == 200
        assert next(t for t in umgesetzt.json()["teams"] if t["name"] == "Rot")["mitglieder"] == 2

        weg = await client.delete(f"/quiz/leitung/{runde['id']}/teams/{blau_id}")
        assert weg.status_code == 200
        assert [t["name"] for t in weg.json()["teams"]] == ["Rot"]


def stand_spieler(antwort: Any) -> list[dict[str, Any]]:
    return list(antwort.json()["spieler"])


async def test_ein_buzzer_je_team(client: AsyncClient, spieler: Spielerfabrik) -> None:
    katalog_id, ids = await _katalog(client, BUZZER)
    runde = await _runde(client, katalog_id)
    team = (await client.post(f"/quiz/leitung/{runde['id']}/teams", json={"name": "Rot"})).json()
    team_id = team["teams"][0]["id"]
    async with spieler() as anna, spieler() as ben:
        await _beitreten(anna, runde["code"], "Anna", team_id=team_id)
        await _beitreten(ben, runde["code"], "Ben", team_id=team_id)
        await _oeffnen(client, runde["id"], ids[0])
        assert (await anna.post(f"/quiz/runden/{runde['code']}/buzzer")).status_code == 200
        zweiter = await ben.post(f"/quiz/runden/{runde['code']}/buzzer")
        assert zweiter.status_code == 409
        assert "Team" in zweiter.json()["detail"]


# ------------------------------------------------------------- Beitritt schliessen


async def test_geschlossene_runde_nimmt_nur_rueckkehrer(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    katalog_id, _ = await _katalog(client, FREITEXT)
    runde = await _runde(client, katalog_id)
    async with spieler() as anna, spieler() as neu, spieler() as zurueck:
        await _beitreten(anna, runde["code"], "Anna")
        stand = await _steuern(client, runde["id"], "beitritt", offen=False)
        assert stand["runde"]["beitritt_offen"] is False
        assert (await neu.get(f"/quiz/runden/{runde['code']}")).json()["beitritt_offen"] is False

        abgewiesen = await _beitreten(neu, runde["code"], "Ben")
        assert abgewiesen.status_code == 409
        assert "geschlossen" in abgewiesen.json()["detail"]

        anna_id = stand["spieler"][0]["id"]
        code = (
            await client.post(f"/quiz/leitung/{runde['id']}/spieler/{anna_id}/wiederkehr")
        ).json()["code"]
        wieder = await _beitreten(zurueck, runde["code"], "Anna", wiederkehrcode=code)
        assert wieder.status_code == 200


# ------------------------------------------------------------- Auswertung


async def test_auswertung_und_csv(client: AsyncClient, spieler: Spielerfabrik) -> None:
    katalog_id, ids = await _katalog(client, FREITEXT, BUZZER)
    runde = await _runde(client, katalog_id)
    async with spieler() as anna, spieler() as boese:
        await _beitreten(anna, runde["code"], "Anna")
        await _beitreten(boese, runde["code"], "=HYPERLINK(1)")
        await _oeffnen(client, runde["id"], ids[0])
        await anna.put(f"/quiz/runden/{runde['code']}/antwort", json={"text": "Berlin"})
        await boese.put(f"/quiz/runden/{runde['code']}/antwort", json={"text": "Bonn"})
        await _steuern(client, runde["id"], "aufloesen")
        await _oeffnen(client, runde["id"], ids[1])
        await anna.post(f"/quiz/runden/{runde['code']}/buzzer")
        await _steuern(client, runde["id"], "buzzer", richtig=True)

    auswertung = (await client.get(f"/quiz/leitung/{runde['id']}/auswertung")).json()
    assert [(f["nummer"], f["richtig"], f["gesamt"]) for f in auswertung] == [(1, 1, 2), (2, 1, 1)]
    assert auswertung[0]["loesung"] == "Berlin"
    assert {a["spieler"]: a["punkte"] for a in auswertung[1]["antworten"]} == {"Anna": 3}

    csv = await client.get(f"/quiz/leitung/{runde['id']}/ergebnis.csv")
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    zeilen = csv.content.decode("utf-8-sig").splitlines()
    assert zeilen[0].startswith("Platz;Name;Team;Gesamt;1: Frage?;2: Frage?")
    assert zeilen[1] == "1;Anna;;5;2;3"
    assert zeilen[2].startswith("2;'=HYPERLINK(1)")


async def test_auswertung_braucht_ein_konto(client: AsyncClient, besucher: AsyncClient) -> None:
    katalog_id, _ = await _katalog(client, FREITEXT)
    runde = await _runde(client, katalog_id)
    assert (await besucher.get(f"/quiz/leitung/{runde['id']}/auswertung")).status_code == 401
    assert (await besucher.get(f"/quiz/leitung/{runde['id']}/ergebnis.csv")).status_code == 401
