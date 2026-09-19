"""Die Regeln, die nur den Spielbericht brauchen.

Jeder Befund hier wird am Ende ein Schreiben an einen Verein. Deshalb steht in
dieser Datei zweierlei, und das zweite ist das wichtigere:

1. dass ein Verstoß gemeldet wird,
2. dass **Unwissen keiner ist** — eine leere Aufstellung, ein unlesbarer
   Zeitstempel, ein fehlendes Datum. Wer daraus einen Befund macht, schickt
   jemanden wegen nichts los.

Die Fristen stehen in § 59 (17) SpO SFV und sind hier mit festen Daten
nachgerechnet, nicht mit der Uhr des Rechners.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from homepi_pruefdienst import regeln
from homepi_pruefdienst.bericht import (
    Confirmation,
    MatchMeta,
    MatchReport,
    Player,
    TeamOfficial,
    TeamSquad,
)


def spieler(name: str, **rest: object) -> Player:
    return Player(name=name, pass_number="12345678", **rest)  # type: ignore[arg-type]


def elf(name: str = "Post SV Dresden 2", **rest: object) -> TeamSquad:
    """Eine Mannschaft, über die wir etwas wissen.

    Mit mindestens einem Spieler: eine leere gilt als *nicht abgerufen*, und
    dann schweigen die Regeln absichtlich.
    """
    vorgabe: dict[str, object] = {"starting_eleven": [spieler("Müller, Max")]}
    return TeamSquad(team_name=name, **{**vorgabe, **rest})  # type: ignore[arg-type]


def bericht(**rest: object) -> MatchReport:
    vorgabe: dict[str, object] = {
        "meta": MatchMeta(
            match_id="633203177",
            home_team="Post SV Dresden 2",
            away_team="SV Fortuna Dresden-Rähnitz",
            match_date="Sa., 13.06.26",
            kickoff="15:00 (15:00 )",
            end_time="16:45",
        ),
        "home_squad": elf(),
        "away_squad": elf("SV Fortuna Dresden-Rähnitz"),
    }
    return MatchReport(**{**vorgabe, **rest})  # type: ignore[arg-type]


def regelnamen(gefunden: list[regeln.Violation]) -> list[str]:
    return [v.rule for v in gefunden]


class TestUeberschrift:
    def test_jede_regel_hat_eine(self) -> None:
        """Ohne Tabelle stand der Vereinsname als Überschrift da — in einer
        Liste von zwanzig Befunden liest man aber, *was* los ist."""
        for regel in regeln._TITEL:
            assert regeln.titel_zu(regel)
            assert "Dresden" not in regeln.titel_zu(regel)

    def test_eine_unbekannte_regel_behaelt_ihre_kennung(self) -> None:
        """Hässlich und genau deshalb richtig: es fällt auf, und jemand trägt
        die Überschrift nach."""
        assert regeln.titel_zu("ganz_neue_regel") == "ganz_neue_regel"


class TestAlsBefund:
    def test_die_felder_kommen_an(self) -> None:
        befund = regeln.als_befund(
            regeln.Violation(
                rule="player_eligibility",
                severity=regeln.Severity.CRITICAL,
                message="Post SV Dresden 2: Müller, Max war nicht spielberechtigt.",
                details={"player": "Müller, Max", "team": "Post SV Dresden 2"},
            )
        )

        assert befund["regel"] == "player_eligibility"
        assert befund["schwere"] == "kritisch"
        assert befund["titel"] == "Spielrecht fraglich"
        assert befund["person"] == "Müller, Max"
        assert befund["mannschaft"] == "Post SV Dresden 2"

    @pytest.mark.parametrize(
        ("schwere", "wort"),
        [
            (regeln.Severity.CRITICAL, "kritisch"),
            (regeln.Severity.WARNING, "warnung"),
            (regeln.Severity.INFO, "hinweis"),
        ],
    )
    def test_die_schwere_wird_uebersetzt(self, schwere: regeln.Severity, wort: str) -> None:
        verstoss = regeln.Violation(rule="incidents", severity=schwere, message="x")

        assert regeln.als_befund(verstoss)["schwere"] == wort

    def test_die_mannschaft_von_aussen_hat_vorrang(self) -> None:
        verstoss = regeln.Violation(
            rule="incidents",
            severity=regeln.Severity.WARNING,
            message="x",
            details={"team": "aus der Regel"},
        )

        assert regeln.als_befund(verstoss, "von aussen")["mannschaft"] == "von aussen"

    def test_ein_langer_text_wird_gekappt(self) -> None:
        verstoss = regeln.Violation(
            rule="incidents", severity=regeln.Severity.WARNING, message="x" * 5000
        )

        assert len(str(regeln.als_befund(verstoss)["text"])) == 2000


class TestPruefe:
    def test_eine_gescheiterte_regel_nimmt_die_anderen_nicht_mit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Achtzig Berichte dürfen nicht an einem ungewöhnlichen
        stehenbleiben."""

        def kaputt(_: MatchReport) -> list[regeln.Violation]:
            raise ValueError("so nicht")

        def heil(_: MatchReport) -> list[regeln.Violation]:
            return [
                regeln.Violation(
                    rule="documents_present", severity=regeln.Severity.INFO, message="da"
                )
            ]

        monkeypatch.setattr(regeln, "alle_regeln", lambda: [kaputt, heil])
        gefunden = regeln.pruefe(bericht())

        assert regelnamen(gefunden) == ["rule_error", "documents_present"]
        assert "so nicht" in gefunden[0].message
        assert gefunden[0].details["regel"] == "kaputt"

    def test_ein_sauberer_bericht_gibt_nichts(self) -> None:
        b = bericht(
            meta=MatchMeta(
                home_team="Post SV Dresden 2",
                away_team="SV Fortuna Dresden-Rähnitz",
                match_date="13.06.2026",
                kickoff="15:00",
                end_time="16:45",
                referee_release_at="13.06.2026, 17:00:00",
            ),
            home_squad=elf(officials=[TeamOfficial("Färber, Jens", ["Leiter Ordnungsdienst"])]),
            confirmations=[
                Confirmation(
                    party="Post SV Dresden 2", confirmed=True, signed_at="13.06.2026, 17:30:00"
                ),
                Confirmation(
                    party="SV Fortuna Dresden-Rähnitz",
                    confirmed=True,
                    signed_at="13.06.2026, 17:40:00",
                ),
            ],
        )

        assert regeln.pruefe(b) == []

    def test_die_regeln_werden_aufgezaehlt_und_nicht_eingesammelt(self) -> None:
        """Eine Regel, die versehentlich mitläuft, ist ein Schreiben an einen
        Verein."""
        assert len(regeln.alle_regeln()) == 7


