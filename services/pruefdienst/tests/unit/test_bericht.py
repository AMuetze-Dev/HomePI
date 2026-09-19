"""Der Extraktor gegen **echtes**, aufgezeichnetes DFBnet-HTML.

Jeder andere Test dieses Dienstes baut seine Daten selbst. Die bleiben alle
grün, während der Leser still nichts mehr zurückgibt — DFBnet gehört uns
nicht, und eine geänderte Seite meldet sich nicht an.

Diese Datei ist die Stolperdrahtleitung. Die Aufnahmen stammen vom
24.06.2026 (`tests/aufnahmen/`) und sind aus der bestehenden Anwendung
übernommen, zusammen mit dem Extraktor.

**Wenn hier etwas rot wird**, ist die Frage nicht, welche Behauptung sich
lockern lässt, sondern: hat DFBnet die Seite geändert? Dann neu aufnehmen,
vergleichen, den Extraktor nachziehen — und erst danach die Zahlen hier.

Die beiden Fehler, die diese Aufnahmen schon einmal gefunden haben, stehen als
eigene Tests da: der Fragebogen „Vorkommnisse" wurde mit seinen eigenen
Beschriftungen als Inhalt gelesen (jedes Spiel ein kritischer Befund), und die
Bestätigungen suchten rückwärts nach dem Namen und fanden den Unterzeichner
des vorigen Blocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homepi_pruefdienst.bericht import MatchReport, MatchReportExtractor

AUFNAHMEN = Path(__file__).resolve().parent.parent / "aufnahmen"
INFO = AUFNAHMEN / "06_match_report_info.html"
TEAMS = AUFNAHMEN / "07_match_report_teams.html"
VERLAUF = AUFNAHMEN / "08_match_report_history.html"

pytestmark = pytest.mark.skipif(
    not (INFO.exists() and TEAMS.exists() and VERLAUF.exists()),
    reason="die Aufnahmen liegen nicht vor",
)


@pytest.fixture(scope="module")
def bericht() -> MatchReport:
    return MatchReportExtractor.from_files(
        info_path=INFO, teams_path=TEAMS, history_path=VERLAUF
    ).extract()


class TestKopfdaten:
    """Die Werte, an denen die Warteschlange und die Kartenzählung hängen."""

    def test_die_kennung(self, bericht: MatchReport) -> None:
        assert bericht.meta.match_id == "633203177"

    def test_der_spieltag(self, bericht: MatchReport) -> None:
        assert bericht.meta.match_date == "Sa., 13.06.26"

    def test_die_paarung(self, bericht: MatchReport) -> None:
        assert bericht.meta.home_team == "Post SV Dresden 2"
        assert bericht.meta.away_team == "SV Fortuna Dresden-Rähnitz"

    def test_der_wettbewerb(self, bericht: MatchReport) -> None:
        """An ihm haengt, ob Gelbe Karten mitzaehlen: ein Freundschaftsspiel
        zaehlt nicht."""
        assert bericht.meta.competition == "Meisterschaft"

    def test_der_stand_des_berichts(self, bericht: MatchReport) -> None:
        assert bericht.meta.report_status == "Prüferfreigabe"

    def test_die_spieltagnummer(self, bericht: MatchReport) -> None:
        assert bericht.meta.match_day == "26"

    def test_wann_der_schiedsrichter_freigegeben_hat(self, bericht: MatchReport) -> None:
        assert bericht.meta.referee_release_at == "13.06.2026, 19:14:41"

    def test_das_ergebnis(self, bericht: MatchReport) -> None:
        assert bericht.meta.result


class TestEreignisse:
    def test_karten(self, bericht: MatchReport) -> None:
        assert len(bericht.cards) == 1
        karte = bericht.cards[0]
        assert karte.card_type in ("Gelbe Karte", "Gelb-Rote Karte", "Rote Karte")
        assert karte.player
        assert karte.person_kind == "spieler"

    def test_tore(self, bericht: MatchReport) -> None:
        assert len(bericht.goals) == 9
        assert all(tor.scorer for tor in bericht.goals)

    def test_wechsel(self, bericht: MatchReport) -> None:
        assert len(bericht.substitutions) == 6
        assert all(w.player_in and w.player_out for w in bericht.substitutions)

    def test_schiedsrichter(self, bericht: MatchReport) -> None:
        assert len(bericht.officials) == 1


class TestAufstellungen:
    """Die kommen **nicht** aus dem HTML -- und das ist hier festgehalten.

    Die Seite nennt die beiden Mannschaftsnamen und sonst nichts. Wer Spieler,
    Geburtsdaten, Spielrecht und Fotos braucht, fragt die
    Aufstellungsschnittstelle (`aufstellung.py`). Genau davon haengen die
    Regeln ab, die etwas wert sind.

    Ohne diesen Test saehe der leere Kader aus wie ein Extraktor, der
    aufgehoert hat zu arbeiten.
    """

    def test_die_mannschaftsnamen_stehen_im_html(self, bericht: MatchReport) -> None:
        assert bericht.home_squad.team_name == "Post SV Dresden 2"
        assert bericht.away_squad.team_name == "SV Fortuna Dresden-Rähnitz"

    def test_die_spieler_aber_nicht(self, bericht: MatchReport) -> None:
        for elf in (bericht.home_squad, bericht.away_squad):
            assert elf.starting_eleven == []
            assert elf.bench == []


class TestBestaetigungen:
    """Schritt 6 im Ablauf. Hier steckten zwei Fehler."""

    def test_beide_mannschaften_werden_gefunden(self, bericht: MatchReport) -> None:
        assert len(bericht.confirmations) == 2

    def test_die_partei_ist_die_mannschaft_und_nicht_der_vorige_unterzeichner(
        self, bericht: MatchReport
    ) -> None:
        """Die alte Rueckwaertssuche lieferte 'Jens Färber (6300post2M)'."""
        assert [b.party for b in bericht.confirmations] == [
            "Post SV Dresden 2",
            "SV Fortuna Dresden-Rähnitz",
        ]

    def test_die_unterschrift_gehoert_zur_richtigen_partei(self, bericht: MatchReport) -> None:
        nach_partei = {b.party: b for b in bericht.confirmations}
        assert nach_partei["Post SV Dresden 2"].signed_by == "Jens Färber (6300post2M)"
        assert nach_partei["SV Fortuna Dresden-Rähnitz"].signed_by == "Marcus Huth (63633098)"

    def test_die_zeitstempel(self, bericht: MatchReport) -> None:
        nach_partei = {b.party: b for b in bericht.confirmations}
        assert nach_partei["Post SV Dresden 2"].signed_at == "13.06.2026, 20:35:49"
        assert nach_partei["SV Fortuna Dresden-Rähnitz"].signed_at == "13.06.2026, 19:15:09"

    def test_bestaetigt_folgt_der_unterschrift(self, bericht: MatchReport) -> None:
        """`confirmed` war einmal immer True - 'ja' und 'nein' sind beides
        feste Beschriftungen."""
        assert all(b.confirmed for b in bericht.confirmations)

    def test_es_wird_kein_kommentar_erfunden(self, bericht: MatchReport) -> None:
        """Die Blockgrenze darf nicht den naechsten Abschnitt mitziehen."""
        assert [b.comment for b in bericht.confirmations] == ["", ""]


class TestVorkommnisse:
    def test_der_fragebogen_ist_kein_vorkommnis(self, bericht: MatchReport) -> None:
        """Er wurde mit seinen eigenen Beschriftungen als Inhalt gelesen -- und
        damit war jeder Spielbericht ein kritischer Befund."""
        assert bericht.incidents_reported is False
        assert bericht.incidents_details["text"] == ""


class TestNachsichtig:
    """Ein Prueflauf ueber achtzig Berichte soll nicht am ersten
    ungewoehnlichen stehenbleiben."""

    def test_ohne_html_kommt_ein_leerer_bericht(self) -> None:
        leer = MatchReportExtractor().extract()

        assert leer.meta.match_id == ""
        assert leer.cards == []
        assert leer.confirmations == []

    def test_unsinn_im_html_wirft_nicht(self) -> None:
        bericht = MatchReportExtractor(
            info_html="<html><body><p>nichts davon</p></body></html>",
            teams_html="<html></html>",
            history_html="",
        ).extract()

        assert bericht.meta.home_team == ""
        assert bericht.goals == []
