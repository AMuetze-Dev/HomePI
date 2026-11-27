"""Der Router gegen eine echte Datenbank.

    HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
        uv run pytest -m 'not smoke'
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

UNBEKANNT = "00000000-0000-0000-0000-000000000000"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


async def _tag(client: AsyncClient, **felder: Any) -> dict[str, Any]:
    daten = {"datum": "2026-06-18", "ort": "Köln", "korrektor": "K. Orrektor", **felder}
    antwort = await client.post("/ihk/tage", json=daten)
    assert antwort.status_code == 201, antwort.text
    ergebnis: dict[str, Any] = antwort.json()
    return ergebnis


async def _pruefling(client: AsyncClient, name: str = "Muster, Max") -> dict[str, Any]:
    tag = await _tag(client)
    antwort = await client.post(f"/ihk/tage/{tag['id']}/prueflinge", json={"name": name})
    assert antwort.status_code == 201, antwort.text
    ergebnis: dict[str, Any] = antwort.json()
    return ergebnis


# ── Prüfungstage ─────────────────────────────────────────────────────────────


async def test_uebersicht_ist_zuerst_leer(client: AsyncClient) -> None:
    assert (await client.get("/ihk/")).json() == []


async def test_ohne_anmeldung_kein_zugriff(client: AsyncClient) -> None:
    await client.post("/auth/abmelden")
    assert (await client.get("/ihk/")).status_code == 401


async def test_tag_anlegen_und_in_der_uebersicht(client: AsyncClient) -> None:
    await _tag(client, datum="2026-06-17")
    neu = await _tag(client, datum="2026-06-18", ort="  Bonn ")

    assert neu["ort"] == "Bonn"
    uebersicht = (await client.get("/ihk/")).json()
    # Der jüngste Tag zuerst
    assert [t["tag"]["datum"] for t in uebersicht] == ["2026-06-18", "2026-06-17"]
    assert uebersicht[0]["tag"]["anzahl_prueflinge"] == 0
    assert uebersicht[0]["prueflinge"] == []


async def test_tag_mit_ungueltigem_datum(client: AsyncClient) -> None:
    antwort = await client.post("/ihk/tage", json={"datum": "18.06.2026"})
    assert antwort.status_code == 422
    assert any("datum" in f["feld"] for f in antwort.json()["fehler"])


async def test_tag_aendern(client: AsyncClient) -> None:
    tag = await _tag(client)
    antwort = await client.patch(f"/ihk/tage/{tag['id']}", json={"korrektor": "Neu"})
    assert antwort.status_code == 200
    assert antwort.json()["korrektor"] == "Neu"
    assert antwort.json()["ort"] == "Köln"


async def test_unbekannter_tag(client: AsyncClient) -> None:
    antwort = await client.get(f"/ihk/tage/{UNBEKANNT}")
    assert antwort.status_code == 404
    assert "problem+json" in antwort.headers["content-type"]
    assert (await client.patch(f"/ihk/tage/{UNBEKANNT}", json={})).status_code == 404
    assert (await client.delete(f"/ihk/tage/{UNBEKANNT}")).status_code == 404
    antwort = await client.post(f"/ihk/tage/{UNBEKANNT}/prueflinge", json={"name": "X"})
    assert antwort.status_code == 404


async def test_tag_loeschen_nimmt_die_prueflinge_mit(client: AsyncClient) -> None:
    pruefling = await _pruefling(client)

    assert (await client.delete(f"/ihk/tage/{pruefling['tag']['id']}")).status_code == 204
    assert (await client.get(f"/ihk/prueflinge/{pruefling['id']}")).status_code == 404


# ── Prüflinge ────────────────────────────────────────────────────────────────


async def test_pruefling_anlegen_numeriert_der_reihe_nach(client: AsyncClient) -> None:
    tag = await _tag(client)
    for name in ("Erster, A", "Zweiter, B"):
        await client.post(f"/ihk/tage/{tag['id']}/prueflinge", json={"name": name})

    detail = (await client.get(f"/ihk/tage/{tag['id']}")).json()
    assert [(p["reihenfolge"], p["name"]) for p in detail["prueflinge"]] == [
        (1, "Erster, A"),
        (2, "Zweiter, B"),
    ]
    assert detail["prueflinge"][0]["doku_punkte"] is None
    assert detail["prueflinge"][0]["dokumente"] == 0

    # Die Übersicht bringt jeden Tag samt seinen Prüflingen in einem Abruf
    uebersicht = (await client.get("/ihk/")).json()
    assert uebersicht[0]["tag"]["anzahl_prueflinge"] == 2
    assert [p["name"] for p in uebersicht[0]["prueflinge"]] == ["Erster, A", "Zweiter, B"]


async def test_uebersicht_trennt_die_prueflinge_nach_tagen(client: AsyncClient) -> None:
    frueh = await _tag(client, datum="2026-06-17")
    spaet = await _tag(client, datum="2026-06-18")
    await client.post(f"/ihk/tage/{frueh['id']}/prueflinge", json={"name": "Früh, F"})
    await client.post(f"/ihk/tage/{spaet['id']}/prueflinge", json={"name": "Spät, S"})

    uebersicht = (await client.get("/ihk/")).json()

    assert [[p["name"] for p in t["prueflinge"]] for t in uebersicht] == [["Spät, S"], ["Früh, F"]]


async def test_kurzansicht_zaehlt_die_dokumente(client: AsyncClient) -> None:
    p = await _pruefling(client)
    await client.post(
        f"/ihk/prueflinge/{p['id']}/dokumente",
        params={"art": "projekt", "dateiname": "a.pdf"},
        content=PDF,
    )

    detail = (await client.get(f"/ihk/tage/{p['tag']['id']}")).json()
    assert detail["prueflinge"][0]["dokumente"] == 1


async def test_pruefling_ohne_namen(client: AsyncClient) -> None:
    tag = await _tag(client)
    antwort = await client.post(f"/ihk/tage/{tag['id']}/prueflinge", json={"name": "   "})
    assert antwort.status_code == 422


async def test_neuer_pruefling_ist_unbewertet(client: AsyncClient) -> None:
    p = await _pruefling(client)

    assert p["korrekturart"] == "Erstkorrektur"
    assert p["status"] == {
        "runtergeladen": False,
        "kontrolliert": False,
        "abgestimmt": False,
        "hochgeladen": False,
    }
    assert p["bewertung"]["doku"] == {}
    assert p["auswertung"]["doku"]["gesamt"] is None
    assert len(p["auswertung"]["doku"]["fehlend"]) == 38
    assert p["auswertung"]["gesamt_mit_mep"] is None
    assert p["zeiten"]["praesi_start"] is None
    assert p["dokumente"] == []
    assert p["jetzt"]


async def test_stammdaten_und_status_aendern(client: AsyncClient) -> None:
    p = await _pruefling(client)

    antwort = await client.patch(
        f"/ihk/prueflinge/{p['id']}",
        json={"ident": "4711", "korrekturart": "Zweitkorrektur", "status": {"kontrolliert": True}},
    )

    assert antwort.status_code == 200
    neu = antwort.json()
    assert (neu["ident"], neu["korrekturart"]) == ("4711", "Zweitkorrektur")
    assert neu["status"]["kontrolliert"] is True
    assert neu["status"]["hochgeladen"] is False
    assert neu["name"] == "Muster, Max"


async def test_unzulaessige_korrekturart(client: AsyncClient) -> None:
    p = await _pruefling(client)
    antwort = await client.patch(f"/ihk/prueflinge/{p['id']}", json={"korrekturart": "Dritte"})
    assert antwort.status_code == 422


async def test_unbekannter_pruefling(client: AsyncClient) -> None:
    pfad = f"/ihk/prueflinge/{UNBEKANNT}"
    assert (await client.get(pfad)).status_code == 404
    assert (await client.patch(pfad, json={})).status_code == 404
    assert (await client.patch(f"{pfad}/bewertung", json={})).status_code == 404
    assert (await client.put(f"{pfad}/teilnoten", json={})).status_code == 404
    antwort = await client.post(f"{pfad}/zeit", json={"aktion": "zuruecksetzen"})
    assert antwort.status_code == 404
    assert (await client.get(f"{pfad}/korrekturbogen")).status_code == 404
    assert (await client.delete(pfad)).status_code == 404


async def test_pruefling_loeschen(client: AsyncClient) -> None:
    p = await _pruefling(client)
    assert (await client.delete(f"/ihk/prueflinge/{p['id']}")).status_code == 204
    assert (await client.get(f"/ihk/prueflinge/{p['id']}")).status_code == 404


# ── Bewertung ────────────────────────────────────────────────────────────────


async def test_bewertung_aendern_rechnet_neu(client: AsyncClient) -> None:
    p = await _pruefling(client)

    antwort = await client.patch(
        f"/ihk/prueflinge/{p['id']}/bewertung",
        json={
            "doku": {"doku.1.1": 1, "doku.1.2": 1},
            "doku_bemerkungen": {"doku.1": "ordentlich"},
            "praesi_skala": {"praesi.1.1": 1, "praesi.1.2": 0.5},
            "praesi_punkte": {"praesi.1": 8},
            "notizen": "nur für mich",
        },
    )

    assert antwort.status_code == 200, antwort.text
    neu = antwort.json()
    assert neu["bewertung"]["doku"] == {"doku.1.1": 1, "doku.1.2": 1}
    assert neu["bewertung"]["notizen"] == "nur für mich"
    form = neu["auswertung"]["doku"]["sektionen"][0]
    assert (form["wert"], form["vollstaendig"]) == (2, False)
    aufbau = neu["auswertung"]["praesentation"]["sektionen"][0]
    assert (aufbau["vorschlag"], aufbau["wert"]) == (8, 8)

    # bleibt nach dem Neuladen, und ein zweites Ändern ergänzt
    await client.patch(f"/ihk/prueflinge/{p['id']}/bewertung", json={"doku": {"doku.1.2": None}})
    geladen = (await client.get(f"/ihk/prueflinge/{p['id']}")).json()
    assert geladen["bewertung"]["doku"] == {"doku.1.1": 1}
    assert geladen["bewertung"]["doku_bemerkungen"] == {"doku.1": "ordentlich"}


async def test_bewertung_ausserhalb_der_grenzen(client: AsyncClient) -> None:
    p = await _pruefling(client)

    antwort = await client.patch(
        f"/ihk/prueflinge/{p['id']}/bewertung", json={"doku": {"doku.1.1": 5}}
    )

    assert antwort.status_code == 422
    assert "0 bis 1" in antwort.json()["detail"]
    geladen = (await client.get(f"/ihk/prueflinge/{p['id']}")).json()
    assert geladen["bewertung"]["doku"] == {}


async def test_unbekanntes_kriterium(client: AsyncClient) -> None:
    p = await _pruefling(client)
    antwort = await client.patch(
        f"/ihk/prueflinge/{p['id']}/bewertung", json={"praesi_punkte": {"praesi.9": 1}}
    )
    assert antwort.status_code == 422
    assert "praesi.9" in antwort.json()["detail"]


# ── Teilnoten und Gesamt ─────────────────────────────────────────────────────


async def test_teilnoten_ergeben_das_gesamtergebnis(client: AsyncClient) -> None:
    p = await _pruefling(client)

    antwort = await client.put(
        f"/ihk/prueflinge/{p['id']}/teilnoten",
        json={
            "teil1": 80,
            "planen_softwareprodukt": 70,
            "algorithmen": 60,
            "wiso": 90,
            "mep": {"bereich": "wiso", "punkte": 40},
        },
    )

    assert antwort.status_code == 200, antwort.text
    auswertung = antwort.json()["auswertung"]
    assert auswertung["gesamt_ohne_mep"]["gesamt"] is None
    assert "projekt" in auswertung["gesamt_ohne_mep"]["fehlend"]
    wiso = auswertung["gesamt_mit_mep"]["bereiche"][2]
    assert (wiso["id"], wiso["wert"]) == ("wiso", 73)
    assert antwort.json()["teilnoten"]["mep"] == {"bereich": "wiso", "punkte": 40}


async def test_teilnoten_ueber_100(client: AsyncClient) -> None:
    p = await _pruefling(client)
    antwort = await client.put(f"/ihk/prueflinge/{p['id']}/teilnoten", json={"teil1": 101})
    assert antwort.status_code == 422
    assert any("teil1" in f["feld"] for f in antwort.json()["fehler"])


# ── Zeitmessung ──────────────────────────────────────────────────────────────


async def test_zeitmessung(client: AsyncClient) -> None:
    p = await _pruefling(client)
    pfad = f"/ihk/prueflinge/{p['id']}/zeit"

    zeiten = (await client.post(pfad, json={"aktion": "praesentation_starten"})).json()["zeiten"]
    assert zeiten["praesi_start"] is not None

    zeiten = (await client.post(pfad, json={"aktion": "fachgespraech_starten"})).json()["zeiten"]
    assert zeiten["praesi_ende"] == zeiten["fg_start"]

    antwort = await client.post(pfad, json={"aktion": "fachgespraech_starten"})
    assert antwort.status_code == 409
    assert "Präsentation läuft" in antwort.json()["detail"]

    zeiten = (await client.post(pfad, json={"aktion": "beenden"})).json()["zeiten"]
    assert zeiten["fg_ende"] is not None

    zeiten = (await client.post(pfad, json={"aktion": "zuruecksetzen"})).json()["zeiten"]
    assert zeiten == {"praesi_start": None, "praesi_ende": None, "fg_start": None, "fg_ende": None}


async def test_unbekannte_zeitaktion(client: AsyncClient) -> None:
    p = await _pruefling(client)
    antwort = await client.post(f"/ihk/prueflinge/{p['id']}/zeit", json={"aktion": "pause"})
    assert antwort.status_code == 422


# ── Dokumente ────────────────────────────────────────────────────────────────


async def test_dokument_hochladen_lesen_entfernen(client: AsyncClient) -> None:
    p = await _pruefling(client)
    basis = f"/ihk/prueflinge/{p['id']}/dokumente"

    antwort = await client.post(
        basis,
        params={"art": "projekt", "dateiname": "C:\\Ablage\\Projekt.pdf"},
        content=PDF,
        headers={"Content-Type": "application/pdf"},
    )
    assert antwort.status_code == 201, antwort.text
    dokument = antwort.json()
    assert (dokument["art"], dokument["dateiname"], dokument["groesse"]) == (
        "projekt",
        "Projekt.pdf",
        len(PDF),
    )

    geladen = (await client.get(f"/ihk/prueflinge/{p['id']}")).json()
    assert [d["id"] for d in geladen["dokumente"]] == [dokument["id"]]

    datei = await client.get(f"{basis}/{dokument['id']}")
    assert datei.status_code == 200
    assert datei.headers["content-type"] == "application/pdf"
    assert datei.content == PDF

    assert (await client.delete(f"{basis}/{dokument['id']}")).status_code == 204
    assert (await client.get(f"{basis}/{dokument['id']}")).status_code == 404
    assert (await client.delete(f"{basis}/{dokument['id']}")).status_code == 404


async def test_nur_pdf_wird_angenommen(client: AsyncClient) -> None:
    p = await _pruefling(client)
    antwort = await client.post(
        f"/ihk/prueflinge/{p['id']}/dokumente",
        params={"art": "kunde", "dateiname": "bild.png"},
        content=b"\x89PNG\r\n",
    )
    assert antwort.status_code == 415
    assert "kein PDF" in antwort.json()["detail"]


async def test_dokument_mit_falscher_art(client: AsyncClient) -> None:
    p = await _pruefling(client)
    antwort = await client.post(
        f"/ihk/prueflinge/{p['id']}/dokumente",
        params={"art": "sonstiges", "dateiname": "a.pdf"},
        content=PDF,
    )
    assert antwort.status_code == 422


async def test_dokument_eines_anderen_prueflings(client: AsyncClient) -> None:
    a = await _pruefling(client, "A, A")
    b = await _pruefling(client, "B, B")
    dokument = (
        await client.post(
            f"/ihk/prueflinge/{a['id']}/dokumente",
            params={"art": "projekt", "dateiname": "a.pdf"},
            content=PDF,
        )
    ).json()

    antwort = await client.get(f"/ihk/prueflinge/{b['id']}/dokumente/{dokument['id']}")
    assert antwort.status_code == 404


# ── Korrekturbogen und Katalog ───────────────────────────────────────────────


async def test_korrekturbogen_als_pdf(client: AsyncClient) -> None:
    p = await _pruefling(client, "Müller, Anna")
    await client.patch(f"/ihk/prueflinge/{p['id']}/bewertung", json={"doku": {"doku.1.1": 1}})

    antwort = await client.get(f"/ihk/prueflinge/{p['id']}/korrekturbogen")

    assert antwort.status_code == 200
    assert antwort.headers["content-type"] == "application/pdf"
    assert antwort.content.startswith(b"%PDF")
    assert "2026-06-18_M" in antwort.headers["content-disposition"]
    assert "Korrekturbogen.pdf" in antwort.headers["content-disposition"]


async def test_katalog(client: AsyncClient) -> None:
    katalog = (await client.get("/ihk/katalog")).json()

    assert [s["nr"] for s in katalog["doku"]] == ["1", "2", "3", "4", "5", "6", "7"]
    assert katalog["doku"][0]["bloecke"] == [
        {"id": "doku.1", "knoten": []},
        {"id": "doku.1.1", "knoten": ["doku.1.1", "doku.1.2", "doku.1.3"]},
    ]
    assert katalog["skala"] == [1, 0.75, 0.5, 0.25, 0]
    assert katalog["praesi_grenze_min"] == 15
    assert katalog["gesamt_grenze_min"] == 30
    assert [b["id"] for b in katalog["bereiche"]] == [
        "planen_softwareprodukt",
        "algorithmen",
        "wiso",
    ]
    assert len(katalog["notenbaender"]) == 6
