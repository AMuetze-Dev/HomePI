"""Zielaufloesung - die eine Stellschraube, mit der dieselben Tests lokal,
in der CI und gegen den Pi laufen."""

from __future__ import annotations

from pathlib import Path

import pytest

from homepi_core.testing import Ziel, ziel_aus_umgebung, ziele_lesen

KONFIG = """\
[ziele.standard]
basis_url = "http://127.0.0.1:8000"

[ziele.pi]
basis_url = "https://api.home.example.com/"
timeout = 10
tls_pruefen = true

[ziele.kaputt]
timeout = 3
"""


@pytest.fixture
def projekt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "homepi.toml").write_text(KONFIG, encoding="utf-8")
    for name in ("HOMEPI_ZIEL", "HOMEPI_BASIS_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_liest_die_ziele(projekt: Path) -> None:
    ziele = ziele_lesen(projekt)

    assert set(ziele) == {"standard", "pi"}
    assert ziele["pi"].timeout == 10


def test_abschliessender_schraegstrich_faellt_weg(projekt: Path) -> None:
    """Sonst entstehen Pfade wie https://host//health."""
    assert ziele_lesen(projekt)["pi"].basis_url == "https://api.home.example.com"


def test_eintrag_ohne_basis_url_wird_uebergangen(projekt: Path) -> None:
    assert "kaputt" not in ziele_lesen(projekt)


def test_ohne_angabe_gilt_standard(projekt: Path) -> None:
    assert ziel_aus_umgebung(projekt).name == "standard"


def test_homepi_ziel_waehlt_aus(projekt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMEPI_ZIEL", "pi")

    assert ziel_aus_umgebung(projekt).basis_url == "https://api.home.example.com"


def test_unbekanntes_ziel_nennt_die_bekannten(
    projekt: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMEPI_ZIEL", "mond")

    with pytest.raises(RuntimeError, match="pi, standard"):
        ziel_aus_umgebung(projekt)


def test_basis_url_schlaegt_alles_andere(projekt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMEPI_ZIEL", "pi")
    monkeypatch.setenv("HOMEPI_BASIS_URL", "http://localhost:9999")

    assert ziel_aus_umgebung(projekt).basis_url == "http://localhost:9999"


def test_ohne_konfigdatei_gibt_es_einen_notnagel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("HOMEPI_ZIEL", "HOMEPI_BASIS_URL"):
        monkeypatch.delenv(name, raising=False)

    ziel = ziel_aus_umgebung(tmp_path)

    assert ziel.name == "notnagel"
    assert ziel.ist_lokal is True


def test_konfig_wird_auch_im_unterverzeichnis_gefunden(projekt: Path) -> None:
    tief = projekt / "services" / "api" / "tests"
    tief.mkdir(parents=True)

    assert ziel_aus_umgebung(tief).name == "standard"


def test_pi_gilt_nicht_als_lokal() -> None:
    assert Ziel(name="pi", basis_url="https://api.home.example.com").ist_lokal is False
