"""Die Lazy-Fassade von homepi_core.

Ohne diese Tests faellt ein Tippfehler in _HERKUNFT erst auf, wenn jemand den
betroffenen Namen zum ersten Mal benutzt - moeglicherweise in Produktion.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

import homepi_core


def test_all_und_herkunft_stimmen_ueberein() -> None:
    assert set(homepi_core.__all__) - {"__version__"} == set(homepi_core._HERKUNFT)


@pytest.mark.parametrize("name", sorted(homepi_core._HERKUNFT))
def test_jeder_export_ist_erreichbar(name: str) -> None:
    assert getattr(homepi_core, name) is not None


def test_unbekannter_name_wirft_attributeerror() -> None:
    with pytest.raises(AttributeError, match="gibtsnicht"):
        _ = homepi_core.gibtsnicht  # type: ignore[attr-defined]


def test_dir_nennt_die_exporte() -> None:
    assert "create_service" in dir(homepi_core)


def test_import_zieht_fastapi_nicht_mit() -> None:
    """Der Grund fuer die Lazy-Fassade: 'homepi deploy' braucht kein FastAPI,
    und das pytest-Plugin wird vor der Coverage-Messung geladen."""
    quelltext = (
        "import sys, homepi_core;print('fastapi' in sys.modules, 'sqlalchemy' in sys.modules)"
    )
    ergebnis = subprocess.run(
        [sys.executable, "-c", quelltext], capture_output=True, text=True, check=True
    )

    assert ergebnis.stdout.strip() == "False False"


def test_zugriff_laedt_nach_und_merkt_sich_das() -> None:
    """In einem eigenen Prozess, weil importlib.reload das Modul-Dict behaelt
    und die Frage 'war es vorher schon da?' damit nicht beantwortbar waere."""
    quelltext = (
        "import homepi_core as h;"
        "vorher = 'create_service' in h.__dict__;"
        "_ = h.create_service;"
        "nachher = 'create_service' in h.__dict__;"
        "print(vorher, nachher)"
    )
    ergebnis = subprocess.run(
        [sys.executable, "-c", quelltext], capture_output=True, text=True, check=True
    )

    assert ergebnis.stdout.strip() == "False True"
