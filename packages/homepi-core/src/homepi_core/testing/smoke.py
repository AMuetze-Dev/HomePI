"""Fertige Rauchtests, die jedes HomePI-Projekt übernehmen kann.

    # tests/smoke/test_smoke.py
    from homepi_core.testing.smoke import *  # noqa: F401,F403

Damit laufen dieselben Prüfungen lokal, in der CI und gegen den Pi:

    pytest -m smoke                          # gegen das Standardziel
    HOMEPI_ZIEL=pi pytest -m smoke           # gegen den Pi
    HOMEPI_BASIS_URL=http://… pytest -m smoke

Sie prüfen, was nach jedem Deploy stimmen muss und was ein Unit-Test
grundsätzlich nicht sehen kann: dass der Prozess wirklich läuft, seine
Abhängigkeiten erreicht und alle Module geladen hat.

Artefakte sind je Benutzer sichtbar. Ein anonymes ``GET /module`` ist deshalb
berechtigterweise leer und sagt nichts über den Zustand der Instanz. Die Tests,
die das Manifest auswerten, brauchen ein Konto:

    HOMEPI_SMOKE_BENUTZER=rauchtest HOMEPI_SMOKE_PASSWORT=… pytest -m smoke

Ohne das überspringen sie sich ausdrücklich, statt auf einer leeren Liste
stillschweigend grün zu werden.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.smoke

ERLAUBTE_STATUS = {"ok", "degraded", "down"}

#: Werte, die es nirgends gibt. Als benannte Konstanten und nicht als Literal
#: neben dem Schluessel "token": ein `"token": "..."` im Quelltext laesst jeden
#: Geheimnis-Scanner anschlagen, und zu Recht - er kann nicht wissen, dass es
#: hier Absicht ist.
ERFUNDEN = "gibt-es-nicht-4711"
ERFUNDEN_LANG = "auch-nicht-4711-lang-genug"


async def test_health_antwortet(smoke_client: httpx.AsyncClient) -> None:
    antwort = await smoke_client.get("/health")

    assert antwort.status_code in (200, 503), f"unerwarteter Code {antwort.status_code}"
    koerper = antwort.json()
    assert koerper["status"] in ERLAUBTE_STATUS
    assert isinstance(koerper["checks"], dict)


async def test_health_ist_gruen(smoke_client: httpx.AsyncClient) -> None:
    """Getrennt vom Formattest: so unterscheidet der Bericht 'Antwort kaputt'
    von 'Abhängigkeit weg'."""
    koerper = (await smoke_client.get("/health")).json()

    gestoert = [name for name, gesund in koerper["checks"].items() if not gesund]
    assert not gestoert, f"gestörte Abhängigkeiten: {', '.join(gestoert)}"


async def test_info_nennt_version_und_umgebung(smoke_client: httpx.AsyncClient) -> None:
    koerper = (await smoke_client.get("/info")).json()

    assert koerper["service"]
    assert koerper["version"], "ohne Version ist nach einem Deploy nicht erkennbar, was läuft"
    assert koerper["environment"]


# --- Ohne Anmeldung --------------------------------------------------------


async def test_ohne_anmeldung_ist_nur_oeffentliches_zu_sehen(
    smoke_client: httpx.AsyncClient,
) -> None:
    """Das Manifest muss auch anonym antworten - ein Besucher der öffentlichen
    Seite soll die Seite sehen und keinen 401."""
    antwort = await smoke_client.get("/module")
    if antwort.status_code == 404:
        pytest.skip("kein Gateway - dieser Dienst betreibt keine Module")

    assert antwort.status_code == 200
    for eintrag in antwort.json():
        assert eintrag.get("zugang") == "oeffentlich", (
            f"Artefakt '{eintrag.get('id')}' ist ohne Anmeldung sichtbar, "
            f"obwohl es als '{eintrag.get('zugang')}' deklariert ist"
        )


async def test_die_anmeldung_ist_erreichbar(smoke_client: httpx.AsyncClient) -> None:
    """Fehlt sie nach einem Deploy, käme niemand mehr an seine Artefakte - und
    ein anonymer Rauchtest bliebe trotzdem grün."""
    antwort = await smoke_client.post(
        "/auth/anmelden", json={"name": ERFUNDEN, "passwort": ERFUNDEN_LANG}
    )
    if antwort.status_code == 404:
        pytest.skip("dieser Dienst hat keine Anmeldung")

    assert antwort.status_code == 401, f"unerwarteter Code {antwort.status_code}"


async def test_die_ersteinrichtung_ist_zu(smoke_client: httpx.AsyncClient) -> None:
    """Der wichtigste Test dieser Datei nach einem Deploy.

    Der Einrichtungs-Endpunkt legt ein Konto an, das alles verwalten darf, und
    er ist naturgemäß ohne Anmeldung erreichbar. Steht er auf einer
    eingerichteten Installation noch offen, kann sie jeder übernehmen, der sie
    erreicht. Geprüft wird mit einem erfundenen Token: 409 heißt "die Tür ist
    zu", 401 hieße "die Tür steht offen, nur der Schlüssel war falsch".
    """
    stand = await smoke_client.get("/auth/einrichtung")
    if stand.status_code == 404:
        pytest.skip("dieser Dienst hat keine Anmeldung")

    if stand.json().get("noetig"):
        pytest.skip("diese Installation ist noch nicht eingerichtet")

    antwort = await smoke_client.post(
        "/auth/einrichtung",
        json={"token": ERFUNDEN, "name": "eindringling", "passwort": ERFUNDEN_LANG},
    )

    assert antwort.status_code == 409, (
        f"Die Ersteinrichtung antwortet mit {antwort.status_code}, obwohl diese "
        "Installation bereits einen Verwalter hat"
    )


# --- Angemeldet ------------------------------------------------------------


async def test_modulmanifest_ist_vollstaendig(
    angemeldeter_smoke_client: httpx.AsyncClient,
) -> None:
    """Überspringt sich selbst, wenn die Instanz kein Gateway ist."""
    antwort = await angemeldeter_smoke_client.get("/module")
    if antwort.status_code == 404:
        pytest.skip("kein Gateway - dieser Dienst betreibt keine Module")

    eintraege: list[dict[str, Any]] = antwort.json()
    assert eintraege, "angemeldet, aber kein einziges Artefakt sichtbar - fehlen die Rechte?"
    for eintrag in eintraege:
        for feld in ("id", "titel", "pfad", "status", "zugang"):
            assert eintrag.get(feld) is not None, f"Feld '{feld}' fehlt in {eintrag}"


async def test_kein_modul_ist_defekt(angemeldeter_smoke_client: httpx.AsyncClient) -> None:
    antwort = await angemeldeter_smoke_client.get("/module")
    if antwort.status_code == 404:
        pytest.skip("kein Gateway")

    defekt = [e for e in antwort.json() if e.get("status") == "fehler"]
    namen = ", ".join(f"{e['id']} ({e['beschreibung']})" for e in defekt)
    assert not defekt, f"Module konnten nicht geladen werden: {namen}"


async def test_jedes_modul_ist_erreichbar(angemeldeter_smoke_client: httpx.AsyncClient) -> None:
    """Ein Modul, das im Manifest steht, dessen Router aber nicht hängt, wäre
    sonst erst beim Klicken auf die Kachel aufgefallen."""
    antwort = await angemeldeter_smoke_client.get("/module")
    if antwort.status_code == 404:
        pytest.skip("kein Gateway")

    for eintrag in antwort.json():
        if eintrag.get("status") != "bereit":
            continue
        pfad = eintrag["pfad"]
        code = (await angemeldeter_smoke_client.get(pfad)).status_code
        # 404 hiesse: nichts unter diesem Praefix eingehaengt.
        # 401/403/422 sind in Ordnung - der Router ist da und antwortet.
        assert code != 404, f"Modul '{eintrag['id']}' ist im Manifest, aber {pfad} ist leer"
        assert code < 500, f"Modul '{eintrag['id']}' antwortet mit {code}"


async def test_geschuetzte_artefakte_weisen_anonyme_ab(
    angemeldeter_smoke_client: httpx.AsyncClient, ziel: Any
) -> None:
    """Die schärfste Prüfung dieser Datei.

    Die Liste der Artefakte kommt aus der angemeldeten Sitzung, der Aufruf von
    einem frischen Client ohne Cookie. Wäre eines davon versehentlich offen,
    fiele es genau hier auf - und sonst nirgends.
    """
    antwort = await angemeldeter_smoke_client.get("/module")
    if antwort.status_code == 404:
        pytest.skip("kein Gateway")

    geschuetzt = [
        e
        for e in antwort.json()
        if e.get("status") == "bereit" and e.get("zugang") != "oeffentlich"
    ]
    if not geschuetzt:
        pytest.skip("auf dieser Instanz ist kein Artefakt geschützt")

    async with httpx.AsyncClient(
        base_url=ziel.basis_url,
        timeout=ziel.timeout,
        verify=ziel.tls_pruefen,
        # Ohne das kommt der 307 von "/geraete" nach "/geraete/" zurueck und
        # nicht die Antwort, um die es hier geht.
        follow_redirects=True,
    ) as anonym:
        for eintrag in geschuetzt:
            if eintrag["zugang"] == "selbst":
                # Prueft Endpunkt fuer Endpunkt - der Wurzelpfad darf offen sein.
                continue
            code = (await anonym.get(eintrag["pfad"])).status_code
            assert code in (401, 403), (
                f"Artefakt '{eintrag['id']}' ist als '{eintrag['zugang']}' deklariert, "
                f"antwortet ohne Anmeldung aber mit {code}"
            )


# --- Allgemeines -----------------------------------------------------------


async def test_anfragekennung_wird_zurueckgegeben(smoke_client: httpx.AsyncClient) -> None:
    """Ohne sie lässt sich ein Fehlerbericht des Benutzers nicht im Log finden."""
    antwort = await smoke_client.get("/info", headers={"X-Request-ID": "rauchtest"})

    assert antwort.headers.get("X-Request-ID") == "rauchtest"


async def test_unbekannter_pfad_liefert_problem_json(smoke_client: httpx.AsyncClient) -> None:
    antwort = await smoke_client.get("/gibt-es-nicht-4711")

    assert antwort.status_code == 404
    assert "problem+json" in antwort.headers.get("content-type", "")
    assert antwort.json()["title"]
