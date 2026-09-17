"""Welche Datenbank Integrationstests anfassen duerfen.

Sie rufen ``drop_all`` auf. Zeigt ``DATABASE_URL`` gerade auf die
Arbeitsdatenbank - und auf einem Entwicklungsrechner tut sie das die meiste
Zeit -, waere ein Testlauf der Verlust aller Konten. Genau das ist einmal
passiert.

Angesprochen wird sie ueber das Modul - so bleibt im Blick, woher sie kommt.
"""

from __future__ import annotations

import pytest

from homepi_core.testing import datenbank as td


class TestTestdatenbank:
    """Integrationstests rufen drop_all auf. Zeigt DATABASE_URL auf die
    Arbeitsdatenbank, waere ein Testlauf der Verlust aller Konten."""

    def test_die_eigene_variable_hat_vorrang(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app:app@h/app")
        monkeypatch.setenv(td.VARIABLE, "postgresql+asyncpg://app:app@h/test")

        assert td.datenbank_fuer_tests().endswith("/test")

    def test_ohne_sie_gilt_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(td.VARIABLE, raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app:app@h/geraete_test")

        assert td.datenbank_fuer_tests().endswith("/geraete_test")

    def test_ohne_beides_die_voreinstellung(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(td.VARIABLE, raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        assert td.datenbank_fuer_tests() == td.STANDARD

    def test_die_arbeitsdatenbank_wird_abgelehnt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(td.VARIABLE, raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app:app@h/app")

        with pytest.raises(td.FalscheDatenbank, match="Testdatenbank"):
            td.datenbank_fuer_tests()

    def test_die_meldung_sagt_was_zu_tun_ist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(td.VARIABLE, raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app:app@h/app")

        with pytest.raises(td.FalscheDatenbank, match=td.VARIABLE):
            td.datenbank_fuer_tests()

    @pytest.mark.parametrize("name", ["test", "app_test", "geraete_test"])
    def test_erlaubte_namen(self, name: str) -> None:
        assert td.ist_testdatenbank(f"postgresql+asyncpg://app:app@h/{name}")

    @pytest.mark.parametrize("name", ["app", "produktion", "testdaten", "homeassistant"])
    def test_abgelehnte_namen(self, name: str) -> None:
        # "testdaten" faengt zwar mit test an, ist aber keine Testdatenbank -
        # die Regel ist bewusst eng.
        assert not td.ist_testdatenbank(f"postgresql+asyncpg://app:app@h/{name}")

    def test_eine_query_stoert_nicht(self) -> None:
        assert td.ist_testdatenbank("postgresql+asyncpg://app:app@h/test?ssl=require")
