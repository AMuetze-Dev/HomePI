"""Die gemeinsame Tabellenbasis aller Module."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from homepi_core import Base, ZeitstempelMixin


class Beispiel(Base, ZeitstempelMixin):
    __tablename__ = "beispiel_modelle_test"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


def test_tabelle_landet_in_der_gemeinsamen_metadata() -> None:
    """Genau darauf beruht, dass das Gateway alle Tabellen in einem Durchgang
    anlegen kann - mit je eigener Base muesste es jedes Modul einzeln kennen."""
    assert "beispiel_modelle_test" in Base.metadata.tables


def test_zeitstempel_werden_ergaenzt() -> None:
    spalten = Base.metadata.tables["beispiel_modelle_test"].columns

    assert "angelegt" in spalten
    assert "geaendert" in spalten


def test_zeitstempel_kommen_von_der_datenbank() -> None:
    """server_default: so stimmen die Zeiten auch, wenn ein Datensatz einmal
    per SQL entsteht."""
    spalten = Base.metadata.tables["beispiel_modelle_test"].columns

    assert spalten["angelegt"].server_default is not None
    assert spalten["angelegt"].nullable is False


def test_zeitstempel_sind_zeitzonenbehaftet() -> None:
    # Ohne Zeitzone ist nach einer Zeitumstellung nicht mehr entscheidbar,
    # was vor was war.
    spalten = Base.metadata.tables["beispiel_modelle_test"].columns

    assert spalten["angelegt"].type.timezone is True
