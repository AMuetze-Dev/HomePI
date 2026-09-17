"""Reine Fachlogik - keine Datenbank, keine Fixtures, Millisekunden.

Hier entsteht der Grossteil der Tests. Faengt ein Test hier an, eine Datenbank
zu brauchen, gehoert die Logik nicht mehr in dienst.py.

Die Regeln kommen aus der Arbeit eines Staffelleiters. Die wichtigste ist die
erste: ein Spiel gilt erst als erledigt, wenn zu **jedem** Befund eine
Entscheidung vorliegt. Das ist die ganze Zusage des Artefakts - nichts
uebersehen - und deshalb steht sie hier und nicht im Router.
"""

from __future__ import annotations

import datetime as dt

import pytest

from homepi_staffelpilot.dienst import (
    BefundSicht,
    GrundFehlt,
    SpielSicht,
    darf_abgehakt_werden,
    entscheidung_pruefen,
    ist_faellig,
    sortiert,
    zusammenfassen,
)


def befund(
    schwere: str = "warnung",
    entscheidung: str = "offen",
    regel: str = "regel",
    titel: str = "Titel",
) -> BefundSicht:
    return BefundSicht(schwere=schwere, entscheidung=entscheidung, regel=regel, titel=titel)


# ── Abhaken ───────────────────────────────────────────────────────────────


class TestAbhaken:
    def test_ohne_befunde_darf_abgehakt_werden(self) -> None:
        """Ein sauber durchgelaufenes Spiel braucht keine Entscheidung."""
        assert darf_abgehakt_werden([]).erlaubt is True

    def test_ein_offener_befund_blockiert(self) -> None:
        entscheidung = darf_abgehakt_werden([befund(entscheidung="offen")])
        assert entscheidung.erlaubt is False
        assert entscheidung.offen == 1

    def test_der_grund_nennt_die_zahl(self) -> None:
        """Eine Meldung, die nur sagt 'geht nicht', schickt zum Suchen."""
        entscheidung = darf_abgehakt_werden([befund(), befund()])
        assert "2" in entscheidung.grund

    def test_bei_einem_einzelnen_steht_die_einzahl_da(self) -> None:
        assert "1 Befund braucht" in darf_abgehakt_werden([befund()]).grund

    @pytest.mark.parametrize("art", ["kenntnis", "verworfen"])
    def test_entschiedene_befunde_blockieren_nicht(self, art: str) -> None:
        assert darf_abgehakt_werden([befund(entscheidung=art)]).erlaubt is True

    def test_gemischt_zaehlt_nur_die_offenen(self) -> None:
        befunde = [befund(entscheidung="kenntnis"), befund(), befund(entscheidung="verworfen")]
        assert darf_abgehakt_werden(befunde).offen == 1

    def test_ein_kritischer_befund_zaehlt_wie_jeder_andere(self) -> None:
        """Die Schwere entscheidet ueber die Reihenfolge, nicht ueber die
        Pflicht. Auch ein Hinweis will zur Kenntnis genommen werden."""
        assert darf_abgehakt_werden([befund(schwere="hinweis")]).erlaubt is False


# ── Entscheidung ──────────────────────────────────────────────────────────


class TestEntscheidung:
    def test_kenntnis_braucht_keinen_grund(self) -> None:
        assert entscheidung_pruefen("kenntnis", "") == ""

    def test_verwerfen_ohne_grund_wird_abgelehnt(self) -> None:
        """'Kein Verstoss' ist die einzige Entscheidung, die einen Befund aus
        der Bearbeitung nimmt. Ohne Begruendung ist sie spaeter nicht mehr
        nachvollziehbar - und genau danach fragt ein Verein."""
        with pytest.raises(GrundFehlt):
            entscheidung_pruefen("verworfen", "")

    def test_ein_grund_aus_leerzeichen_ist_keiner(self) -> None:
        with pytest.raises(GrundFehlt):
            entscheidung_pruefen("verworfen", "   ")

    def test_der_grund_wird_getrimmt(self) -> None:
        assert entscheidung_pruefen("verworfen", "  Spieler war spielberechtigt  ") == (
            "Spieler war spielberechtigt"
        )

    def test_ein_grund_bei_kenntnis_bleibt_erhalten(self) -> None:
        """Verboten ist er nicht - eine Notiz zur Kenntnisnahme ist sinnvoll."""
        assert entscheidung_pruefen("kenntnis", " gesehen ") == "gesehen"


# ── Reihenfolge ───────────────────────────────────────────────────────────