class TestVorkommnisse:
    def test_ohne_eintrag_schweigt_die_regel(self) -> None:
        assert regeln._check_incidents(bericht(incidents_details={"text": ""})) == []

    def test_ein_freitext_wird_vorgelegt(self) -> None:
        gefunden = regeln._check_incidents(
            bericht(incidents_details={"text": "Zuschauer auf dem Platz."})
        )

        assert regelnamen(gefunden) == ["incidents"]
        assert gefunden[0].severity is regeln.Severity.WARNING
        assert "Zuschauer auf dem Platz." in gefunden[0].message

    def test_stichworte_heben_nur_die_schwere_an(self) -> None:
        """Bewertet wird nichts — ein Eintrag über Gewalt soll nur nicht
        zwischen zwanzig Routinenotizen verschwinden."""
        gefunden = regeln._check_incidents(
            bericht(incidents_details={"text": "Tätlichkeit gegen den Schiedsrichter."})
        )

        assert gefunden[0].severity is regeln.Severity.CRITICAL
        assert gefunden[0].details["severe"] is True

    def test_angekreuztes_allein_genuegt(self) -> None:
        gefunden = regeln._check_incidents(
            bericht(incidents_details={"checked_labels": ["Polizeieinsatz"]})
        )

        assert "Angekreuzt: Polizeieinsatz." in gefunden[0].message
        assert gefunden[0].severity is regeln.Severity.CRITICAL

    def test_langer_freitext_wird_gekuerzt(self) -> None:
        gefunden = regeln._check_incidents(bericht(incidents_details={"text": "ab " * 400}))

        assert gefunden[0].message.endswith("…")


