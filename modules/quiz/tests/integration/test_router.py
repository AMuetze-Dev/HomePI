"""Der Router gegen eine echte Datenbank.

Als Integration markiert, weil er fast nur aus Datenbankzugriff besteht.

    HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
        uv run pytest -m 'not smoke'
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select, update

from homepi_quiz.modelle import Runde, Spieler

pytestmark = pytest.mark.integration

#: Je Aufruf ein eigenes Handy - siehe die Fixture `spieler` in der conftest.
Spielerfabrik = Callable[[], AbstractAsyncContextManager[AsyncClient]]

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


# ------------------------------------------------------------- Helfer


async def _katalog(client: AsyncClient, *fragen: dict[str, Any]) -> str:
    antwort = await client.post("/quiz/kataloge", json={"titel": "Kneipenquiz"})
    assert antwort.status_code == 201, antwort.text
    katalog_id: str = antwort.json()["id"]
    for frage in fragen:
        angelegt = await client.post(f"/quiz/kataloge/{katalog_id}/fragen", json=frage)
        assert angelegt.status_code == 201, angelegt.text
    return katalog_id


def _frage(daten: dict[str, Any], **mehr: Any) -> dict[str, Any]:
    return {"text": "Frage?", "punkte": 2, **mehr, "daten": daten}


FREITEXT = _frage({"typ": "freitext", "loesungen": ["Berlin"]}, text="Hauptstadt?")
BUZZER = _frage({"typ": "buzzer", "loesung": "Zugspitze"}, punkte=3)


async def _runde(client: AsyncClient, katalog_id: str) -> dict[str, Any]:
    antwort = await client.post("/quiz/leitung", json={"katalog_id": katalog_id})
    assert antwort.status_code == 201, antwort.text
    return dict(antwort.json())


async def _steuern(client: AsyncClient, runde_id: str, aktion: str, **daten: Any) -> dict[str, Any]:
    antwort = await client.post(f"/quiz/leitung/{runde_id}/{aktion}", json=daten or None)
    assert antwort.status_code == 200, antwort.text
    return dict(antwort.json())


async def _frage_oeffnen(
    client: AsyncClient, runde_id: str, index: int = 0, **zeigen: Any
) -> dict[str, Any]:
    stand = (await client.get(f"/quiz/leitung/{runde_id}")).json()
    await _steuern(client, runde_id, "frage", frage_id=stand["fragen"][index]["id"])
    return await _steuern(client, runde_id, "zeigen", **(zeigen or {"timer": False}))


async def _beitreten(handy: AsyncClient, code: str, name: str) -> dict[str, Any]:
    antwort = await handy.post(f"/quiz/runden/{code}/beitreten", json={"name": name})
    assert antwort.status_code == 200, antwort.text
    return dict(antwort.json())


# ------------------------------------------------------------- Zugriff


async def test_ueberblick_ohne_konto(besucher: AsyncClient) -> None:
    antwort = await besucher.get("/quiz/")
    assert antwort.status_code == 200
    assert antwort.json() == {"laufende_runden": 0}


@pytest.mark.parametrize(
    "methode,pfad",
    [
        ("GET", "/quiz/kataloge"),
        ("POST", "/quiz/kataloge"),
        ("GET", "/quiz/leitung"),
        ("POST", "/quiz/leitung"),
    ],
)
async def test_leitung_braucht_ein_konto(besucher: AsyncClient, methode: str, pfad: str) -> None:
    assert (await besucher.request(methode, pfad, json={})).status_code == 401


async def test_konto_ohne_recht_bekommt_403(fremder: AsyncClient) -> None:
    assert (await fremder.get("/quiz/kataloge")).status_code == 403


async def test_leser_sieht_aber_leitet_nicht(client: AsyncClient, leser: AsyncClient) -> None:
    katalog_id = await _katalog(client, FREITEXT)
    assert (await leser.get(f"/quiz/kataloge/{katalog_id}")).status_code == 200
    assert (await leser.post("/quiz/leitung", json={"katalog_id": katalog_id})).status_code == 403
    assert (await leser.delete(f"/quiz/kataloge/{katalog_id}")).status_code == 403


# ------------------------------------------------------------- Kataloge


async def test_katalog_mit_fragen(client: AsyncClient) -> None:
    katalog_id = await _katalog(client, FREITEXT, BUZZER)

    detail = (await client.get(f"/quiz/kataloge/{katalog_id}")).json()
    assert [f["daten"]["typ"] for f in detail["fragen"]] == ["freitext", "buzzer"]
    assert detail["fragen"][0]["daten"]["loesungen"] == ["Berlin"]
    assert (await client.get("/quiz/kataloge")).json()[0]["anzahl_fragen"] == 2

    umbenannt = await client.put(
        f"/quiz/kataloge/{katalog_id}", json={"titel": "Neu", "beschreibung": "x"}
    )
    assert umbenannt.json()["titel"] == "Neu"


async def test_frage_aendern_umsortieren_loeschen(client: AsyncClient) -> None:
    katalog_id = await _katalog(client, FREITEXT, BUZZER)
    a, b = [f["id"] for f in (await client.get(f"/quiz/kataloge/{katalog_id}")).json()["fragen"]]

    geaendert = await client.put(f"/quiz/fragen/{a}", json=_frage({"typ": "zahl", "loesung": 16}))
    assert geaendert.json()["daten"]["typ"] == "zahl"

    neu = await client.put(f"/quiz/kataloge/{katalog_id}/reihenfolge", json={"fragen": [b, a]})
    assert [f["id"] for f in neu.json()["fragen"]] == [b, a]
    unvollstaendig = await client.put(
        f"/quiz/kataloge/{katalog_id}/reihenfolge", json={"fragen": [b]}
    )
    assert unvollstaendig.status_code == 422

    assert (await client.delete(f"/quiz/fragen/{a}")).status_code == 204
    assert (await client.put(f"/quiz/fragen/{a}", json=FREITEXT)).status_code == 404


async def test_ungueltige_frage_nennt_den_grund(client: AsyncClient) -> None:
    katalog_id = await _katalog(client)
    antwort = await client.post(
        f"/quiz/kataloge/{katalog_id}/fragen",
        json=_frage({"typ": "auswahl", "optionen": [{"text": "a"}, {"text": "b"}]}),
    )
    assert antwort.status_code == 422
    assert "richtig" in antwort.text


async def test_unbekannter_katalog(client: AsyncClient) -> None:
    unbekannt = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/quiz/kataloge/{unbekannt}")).status_code == 404
    assert (await client.post("/quiz/leitung", json={"katalog_id": unbekannt})).status_code == 404


async def test_leerer_katalog_ist_nicht_spielbar(client: AsyncClient) -> None:
    katalog_id = await _katalog(client)
    antwort = await client.post("/quiz/leitung", json={"katalog_id": katalog_id})
    assert antwort.status_code == 409
    assert "keine Fragen" in antwort.json()["detail"]


async def test_katalog_mit_laufender_runde_bleibt(client: AsyncClient) -> None:
    katalog_id = await _katalog(client, FREITEXT)
    runde = await _runde(client, katalog_id)

    assert (await client.delete(f"/quiz/kataloge/{katalog_id}")).status_code == 409
    await _steuern(client, runde["id"], "beenden")
    assert (await client.delete(f"/quiz/kataloge/{katalog_id}")).status_code == 204


# ------------------------------------------------------------- Bilder


async def test_bild_hochladen_und_pruefen(client: AsyncClient) -> None:
    katalog_id = await _katalog(client, _frage({"typ": "hotspot", "ziele": [{"x": 50, "y": 50}]}))
    frage_id = (await client.get(f"/quiz/kataloge/{katalog_id}")).json()["fragen"][0]["id"]

    svg = await client.put(
        f"/quiz/fragen/{frage_id}/bild",
        content=b"<svg/>",
        headers={"content-type": "image/svg+xml"},
    )
    assert svg.status_code == 422

    hoch = await client.put(
        f"/quiz/fragen/{frage_id}/bild", content=PNG, headers={"content-type": "image/png"}
    )
    assert hoch.status_code == 200 and hoch.json()["hat_bild"]
    geholt = await client.get(f"/quiz/fragen/{frage_id}/bild")
    assert geholt.content == PNG and geholt.headers["content-type"] == "image/png"

    assert (await client.delete(f"/quiz/fragen/{frage_id}/bild")).status_code == 204
    assert (await client.get(f"/quiz/fragen/{frage_id}/bild")).status_code == 404


async def test_hotspot_ohne_bild_laesst_sich_nicht_zeigen(client: AsyncClient) -> None:
    katalog_id = await _katalog(client, _frage({"typ": "hotspot", "ziele": [{"x": 50, "y": 50}]}))
    runde = await _runde(client, katalog_id)
    stand = (await client.get(f"/quiz/leitung/{runde['id']}")).json()
    await _steuern(client, runde["id"], "frage", frage_id=stand["fragen"][0]["id"])

    antwort = await client.post(f"/quiz/leitung/{runde['id']}/zeigen", json={})
    assert antwort.status_code == 409
    assert "Bild" in antwort.json()["detail"]


async def test_bild_erreicht_spieler_erst_mit_der_frage(
    client: AsyncClient, besucher: AsyncClient
) -> None:
    katalog_id = await _katalog(client, _frage({"typ": "bild", "loesungen": ["Turm"]}))
    frage_id = (await client.get(f"/quiz/kataloge/{katalog_id}")).json()["fragen"][0]["id"]
    await client.put(
        f"/quiz/fragen/{frage_id}/bild", content=PNG, headers={"content-type": "image/png"}
    )
    runde = await _runde(client, katalog_id)
    await _steuern(client, runde["id"], "frage", frage_id=frage_id)

    assert (await besucher.get(f"/quiz/runden/{runde['code']}/bild")).status_code == 404
    assert (await besucher.get(f"/quiz/fragen/{frage_id}/bild")).status_code == 401

    await _steuern(client, runde["id"], "zeigen", timer=False)
    assert (await besucher.get(f"/quiz/runden/{runde['code']}/bild")).content == PNG

    await _steuern(client, runde["id"], "bild", sichtbar=False)
    assert (await besucher.get(f"/quiz/runden/{runde['code']}/bild")).status_code == 404


# ------------------------------------------------------------- Namen und Token


async def test_beitritt_vergibt_den_namen_einmal(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))

    async with spieler() as anna, spieler() as fremd:
        stand = await _beitreten(anna, runde["code"].lower(), "  Anna ")
        assert stand["ich"]["name"] == "Anna"
        cookie = anna.cookies.get(f"homepi_quiz_{runde['code']}")
        assert cookie and len(cookie) > 40

        for versuch in ("anna", "ANNA", "Anna"):
            antwort = await fremd.post(
                f"/quiz/runden/{runde['code']}/beitreten", json={"name": versuch}
            )
            assert antwort.status_code == 409, versuch
            assert "schon mit" in antwort.json()["detail"]

        # Ein zweiter Druck legt niemanden doppelt an.
        assert (await _beitreten(anna, runde["code"], "Anna 2"))["ich"]["name"] == "Anna"


async def test_das_token_steht_nur_gehasht_in_der_datenbank(
    client: AsyncClient, spieler: Spielerfabrik, anwendung: FastAPI
) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))
    async with spieler() as anna:
        await _beitreten(anna, runde["code"], "Anna")
        token = anna.cookies[f"homepi_quiz_{runde['code']}"]

    async with anwendung.state.homepi.db.session() as sitzung:
        gespeichert = await sitzung.scalar(select(Spieler.token_hash))
    assert gespeichert and token not in gespeichert and len(gespeichert) == 64


async def test_ohne_token_keine_antwort(client: AsyncClient, besucher: AsyncClient) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))
    await _frage_oeffnen(client, runde["id"])

    antwort = await besucher.put(f"/quiz/runden/{runde['code']}/antwort", json={"text": "Berlin"})
    assert antwort.status_code == 401
    assert (await besucher.post(f"/quiz/runden/{runde['code']}/buzzer")).status_code == 401


async def test_ein_fremdes_cookie_einer_anderen_runde_gilt_nicht(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    katalog_id = await _katalog(client, FREITEXT)
    erste, zweite = await _runde(client, katalog_id), await _runde(client, katalog_id)
    await _frage_oeffnen(client, zweite["id"])

    async with spieler() as anna:
        await _beitreten(anna, erste["code"], "Anna")
        token = anna.cookies[f"homepi_quiz_{erste['code']}"]
        anna.cookies.set(f"homepi_quiz_{zweite['code']}", token)
        antwort = await anna.put(f"/quiz/runden/{zweite['code']}/antwort", json={"text": "x"})
    assert antwort.status_code == 401


async def test_unbekannter_code(besucher: AsyncClient) -> None:
    assert (await besucher.get("/quiz/runden/ZZZZZZ")).status_code == 404
    assert (await besucher.get("/quiz/runden/viel-zu-lang")).status_code == 404


async def test_nach_dem_ende_tritt_niemand_mehr_bei(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))
    await _steuern(client, runde["id"], "beenden")
    async with spieler() as spaet:
        antwort = await spaet.post(f"/quiz/runden/{runde['code']}/beitreten", json={"name": "Spät"})
    assert antwort.status_code == 409


async def test_wiederkehr_nach_verlorenem_geraet(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))
    async with spieler() as altes, spieler() as neues, spieler() as dieb:
        await _beitreten(altes, runde["code"], "Anna")
        anna = (await client.get(f"/quiz/leitung/{runde['id']}")).json()["spieler"][0]

        # Ohne Code ist der Name vergeben - auch fuer Anna selbst.
        ohne = await neues.post(f"/quiz/runden/{runde['code']}/beitreten", json={"name": "Anna"})
        assert ohne.status_code == 409

        code = (
            await client.post(f"/quiz/leitung/{runde['id']}/spieler/{anna['id']}/wiederkehr")
        ).json()["code"]

        falsch = await dieb.post(
            f"/quiz/runden/{runde['code']}/beitreten",
            json={"name": "Anna", "wiederkehrcode": "AAAA-AAAA"},
        )
        assert falsch.status_code == 403

        zurueck = await neues.post(
            f"/quiz/runden/{runde['code']}/beitreten",
            json={"name": "anna", "wiederkehrcode": code.lower()},
        )
        assert zurueck.status_code == 200 and zurueck.json()["ich"]["name"] == "Anna"

        # Das alte Geraet ist abgemeldet, der Code verbraucht.
        assert (await altes.get(f"/quiz/runden/{runde['code']}")).json()["ich"] is None
        nochmal = await dieb.post(
            f"/quiz/runden/{runde['code']}/beitreten", json={"name": "Anna", "wiederkehrcode": code}
        )
        assert nochmal.status_code == 403


async def test_spieler_entfernen_gibt_den_namen_frei(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))
    async with spieler() as anna, spieler() as neu:
        await _beitreten(anna, runde["code"], "Anna")
        anna_id = (await client.get(f"/quiz/leitung/{runde['id']}")).json()["spieler"][0]["id"]
        weg = await client.delete(f"/quiz/leitung/{runde['id']}/spieler/{anna_id}")
        assert weg.status_code == 204
        assert (await _beitreten(neu, runde["code"], "Anna"))["ich"]["name"] == "Anna"


# ------------------------------------------------------------- Ablauf


async def test_freitext_runde_von_anfang_bis_ende(
    client: AsyncClient, spieler: Spielerfabrik, besucher: AsyncClient
) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))
    code = runde["code"]

    async with spieler() as anna, spieler() as ben:
        await _beitreten(anna, code, "Anna")
        await _beitreten(ben, code, "Ben")

        stand = await _steuern(
            client,
            runde["id"],
            "frage",
            frage_id=(await client.get(f"/quiz/leitung/{runde['id']}")).json()["fragen"][0]["id"],
        )
        assert stand["phase"] == "bereit"
        vorher = (await besucher.get(f"/quiz/runden/{code}")).json()
        assert vorher["frage"]["text"] is None, "Vor dem Zeigen bleibt die Frage verdeckt"
        assert (
            await anna.put(f"/quiz/runden/{code}/antwort", json={"text": "Berlin"})
        ).status_code == 409

        await _steuern(client, runde["id"], "zeigen", timer=False)
        offen = (await besucher.get(f"/quiz/runden/{code}")).json()
        assert offen["frage"]["text"] == "Hauptstadt?"
        assert "Berlin" not in str(offen), "Die Loesung verraet sich nicht vor dem Aufloesen"

        assert (
            await anna.put(
                f"/quiz/runden/{code}/antwort", json={"text": "berlin", "eingeloggt": True}
            )
        ).status_code == 200
        await ben.put(f"/quiz/runden/{code}/antwort", json={"text": "Bonn"})
        await ben.put(f"/quiz/runden/{code}/antwort", json={"text": "Hamburg"})
        leer = await ben.put(f"/quiz/runden/{code}/antwort", json={"text": "  "})
        assert leer.status_code == 422

        steuerung = (await client.get(f"/quiz/leitung/{runde['id']}")).json()
        assert {a["spieler"]: a["anzeige"] for a in steuerung["antworten"]} == {
            "Anna": "berlin",
            "Ben": "Hamburg",
        }
        assert [s["verbunden"] for s in steuerung["spieler"]] == [True, True]

        await _steuern(client, runde["id"], "sperren")
        assert (
            await ben.put(f"/quiz/runden/{code}/antwort", json={"text": "Berlin"})
        ).status_code == 409

        aufgeloest = await _steuern(client, runde["id"], "aufloesen")
        assert aufgeloest["beantwortet"] == [aufgeloest["frage"]["id"]]

        ende = (await anna.get(f"/quiz/runden/{code}")).json()
        assert ende["frage"]["loesung"]["anzeige"] == "Berlin"
        assert ende["ich"]["antwort"]["richtig"] is True
        assert [(p["name"], p["punkte"], p["rang"]) for p in ende["rangliste"]] == [
            ("Anna", 2, 1),
            ("Ben", 0, 2),
        ]
        assert set(ende["rangliste"][0]) == {"name", "punkte", "rang", "team"}, (
            "Oeffentlich nur Name und Punkte"
        )

        await _steuern(client, runde["id"], "beenden")
        assert (await besucher.get(f"/quiz/runden/{code}")).json()["status"] == "beendet"


async def test_frist_schliesst_die_eingabe(
    client: AsyncClient, spieler: Spielerfabrik, anwendung: FastAPI
) -> None:
    runde = await _runde(client, await _katalog(client, {**FREITEXT, "zeitlimit": 30}))
    async with spieler() as anna:
        await _beitreten(anna, runde["code"], "Anna")
        stand = await _frage_oeffnen(client, runde["id"], timer=True)
        assert stand["frist"] is not None

        async with anwendung.state.homepi.db.session() as sitzung:
            await sitzung.execute(
                update(Runde).values(frist=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=10))
            )
        antwort = await anna.put(f"/quiz/runden/{runde['code']}/antwort", json={"text": "Berlin"})
    assert antwort.status_code == 409
    assert "Zeit" in antwort.json()["detail"]


async def test_alle_automatisch_bewerteten_typen(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    fragen = [
        _frage({"typ": "zahl", "loesung": 16, "toleranz": 1}),
        _frage({"typ": "schaetzung", "minimum": 0, "maximum": 10, "loesung": 3.7}),
        _frage({"typ": "auswahl", "optionen": [{"text": "a", "richtig": True}, {"text": "b"}]}),
        _frage({"typ": "sortieren", "elemente": ["eins", "zwei", "drei"]}),
    ]
    runde = await _runde(client, await _katalog(client, *fragen))
    code = runde["code"]

    async with spieler() as anna:
        await _beitreten(anna, code, "Anna")
        for index in range(len(fragen)):
            await _frage_oeffnen(client, runde["id"], index)
            sicht = (await anna.get(f"/quiz/runden/{code}")).json()["frage"]
            if sicht["typ"] == "sortieren":
                texte = {e["text"]: e["kennung"] for e in sicht["elemente"]}
                eingabe: dict[str, Any] = {
                    "reihenfolge": [texte["eins"], texte["zwei"], texte["drei"]]
                }
            else:
                eingabe = (
                    {"zahl": {"zahl": 15.5, "schaetzung": 4}[sicht["typ"]]}
                    if sicht["typ"] != "auswahl"
                    else {"auswahl": [0]}
                )
            antwort = await anna.put(f"/quiz/runden/{code}/antwort", json=eingabe)
            assert antwort.status_code == 200, antwort.text
            await _steuern(client, runde["id"], "aufloesen")
            assert (await anna.get(f"/quiz/runden/{code}")).json()["ich"]["antwort"]["richtig"], (
                sicht["typ"]
            )

        assert (await anna.get(f"/quiz/runden/{code}")).json()["ich"]["punkte"] == 8


async def test_zurueck_zur_aufgeloesten_frage_behaelt_die_punkte(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT, BUZZER))
    async with spieler() as anna:
        await _beitreten(anna, runde["code"], "Anna")
        await _frage_oeffnen(client, runde["id"], 0)
        await anna.put(f"/quiz/runden/{runde['code']}/antwort", json={"text": "Berlin"})
        await _steuern(client, runde["id"], "aufloesen")
        erste = (await client.get(f"/quiz/leitung/{runde['id']}")).json()["fragen"][0]["id"]

        await _frage_oeffnen(client, runde["id"], 1)
        wieder = await _steuern(client, runde["id"], "frage", frage_id=erste)
        assert wieder["phase"] == "aufgeloest"
        assert (await anna.get(f"/quiz/runden/{runde['code']}")).json()["ich"]["punkte"] == 2


async def test_falsche_reihenfolge_der_aktionen(client: AsyncClient) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))
    zeigen = await client.post(f"/quiz/leitung/{runde['id']}/zeigen", json={})
    assert zeigen.status_code == 409
    assert "keine Frage" in zeigen.json()["detail"]

    fremde_frage = (await client.get(f"/quiz/kataloge/{await _katalog(client, BUZZER)}")).json()[
        "fragen"
    ][0]["id"]
    antwort = await client.post(
        f"/quiz/leitung/{runde['id']}/frage", json={"frage_id": fremde_frage}
    )
    assert antwort.status_code == 404

    await _steuern(client, runde["id"], "beenden")
    danach = await client.post(
        f"/quiz/leitung/{runde['id']}/frage", json={"frage_id": fremde_frage}
    )
    assert danach.status_code in (404, 409)


async def test_beenden_wertet_die_offene_frage_noch(
    client: AsyncClient, spieler: Spielerfabrik
) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))
    async with spieler() as anna:
        await _beitreten(anna, runde["code"], "Anna")
        await _frage_oeffnen(client, runde["id"])
        await anna.put(f"/quiz/runden/{runde['code']}/antwort", json={"text": "Berlin"})
        ende = await _steuern(client, runde["id"], "beenden")
    assert ende["runde"]["status"] == "beendet"
    assert ende["spieler"][0]["punkte"] == 2


# ------------------------------------------------------------- Buzzer


async def test_buzzer_reihenfolge_und_urteil(client: AsyncClient, spieler: Spielerfabrik) -> None:
    runde = await _runde(client, await _katalog(client, BUZZER))
    code = runde["code"]
    async with spieler() as anna, spieler() as ben, spieler() as cleo:
        for handy, name in ((anna, "Anna"), (ben, "Ben"), (cleo, "Cleo")):
            await _beitreten(handy, code, name)
        await _frage_oeffnen(client, runde["id"])

        assert (
            await anna.put(f"/quiz/runden/{code}/antwort", json={"text": "x"})
        ).status_code == 409
        await ben.post(f"/quiz/runden/{code}/buzzer")
        await anna.post(f"/quiz/runden/{code}/buzzer")
        doppelt = await ben.post(f"/quiz/runden/{code}/buzzer")
        assert doppelt.status_code == 409

        tafel = (await cleo.get(f"/quiz/runden/{code}")).json()
        assert tafel["buzzer"] == "Ben"
        assert (await anna.get(f"/quiz/runden/{code}")).json()["ich"]["buzzer_position"] == 2

        stand = await _steuern(client, runde["id"], "buzzer", richtig=False)
        assert [(b["spieler"], b["urteil"]) for b in stand["buzzer"]] == [
            ("Ben", "falsch"),
            ("Anna", "wartet"),
        ]
        assert (await cleo.get(f"/quiz/runden/{code}")).json()["buzzer"] == "Anna"

        stand = await _steuern(client, runde["id"], "buzzer", richtig=True)
        assert stand["phase"] == "aufgeloest"
        assert {s["name"]: s["punkte"] for s in stand["spieler"]} == {
            "Anna": 3,
            "Ben": 0,
            "Cleo": 0,
        }

        nochmal = await client.post(f"/quiz/leitung/{runde['id']}/buzzer", json={"richtig": True})
        assert nochmal.status_code == 409


async def test_buzzer_zuruecksetzen(client: AsyncClient, spieler: Spielerfabrik) -> None:
    runde = await _runde(client, await _katalog(client, BUZZER))
    async with spieler() as anna:
        await _beitreten(anna, runde["code"], "Anna")
        await _frage_oeffnen(client, runde["id"])
        await anna.post(f"/quiz/runden/{runde['code']}/buzzer")
        stand = await _steuern(client, runde["id"], "buzzer/zuruecksetzen")
        assert stand["buzzer"] == []
        assert (await anna.post(f"/quiz/runden/{runde['code']}/buzzer")).status_code == 200


async def test_urteil_ohne_buzzer(client: AsyncClient) -> None:
    runde = await _runde(client, await _katalog(client, BUZZER))
    await _frage_oeffnen(client, runde["id"])
    antwort = await client.post(f"/quiz/leitung/{runde['id']}/buzzer", json={"richtig": True})
    assert antwort.status_code == 409
    assert "niemand" in antwort.json()["detail"]


# ------------------------------------------------------------- Punkte von Hand


async def test_punkte_von_hand(client: AsyncClient, spieler: Spielerfabrik) -> None:
    runde = await _runde(client, await _katalog(client, _frage({"typ": "bild"})))
    katalog = (await client.get(f"/quiz/leitung/{runde['id']}")).json()
    await client.put(
        f"/quiz/fragen/{katalog['fragen'][0]['id']}/bild",
        content=PNG,
        headers={"content-type": "image/png"},
    )

    async with spieler() as anna:
        await _beitreten(anna, runde["code"], "Anna")
        await _frage_oeffnen(client, runde["id"])
        await anna.put(f"/quiz/runden/{runde['code']}/antwort", json={"text": "Eiffelturm"})
        stand = await _steuern(client, runde["id"], "aufloesen")
        antwort = stand["antworten"][0]
        assert antwort["punkte"] is None, "Bildfrage ohne Loesung wertet die Leitung"

        bewertet = await client.put(
            f"/quiz/leitung/{runde['id']}/antworten/{antwort['id']}", json={"punkte": 2}
        )
        assert bewertet.json()["antworten"][0]["richtig"] is True

        anna_id = stand["spieler"][0]["id"]
        bonus = await client.post(
            f"/quiz/leitung/{runde['id']}/spieler/{anna_id}/korrektur",
            json={"punkte": -1, "grund": "Vorsagen"},
        )
        assert bonus.json()["spieler"][0]["punkte"] == 1
        null = await client.post(
            f"/quiz/leitung/{runde['id']}/spieler/{anna_id}/korrektur", json={"punkte": 0}
        )
        assert null.status_code == 422

    unbekannt = "00000000-0000-0000-0000-000000000000"
    assert (
        await client.put(f"/quiz/leitung/{runde['id']}/antworten/{unbekannt}", json={"punkte": 1})
    ).status_code == 404
    assert (
        await client.post(
            f"/quiz/leitung/{runde['id']}/spieler/{unbekannt}/korrektur", json={"punkte": 1}
        )
    ).status_code == 404


async def test_runden_liste_und_loeschen(client: AsyncClient, besucher: AsyncClient) -> None:
    runde = await _runde(client, await _katalog(client, FREITEXT))
    await _frage_oeffnen(client, runde["id"])
    liste = (await client.get("/quiz/leitung")).json()
    assert [(r["code"], r["status"], r["katalog_titel"]) for r in liste] == [
        (runde["code"], "laeuft", "Kneipenquiz")
    ]
    assert (await besucher.get("/quiz/")).json() == {"laufende_runden": 1}

    assert (await client.delete(f"/quiz/leitung/{runde['id']}")).status_code == 204
    assert (await client.get(f"/quiz/leitung/{runde['id']}")).status_code == 404
