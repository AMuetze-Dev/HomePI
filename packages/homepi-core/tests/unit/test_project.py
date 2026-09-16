"""Projekterkennung der CLI. Arbeitet mit echten Wegwerf-Repos statt Mocks -
die Logik haengt an git, und ein nachgebautes git waere kein Test."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from homepi_core.cli.project import projekt_ermitteln
from homepi_core.cli.shell import CliFehler


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git("init", "-q", cwd=tmp_path)
    _git("remote", "add", "origin", "https://github.com/Owner/HomePI.git", cwd=tmp_path)
    return tmp_path


def test_service_kommt_aus_tool_homepi(repo: Path) -> None:
    dienst = repo / "services" / "geraete"
    dienst.mkdir(parents=True)
    (dienst / "pyproject.toml").write_text(
        '[project]\nname = "irgendwas"\nversion = "1.2.3"\n'
        '[tool.homepi]\nservice = "geraete"\nstack = "apps"\n',
        encoding="utf-8",
    )

    projekt = projekt_ermitteln(dienst)

    assert projekt.service == "geraete"
    assert projekt.version == "1.2.3"
    assert projekt.stack == "apps"


def test_ohne_tool_homepi_zaehlt_der_projektname(repo: Path) -> None:
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "homepi-messwerte"\nversion = "0.1.0"\n', encoding="utf-8"
    )

    # Der Praefix steckt schon im Image-Namen und wuerde sonst doppelt auftauchen
    assert projekt_ermitteln(repo).service == "messwerte"


def test_remote_wird_zu_owner_name(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")

    projekt = projekt_ermitteln(repo)

    assert projekt.repo == "Owner/HomePI"
    assert projekt.image == "ghcr.io/owner/homepi-x"


def test_ssh_remote_wird_genauso_erkannt(tmp_path: Path) -> None:
    _git("init", "-q", cwd=tmp_path)
    _git("remote", "add", "origin", "git@github.com:Owner/HomePI.git", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")

    assert projekt_ermitteln(tmp_path).repo == "Owner/HomePI"


def test_ausserhalb_eines_repos_gibt_es_eine_klare_meldung(tmp_path: Path) -> None:
    with pytest.raises(CliFehler, match="Git-Repository"):
        projekt_ermitteln(tmp_path)


def test_service_laesst_sich_ueberschreiben(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")

    assert projekt_ermitteln(repo, service="anders").service == "anders"
