"""Die Übersetzung der Aufstellungsschnittstelle — rein, also prüfbar.

Hier hängen die Regeln dran, die etwas wert sind: ohne Geburtsdatum keine
Altersprüfung, ohne Fotozeitstempel kein § 67 (3), ohne Spielrecht kein § 70.
Und der teuerste Fehler wäre nicht ein falscher Wert, sondern ein **erfundener**
— ein Unwissen, das als Verstoß gemeldet wird, schickt einen Verein wegen
nichts los.
"""

from __future__ import annotations

import pytest

from homepi_pruefdienst import aufstellung


class TestName:
    def test_nachname_zuerst(self) -> None:
        assert aufstellung.name_zusammensetzen("Max", "Müller") == "Müller, Max"

    def test_ohne_vornamen_bleibt_der_nachname_allein(self) -> None:
        assert aufstellung.name_zusammensetzen("", "Müller") == "Müller"

    def test_ohne_alles_bleibt_es_leer(self) -> None:
        assert aufstellung.name_zusammensetzen("", "") == ""


class TestDatum:
    def test_iso_wird_deutsch(self) -> None:
        assert aufstellung.datum_deutsch("2008-03-14") == "14.03.2008"

    def test_mit_uhrzeit_und_zeitzone(self) -> None:
        assert aufstellung.datum_deutsch("2008-03-14T00:00:00Z") == "14.03.2008"

    def test_leer_bleibt_leer(self) -> None:
        assert aufstellung.datum_deutsch("") == ""

    def test_unlesbares_bleibt_stehen(self) -> None:
        """Es zu verwerfen hiesse, still ein Geburtsdatum zu verlieren - und
        die Altersregeln schweigen dann, statt zu melden."""
        assert aufstellung.datum_deutsch("irgendwann") == "irgendwann"


class TestFoto:
    def test_ein_foto_mit_zeitstempel(self) -> None:
        zustand, stand = aufstellung.foto_aus_api(
            {"playerPhoto": {"id": "x", "timestamp": "2019-07-01T10:00:00Z"}}, True
        )

        assert zustand == "vorhanden"
        assert stand == "2019-07-01T10:00:00Z"

    def test_kein_foto_heisst_fehlt(self) -> None:
        assert aufstellung.foto_aus_api({"playerPhoto": None}, True) == ("fehlt", "")

    def test_ein_fehlendes_feld_ist_unwissen_und_nicht_fehlt(self) -> None:
        """Das erste ist "wir wissen es nicht", das zweite "es gibt keins".
        Aus dem einen ein Schreiben zu machen waere falsch."""
        assert aufstellung.foto_aus_api({}, True) == ("", "")

    def test_ohne_berechtigung_schweigen_wir(self) -> None:
        """`null` sagt dann nichts ueber das Foto, sondern etwas ueber die
        eigene Berechtigung."""
        assert aufstellung.foto_aus_api({"playerPhoto": None}, False) == ("", "")

    def test_ein_foto_ohne_zeitstempel_gilt_als_vorhanden(self) -> None:
        zustand, stand = aufstellung.foto_aus_api({"playerPhoto": {"id": "x"}}, True)

        assert zustand == "vorhanden"
        assert stand == ""


def spieler(**abweichend: object) -> dict[str, object]:
    vorgabe: dict[str, object] = {
        "firstName": "Max",
        "lastName": "Müller",
        "playerIdCardNumber": "12345678",
        "dateOfBirth": "2004-03-14",
        "jerseyNumber": 7,
        "goalkeeper": False,
        "captain": True,
        "playerId": "p1",
    }
    return {**vorgabe, **abweichend}


