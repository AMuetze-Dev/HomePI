"""Der Vergleich zwischen Modellen und Datenbank.

Er entstand aus einem Fehler, der lautlos war: ``create_all`` legt fehlende
Tabellen an und rührt vorhandene nicht an. Eine neue Spalte fehlt danach - und
jede Abfrage auf diese Tabelle scheitert. Die Tabelle ist ja da, also meldete
das alte Werkzeug "alles vorhanden".
"""

from __future__ import annotations

import pytest

from homepi_core.schema import Schemastand, _vergleiche, erwartet


class _Pruefer:
    """Ein Inspector, der antwortet, was der Test vorgibt."""

    def __init__(self, tabellen: dict[str, list[str]]) -> None:
        self._tabellen = tabellen

    def get_table_names(self) -> list[str]:
        return list(self._tabellen)

    def get_columns(self, name: str) -> list[dict[str, str]]:
        return [{"name": spalte} for spalte in self._tabellen[name]]


ERWARTUNG = {"benutzer": {"id", "name", "passwort_wechseln"}, "geraete": {"id", "raum"}}


class TestVergleich:
    def test_alles_da(self) -> None:
        stand = _vergleiche(
            ERWARTUNG,
            _Pruefer({"benutzer": ["id", "name", "passwort_wechseln"], "geraete": ["id", "raum"]}),
        )

        assert stand.vollstaendig
        assert stand.als_meldung() == "Schema vollständig."

    def test_fehlende_tabelle(self) -> None:
        stand = _vergleiche(ERWARTUNG, _Pruefer({"benutzer": ["id", "name", "passwort_wechseln"]}))

        assert stand.fehlende_tabellen == ["geraete"]
        assert not stand.vollstaendig
        # Der harmlose Fall: eine frische Datenbank laesst sich anlegen.
        assert stand.nur_tabellen_fehlen

    def test_fehlende_spalte(self) -> None:
        """Der Fall, der frueher durchging."""
        stand = _vergleiche(
            ERWARTUNG, _Pruefer({"benutzer": ["id", "name"], "geraete": ["id", "raum"]})
        )

        assert stand.fehlende_tabellen == []
        assert stand.fehlende_spalten == {"benutzer": ["passwort_wechseln"]}
        assert not stand.vollstaendig
        assert not stand.nur_tabellen_fehlen

    def test_eine_spalte_zu_viel_stoert_nicht(self) -> None:
        """Eine Spalte, die kein Modell kennt, ist kein Fehler - sie kann aus
        einer aelteren Fassung stammen und tut niemandem weh."""
        stand = _vergleiche(
            ERWARTUNG,
            _Pruefer(
                {
                    "benutzer": ["id", "name", "passwort_wechseln", "uralt"],
                    "geraete": ["id", "raum"],
                }
            ),
        )

        assert stand.vollstaendig

    def test_eine_tabelle_zu_viel_auch_nicht(self) -> None:
        stand = _vergleiche(
            ERWARTUNG,
            _Pruefer(
                {
                    "benutzer": ["id", "name", "passwort_wechseln"],
                    "geraete": ["id", "raum"],
                    "alembic_version": ["version_num"],
                }
            ),
        )

        assert stand.vollstaendig

    def test_beides_zugleich(self) -> None:
        stand = _vergleiche(ERWARTUNG, _Pruefer({"benutzer": ["id"]}))

        assert stand.fehlende_tabellen == ["geraete"]
        assert stand.fehlende_spalten == {"benutzer": ["name", "passwort_wechseln"]}


class TestMeldung:
    def test_nennt_die_fehlende_spalte_mitsamt_tabelle(self) -> None:
        """Ohne den Tabellennamen weiss niemand, wo er migrieren soll."""
        stand = Schemastand(fehlende_spalten={"benutzer": ["passwort_wechseln"]})

        assert "benutzer" in stand.als_meldung()
        assert "passwort_wechseln" in stand.als_meldung()

    def test_nennt_fehlende_tabellen(self) -> None:
        stand = Schemastand(fehlende_tabellen=["geraete", "sitzungen"])

        assert "geraete" in stand.als_meldung()
        assert "sitzungen" in stand.als_meldung()


def test_erwartet_kennt_die_tabellen_der_anmeldung() -> None:
    """Sie kommen aus homepi-core selbst und nicht aus einem Artefakt."""
    import homepi_core.auth.modelle  # noqa: F401  (registriert die Tabellen)

    tabellen = erwartet()

    assert "passwort_wechseln" in tabellen["benutzer"]
    assert {"benutzer", "benutzer_rechte", "sitzungen", "einrichtung"} <= set(tabellen)


@pytest.mark.parametrize("name", ["benutzer", "sitzungen"])
def test_jede_tabelle_hat_spalten(name: str) -> None:
    import homepi_core.auth.modelle  # noqa: F401

    assert erwartet()[name]
