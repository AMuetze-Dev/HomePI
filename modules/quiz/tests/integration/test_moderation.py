"""Jeder startet und leitet eine Runde - ohne Konto, mit Moderatorcode."""

from __future__ import annotations

import datetime as dt
import io
import json
import zipfile
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select, update

from homepi_quiz.modelle import Katalog, Moderation, Runde

pytestmark = pytest.mark.integration

Spielerfabrik = Callable[[], AbstractAsyncContextManager[AsyncClient]]

FREITEXT = {
    "text": "Hauptstadt?",
    "punkte": 2,
    "daten": {"typ": "freitext", "loesungen": ["Paris"]},
}


async def _katalog(client: AsyncClient, frei: bool = True) -> str:
    katalog_id: str = (await client.post("/quiz/kataloge", json={"titel": "Abend"})).json()["id"]
    await client.post(f"/quiz/kataloge/{katalog_id}/fragen", json=FREITEXT)
    if frei:
        antwort = await client.put(f"/quiz/kataloge/{katalog_id}/freigabe", json={"frei": True})
        assert antwort.status_code == 200, antwort.text
        assert antwort.json()["freigegeben"] is True
    return katalog_id


def _quiz_zip() -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as paket:
        paket.writestr(
            "quiz.json",
            json.dumps(
                {
                    "title": "Mein Quiz",
                    "questions": [
                        {"type": "text", "question": "Wer?", "correctAnswerText": "Ich"},
                        {"type": "tanzen", "question": "?"},
                    ],
                }
            ),
        )
    return puffer.getvalue()


async def test_ohne_konto_sieht_man_nur_freigegebene_kataloge_ohne_fragen(
    client: AsyncClient, besucher: AsyncClient
) -> None:
    frei = await _katalog(client)
    await _katalog(client, frei=False)

    liste = (await besucher.get("/quiz/kataloge/frei")).json()
    assert [k["id"] for k in liste] == [frei]
    assert set(liste[0]) == {"id", "titel", "beschreibung", "anzahl_fragen"}
    assert "Paris" not in json.dumps(liste)


async def test_freigeben_nur_mit_recht(client: AsyncClient, leser: AsyncClient) -> None:
    katalog_id = await _katalog(client, frei=False)
    assert (
        await leser.put(f"/quiz/kataloge/{katalog_id}/freigabe", json={"frei": True})
    ).status_code == 403
    zurueck = await client.put(f"/quiz/kataloge/{katalog_id}/freigabe", json={"frei": False})
    assert zurueck.json()["freigegeben"] is False


async def test_ohne_konto_starten_und_leiten(client: AsyncClient, spieler: Spielerfabrik) -> None:
    katalog_id = await _katalog(client)
    async with spieler() as moderator, spieler() as fremd, spieler() as anna:
        gestartet = await moderator.post("/quiz/starten", json={"katalog_id": katalog_id})
        assert gestartet.status_code == 201, gestartet.text
        ergebnis = gestartet.json()
        rid, code = ergebnis["runde"]["id"], ergebnis["moderatorcode"]
        assert len(code) == 19

        # Mit dem Cookie aus dem Start: leiten
        stand = await moderator.get(f"/quiz/leitung/{rid}")
        assert stand.status_code == 200
        assert stand.json()["fragen"][0]["daten"]["loesungen"] == ["Paris"]

        # Ein anderes Geraet ohne Code: nichts
        assert (await fremd.get(f"/quiz/leitung/{rid}")).status_code == 401
        assert (await fremd.post(f"/quiz/leitung/{rid}/beenden")).status_code == 401

        # Und mit Code auf einem zweiten Geraet: Wiedereinstieg
        falsch = await fremd.post("/quiz/leitung/zugang", json={"code": "AAAA-AAAA-AAAA-AAAA"})
        assert falsch.status_code == 401
        richtig = await fremd.post("/quiz/leitung/zugang", json={"code": code.lower()})
        assert richtig.status_code == 200
        assert richtig.json()["id"] == rid
        assert (await fremd.get(f"/quiz/leitung/{rid}")).status_code == 200

        # Spieler kommen wie immer herein, die Leitung steuert
        await anna.post(
            f"/quiz/runden/{ergebnis['runde']['code']}/beitreten", json={"name": "Anna"}
        )
        frage = stand.json()["fragen"][0]["id"]
        assert (
            await moderator.post(f"/quiz/leitung/{rid}/frage", json={"frage_id": frage})
        ).status_code == 200
        assert (await moderator.post(f"/quiz/leitung/{rid}/zeigen", json={})).status_code == 200