class TestKommentare:
    def test_ein_kommentar_wird_woertlich_vorgelegt(self) -> None:
        gefunden = regeln._check_confirmation_comments(
            bericht(
                confirmations=[
                    Confirmation(party="Post SV Dresden 2", comment="  Ergebnis  stimmt nicht ")
                ]
            )
        )

        assert regelnamen(gefunden) == ["confirmation_comment"]
        assert "Ergebnis stimmt nicht" in gefunden[0].message

    def test_ohne_kommentar_kein_befund(self) -> None:
        b = bericht(confirmations=[Confirmation(party="Post SV Dresden 2", comment="   ")])

        assert regeln._check_confirmation_comments(b) == []

    def test_ohne_partei_steht_wenigstens_unbekannt_da(self) -> None:
        gefunden = regeln._check_confirmation_comments(
            bericht(confirmations=[Confirmation(party="", comment="etwas")])
        )

        assert gefunden[0].message.startswith("Unbekannt")


class TestOrdnungsdienst:
    def test_eine_unbekannte_aufstellung_ist_kein_verstoss(self) -> None:
        """Der Fehlalarm, den die echte Aufnahme gezeigt hat: aus dem HTML
        kommt nur der Name, und daraus wurde 'kein Ordnungsdienst'."""
        assert regeln.aufstellung_bekannt(TeamSquad(team_name="Post SV Dresden 2")) is False
        assert regeln._check_order_manager(bericht(home_squad=TeamSquad())) == []

    @pytest.mark.parametrize("feld", ["starting_eleven", "bench"])
    def test_ein_spieler_genuegt_als_wissen(self, feld: str) -> None:
        assert regeln.aufstellung_bekannt(TeamSquad(**{feld: [spieler("Müller, Max")]})) is True

    def test_ein_offizieller_genuegt_auch(self) -> None:
        squad = TeamSquad(officials=[TeamOfficial("Färber, Jens", ["Trainer"])])

        assert regeln.aufstellung_bekannt(squad) is True

    def test_fehlt_er_in_bekannter_aufstellung_ist_es_ein_befund(self) -> None:
        gefunden = regeln._check_order_manager(bericht())

        assert regelnamen(gefunden) == ["order_manager_missing"]
        assert gefunden[0].severity is regeln.Severity.CRITICAL

    def test_nur_die_heimmannschaft_wird_geprueft(self) -> None:
        """Der Ordnungsdienst gehört dem, der den Platz betreibt — eine
        Mahnung an jeden Gastverein war reine Arbeit zum Wegreden."""
        b = bericht(
            home_squad=elf(officials=[TeamOfficial("Färber, Jens", ["Leiter Ordnungsdienst"])]),
            away_squad=elf("SV Fortuna Dresden-Rähnitz"),
        )

        assert regeln._check_order_manager(b) == []

    def test_doppelrolle_wird_gemeldet(self) -> None:
        b = bericht(
            home_squad=elf(
                officials=[TeamOfficial("Färber, Jens", ["Leiter Ordnungsdienst", "Trainer"])]
            )
        )
        gefunden = regeln._check_order_manager(b)

        assert regelnamen(gefunden) == ["order_manager_dual_role"]
        assert "Trainer" in gefunden[0].message

    def test_ordnungsdienst_der_mitspielt(self) -> None:
        b = bericht(
            home_squad=elf(
                starting_eleven=[spieler("Färber, Jens")],
                officials=[TeamOfficial("Färber, Jens", ["Leiter Ordnungsdienst"])],
            )
        )

        assert regelnamen(regeln._check_order_manager(b)) == ["order_manager_is_player"]


