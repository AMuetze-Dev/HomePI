from __future__ import annotations

import asyncio

import pytest

from homepi_core.health import HealthRegistry, Status, evaluate

ESSENZIELL = frozenset({"database"})


def test_alles_gesund_ist_ok() -> None:
    bericht = evaluate({"database": True, "cache": True}, ESSENZIELL)

    assert bericht.status is Status.OK
    assert bericht.http_status == 200


def test_essenzielles_kaputt_ist_down() -> None:
    bericht = evaluate({"database": False, "cache": True}, ESSENZIELL)

    assert bericht.status is Status.DOWN
    assert bericht.http_status == 503


def test_nebensaechliches_kaputt_ist_degraded() -> None:
    bericht = evaluate({"database": True, "cache": False}, ESSENZIELL)

    assert bericht.status is Status.DEGRADED
    assert bericht.http_status == 503


def test_leere_pruefung_ist_ein_programmierfehler() -> None:
    with pytest.raises(ValueError, match="mindestens eine"):
        evaluate({}, ESSENZIELL)


def test_bericht_ist_unveraenderlich() -> None:
    bericht = evaluate({"database": True}, ESSENZIELL)

    with pytest.raises(AttributeError):
        bericht.status = Status.DOWN  # type: ignore[misc]


# --- Registry --------------------------------------------------------------


async def test_registry_ohne_sonden_ist_gesund() -> None:
    assert (await HealthRegistry().run()).status is Status.OK


async def test_registry_fuehrt_sonden_aus() -> None:
    registry = HealthRegistry()

    async def ja() -> bool:
        return True

    async def nein() -> bool:
        return False

    registry.register("database", ja)
    registry.register("cache", nein, essential=False)

    bericht = await registry.run()

    assert bericht.status is Status.DEGRADED
    assert bericht.checks == {"database": True, "cache": False}


async def test_werfende_sonde_zaehlt_als_nein() -> None:
    """Ein Healthcheck, der eine Exception durchlaesst, ist kein Healthcheck."""
    registry = HealthRegistry()

    async def explodiert() -> bool:
        raise RuntimeError("Verbindung weg")

    registry.register("database", explodiert)

    assert (await registry.run()).status is Status.DOWN


async def test_haengende_sonde_laeuft_in_den_timeout() -> None:
    registry = HealthRegistry()

    async def haengt() -> bool:
        await asyncio.sleep(10)
        return True

    registry.register("database", haengt)

    bericht = await registry.run(timeout=0.05)

    assert bericht.status is Status.DOWN


async def test_sonden_laufen_nebenlaeufig() -> None:
    """Sonst waere die Gesamtdauer die Summe aller Sonden - bei drei
    Abhaengigkeiten mit je fuenf Sekunden Timeout waeren das fuenfzehn."""
    registry = HealthRegistry()

    async def langsam() -> bool:
        await asyncio.sleep(0.1)
        return True

    for name in ("a", "b", "c"):
        registry.register(name, langsam)

    start = asyncio.get_running_loop().time()
    await registry.run()
    dauer = asyncio.get_running_loop().time() - start

    assert dauer < 0.25, f"lief offenbar nacheinander ({dauer:.2f}s)"


def test_doppelte_registrierung_faellt_auf() -> None:
    registry = HealthRegistry()

    async def probe() -> bool:
        return True

    registry.register("db", probe)
    with pytest.raises(ValueError, match="bereits registriert"):
        registry.register("db", probe)
