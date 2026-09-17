"""pytest-Plugin. Wird über den Entry Point ``pytest11`` automatisch geladen,
sobald ``homepi-core[test]`` installiert ist - kein ``pytest_plugins`` nötig.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import httpx

    from .datenbank import Lauf
    from .ziel import Ziel

# Absichtlich KEIN Import auf Modulebene ausser pytest und asyncio: dieses
# Modul wird ueber den pytest11-Entry-Point beim Start JEDES Projekts geladen,
# das homepi-core[test] installiert hat. Httpx, asyncpg und die Zielaufloesung
# kommen erst, wenn sie wirklich gebraucht werden.

#: Der Lauf, zu dem die angelegte Datenbank gehoert. Modulweit, weil
#: pytest_configure und pytest_sessionfinish sich nichts uebergeben koennen.
_lauf: Lauf | None = None


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "smoke: spricht mit einer laufenden Instanz (HOMEPI_ZIEL / HOMEPI_BASIS_URL)",
    )
    _datenbank_vorbereiten(config)


def pytest_report_header() -> list[str]:
    """Sagt im Kopf des Laufs, wohin geschrieben wird.

    Ohne das muesste man raten, ob dieser Lauf gerade eine eigene Datenbank
    benutzt oder die vorgegebene - und genau diese Frage war der Grund fuer
    das Ganze.
    """
    if _lauf is None:
        return []
    return [f"Testdatenbank: {_lauf.name} (neu angelegt, wird am Ende weggeworfen)"]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    # Bei rotem Lauf bleibt sie stehen: dann will man hineinsehen koennen. Der
    # naechste Lauf legt sie ohnehin neu an, es haeuft sich also nichts an.
    _datenbank_abraeumen(behalten=exitstatus != 0)


def pytest_unconfigure(config: pytest.Config) -> None:
    # Netz fuer den Fall, dass die Sitzung gar nicht erst zustande kam.
    _datenbank_abraeumen(behalten=True)


def _datenbank_vorbereiten(config: pytest.Config) -> None:
    """Legt fuer diesen Lauf eine eigene Datenbank an und stellt sie ein.

    Hier und nicht in einer Fixture: die Integrationstests halten die URL als
    Modulkonstante, und die steht schon beim Einlesen der Testdatei fest -
    lange bevor die erste Fixture laeuft.
    """
    global _lauf
    import os

    from .datenbank import VARIABLE, Lauf, abgeschaltet, anlegen, datenbank_fuer_tests, name_fuer

    if abgeschaltet() or not _braucht_datenbank(config):
        return

    # Laeuft die Umgebung auf eine Arbeitsdatenbank, soll das hier abbrechen
    # und nicht erst beim ersten drop_all.
    vorlage = datenbank_fuer_tests()
    name = name_fuer(config.rootpath.name)

    try:
        url = asyncio.run(anlegen(vorlage, name))
    except Exception as problem:
        # Kein Abbruch: ohne erreichbare Postgres laeuft dieser Lauf genau so
        # wie vor dieser Erweiterung - gegen die vorgegebene Datenbank. Die
        # Integrationstests scheitern dann mit ihrer eigenen, deutlicheren
        # Meldung, und Unit-Tests brauchen ueberhaupt keine Datenbank.
        config.issue_config_time_warning(
            pytest.PytestWarning(
                f"Eigene Testdatenbank '{name}' liess sich nicht anlegen ({problem}). "
                f"Dieser Lauf benutzt '{vorlage.rsplit('/', 1)[-1]}'."
            ),
            stacklevel=1,
        )
        return

    _lauf = Lauf(vorlage=vorlage, name=name, url=url, vorher=os.environ.get(VARIABLE))
    os.environ[VARIABLE] = url


def _datenbank_abraeumen(*, behalten: bool) -> None:
    """Stellt die vorherige Datenbank wieder ein und raeumt die eigene weg."""
    global _lauf
    import os

    from .datenbank import VARIABLE, wegwerfen

    if _lauf is None or not _lauf.offen:
        return
    _lauf.offen = False

    if _lauf.vorher is None:
        os.environ.pop(VARIABLE, None)
    else:
        os.environ[VARIABLE] = _lauf.vorher

    if behalten:
        print(f"\nTestdatenbank '{_lauf.name}' bleibt stehen - zum Hineinsehen:\n  {_lauf.url}")
        return

    try:
        asyncio.run(wegwerfen(_lauf.vorlage, _lauf.name))
    # Aufraeumen darf keinen Lauf umwerfen - auch nicht einen gruenen.
    except Exception as problem:
        print(f"\nTestdatenbank '{_lauf.name}' liess sich nicht wegwerfen: {problem}")


def _braucht_datenbank(config: pytest.Config) -> bool:
    """Ob dieser Lauf ueberhaupt eine Datenbank anfassen kann.

    ``-m smoke`` waehlt ausschliesslich die Tests, die mit einer laufenden
    Instanz sprechen. Die haben ihre eigene Datenbank - hier eine anzulegen
    waere ein Zugriff auf fremdes Gebiet, und auf dem Pi scheitert er.
    """
    return (config.option.markexpr or "").strip() != "smoke"


@pytest.fixture(scope="session")
def testdatenbank() -> str:
    """Die URL, gegen die Integrationstests laufen duerfen.

    Das ist die zu Beginn des Laufs angelegte, leere Datenbank - oder, falls
    sich keine anlegen liess, die vorgegebene. In beiden Faellen bricht sie
    ab, wenn die Umgebung auf eine Arbeitsdatenbank zeigt.
    """
    from .datenbank import datenbank_fuer_tests

    return datenbank_fuer_tests()


@pytest.fixture(scope="session")
def ziel() -> Ziel:
    from .ziel import ziel_aus_umgebung

    return ziel_aus_umgebung()


@pytest.fixture
async def smoke_client(ziel: Ziel) -> AsyncIterator[httpx.AsyncClient]:
    """Client gegen das konfigurierte Ziel.

    Läuft dort nichts, scheitert der Test mit einer Meldung, die den Grund
    nennt - nicht mit einem nackten ConnectError, den man erst zuordnen muss.
    """
    import httpx

    async with httpx.AsyncClient(
        base_url=ziel.basis_url,
        timeout=ziel.timeout,
        verify=ziel.tls_pruefen,
        follow_redirects=True,
    ) as client:
        try:
            await client.get("/health")
        except httpx.ConnectError as problem:
            pytest.fail(
                f"Ziel '{ziel.name}' ({ziel.basis_url}) ist nicht erreichbar: {problem}\n"
                "Lokal starten:  uv run uvicorn <modul>:app\n"
                "Anderes Ziel:   HOMEPI_ZIEL=pi pytest -m smoke"
            )
        yield client


@pytest.fixture
async def angemeldeter_smoke_client(
    smoke_client: httpx.AsyncClient,
) -> AsyncIterator[httpx.AsyncClient]:
    """Wie ``smoke_client``, aber angemeldet.

    Seit Artefakte je Benutzer sichtbar sind, sagt ein anonymes ``GET /module``
    nichts mehr über den Zustand der Instanz: es ist berechtigterweise leer.
    Ohne Konto überspringen sich die betroffenen Tests deshalb ausdrücklich,
    statt auf einer leeren Liste stillschweigend grün zu werden.

        HOMEPI_SMOKE_BENUTZER=rauchtest HOMEPI_SMOKE_PASSWORT=… pytest -m smoke
    """
    import os

    name = os.environ.get("HOMEPI_SMOKE_BENUTZER", "").strip()
    passwort = os.environ.get("HOMEPI_SMOKE_PASSWORT", "")
    if not name or not passwort:
        pytest.skip(
            "HOMEPI_SMOKE_BENUTZER/HOMEPI_SMOKE_PASSWORT nicht gesetzt - "
            "ohne Konto sind die Artefakte erwartungsgemäß unsichtbar"
        )

    antwort = await smoke_client.post("/auth/anmelden", json={"name": name, "passwort": passwort})
    if antwort.status_code != 200:
        pytest.fail(
            f"Anmeldung als '{name}' scheiterte mit {antwort.status_code}. "
            "Konto anlegen: homepi benutzer anlegen <name> --passwort-stdin"
        )

    yield smoke_client

    await smoke_client.post("/auth/abmelden")
