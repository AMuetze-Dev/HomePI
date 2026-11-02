"""Der Router gegen eine echte Datenbank.

Als Integration markiert, weil er fast nur aus Datenbankzugriff besteht: gegen
eine nachgebaute Sitzung wuerde man vor allem den Nachbau testen.

    make dev
    HOMEPI_TEST_DATABASE_URL='postgresql+asyncpg://app:app@127.0.0.1:15432/test' \
        uv run pytest -m 'not smoke'
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration

PFAD = "/haushaltsbuch"


async def _person(client: AsyncClient, name: str) -> str:
    antwort = await client.post(f"{PFAD}/personen", json={"name": name})
    assert antwort.status_code == 201, antwort.text
    return str(antwort.json()["id"])


async def _konto(client: AsyncClient, name: str, inhaber: str | None = None) -> str:
    antwort = await client.post(
        f"{PFAD}/konten", json={"name": name, "art": "verteiler", "inhaber_id": inhaber}
    )
    assert antwort.status_code == 201, antwort.text
    return str(antwort.json()["id"])


async def _kategorie(client: AsyncClient, name: str, spart: bool = False) -> str:
    antwort = await client.post(
        f"{PFAD}/kategorien", json={"name": name, "zaehlt_als_sparen": spart}
    )
    assert antwort.status_code == 201, antwort.text
    return str(antwort.json()["id"])


async def _posten(client: AsyncClient, **felder: Any) -> dict[str, Any]:
    antwort = await client.post(f"{PFAD}/posten", json=felder)
    assert antwort.status_code == 201, antwort.text
    ergebnis: dict[str, Any] = antwort.json()
    return ergebnis


# ------------------------------------------------------------- Erstzustand


async def test_ein_leeres_haushaltsbuch_antwortet_statt_zu_scheitern(
    client: AsyncClient,
) -> None:
    antwort = await client.get(f"{PFAD}/")

    assert antwort.status_code == 200
    assert antwort.json()["personen"] == []
    assert antwort.json()["ruecklagen_summe"] == "0.00"


async def test_das_grundgeruest_legt_die_ueblichen_kategorien_an(client: AsyncClient) -> None:
    angelegt = await client.post(f"{PFAD}/kategorien/grundgeruest")

    assert angelegt.status_code == 200
    assert "Wohnen" in [k["name"] for k in angelegt.json()]
    assert any(k["zaehlt_als_sparen"] for k in angelegt.json())


async def test_das_grundgeruest_zweimal_erzeugt_keine_dubletten(client: AsyncClient) -> None:
    erste = (await client.post(f"{PFAD}/kategorien/grundgeruest")).json()
    zweite = (await client.post(f"{PFAD}/kategorien/grundgeruest")).json()

    assert [k["name"] for k in erste] == [k["name"] for k in zweite]


# ------------------------------------------------------------------- CRUD


async def test_person_anlegen_aendern_entfernen(client: AsyncClient) -> None:
    kennung = await _person(client, "Aaron")

    geaendert = await client.patch(f"{PFAD}/personen/{kennung}", json={"name": "Aaron M."})
    assert geaendert.json()["name"] == "Aaron M."

    assert (await client.delete(f"{PFAD}/personen/{kennung}")).status_code == 204
    assert (await client.get(f"{PFAD}/personen")).json() == []


async def test_doppelter_name_wird_abgelehnt(client: AsyncClient) -> None:
    await _person(client, "Aaron")

    antwort = await client.post(f"{PFAD}/personen", json={"name": "Aaron"})

    assert antwort.status_code == 409
    assert "problem+json" in antwort.headers["content-type"]


async def test_ein_name_aus_leerzeichen_ist_kein_name(client: AsyncClient) -> None:
    antwort = await client.post(f"{PFAD}/personen", json={"name": "   "})

    assert antwort.status_code == 422
    assert any("name" in f["feld"] for f in antwort.json()["fehler"])


async def test_unbekannte_kennung_ergibt_404(client: AsyncClient) -> None:
    leer = "00000000-0000-0000-0000-000000000000"

    assert (await client.get(f"{PFAD}/posten/{leer}")).status_code == 404


async def test_eine_person_mit_konto_laesst_sich_nicht_einfach_loeschen(
    client: AsyncClient,
) -> None:
    """Sonst verschwindet mit ihr stillschweigend die halbe Aufteilung."""
    person = await _person(client, "Aaron")
    await _konto(client, "CON1", person)

    antwort = await client.delete(f"{PFAD}/personen/{person}")

    assert antwort.status_code == 409
    assert "Konten" in antwort.json()["detail"]


async def test_ein_konto_laesst_sich_wieder_gemeinschaftlich_machen(
    client: AsyncClient,
) -> None:
    person = await _person(client, "Aaron")
    konto = await _konto(client, "DKB1", person)

    antwort = await client.patch(f"{PFAD}/konten/{konto}", json={"gemeinschaftlich": True})

    assert antwort.json()["inhaber_id"] is None


async def test_eine_geloeschte_kategorie_nimmt_ihre_posten_nicht_mit(
    client: AsyncClient,
) -> None:
    konto = await _konto(client, "CON1")
    kategorie = await _kategorie(client, "Konsum")
    posten = await _posten(
        client, name="Handy", art="ausgabe", betrag="31.90", konto_id=konto, kategorie_id=kategorie
    )

    assert (await client.delete(f"{PFAD}/kategorien/{kategorie}")).status_code == 204

    uebrig = (await client.get(f"{PFAD}/posten/{posten['id']}")).json()
    assert uebrig["kategorie_id"] is None


# -------------------------------------------------------------- Rechnung


async def test_der_monatsplan_teilt_gemeinsame_kosten_nach_gewicht(
    client: AsyncClient,
) -> None:
    aaron = await _person(client, "Aaron")
    jessi = await _person(client, "Jessi")
    gemeinsam = await _konto(client, "DKB1")
    await _konto(client, "CON1", aaron)
    wohnen = await _kategorie(client, "Wohnen")

    await _posten(
        client,
        name="Miete",
        art="ausgabe",
        betrag="900.00",
        konto_id=gemeinsam,
        kategorie_id=wohnen,
        anteile=[{"person_id": jessi, "gewicht": 1}, {"person_id": aaron, "gewicht": 2}],
    )

    plan = (await client.get(f"{PFAD}/")).json()
    beitraege = {p["name"]: p["einzahlung_gemeinschaft"] for p in plan["personen"]}

    assert beitraege == {"Aaron": "600.00", "Jessi": "300.00"}


async def test_ein_jaehrlicher_posten_wird_zur_monatlichen_ruecklage(
    client: AsyncClient,
) -> None:
    konto = await _konto(client, "CON1")
    await _posten(
        client,
        name="Kfz-Versicherung",
        art="ausgabe",
        betrag="600.00",
        konto_id=konto,
        intervall_monate=12,
        faelligkeitsmonat=1,
    )

    plan = (await client.get(f"{PFAD}/", params={"jahr": 2026, "monat": 6})).json()
    zeile = plan["ruecklagen"][0]

    assert zeile["monatsrate"] == "50.00"
    assert zeile["faellige_monate"] == [1]
    assert zeile["ruecklagenstand"] == "250.00"
    assert plan["faellig"] == []


async def test_ein_posten_laesst_sich_pausieren_statt_loeschen(client: AsyncClient) -> None:
    konto = await _konto(client, "CON1")
    posten = await _posten(client, name="Netflix", art="ausgabe", betrag="24.98", konto_id=konto)

    await client.patch(f"{PFAD}/posten/{posten['id']}", json={"aktiv": False})

    zusammen = (await client.get(f"{PFAD}/zusammenfassung")).json()
    assert zusammen["posten"] == 0
    assert len((await client.get(f"{PFAD}/posten")).json()) == 1


async def test_eine_aufteilung_laesst_sich_wieder_aufheben(client: AsyncClient) -> None:
    aaron = await _person(client, "Aaron")
    gemeinsam = await _konto(client, "DKB1")
    posten = await _posten(
        client,
        name="Strom",
        art="ausgabe",
        betrag="82.00",
        konto_id=gemeinsam,
        anteile=[{"person_id": aaron, "gewicht": 1}],
    )

    antwort = await client.patch(f"{PFAD}/posten/{posten['id']}", json={"anteile": []})

    assert antwort.json()["anteile"] == []
    plan = (await client.get(f"{PFAD}/")).json()
    assert plan["gemeinschaft"]["ohne_aufteilung"] == ["Strom"]


async def test_dieselbe_person_darf_in_einem_posten_nicht_zweimal_stehen(
    client: AsyncClient,
) -> None:
    aaron = await _person(client, "Aaron")
    konto = await _konto(client, "DKB1")

    antwort = await client.post(
        f"{PFAD}/posten",
        json={
            "name": "Miete",
            "art": "ausgabe",
            "betrag": "900.00",
            "konto_id": konto,
            "anteile": [
                {"person_id": aaron, "gewicht": 1},
                {"person_id": aaron, "gewicht": 2},
            ],
        },
    )

    assert antwort.status_code == 422


async def test_ein_posten_auf_einem_unbekannten_konto_nennt_das_konto(
    client: AsyncClient,
) -> None:
    antwort = await client.post(
        f"{PFAD}/posten",
        json={
            "name": "Irgendwas",
            "art": "ausgabe",
            "betrag": "1.00",
            "konto_id": "00000000-0000-0000-0000-000000000000",
        },
    )

    assert antwort.status_code == 404
    assert "Konto" in antwort.json()["title"]


# -------------------------------------------------------------- Flussbild


async def test_das_flussbild_verbindet_einkommen_konto_und_posten(
    client: AsyncClient,
) -> None:
    aaron = await _person(client, "Aaron")
    konto = await _konto(client, "CON1", aaron)
    konsum = await _kategorie(client, "Konsum")
    await _posten(client, name="Sold", art="einnahme", betrag="3000.00", konto_id=konto)
    await _posten(
        client,
        name="Handy",
        art="ausgabe",
        betrag="31.90",
        konto_id=konto,
        kategorie_id=konsum,
    )

    bild = (await client.get(f"{PFAD}/flussbild")).json()
    ebene = {k["id"]: k["ebene"] for k in bild["knoten"]}

    assert bild["ebenen"] == 4
    assert all(ebene[f["von"]] < ebene[f["nach"]] for f in bild["fluesse"])


# ----------------------------------------------------------------- Rechte


async def test_ein_leser_sieht_den_plan(leser: AsyncClient) -> None:
    assert (await leser.get(f"{PFAD}/")).status_code == 200
    assert (await leser.get(f"{PFAD}/flussbild")).status_code == 200


async def test_ein_leser_aendert_nichts(leser: AsyncClient) -> None:
    """Die Freundin soll zusehen koennen, ohne dass eine Miete verrutscht."""
    antwort = await leser.post(f"{PFAD}/personen", json={"name": "Heimlich"})

    assert antwort.status_code == 403


async def test_ohne_anmeldung_gibt_es_gar_nichts(anwendung: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=anwendung), base_url="http://test") as fremd:
        assert (await fremd.get(f"{PFAD}/")).status_code == 401