class TestMannschaftsname:
    def test_die_aufstellung_hat_vorrang(self) -> None:
        b = bericht(home_squad=elf("Post SV Dresden 2"))
        b.meta.home_team = "Post SV Dresden II"

        assert regeln.canonical_team(b, home=True) == "Post SV Dresden 2"

    def test_sonst_die_begegnungszeile(self) -> None:
        b = bericht(away_squad=TeamSquad(team_name="  "))

        assert regeln.canonical_team(b, home=False) == "SV Fortuna Dresden-Rähnitz"

    def test_und_zur_not_heim_oder_gast(self) -> None:
        """Ein leerer Wert hat Meldungen mit einem nackten Doppelpunkt
        beginnen lassen."""
        leer = MatchReport()

        assert regeln.canonical_team(leer, home=True) == "Heim"
        assert regeln.canonical_team(leer, home=False) == "Gast"


class TestBestaetigungen:
    def test_fehlende_bestaetigung_nach_ablauf_ist_kritisch(self) -> None:
        gefunden = regeln._check_team_confirmations(bericht())

        assert regelnamen(gefunden) == ["confirmation_missing", "confirmation_missing"]
        assert all(v.severity is regeln.Severity.CRITICAL for v in gefunden)
        assert "abgelaufen" in gefunden[0].message

    def test_vor_ablauf_ist_es_nur_eine_warnung(self) -> None:
        b = bericht(meta=MatchMeta(match_date="13.06.2099", kickoff="15:00", end_time="16:45"))
        gefunden = regeln._check_team_confirmations(b)

        assert all(v.severity is regeln.Severity.WARNING for v in gefunden)
        assert "noch nicht bestätigt" in gefunden[0].message

    def test_ohne_spieltag_gibt_es_keine_frist(self) -> None:
        b = bericht(meta=MatchMeta(home_team="A", away_team="B", match_date=""))
        gefunden = regeln._check_team_confirmations(b)

        assert regelnamen(gefunden) == ["confirmation_missing", "confirmation_missing"]
        assert gefunden[0].details == {"team": "Post SV Dresden 2"}

    def test_ein_unlesbarer_zeitstempel_schweigt_nicht(self) -> None:
        """Nichts zu sagen sähe hier genauso aus wie 'fristgerecht'."""
        b = bericht(
            confirmations=[
                Confirmation(party="Post SV Dresden 2", confirmed=True, signed_at="neulich"),
                Confirmation(
                    party="SV Fortuna Dresden-Rähnitz",
                    confirmed=True,
                    signed_at="13.06.2026, 17:45:00",
                ),
            ]
        )
        gefunden = regeln._check_team_confirmations(b)

        assert regelnamen(gefunden) == ["confirmation_unlesbar"]
        assert "neulich" in gefunden[0].message

    def test_zu_spaet_bestaetigt(self) -> None:
        b = bericht(
            confirmations=[
                Confirmation(
                    party="Post SV Dresden 2", confirmed=True, signed_at="13.06.2026, 20:35:49"
                ),
                Confirmation(
                    party="SV Fortuna Dresden-Rähnitz",
                    confirmed=True,
                    signed_at="13.06.2026, 17:45:00",
                ),
            ]
        )
        gefunden = regeln._check_team_confirmations(b)

        assert regelnamen(gefunden) == ["confirmation_late"]
        assert "2 Std. 35 Min. zu spät" in gefunden[0].message

    def test_eine_stunde_nach_abpfiff_ist_der_normalfall(self) -> None:
        """Die Mannschaften duschen erst. Ein Spielende 21:45 und eine
        Bestätigung 22:15 als 'zu spät' zu melden war reines Rauschen."""
        b = bericht(
            meta=MatchMeta(
                home_team="Post SV Dresden 2",
                away_team="SV Fortuna Dresden-Rähnitz",
                match_date="13.06.2026",
                kickoff="20:00",
                end_time="21:45",
            ),
            confirmations=[
                Confirmation(
                    party="Post SV Dresden 2", confirmed=True, signed_at="13.06.2026, 22:15:00"
                ),
                Confirmation(
                    party="SV Fortuna Dresden-Rähnitz",
                    confirmed=True,
                    signed_at="13.06.2026, 22:40:00",
                ),
            ],
        )

        assert regeln._check_team_confirmations(b) == []

    def test_ohne_schiedsrichter_beginnt_die_frist_des_gastes_spaeter(self) -> None:
        """Der Bericht wird weitergereicht; an einer gemeinsamen Frist
        gemessen sah jeder Gast eines Abendspiels zu spät aus."""
        b = bericht(
            meta=MatchMeta(
                home_team="Post SV Dresden 2",
                away_team="SV Fortuna Dresden-Rähnitz",
                match_date="13.06.2026",
                kickoff="20:00",
                end_time="21:45",
            ),
            confirmations=[
                Confirmation(
                    party="Post SV Dresden 2", confirmed=True, signed_at="13.06.2026, 22:50:00"
                ),
                Confirmation(
                    party="SV Fortuna Dresden-Rähnitz",
                    confirmed=True,
                    signed_at="13.06.2026, 23:30:00",
                ),
            ],
        )
        gefunden = regeln._check_team_confirmations(b)

        # Das Heim ist zu spät (Frist 22:45), der Gast nicht (22:50 + 60 Min.).
        assert [v.details["team"] for v in gefunden] == ["Post SV Dresden 2"]

    def test_mit_freigabe_laeuft_die_frist_ab_der_freigabe(self) -> None:
        b = bericht(
            meta=MatchMeta(
                home_team="Post SV Dresden 2",
                away_team="SV Fortuna Dresden-Rähnitz",
                match_date="13.06.2026",
                kickoff="15:00",
                end_time="16:45",
                referee_release_at="13.06.2026, 19:14:41",
            ),
            confirmations=[
                Confirmation(
                    party="Post SV Dresden 2", confirmed=True, signed_at="13.06.2026, 20:10:00"
                ),
                Confirmation(
                    party="SV Fortuna Dresden-Rähnitz",
                    confirmed=True,
                    signed_at="13.06.2026, 19:15:09",
                ),
            ],
        )

        assert regeln._check_team_confirmations(b) == []