class TestSpieler:
    def test_die_felder_kommen_an(self) -> None:
        roh = aufstellung.spieler_aus_api(spieler())

        assert roh["name"] == "Müller, Max"
        assert roh["pass_number"] == "12345678"
        assert roh["birthdate"] == "14.03.2004"
        assert roh["jersey_number"] == "7"
        assert roh["is_captain"] is True
        assert roh["is_goalkeeper"] is False

    def test_die_rueckennummer_wird_text(self) -> None:
        """DFBnet schickt eine Zahl; auf dem Bogen steht Text."""
        assert aufstellung.spieler_aus_api(spieler(jerseyNumber=11))["jersey_number"] == "11"

    def test_nationalitaet_und_status_werden_abzeichen(self) -> None:
        roh = aufstellung.spieler_aus_api(
            spieler(
                nationality={"shortName": "POL"},
                playerStatusShort={"shortName": "A"},
            )
        )

        assert roh["badges"] == ["POL", "A"]

    def test_dasselbe_abzeichen_steht_nicht_zweimal(self) -> None:
        roh = aufstellung.spieler_aus_api(
            spieler(nationality={"shortName": "A"}, playerStatusShort={"shortName": "A"})
        )

        assert roh["badges"] == ["A"]

    def test_ohne_beides_bleibt_die_liste_leer(self) -> None:
        assert aufstellung.spieler_aus_api(spieler())["badges"] == []

    def test_ein_null_objekt_faellt_nicht_um(self) -> None:
        """DFBnet schickt fuer 'nichts' mal `{}` und mal `null`."""
        roh = aufstellung.spieler_aus_api(spieler(nationality=None, playerStatusShort=None))

        assert roh["badges"] == []

    @pytest.mark.parametrize(
        "feld",
        [
            "eligible_for_team",
            "eligible_for_club",
            "no_championship_eligibility",
            "guest_eligibility",
            "second_eligibility",
        ],
    )
    def test_unbekanntes_spielrecht_bleibt_none(self, feld: str) -> None:
        """`None` heisst durchgehend: nicht bekannt. Es zu `False` zu machen
        hiesse, jedem Spieler ein fehlendes Spielrecht anzudichten."""
        assert aufstellung.spieler_aus_api(spieler())[feld] is None

    def test_das_spielrecht_wird_uebernommen_und_nicht_umgedeutet(self) -> None:
        roh = aufstellung.spieler_aus_api(
            spieler(
                eligibleForTeam=False,
                noChampionshipEligibility=True,
                championshipEligibilityFrom="2026-08-01",
                beginDateForCompetitiveMatches="2026-09-01",
                suspensionLineUpError="gesperrt bis 20.09.",
            )
        )

        assert roh["eligible_for_team"] is False
        assert roh["no_championship_eligibility"] is True
        assert roh["championship_from"] == "2026-08-01"
        assert roh["competitive_from"] == "2026-09-01"
        assert roh["suspension_note"] == "gesperrt bis 20.09."

    def test_ein_null_datum_wird_zur_leeren_zeichenkette(self) -> None:
        roh = aufstellung.spieler_aus_api(
            spieler(championshipEligibilityFrom=None, suspensionLineUpError=None)
        )

        assert roh["championship_from"] == ""
        assert roh["suspension_note"] == ""

    def test_das_foto_kommt_mit(self) -> None:
        roh = aufstellung.spieler_aus_api(
            spieler(playerPhoto={"timestamp": "2019-07-01T10:00:00Z"})
        )

        assert roh["photo_state"] == "vorhanden"
        assert roh["photo_timestamp"] == "2019-07-01T10:00:00Z"


class TestVereinswappen:
    def test_die_kennung_aus_der_adresse(self) -> None:
        url = "https://www.dfbnet.org/logo?id=4711&groesse=klein"

        assert aufstellung.vereinswappen_aus_url(url) == "4711"

    def test_ohne_kennung_kommt_nichts(self) -> None:
        assert aufstellung.vereinswappen_aus_url("https://example.org/wappen.png") == ""

    def test_eine_leere_adresse_faellt_nicht_um(self) -> None:
        assert aufstellung.vereinswappen_aus_url("") == ""


class TestAntwortLesen:
    def test_utf8_wie_versprochen(self) -> None:
        assert aufstellung.json_lesen('{"name": "Müller"}'.encode()) == {"name": "Müller"}

    def test_und_die_kodierung_die_wirklich_drinsteht(self) -> None:
        """DFBnet sagt UTF-8 und schickt manchmal ISO-8859-1. Wer das nicht
        abfängt, findet 'Müller' in keiner DFBnet-Warnung wieder."""
        assert aufstellung.json_lesen('{"name": "Müller"}'.encode("latin-1")) == {"name": "Müller"}

    def test_ein_ersatzzeichen_im_text_gilt_als_falsche_kodierung(self) -> None:
        """Es decodiert sauber und ist trotzdem kaputt -- dann wird die
        andere Kodierung versucht, statt das Zeichen stehen zu lassen."""
        gelesen = aufstellung.json_lesen('{"name": "M�ller"}'.encode())

        assert "�" not in str(gelesen["name"])

    def test_eine_liste_kommt_auch_durch(self) -> None:
        assert aufstellung.json_lesen(b"[]") == []