async def test_der_code_einer_runde_leitet_keine_andere(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    katalog_id = await _katalog(client)
    async with spieler() as a, spieler() as b:
        runde_a = (await a.post("/quiz/starten", json={"katalog_id": katalog_id})).json()
        runde_b = (await b.post("/quiz/starten", json={"katalog_id": katalog_id})).json()
        assert (await a.get(f"/quiz/leitung/{runde_b['runde']['id']}")).status_code == 401
        assert (await a.get(f"/quiz/leitung/{runde_a['runde']['id']}")).status_code == 200


async def test_nicht_freigegebener_katalog_nur_mit_recht(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    katalog_id = await _katalog(client, frei=False)
    async with spieler() as fremd:
        abgelehnt = await fremd.post("/quiz/starten", json={"katalog_id": katalog_id})
        assert abgelehnt.status_code == 403
    erlaubt = await client.post("/quiz/starten", json={"katalog_id": katalog_id})
    assert erlaubt.status_code == 201


async def test_eigenes_quiz_ohne_konto(
    client: AsyncClient, spieler: Spielerfabrik, anwendung: FastAPI
) -> None:
    async with spieler() as moderator:
        antwort = await moderator.post("/quiz/starten/eigenes", content=_quiz_zip())
        assert antwort.status_code == 201, antwort.text
        ergebnis = antwort.json()
        assert ergebnis["runde"]["katalog_titel"] == "Mein Quiz"
        assert any("tanzen" in h for h in ergebnis["hinweise"])
        rid = ergebnis["runde"]["id"]
        assert (await moderator.get(f"/quiz/leitung/{rid}")).status_code == 200

    # Der eigene Katalog ist weder frei noch in der Liste der anderen.
    assert all(k["titel"] != "Mein Quiz" for k in (await client.get("/quiz/kataloge/frei")).json())


async def test_eigenes_quiz_kaputt(spieler: Spielerfabrik) -> None:
    async with spieler() as moderator:
        antwort = await moderator.post("/quiz/starten/eigenes", content=b"kaputt")
    assert antwort.status_code == 422


async def test_eigenes_quiz_zu_gross(
    spieler: Spielerfabrik, monkeypatch: pytest.MonkeyPatch
) -> None:
    from homepi_quiz import dienst

    monkeypatch.setattr(dienst, "MAX_EIGENES_PAKET", 10)
    async with spieler() as moderator:
        antwort = await moderator.post("/quiz/starten/eigenes", content=_quiz_zip())
    assert antwort.status_code == 413


async def test_zu_viele_runden_ohne_konto(
    client: AsyncClient, spieler: Spielerfabrik, monkeypatch: pytest.MonkeyPatch
) -> None:
    from homepi_quiz import dienst

    monkeypatch.setattr(dienst, "MAX_RUNDEN_OHNE_KONTO", 1)
    katalog_id = await _katalog(client)
    async with spieler() as a:
        assert (await a.post("/quiz/starten", json={"katalog_id": katalog_id})).status_code == 201
        assert (await a.post("/quiz/starten", json={"katalog_id": katalog_id})).status_code == 429


async def test_moderatorcode_neu_ausstellen(client: AsyncClient, spieler: Spielerfabrik) -> None:
    katalog_id = await _katalog(client)
    async with spieler() as moderator, spieler() as zweites:
        ergebnis = (await moderator.post("/quiz/starten", json={"katalog_id": katalog_id})).json()
        rid, alt = ergebnis["runde"]["id"], ergebnis["moderatorcode"]
        neu = (await moderator.post(f"/quiz/leitung/{rid}/moderatorcode")).json()["moderatorcode"]
        assert neu != alt
        assert (await zweites.post("/quiz/leitung/zugang", json={"code": alt})).status_code == 401
        assert (await zweites.post("/quiz/leitung/zugang", json={"code": neu})).status_code == 200


async def test_ruhende_runden_ohne_konto_werden_aufgeraeumt(
    client: AsyncClient, spieler: Spielerfabrik, anwendung: FastAPI
) -> None:
    katalog_id = await _katalog(client)
    async with spieler() as moderator:
        alt = (await moderator.post("/quiz/starten/eigenes", content=_quiz_zip())).json()
        mit_konto = (await client.post("/quiz/starten", json={"katalog_id": katalog_id})).json()

    async with anwendung.state.homepi.db.session() as sitzung:
        await sitzung.execute(
            update(Moderation).values(
                zuletzt_aktiv=dt.datetime.now(dt.UTC) - dt.timedelta(hours=49)
            )
        )

    # Aufgeraeumt wird beim naechsten Blick auf die Kachel.
    await client.get("/quiz/")

    async with anwendung.state.homepi.db.session() as sitzung:
        runden = {r.id for r in await sitzung.scalars(select(Runde))}
        kataloge = {k.titel for k in await sitzung.scalars(select(Katalog))}
    assert alt["runde"]["id"] not in {str(r) for r in runden}
    assert mit_konto["runde"]["id"] in {str(r) for r in runden}, "mit Konto bleibt"
    assert "Mein Quiz" not in kataloge, "der eigene Katalog geht mit"
    assert "Abend" in kataloge


async def test_leitung_holt_ton_und_bild_der_aktuellen_frage(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    katalog_id = await _katalog(client)
    frage = (await client.get(f"/quiz/kataloge/{katalog_id}")).json()["fragen"][0]["id"]
    await client.put(
        f"/quiz/fragen/{frage}/medien/ton",
        content=b"ID3" + b"\x00" * 20,
        headers={"content-type": "audio/mpeg"},
    )
    async with spieler() as moderator:
        rid = (await moderator.post("/quiz/starten", json={"katalog_id": katalog_id})).json()[
            "runde"
        ]["id"]
        assert (await moderator.get(f"/quiz/leitung/{rid}/medien/ton")).status_code == 404
        await moderator.post(f"/quiz/leitung/{rid}/frage", json={"frage_id": frage})
        ton = await moderator.get(f"/quiz/leitung/{rid}/medien/ton")
        assert ton.status_code == 200 and ton.headers["content-type"] == "audio/mpeg"
