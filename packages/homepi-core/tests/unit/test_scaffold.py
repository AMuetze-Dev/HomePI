"""homepi new - erzeugt Dateien, also wird gegen echte Dateien getestet."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from homepi_core.cli import scaffold
from homepi_core.cli.shell import CliFehler


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git("init", "-q", cwd=tmp_path)
    _git("remote", "add", "origin", "https://github.com/Owner/HomePI.git", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "homepi"\n', encoding="utf-8")

    stack = tmp_path / "stacks" / "apps"
    stack.mkdir(parents=True)
    (stack / "docker-compose.yml").write_text(
        "name: apps\n\ninclude:\n  - services/api.yml\n\nnetworks:\n  edge:\n    external: true\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    return tmp_path


def _args(name: str, **rest: object) -> argparse.Namespace:
    grund = {"name": name, "ziel": None, "port": 8000, "no_db": False, "force": False}
    return argparse.Namespace(**{**grund, **rest})


def test_legt_die_erwarteten_dateien_an(repo: Path) -> None:
    scaffold.ausfuehren(_args("geraete"))

    dienst = repo / "services" / "geraete"
    for pfad in (
        "pyproject.toml",
        "Dockerfile",
        "README.md",
        "src/homepi_geraete/main.py",
        "src/homepi_geraete/settings.py",
        "src/homepi_geraete/__init__.py",
        "tests/conftest.py",
        "tests/unit/test_service.py",
    ):
        assert (dienst / pfad).is_file(), pfad


def test_platzhalter_werden_vollstaendig_ersetzt(repo: Path) -> None:
    scaffold.ausfuehren(_args("geraete"))

    dienst = repo / "services" / "geraete"
    for datei in dienst.rglob("*"):
        if datei.is_file():
            inhalt = datei.read_text(encoding="utf-8")
            assert "{{" not in inhalt, f"unersetzter Platzhalter in {datei.name}"


def test_bindestrich_wird_zum_unterstrich_im_modul(repo: Path) -> None:
    """Python-Module duerfen keinen Bindestrich enthalten."""
    scaffold.ausfuehren(_args("mess-werte"))

    assert (repo / "services" / "mess-werte" / "src" / "homepi_mess_werte").is_dir()


def test_env_variable_wird_grossgeschrieben(repo: Path) -> None:
    scaffold.ausfuehren(_args("mess-werte"))

    fragment = (repo / "stacks" / "apps" / "services" / "mess-werte.yml").read_text(
        encoding="utf-8"
    )

    assert "${MESS_WERTE_IMAGE:-" in fragment


def test_fragment_wird_im_stack_eingetragen(repo: Path) -> None:
    scaffold.ausfuehren(_args("geraete"))

    stack = (repo / "stacks" / "apps" / "docker-compose.yml").read_text(encoding="utf-8")

    assert "  - services/api.yml" in stack
    assert "  - services/geraete.yml" in stack
    # nach der include-Liste darf nichts durcheinandergeraten sein
    assert stack.index("services/geraete.yml") < stack.index("networks:")


def test_zweiter_aufruf_traegt_nicht_doppelt_ein(repo: Path) -> None:
    scaffold.ausfuehren(_args("geraete"))
    scaffold.ausfuehren(_args("geraete", force=True))

    stack = (repo / "stacks" / "apps" / "docker-compose.yml").read_text(encoding="utf-8")

    assert stack.count("services/geraete.yml") == 1


def test_no_db_laesst_die_datenbank_weg(repo: Path) -> None:
    scaffold.ausfuehren(_args("ohnedb", no_db=True))

    fragment = (repo / "stacks" / "apps" / "services" / "ohnedb.yml").read_text(encoding="utf-8")

    assert "DATABASE_URL" not in fragment


def test_vorhandene_dateien_werden_nicht_ueberschrieben(repo: Path) -> None:
    scaffold.ausfuehren(_args("geraete"))
    eigen = repo / "services" / "geraete" / "src" / "homepi_geraete" / "main.py"
    eigen.write_text("# meine Arbeit\n", encoding="utf-8")

    scaffold.ausfuehren(_args("geraete"))

    assert eigen.read_text(encoding="utf-8") == "# meine Arbeit\n"


def test_force_ueberschreibt(repo: Path) -> None:
    scaffold.ausfuehren(_args("geraete"))
    eigen = repo / "services" / "geraete" / "src" / "homepi_geraete" / "main.py"
    eigen.write_text("# weg damit\n", encoding="utf-8")

    scaffold.ausfuehren(_args("geraete", force=True))

    assert "create_service" in eigen.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["Geraete", "1geraete", "geraete_x", "ger aete", "-x"])
def test_unbrauchbare_namen_werden_abgelehnt(repo: Path, name: str) -> None:
    """Der Name landet in Hostnamen, Image-Namen und Python-Modulen."""
    with pytest.raises(CliFehler, match="gültiger Servicename"):
        scaffold.ausfuehren(_args(name))
