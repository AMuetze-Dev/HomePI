"""homepi new - erzeugt Dateien, also wird gegen echte Dateien getestet."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from homepi_core.cli import scaffold
from homepi_core.cli.shell import CliFehler

GATEWAY_PYPROJECT = """\
[project]
name = "homepi-gateway"
dependencies = [
    "homepi-core",
]

[tool.uv.sources]
homepi-core = { path = "../../packages/homepi-core", editable = true }
"""

REGISTER_TS = """\
import type { ModulOberflaeche } from "./typen";

export const OBERFLAECHEN: readonly ModulOberflaeche[] = [
];

export function oberflaecheFuer(id: string) {
  return OBERFLAECHEN.find((o) => o.id === id);
}
"""

APPS_STACK = "name: apps\n\ninclude:\n  - services/gateway.yml\n\nnetworks:\n  edge:\n"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git("init", "-q", cwd=tmp_path)
    _git("remote", "add", "origin", "https://github.com/Owner/HomePI.git", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "homepi"\n', encoding="utf-8")

    gateway = tmp_path / "services" / "gateway"
    gateway.mkdir(parents=True)
    (gateway / "pyproject.toml").write_text(GATEWAY_PYPROJECT, encoding="utf-8")

    web = tmp_path / "services" / "web" / "src" / "module"
    web.mkdir(parents=True)
    (web / "register.ts").write_text(REGISTER_TS, encoding="utf-8")

    stack = tmp_path / "stacks" / "apps"
    stack.mkdir(parents=True)
    (stack / "docker-compose.yml").write_text(APPS_STACK, encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    return tmp_path


def _args(name: str, **rest: object) -> argparse.Namespace:
    grund: dict[str, object] = {
        "name": name,
        "modus": "modul",
        "titel": None,
        "beschreibung": "",
        "ziel": None,
        "port": 8000,
        "no_db": False,
        "no_web": False,
        "force": False,
    }
    return argparse.Namespace(**{**grund, **rest})


# --------------------------------------------------------------------- Modul


class TestModul:
    def test_legt_backend_und_oberflaeche_an(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte"))

        artefakt = repo / "modules" / "messwerte"
        for pfad in (
            "pyproject.toml",
            "AGENTS.md",
            "README.md",
            "src/homepi_messwerte/__init__.py",
            "src/homepi_messwerte/router.py",
            "src/homepi_messwerte/dienst.py",
            "src/homepi_messwerte/schemas.py",
            "src/homepi_messwerte/modelle.py",
            "src/homepi_messwerte/speicher.py",
            "tests/conftest.py",
            "tests/unit/test_dienst.py",
            "tests/unit/test_anmeldung.py",
            "tests/integration/test_router.py",
        ):
            assert (artefakt / pfad).is_file(), pfad

        web = repo / "services" / "web" / "src" / "module" / "messwerte"
        for pfad in (
            "api.ts",
            "MesswerteSeite.tsx",
            "MesswerteSeite.module.css",
            "MesswerteSeite.test.tsx",
        ):
            assert (web / pfad).is_file(), pfad

    def test_platzhalter_werden_vollstaendig_ersetzt(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte"))

        for wurzel in (
            repo / "modules" / "messwerte",
            repo / "services" / "web" / "src" / "module" / "messwerte",
        ):
            for datei in wurzel.rglob("*"):
                if datei.is_file():
                    inhalt = datei.read_text(encoding="utf-8")
                    assert "{{" not in inhalt, f"unersetzter Platzhalter in {datei.name}"

    def test_entry_point_traegt_die_kennung(self, repo: Path) -> None:
        # Ohne diese Zeile findet das Gateway das Modul nicht - die Kachel
        # fehlt dann kommentarlos.
        scaffold.ausfuehren(_args("messwerte"))

        projektdatei = (repo / "modules" / "messwerte" / "pyproject.toml").read_text(
            encoding="utf-8"
        )

        assert '[project.entry-points."homepi.module"]' in projektdatei
        assert 'messwerte = "homepi_messwerte:modul"' in projektdatei

    def test_bindestrich_wird_zum_unterstrich_im_modul(self, repo: Path) -> None:
        """Python-Module dürfen keinen Bindestrich enthalten."""
        scaffold.ausfuehren(_args("mess-werte"))

        assert (repo / "modules" / "mess-werte" / "src" / "homepi_mess_werte").is_dir()

    def test_komponente_bekommt_pascalcase(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("mess-werte"))

        web = repo / "services" / "web" / "src" / "module" / "mess-werte"
        assert (web / "MessWerteSeite.tsx").is_file()
        assert "export function MessWerteSeite()" in (web / "MessWerteSeite.tsx").read_text(
            encoding="utf-8"
        )

    def test_titel_laesst_sich_setzen(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte", titel="Messwerte im Haus"))

        init = (
            repo / "modules" / "messwerte" / "src" / "homepi_messwerte" / "__init__.py"
        ).read_text(encoding="utf-8")

        assert 'titel="Messwerte im Haus"' in init

    def test_titel_kommt_sonst_aus_dem_namen(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("mess-werte"))

        init = (
            repo / "modules" / "mess-werte" / "src" / "homepi_mess_werte" / "__init__.py"
        ).read_text(encoding="utf-8")

        assert 'titel="Mess werte"' in init

    def test_wird_als_abhaengigkeit_des_gateways_eingetragen(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte"))

        inhalt = (repo / "services" / "gateway" / "pyproject.toml").read_text(encoding="utf-8")

        assert '"homepi-messwerte",' in inhalt
        assert 'homepi-messwerte = { path = "../../modules/messwerte", editable = true }' in inhalt

    def test_oberflaeche_wird_im_register_eingetragen(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte"))

        inhalt = (repo / "services" / "web" / "src" / "module" / "register.ts").read_text(
            encoding="utf-8"
        )

        assert 'import { MesswerteSeite } from "./messwerte/MesswerteSeite";' in inhalt
        assert '{ id: "messwerte", Komponente: MesswerteSeite },' in inhalt
        # Der Eintrag muss INNERHALB der Liste stehen
        assert inhalt.index("OBERFLAECHEN") < inhalt.index('id: "messwerte"')
        assert inhalt.index('id: "messwerte"') < inhalt.index("];")

    def test_import_landet_hinter_den_vorhandenen(self, repo: Path) -> None:
        # An den Dateianfang geschoben stuende der neue Import vor allen
        # anderen - die Reihenfolge zerfiele mit jedem Artefakt weiter.
        register = repo / "services" / "web" / "src" / "module" / "register.ts"
        register.write_text(
            'import { AlphaSeite } from "./alpha/AlphaSeite";\n'
            'import type { ModulOberflaeche } from "./typen";\n'
            "\nexport const OBERFLAECHEN: readonly ModulOberflaeche[] = [\n];\n",
            encoding="utf-8",
        )

        scaffold.ausfuehren(_args("messwerte"))

        zeilen = register.read_text(encoding="utf-8").splitlines()
        neuer = zeilen.index('import { MesswerteSeite } from "./messwerte/MesswerteSeite";')
        assert neuer > zeilen.index('import { AlphaSeite } from "./alpha/AlphaSeite";')
        assert neuer > zeilen.index('import type { ModulOberflaeche } from "./typen";')

    def test_zweiter_aufruf_traegt_nicht_doppelt_ein(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte"))
        scaffold.ausfuehren(_args("messwerte", force=True))

        gateway = (repo / "services" / "gateway" / "pyproject.toml").read_text(encoding="utf-8")
        register = (repo / "services" / "web" / "src" / "module" / "register.ts").read_text(
            encoding="utf-8"
        )

        assert gateway.count('"homepi-messwerte",') == 1
        assert register.count('id: "messwerte"') == 1

    def test_no_web_laesst_die_oberflaeche_weg(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte", no_web=True))

        assert not (repo / "services" / "web" / "src" / "module" / "messwerte").exists()
        assert "messwerte" not in (
            repo / "services" / "web" / "src" / "module" / "register.ts"
        ).read_text(encoding="utf-8")
        # Das Backend entsteht trotzdem - die generische Ansicht reicht erst mal.
        assert (repo / "modules" / "messwerte" / "pyproject.toml").is_file()

    def test_no_db_laesst_die_persistenz_weg(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte", no_db=True))

        artefakt = repo / "modules" / "messwerte"
        assert not (artefakt / "src" / "homepi_messwerte" / "modelle.py").exists()
        assert not (artefakt / "src" / "homepi_messwerte" / "speicher.py").exists()
        assert not (artefakt / "tests" / "integration" / "test_router.py").exists()

    def test_vorhandene_dateien_werden_nicht_ueberschrieben(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte"))
        eigen = repo / "modules" / "messwerte" / "src" / "homepi_messwerte" / "dienst.py"
        eigen.write_text("# meine Arbeit\n", encoding="utf-8")

        scaffold.ausfuehren(_args("messwerte"))

        assert eigen.read_text(encoding="utf-8") == "# meine Arbeit\n"

    def test_force_ueberschreibt(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("messwerte"))
        eigen = repo / "modules" / "messwerte" / "src" / "homepi_messwerte" / "dienst.py"
        eigen.write_text("# weg damit\n", encoding="utf-8")

        scaffold.ausfuehren(_args("messwerte", force=True))

        assert "normalisiere" in eigen.read_text(encoding="utf-8")

    def test_agents_md_nennt_die_abnahmekriterien(self, repo: Path) -> None:
        # Die Datei ist der Auftrag für den Agenten - ohne Schwellen und
        # Befehle wäre sie nur Prosa.
        scaffold.ausfuehren(_args("messwerte"))

        inhalt = (repo / "modules" / "messwerte" / "AGENTS.md").read_text(encoding="utf-8")

        for erwartet in ("Abnahmekriterien", "uv run mypy", "make smoke", "homepi deploy"):
            assert erwartet in inhalt, erwartet


# ------------------------------------------------------------------- Service


class TestService:
    def test_legt_eigenstaendigen_dienst_an(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("rechenknecht", modus="service"))

        dienst = repo / "services" / "rechenknecht"
        assert (dienst / "Dockerfile").is_file()
        assert (dienst / "src" / "homepi_rechenknecht" / "main.py").is_file()
        assert (repo / "stacks" / "apps" / "services" / "rechenknecht.yml").is_file()

    def test_fragment_wird_im_stack_eingetragen(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("rechenknecht", modus="service"))

        stack = (repo / "stacks" / "apps" / "docker-compose.yml").read_text(encoding="utf-8")

        assert "  - services/rechenknecht.yml" in stack
        assert stack.index("services/rechenknecht.yml") < stack.index("networks:")

    def test_env_variable_wird_grossgeschrieben(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("mess-werte", modus="service"))

        fragment = (repo / "stacks" / "apps" / "services" / "mess-werte.yml").read_text(
            encoding="utf-8"
        )

        assert "${MESS_WERTE_IMAGE:-" in fragment

    def test_no_db_laesst_die_datenbank_weg(self, repo: Path) -> None:
        scaffold.ausfuehren(_args("ohnedb", modus="service", no_db=True))

        fragment = (repo / "stacks" / "apps" / "services" / "ohnedb.yml").read_text(
            encoding="utf-8"
        )

        assert "DATABASE_URL" not in fragment


# --------------------------------------------------------------------- Namen


@pytest.mark.parametrize("name", ["Messwerte", "1mess", "mess_werte", "mess werte", "-x"])
def test_unbrauchbare_namen_werden_abgelehnt(repo: Path, name: str) -> None:
    """Der Name landet in URLs, Image-Namen und Python-Modulen."""
    with pytest.raises(CliFehler, match="gültige Kennung"):
        scaffold.ausfuehren(_args(name))