class TestFotoBerechtigung:
    def test_ohne_angabe_gilt_sie_als_da(self) -> None:
        assert aufstellung.fotos_sichtbar({}) is True

    def test_nur_ein_ausdrueckliches_nein_zaehlt(self) -> None:
        """Sonst spricht man jeder fremden Mannschaft sämtliche Fotos ab."""
        assert aufstellung.fotos_sichtbar({"authorizedToViewPlayerPhotos": False}) is False
        assert aufstellung.fotos_sichtbar({"authorizedToViewPlayerPhotos": True}) is True


class TestOffizielle:
    def test_die_rollen_stehen_in_badges(self) -> None:
        """Daran hängt die Regel zum Ordnungsdienst — der Extraktor liest sie
        genau dort."""
        roh = aufstellung.offizieller_aus_api(
            {
                "firstName": "Jens",
                "lastName": "Färber",
                "types": [{"name": "Leiter Ordnungsdienst"}, {"name": "Trainer"}],
            }
        )

        assert roh["name"] == "Färber, Jens"
        assert roh["badges"] == ["Leiter Ordnungsdienst", "Trainer"]
        assert roh["is_official"] is True

    def test_eine_rolle_ohne_namen_faellt_weg(self) -> None:
        roh = aufstellung.offizieller_aus_api({"types": [{"name": ""}, {}]})

        assert roh["badges"] == []


def lineup(**abweichend: object) -> dict[str, object]:
    vorgabe: dict[str, object] = {
        "lineUpPlayers": [spieler()],
        "reservePlayers": [spieler(firstName="Paul", lastName="Schmidt")],
        "teamOfficials": [{"firstName": "Jens", "lastName": "Färber", "types": []}],
    }
    return {**vorgabe, **abweichend}


class TestAbschnitte:
    def test_die_drei_abschnitte_mit_ihren_ueberschriften(self) -> None:
        """Die Überschriften sind keine Zierde: der Extraktor entscheidet an
        ihnen, was Startelf und was Bank ist."""
        abschnitte = aufstellung.abschnitte_aus(lineup())

        assert [a["title"] for a in abschnitte] == [
            "Trainerbank (1 Teamoffizielle)",
            "Startaufstellung (1 Spieler)",
            "Ersatzbank (1 Spieler)",
        ]

    def test_ein_leerer_abschnitt_steht_nicht_da(self) -> None:
        abschnitte = aufstellung.abschnitte_aus(
            {"lineUpPlayers": [spieler()], "reservePlayers": []}
        )

        assert [a["title"] for a in abschnitte] == ["Startaufstellung (1 Spieler)"]

    def test_eine_leere_aufstellung_gibt_nichts(self) -> None:
        """Und bleibt damit für die Regeln *unbekannt* statt leer gemeldet."""
        assert aufstellung.abschnitte_aus({}) == []

    def test_die_bankoffiziellen_kommen_mit(self) -> None:
        abschnitte = aufstellung.abschnitte_aus(
            lineup(additionalBenchOfficials=[{"firstName": "Ute", "lastName": "Kern"}])
        )

        assert abschnitte[0]["title"] == "Trainerbank (2 Teamoffizielle)"

    def test_ohne_berechtigung_bleibt_das_foto_unbekannt(self) -> None:
        abschnitte = aufstellung.abschnitte_aus(
            lineup(authorizedToViewPlayerPhotos=False, lineUpPlayers=[spieler()])
        )
        startelf = next(a for a in abschnitte if "Start" in str(a["title"]))

        assert startelf["players"][0]["photo_state"] == ""


class TestMannschaft:
    def test_alles_zusammen(self) -> None:
        eintrag = aufstellung.mannschaft_aus_api(
            {
                "id": "t1",
                "teamName": "Post SV Dresden 2",
                "clubLogoUrl": "https://www.dfbnet.org/logo?id=4711&groesse=klein",
            },
            lineup(),
        )

        assert eintrag is not None
        assert eintrag["teamName"] == "Post SV Dresden 2"
        assert eintrag["team_id"] == "t1"
        assert eintrag["club_logo_id"] == "4711"
        assert len(eintrag["sections"]) == 3

    def test_ohne_kennung_kommt_nichts(self) -> None:
        """Ein Kader am falschen Verein ist schlimmer als keiner."""
        assert aufstellung.mannschaft_aus_api({"teamName": "irgendwer"}, lineup()) is None

    def test_ein_fehlendes_wappen_faellt_nicht_um(self) -> None:
        eintrag = aufstellung.mannschaft_aus_api({"id": "t1", "clubLogoUrl": None}, {})

        assert eintrag is not None
        assert eintrag["club_logo_id"] == ""
