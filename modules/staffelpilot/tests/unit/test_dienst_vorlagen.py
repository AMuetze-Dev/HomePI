"""Welche mitgelieferten Regeln das Artefakt übernimmt.

Der Prüfdienst bringt neun Regeldateien mit. Sie lagen bisher nur in seinem
Ordner: die Oberfläche zeigte „Keine eigenen Regeldateien", obwohl neun liefen
— und zu bearbeiten gab es nichts.

Hier steht die Entscheidung, und nur sie: **einmal**, und **nie über etwas
drüber**. Beides ist der Grund, warum es eine eigene Funktion ist und keine
Zeile im Speicher.
"""

from __future__ import annotations

from homepi_staffelpilot import dienst

NEUN = [f"{i}0_regel.py" for i in range(1, 10)]


class TestVorlagenAuswaehlen:
    def test_beim_ersten_mal_kommt_alles(self) -> None:
        gewaehlt = dienst.vorlagen_auswaehlen(NEUN, vorhanden=[], schon_geschehen=False)

        assert gewaehlt == NEUN

    def test_beim_zweiten_mal_nichts(self) -> None:
        """Wer eine Regel löscht, soll sie los sein. Ein Dienst, der beim
        nächsten Lauf wieder anbietet, holt sie zurück."""
        gewaehlt = dienst.vorlagen_auswaehlen(NEUN, vorhanden=[], schon_geschehen=True)

        assert gewaehlt == []

    def test_was_schon_dasteht_bleibt_stehen(self) -> None:
        """Niemals überschreiben: eine von Hand geschärfte Regel darf eine
        Vorlage nicht zurücksetzen. Das ist die zweite Sperre neben dem
        Vermerk — fiele der aus, griffe noch diese."""
        gewaehlt = dienst.vorlagen_auswaehlen(
            NEUN, vorhanden=["10_regel.py", "90_regel.py"], schon_geschehen=False
        )

        assert "10_regel.py" not in gewaehlt
        assert "90_regel.py" not in gewaehlt
        assert len(gewaehlt) == 7

    def test_die_reihenfolge_bleibt(self) -> None:
        """`10_` vor `20_`: der Lader sortiert nach Namen, und eine
        `90_eigene.py` soll am Ende gezielt etwas ersetzen können."""
        gewaehlt = dienst.vorlagen_auswaehlen(
            ["90_regel.py", "10_regel.py"], vorhanden=[], schon_geschehen=False
        )

        assert gewaehlt == ["10_regel.py", "90_regel.py"]

    def test_nichts_angeboten_ist_kein_fehler(self) -> None:
        assert dienst.vorlagen_auswaehlen([], vorhanden=[], schon_geschehen=False) == []