class TestBestaetigungZuordnen:
    def test_direkt_ueber_den_namen(self) -> None:
        conf = Confirmation(party="Post SV Dresden 2", confirmed=True)
        b = bericht(confirmations=[conf, Confirmation(party="SV Fortuna Dresden-Rähnitz")])

        assert regeln._find_confirmation(b, "Post SV Dresden 2") is conf

    def test_sonst_nach_der_reihenfolge(self) -> None:
        """Manchmal steht in `party` der Unterzeichner und nicht die
        Mannschaft."""
        erste = Confirmation(party="Jens Färber (6300post2M)", confirmed=True)
        zweite = Confirmation(party="Marcus Huth (63633098)", confirmed=True)
        b = bericht(confirmations=[erste, zweite])

        assert regeln._find_confirmation(b, "Post SV Dresden 2") is erste
        assert regeln._find_confirmation(b, "SV Fortuna Dresden-Rähnitz") is zweite

    def test_der_schiedsrichter_zaehlt_nicht_als_mannschaft(self) -> None:
        b = bericht(confirmations=[Confirmation(party="Schiedsrichter", confirmed=True)])

        assert regeln._find_confirmation(b, "Post SV Dresden 2") is None


class TestVerspaetung:
    @pytest.mark.parametrize(
        ("minuten", "text"),
        [
            (11, "11 Min."),
            (60, "1 Std."),
            (155, "2 Std. 35 Min."),
            (24 * 60, "1 Tag"),
            (49 * 60, "2 Tage 1 Std."),
        ],
    )
    def test_die_einheit_traegt_die_aussage(self, minuten: int, text: str) -> None:
        """'0 Std. zu spät' für elf Minuten las sich wie ein Rundungsartefakt
        und ließ einen echten Befund wie Rauschen aussehen."""
        assert regeln._verspaetung(timedelta(minutes=minuten)) == text


