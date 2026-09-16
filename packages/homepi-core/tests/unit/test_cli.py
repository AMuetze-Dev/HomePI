"""CLI-Verdrahtung: Argumente, Rückgabecodes, Trockenlauf."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from homepi_core.cli import deploy, main, shell


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git("init", "-q", cwd=tmp_path)
    _git("remote", "add", "origin", "https://github.com/Owner/HomePI.git", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "homepi-geraete"\nversion = "1.0.0"\n'
        '[tool.homepi]\nservice = "geraete"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_ohne_befehl_gibt_es_hilfe_und_code_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert main.main([]) == 1
    assert "homepi deploy" in capsys.readouterr().out


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    from homepi_core import __version__

    assert main.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_info_zeigt_den_service(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main.main(["info"]) == 0

    ausgabe = capsys.readouterr().out
    assert "geraete" in ausgabe
    assert "ghcr.io/owner/homepi-geraete" in ausgabe


def test_info_ausserhalb_eines_repos_meldet_verstaendlich(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main.main(["info"]) == 1
    assert "Git-Repository" in capsys.readouterr().err


def test_dry_run_stoesst_nichts_an(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Der Trockenlauf darf weder gh aufrufen noch die Pipeline anfassen."""
    aufrufe: list[tuple[str, ...]] = []

    def gefaelscht(*befehl: str, cwd: str | None = None, pflicht: bool = True) -> shell.Ergebnis:
        aufrufe.append(befehl)
        return shell.Ergebnis(0, "", "")

    monkeypatch.setattr(deploy, "lauf", gefaelscht)

    assert main.main(["deploy", "--dry-run"]) == 0

    assert not any(b[0] == "gh" and "workflow" in b for b in aufrufe)
    ausgabe = capsys.readouterr().out
    assert "gh workflow run images.yml" in ausgabe
    assert "-f service=geraete" in ausgabe


def test_deploy_bricht_bei_ungespeicherten_aenderungen_ab(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Gebaut wird der Stand auf GitHub - ein schmutziges Arbeitsverzeichnis
    würde etwas anderes ausrollen, als der Benutzer gerade sieht."""

    def gefaelscht(*befehl: str, cwd: str | None = None, pflicht: bool = True) -> shell.Ergebnis:
        if befehl[:2] == ("git", "status"):
            return shell.Ergebnis(0, " M src/main.py", "")
        return shell.Ergebnis(0, "", "")

    monkeypatch.setattr(deploy, "lauf", gefaelscht)

    assert main.main(["deploy"]) == 1
    assert "ungespeicherte Änderungen" in capsys.readouterr().err


def test_deploy_verlangt_angemeldetes_gh(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def gefaelscht(*befehl: str, cwd: str | None = None, pflicht: bool = True) -> shell.Ergebnis:
        if befehl[:3] == ("gh", "auth", "status"):
            return shell.Ergebnis(1, "", "nicht angemeldet")
        return shell.Ergebnis(0, "", "")

    monkeypatch.setattr(deploy, "lauf", gefaelscht)

    assert main.main(["deploy"]) == 1
    assert "gh auth login" in capsys.readouterr().err


def test_fehlendes_programm_meldet_sich_deutlich() -> None:
    with pytest.raises(shell.CliFehler, match="nicht installiert"):
        shell.lauf("dieses-programm-gibt-es-nicht")


def test_lauf_kann_fehler_durchreichen() -> None:
    ergebnis = shell.lauf("git", "rev-parse", "--verify", "diesen-ref-gibt-es-nicht", pflicht=False)

    assert ergebnis.erfolg is False
