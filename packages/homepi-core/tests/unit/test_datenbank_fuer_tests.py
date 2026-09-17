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


class TestEigeneDatenbankJeLauf:
    """Jeder Lauf schreibt in eine frisch angelegte Datenbank.

    Eine gemeinsame "test" ueberlebt den Lauf. Was ein abgebrochener Durchgang
    liegen laesst, sieht der naechste - und ein Test, der nur wegen eines
    Restes gruen ist, ist schlimmer als ein roter.
    """

    def test_der_name_kommt_vom_projekt(self) -> None:
        assert td.name_fuer("homepi-core") == "homepi_core_test"
        assert td.name_fuer("geraete") == "geraete_test"

    def test_der_name_endet_immer_auf_die_nachsilbe(self) -> None:
        # Sonst wuerde die eigene Datenbank an der Pruefung scheitern, die sie
        # gerade schuetzen soll.
        for kennung in ["Verwaltung", "web-ui", "a.b.c", "schon_test"]:
            assert td.name_fuer(kennung).endswith(td.NACHSILBE)

    def test_aus_test_wird_nicht_test_test(self) -> None:
        assert td.name_fuer("geraete_test") == "geraete_test"

    def test_ein_leerer_oder_seltsamer_name_bekommt_einen(self) -> None:
        assert td.name_fuer("---") == "homepi_test"
        assert td.name_fuer("42") == "homepi_42_test"

    def test_postgres_grenze_wird_eingehalten(self) -> None:
        assert len(td.name_fuer("x" * 200)) <= td.NAMENSLAENGE

    def test_die_verbindung_bleibt_bis_auf_die_datenbank_gleich(self) -> None:
        url = "postgresql+asyncpg://app:geheim@127.0.0.1:15432/test"

        assert td.mit_datenbank(url, "geraete_test").endswith(
            "app:geheim@127.0.0.1:15432/geraete_test"
        )

    def test_eine_query_bleibt_erhalten(self) -> None:
        url = "postgresql+asyncpg://app:app@h/test?ssl=require"

        assert (
            td.mit_datenbank(url, "x_test") == "postgresql+asyncpg://app:app@h/x_test?ssl=require"
        )

    def test_asyncpg_bekommt_die_url_ohne_treiber(self) -> None:
        # asyncpg kennt "postgresql+asyncpg" nicht - das ist ein Schema von
        # SQLAlchemy.
        assert td.dsn("postgresql+asyncpg://app:app@h/test") == "postgresql://app:app@h/test"
        assert td.dsn("postgresql://app:app@h/test") == "postgresql://app:app@h/test"

    @pytest.mark.parametrize(
        "name",
        ['boes"; DROP DATABASE app; --_test', "Gross_test", "app", "_test", "geraete"],
    )
    def test_nur_harmlose_namen_kommen_in_ein_sql_kommando(self, name: str) -> None:
        # Der Name stammt aus einem Verzeichnisnamen und laesst sich nicht als
        # Parameter binden - also wird er geprueft, bevor er eingesetzt wird.
        with pytest.raises(td.FalscheDatenbank):
            td.pruefe_name(name)

    def test_was_name_fuer_erzeugt_kommt_durch(self) -> None:
        for kennung in ["homepi-core", "Verwaltung", "web ui", "42", "---"]:
            td.pruefe_name(td.name_fuer(kennung))

    def test_der_schalter_laesst_sich_umlegen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(td.SCHALTER, raising=False)
        assert not td.abgeschaltet()

        monkeypatch.setenv(td.SCHALTER, "0")
        assert td.abgeschaltet()