class TestUhrzeit:
    def test_eine_uhrzeit_auf_den_spieltag(self) -> None:
        tag = datetime(2026, 6, 13)

        assert regeln._uhrzeit_auf(tag, "17:00 (17:00 )") == datetime(2026, 6, 13, 17, 0)

    def test_vierundzwanzig_uhr_faellt_nicht_um(self) -> None:
        """DFBnet schreibt '24:00'; `replace(hour=24)` wirft — und das kam als
        `rule_error` heraus und blockierte den ganzen Bericht."""
        assert regeln._uhrzeit_auf(datetime(2026, 6, 13), "24:00") == datetime(2026, 6, 14)

    def test_ohne_uhrzeit_kommt_nichts(self) -> None:
        assert regeln._uhrzeit_auf(datetime(2026, 6, 13), "unbekannt") is None

    def test_ein_spiel_ueber_mitternacht_endet_am_folgetag(self) -> None:
        b = bericht(meta=MatchMeta(match_date="13.06.2026", kickoff="22:00", end_time="00:30"))

        assert regeln._match_end(b) == datetime(2026, 6, 14, 0, 30)

    def test_ohne_spieltag_kein_spielende(self) -> None:
        assert regeln._match_end(bericht(meta=MatchMeta(end_time="16:45"))) is None
        assert regeln._anstoss(bericht(meta=MatchMeta(kickoff="15:00"))) is None

    def test_ohne_endzeit_auch_nicht(self) -> None:
        assert regeln._match_end(bericht(meta=MatchMeta(match_date="13.06.2026"))) is None


class TestFreigabefrist:
    def test_regelfall_ist_achtzehn_uhr(self) -> None:
        b = bericht(meta=MatchMeta(match_date="13.06.2026", kickoff="15:00", end_time="16:45"))

        assert regeln.referee_release_deadline(b) == datetime(2026, 6, 13, 18, 0)

    def test_ein_abendspiel_bekommt_eine_stunde_nach_abpfiff(self) -> None:
        """Ein Spiel, das 18:40 endet, kann nicht um 18:00 freigegeben sein —
        die größte Quelle falscher Befunde."""
        b = bericht(meta=MatchMeta(match_date="13.06.2026", kickoff="17:00", end_time="18:40"))

        assert regeln.referee_release_deadline(b) == datetime(2026, 6, 13, 19, 40)

    def test_ohne_spieltag_gibt_es_keine(self) -> None:
        assert regeln.referee_release_deadline(bericht(meta=MatchMeta())) is None

    def test_ohne_endzeit_bleibt_der_regelfall(self) -> None:
        b = bericht(meta=MatchMeta(match_date="13.06.2026"))

        assert regeln.referee_release_deadline(b) == datetime(2026, 6, 13, 18, 0)


class TestFreigabe:
    def test_rechtzeitig_ist_kein_befund(self) -> None:
        b = bericht(
            meta=MatchMeta(
                match_date="13.06.2026",
                kickoff="15:00",
                end_time="16:45",
                referee_release_at="13.06.2026, 17:30:00",
            )
        )

        assert regeln._check_release_timeliness(b) == []

    def test_ohne_zeitstempel_wird_nichts_geraten(self) -> None:
        b = bericht(meta=MatchMeta(match_date="13.06.2026", kickoff="15:00", end_time="16:45"))

        assert regeln._check_release_timeliness(b) == []

    def test_ohne_spieltag_ebenso(self) -> None:
        b = bericht(meta=MatchMeta(referee_release_at="13.06.2026, 20:00:00"))

        assert regeln._check_release_timeliness(b) == []

    def test_zu_spaet_ist_eine_warnung(self) -> None:
        b = bericht(
            meta=MatchMeta(
                match_date="13.06.2026",
                kickoff="15:00",
                end_time="16:45",
                referee_release_at="13.06.2026, 20:00:00",
            )
        )
        gefunden = regeln._check_release_timeliness(b)

        assert regelnamen(gefunden) == ["release_late"]
        assert gefunden[0].severity is regeln.Severity.WARNING
        assert gefunden[0].details["hours_late"] == 2.0

    def test_ab_einem_tag_ist_es_kritisch(self) -> None:
        b = bericht(
            meta=MatchMeta(
                match_date="13.06.2026",
                kickoff="15:00",
                end_time="16:45",
                referee_release_at="15.06.2026, 09:00:00",
            )
        )
        gefunden = regeln._check_release_timeliness(b)

        assert gefunden[0].severity is regeln.Severity.CRITICAL