class TestSortierung:
    def test_kritisch_steht_vor_warnung_vor_hinweis(self) -> None:
        befunde = [befund(schwere="hinweis"), befund(schwere="kritisch"), befund(schwere="warnung")]
        assert [b.schwere for b in sortiert(befunde)] == ["kritisch", "warnung", "hinweis"]

    def test_gleiche_schwere_bleibt_in_der_eingangsreihenfolge(self) -> None:
        """Stabil sortiert: sonst springen Befunde bei jedem Laden umher, und
        man verliert die Stelle, an der man war."""
        befunde = [befund(titel="B"), befund(titel="A"), befund(titel="C")]
        assert [b.titel for b in sortiert(befunde)] == ["B", "A", "C"]

    def test_offene_stehen_vor_entschiedenen(self) -> None:
        """Was noch Arbeit ist, gehoert nach oben."""
        befunde = [
            befund(schwere="warnung", entscheidung="kenntnis", titel="erledigt"),
            befund(schwere="warnung", entscheidung="offen", titel="offen"),
        ]
        assert [b.titel for b in sortiert(befunde)] == ["offen", "erledigt"]

    def test_ein_offener_hinweis_steht_trotzdem_hinter_einem_kritischen(self) -> None:
        """Die Schwere wiegt schwerer als der Bearbeitungsstand."""
        befunde = [
            befund(schwere="hinweis", entscheidung="offen", titel="hinweis"),
            befund(schwere="kritisch", entscheidung="kenntnis", titel="kritisch"),
        ]
        assert [b.titel for b in sortiert(befunde)] == ["kritisch", "hinweis"]

    def test_eine_leere_liste_bleibt_leer(self) -> None:
        assert sortiert([]) == []


# ── Faelligkeit ───────────────────────────────────────────────────────────


class TestFaelligkeit:
    """Der Pruefzeitraum: wie weit zurueck geschaut wird.

    Ein Spiel von vorgestern ist faellig, eines aus der Vorsaison nicht mehr -
    sonst wuerde jeder Prueflauf die ganze Historie noch einmal aufmachen.
    """

    def test_das_spiel_von_gestern_ist_faellig(self) -> None:
        heute = dt.date(2026, 9, 17)
        assert ist_faellig(dt.date(2026, 9, 16), heute, tage=30) is True

    def test_das_spiel_von_heute_auch(self) -> None:
        heute = dt.date(2026, 9, 17)
        assert ist_faellig(heute, heute, tage=30) is True

    def test_am_rand_des_zeitraums_noch(self) -> None:
        """Genau 30 Tage sind drin, nicht drueber."""
        heute = dt.date(2026, 9, 17)
        assert ist_faellig(dt.date(2026, 8, 18), heute, tage=30) is True

    def test_einen_tag_darueber_nicht_mehr(self) -> None:
        heute = dt.date(2026, 9, 17)
        assert ist_faellig(dt.date(2026, 8, 17), heute, tage=30) is False

    def test_ein_spiel_in_der_zukunft_ist_nicht_faellig(self) -> None:
        """Es ist noch nicht gespielt. Ein Befund darauf waere eine Erfindung."""
        heute = dt.date(2026, 9, 17)
        assert ist_faellig(dt.date(2026, 9, 18), heute, tage=30) is False


# ── Zusammenfassung ───────────────────────────────────────────────────────


class TestZusammenfassung:
    def test_ohne_spiele_steht_ueberall_null(self) -> None:
        z = zusammenfassen([], staffeln_aktiv=0)
        assert (z.spiele, z.offen, z.abgehakt, z.befunde_offen, z.befunde_kritisch) == (0,) * 5

    def test_sie_zaehlt_spiele_und_befunde(self) -> None:
        spiele = [
            SpielSicht(abgehakt=False, befunde=[befund(schwere="kritisch"), befund()]),
            SpielSicht(abgehakt=True, befunde=[befund(entscheidung="kenntnis")]),
        ]
        z = zusammenfassen(spiele, staffeln_aktiv=3)
        assert z.spiele == 2
        assert z.offen == 1
        assert z.abgehakt == 1
        assert z.befunde_offen == 2
        assert z.befunde_kritisch == 1
        assert z.staffeln_aktiv == 3

    def test_kritisch_zaehlt_nur_was_noch_offen_ist(self) -> None:
        """Ein entschiedener Feldverweis ist keine offene Arbeit mehr - er
        darf die Zahl auf der Kachel nicht dauerhaft rot halten."""
        spiele = [
            SpielSicht(
                abgehakt=False,
                befunde=[befund(schwere="kritisch", entscheidung="kenntnis")],
            )
        ]
        assert zusammenfassen(spiele, staffeln_aktiv=1).befunde_kritisch == 0