class TestBestaetigungsfrist:
    def test_ohne_endzeit_bleibt_es_bei_achtzehn_uhr(self) -> None:
        b = bericht(meta=MatchMeta(match_date="13.06.2026"))

        assert regeln._confirmation_deadline(b) == datetime(2026, 6, 13, 18, 0)

    def test_ohne_spieltag_gibt_es_keine(self) -> None:
        assert regeln._confirmation_deadline(bericht(meta=MatchMeta())) is None

    def test_ohne_schiedsrichter_und_ohne_heim_bleibt_die_grundfrist(self) -> None:
        """Der Gast bekommt erst dann spaeter, wenn das Heim wirklich
        bestaetigt hat -- geraten wird nichts."""
        b = bericht(meta=MatchMeta(match_date="13.06.2026", kickoff="15:00", end_time="16:45"))

        assert regeln._confirmation_deadline(b, gast=True) == datetime(2026, 6, 13, 18, 0)


class TestFuerDasArtefakt:
    def test_befunde_aus_liefert_fertige_zeilen(self) -> None:
        b = bericht(documents=[{"name": "Attest.pdf"}])

        befunde = regeln.befunde_aus(b)

        assert {"documents_present"} <= {str(x["regel"]) for x in befunde}
        assert all(
            set(x) == {"regel", "schwere", "titel", "text", "person", "mannschaft"} for x in befunde
        )

    def test_ein_nicht_gelesener_bericht_ist_eine_warnung_und_keine_leere_liste(self) -> None:
        befunde = regeln.nicht_gelesen("die Seite kam nicht")

        assert [x["regel"] for x in befunde] == ["bericht_ungelesen"]
        assert befunde[0]["schwere"] == "warnung"
        assert "die Seite kam nicht" in str(befunde[0]["text"])
        assert befunde[0]["titel"] == "Spielbericht nicht gelesen"


class TestDokumente:
    def test_ohne_dokumente_kein_hinweis(self) -> None:
        assert regeln._check_documents(bericht()) == []

    def test_mit_dokumenten_ein_hinweis(self) -> None:
        gefunden = regeln._check_documents(bericht(documents=[{"name": "Attest.pdf"}]))

        assert regelnamen(gefunden) == ["documents_present"]
        assert gefunden[0].severity is regeln.Severity.INFO


class TestSpielrecht:
    def test_ein_sperrvermerk_wird_gemeldet(self) -> None:
        b = bericht(
            home_squad=elf(
                starting_eleven=[spieler("Müller, Max", badges=["POL", "gesperrt bis 20.09."])]
            )
        )
        gefunden = regeln._check_player_eligibility(b)

        assert regelnamen(gefunden) == ["player_eligibility"]
        assert gefunden[0].details["player"] == "Müller, Max"

    @pytest.mark.parametrize("abzeichen", ["Stammspieler", "U23", "A"])
    def test_neutrale_kennzeichen_sind_kein_verstoss(self, abzeichen: str) -> None:
        """'Stammspieler' zählt gegen eine Obergrenze (§ 68 (2) b)), 'U23' ist
        sogar eine Ausnahme davon (c)) — beides als 'nicht spielberechtigt' zu
        melden ertränkte die echten Befunde."""
        b = bericht(home_squad=elf(starting_eleven=[spieler("Müller, Max", badges=[abzeichen])]))

        assert regeln._check_player_eligibility(b) == []

    def test_auch_auf_der_bank_wird_gesehen(self) -> None:
        b = bericht(
            home_squad=elf(bench=[spieler("Schmidt, Paul", badges=["nicht spielberechtigt"])])
        )

        assert regelnamen(regeln._check_player_eligibility(b)) == ["player_eligibility"]

    def test_eine_dfbnet_warnung_mit_spielernamen_wird_durchgereicht(self) -> None:
        b = bericht(
            home_squad=elf(starting_eleven=[spieler("Müller, Max")]),
            away_squad=elf("SV Fortuna Dresden-Rähnitz", starting_eleven=[spieler("Huth, M.")]),
            raw_warnings=["Müller, Max besitzt kein gültiges Spielrecht."],
        )
        gefunden = regeln._check_player_eligibility(b)

        assert regelnamen(gefunden) == ["dfbnet_warning"]
        assert gefunden[0].details["player"] == "Müller, Max"

    def test_eine_warnung_ohne_spielernamen_bleibt_liegen(self) -> None:
        b = bericht(raw_warnings=["Der Spielbericht wurde nachträglich geändert."])

        assert regeln._check_player_eligibility(b) == []


class TestDatumLesen:
    @pytest.mark.parametrize(
        ("text", "erwartet"),
        [
            ("Sa., 13.06.26", datetime(2026, 6, 13)),
            ("13.06.2026", datetime(2026, 6, 13)),
            ("2026-06-13", datetime(2026, 6, 13)),
        ],
    )
    def test_die_schreibweisen_aus_dfbnet_und_aus_der_datenbank(
        self, text: str, erwartet: datetime
    ) -> None:
        assert regeln._parse_date(text) == erwartet

    @pytest.mark.parametrize("text", ["", "irgendwann"])
    def test_unlesbares_bleibt_none(self, text: str) -> None:
        assert regeln._parse_date(text) is None

    @pytest.mark.parametrize(
        "text",
        [
            "13.06.2026, 19:25:47",
            "13.06.2026, 19:25",
            "13.06.26, 19:25:47",
            "13.06.2026 19:25",
            "2026-06-13 19:25:47",
            "2026-06-13T19:25:47",
        ],
    )
    def test_zeitstempel_in_allen_schreibweisen(self, text: str) -> None:
        """Ein Zeitstempel, der nicht gelesen wird, schaltet die
        Fristenprüfung still ab."""
        gelesen = regeln._parse_datetime(text)

        assert gelesen is not None
        assert gelesen.date() == datetime(2026, 6, 13).date()

    @pytest.mark.parametrize("text", ["", "neulich"])
    def test_unlesbarer_zeitstempel_bleibt_none(self, text: str) -> None:
        assert regeln._parse_datetime(text) is None

    def test_die_deutsche_schreibweise_fuer_meldungen(self) -> None:
        assert regeln._fmt_dt(datetime(2026, 6, 13, 19, 25)) == "13.06.2026, 19:25"
        assert regeln._fmt_dt(None) == ""


class TestKleinkram:
    @pytest.mark.parametrize(
        ("text", "erwartet"), [("42", 42), ("42'", 42), ("", None), ("keine", None)]
    )
    def test_die_spielminute(self, text: str, erwartet: int | None) -> None:
        assert regeln._parse_minute(text) == erwartet

    def test_die_saison_beginnt_am_ersten_juli(self) -> None:
        """ISO mit Absicht: bei deutscher Schreibweise war
        '20.10.2024' >= '01.07.2025' wahr."""
        assert regeln._season_start_from_match_date("13.06.2026") == "2025-07-01"
        assert regeln._season_start_from_match_date("13.08.2026") == "2026-07-01"

    def test_ohne_spieltag_keine_saison(self) -> None:
        assert regeln._season_start_from_match_date("irgendwann") is None
