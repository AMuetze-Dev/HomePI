"""§ 67 (3) SpO SFV — Spielerfotos.

Zwei Sätze, beide aus den Daten prüfbar:

* § 67 (2): „Bei Online-Anträgen ist immer ein aktuelles digitales Spielerfoto
  […] mit hochzuladen." Zusammen mit § 56 (1) — Nachweis der Spielberechtigung
  ist die Spielberechtigungsliste „mit Lichtbild der Spielerin/des Spielers" —
  ist ein Spieler ohne Foto nicht zu identifizieren.
* § 67 (3): „Die Aktualität der Spielerfotos […] ist von den Vereinen in
  regelmäßigen Abständen zu überprüfen […] a) Im Kinder- und Juniorenbereich:
  […] beim Wechsel aus dem Junioren- in den Erwachsenenbereich (nach
  A-Jun./B-Juniorinnen) b) Im Erwachsenenbereich: alle 10 Jahre."

Die Grenze ist der **18. Geburtstag**. § 42 (1): „Herrenspieler sind Spieler,
die das 18. Lebensjahr vollendet haben." § 42 (6): „A-Junioren sind nach
Vollendung des 18. Lebensjahres spielberechtigt für alle Herrenmannschaften."
Ab diesem Tag kann der Wechsel erfolgen, also ist ein Foto, das älter ist,
sicher eines aus der Juniorenzeit.

Eine frühere Fassung setzte den 1. Juli des Jahres an, in dem der Spieler 19
wird — das Ende der A-Junioren. Das war zu spät und pauschal: ein Foto vom
18. Geburtstag bis zu jenem Juli konnte längst ein Herrenfoto sein und wurde
trotzdem gemeldet. Gemeldet vom Staffelleiter am 09.09.2026.

Die U23 aus § 68 (2) c) ist eine dritte Zahl und eine andere Vorschrift
(Stammspieler); mit dem Foto hat sie nichts zu tun.

Die Grenze wird **in der Regeldatei** gerechnet, nicht im Programm: sonst
stünde sie fest, während die Regel darüber angeblich anpassbar ist.

Die Daten stammen aus der DFBnet-Aufstellungs-API: `playerPhoto` ist entweder
ein Objekt mit `timestamp` oder `null`. Fehlt das Feld ganz — ältere
gespeicherte Berichte, DOM-Rückfallebene, fehlende Berechtigung —, ist der
Zustand *unbekannt*, und dann schweigen alle drei Regeln.
"""

from datetime import date

import pytest

from homepi_pruefdienst import katalog as regelbruecke
from homepi_pruefdienst.aufstellung import spieler_aus_api as _api_player_to_raw
from homepi_pruefdienst.bericht import MatchMeta, MatchReport, Player, TeamSquad
from homepi_pruefdienst.regelwerk import vorlagen_ausrollen
from homepi_pruefdienst.regelwerk.uebersetzer import uebersetzen

from .hilfe import StaffelConfig
from .hilfe import spieler_aus_api as _spieler_aus_api


@pytest.fixture
def regelordner(tmp_path):
    ordner = tmp_path / "regeln"
    vorlagen_ausrollen(ordner)
    regelbruecke.zuruecksetzen()
    yield ordner
    regelbruecke.zuruecksetzen()


SPIELTAG = "04.09.2026"


def staffel(**felder):
    grund = dict(
        name="Ü35 2. Stadtklasse",
        altersklasse="ue35",
        dfbnet_filter="2.Kreisklasse",
        sportrichter_email="sr@example.de",
        saison="26/27",
    )
    grund.update(felder)
    return StaffelConfig(**grund)


def spieler(name, geburt="01.01.1985", zustand="vorhanden", stand=""):
    return Player(
        name=name,
        pass_number=f"P-{name}",
        birthdate=geburt,
        jersey_number="7",
        photo_state=zustand,
        photo_timestamp=stand,
    )


def bericht(heim):
    gast = [spieler(f"G{i}") for i in range(11)]
    return MatchReport(
        meta=MatchMeta(
            home_team="SV Fortschritt Meißen-West",
            away_team="SG Gittersee",
            match_date=SPIELTAG,
            match_day="2",
            kickoff="10:00",
            league_class="2.Kreisklasse",
            competition="Meisterschaft",
            match_id="ABC123",
        ),
        home_squad=TeamSquad(
            team="Heim",
            team_name="SV Fortschritt Meißen-West",
            starting_eleven=list(heim),
        ),
        away_squad=TeamSquad(team="Gast", team_name="SG Gittersee", starting_eleven=list(gast)),
    )


def pruefe(report, ordner):
    return regelbruecke.pruefen(report, staffel(), ordner)


def regeln_von(verstoesse):
    return sorted(v.rule for v in verstoesse)


def befund(verstoesse, kennung):
    treffer = [v for v in verstoesse if v.rule == kennung]
    return treffer[0] if treffer else None


def elf(erster=None):
    kader = [spieler(f"S{i}") for i in range(11)]
    if erster is not None:
        kader[0] = erster
    return kader


# ────────────────────────────────────────────────────── was DFBnet liefert
class TestAusDerApi:
    """`playerPhoto` in der Aufstellungs-API, an echten Antworten abgelesen."""

    def test_ein_foto_bringt_zustand_und_zeitstempel(self):
        roh = _api_player_to_raw(
            {
                "firstName": "Jens",
                "lastName": "Kalkowski",
                "playerPhoto": {
                    "id": "02BMH6511S000000VS5489BBVVS799DU",
                    "timestamp": "2020-08-09T14:28:14.786+02:00",
                },
            }
        )
        assert roh["photo_state"] == "vorhanden"
        assert roh["photo_timestamp"] == "2020-08-09T14:28:14.786+02:00"

    def test_playerphoto_null_heisst_kein_foto(self):
        """Der Fall aus dem echten Spiel: ein Ersatzspieler ohne Bild."""
        roh = _api_player_to_raw({"lastName": "Schilde", "playerPhoto": None})
        assert roh["photo_state"] == "fehlt"
        assert roh["photo_timestamp"] == ""

    def test_ohne_das_feld_ist_der_zustand_unbekannt(self):
        """Nicht „fehlt": eine Antwort ohne das Feld ist keine Aussage."""
        roh = _api_player_to_raw({"lastName": "Alt"})
        assert roh["photo_state"] == ""

    def test_ohne_berechtigung_wird_nichts_behauptet(self):
        """`authorizedToViewPlayerPhotos` kann false sein.

        Dann liefert DFBnet für jeden Spieler `null`, und ohne diese Sperre
        meldete das Programm einem anderen Staffelleiter jede Mannschaft
        vollständig als „ohne Foto".
        """
        roh = _api_player_to_raw({"lastName": "Ohne"}, fotos_sichtbar=False)
        assert roh["photo_state"] == ""

    def test_der_zustand_uebersteht_den_weg_in_den_bericht(self):
        """In der alten Anwendung lag dazwischen die Datenbank, hier der
        Extraktor. "fehlt" darf unterwegs nicht zu "" werden -- das eine ist
        ein Verstoss, das andere Unwissen."""
        zurueck = _spieler_aus_api({"lastName": "Schilde", "playerPhoto": None})

        assert zurueck.photo_state == "fehlt"


# ────────────────────────────────────────────────────── Vokabeln der Regel
class TestVokabeln:
    def test_hat_foto_ist_dreiwertig(self):
        report = bericht(
            [
                spieler("Mit", zustand="vorhanden", stand="2024-05-01T10:00:00+02:00"),
                spieler("Ohne", zustand="fehlt"),
                spieler("Unbekannt", zustand=""),
            ]
        )
        aufstellung = uebersetzen(report, staffel()).mannschaften[0].spieler
        assert {s.name: s.hat_foto for s in aufstellung} == {
            "Mit": True,
            "Ohne": False,
            "Unbekannt": None,
        }

    def test_der_zeitstempel_wird_zum_datum(self):
        report = bericht([spieler("Mit", stand="2020-08-09T14:28:14.786+02:00")])
        person = uebersetzen(report, staffel()).mannschaften[0].spieler[0]
        assert person.foto_stand == date(2020, 8, 9)
        assert person.foto_alter == 6  # Spieltag 04.09.2026

    def test_das_geburtsdatum_reist_mit(self):
        """Mehr braucht die Regel nicht — sie rechnet die Grenze selbst."""
        report = bericht([spieler("Jung", geburt="14.11.2004")])
        person = uebersetzen(report, staffel()).mannschaften[0].spieler[0]
        assert person.geburtsdatum == date(2004, 11, 14)

    def test_die_grenze_steht_nicht_mehr_im_programm(self):
        """§ 42 (1) gehört in die Regeldatei, nicht in die Vokabeln.

        Sonst ist die Zahl festgeschrieben, während die Regel darüber
        anpassbar heißt.
        """
        person = uebersetzen(bericht(elf()), staffel()).mannschaften[0].spieler[0]
        assert not hasattr(person, "erwachsen_seit")
        assert not hasattr(person, "foto_aus_juniorenzeit")


# ────────────────────────────────────────────────────────── die Regeln
class TestRegeln:
    def test_ein_kader_mit_aktuellen_fotos_ist_still(self, regelordner):
        kader = elf(spieler("Aktuell", stand="2024-05-01T10:00:00+02:00"))
        namen = regeln_von(pruefe(bericht(kader), regelordner))
        assert not [n for n in namen if n.startswith("spielerfoto")]

    def test_ein_spieler_ohne_foto(self, regelordner):
        kader = elf(spieler("Schilde", zustand="fehlt"))
        treffer = befund(pruefe(bericht(kader), regelordner), "spielerfoto_fehlt")
        assert treffer is not None
        assert "Schilde" in treffer.message

    def test_ein_foto_aelter_als_zehn_jahre(self, regelordner):
        kader = elf(spieler("Alt", stand="2015-06-30T10:00:00+02:00"))
        treffer = befund(pruefe(bericht(kader), regelordner), "spielerfoto_zu_alt")
        assert treffer is not None
        assert "Alt" in treffer.message
        assert "11" in treffer.message

    def test_genau_zehn_jahre_ist_noch_keine_ueberschreitung(self, regelordner):
        """„alle 10 Jahre" — bei zehn ist die Frist erreicht, nicht überschritten."""
        kader = elf(spieler("Grenze", stand="2016-09-05T10:00:00+02:00"))
        assert "spielerfoto_zu_alt" not in regeln_von(pruefe(bericht(kader), regelordner))

    def test_ein_foto_aus_der_juniorenzeit(self, regelordner):
        """Geboren 2004, erwachsen seit 01.07.2023, Foto von 2022.

        Keine zehn Jahre alt — die Zehnjahresregel greift also nicht, und ohne
        § 67 (3) a) bliebe dieses Foto bis 2032 unbemerkt.
        """
        kader = elf(spieler("Jung", geburt="14.11.2004", stand="2022-03-01T10:00:00+02:00"))
        treffer = befund(pruefe(bericht(kader), regelordner), "spielerfoto_aus_juniorenzeit")
        assert treffer is not None
        assert "Jung" in treffer.message

    def test_unter_achtzehn_wird_nicht_gemeldet(self, regelordner):
        """Vor dem 18. Geburtstag kann der Wechsel nicht stattgefunden haben.

        Geboren 03.02.2009, am Spieltag 17. Die Pflicht aus § 67 (3) a)
        entsteht frühestens mit § 42 (1) — ohne diese Grenze meldete die Regel
        jeden jungen Spieler, und das auf jedem Spielbericht neu.
        """
        kader = elf(spieler("Noch Junior", geburt="03.02.2009", stand="2024-05-01T10:00:00+02:00"))
        assert "spielerfoto_aus_juniorenzeit" not in regeln_von(pruefe(bericht(kader), regelordner))

    def test_ab_dem_achtzehnten_geburtstag_wird_gemeldet(self, regelordner):
        """Geboren 03.02.2008, 18 seit dem 03.02.2026, Spiel am 04.09.2026.

        Das Foto von 2024 stammt aus der Zeit davor — nach § 42 (6) durfte er
        seit dem 03.02.2026 bei den Herren spielen, das Foto gehört erneuert.
        """
        kader = elf(spieler("Aufgerückt", geburt="03.02.2008", stand="2024-05-01T10:00:00+02:00"))
        assert "spielerfoto_aus_juniorenzeit" in regeln_von(pruefe(bericht(kader), regelordner))

    def test_ein_foto_nach_dem_achtzehnten_geburtstag_ist_in_ordnung(self, regelordner):
        """Die Gegenprobe zur alten Fassung: genau dieses Foto meldete sie.

        Geboren 03.02.2008, Foto vom 01.05.2026 — also nach dem 18.
        Geburtstag. Die alte Grenze (1. Juli 2027) hätte es als Juniorenfoto
        gemeldet, obwohl es keines ist.
        """
        kader = elf(spieler("Neues Bild", geburt="03.02.2008", stand="2026-05-01T10:00:00+02:00"))
        assert "spielerfoto_aus_juniorenzeit" not in regeln_von(pruefe(bericht(kader), regelordner))

    def test_ein_geburtstag_am_29_februar_bringt_nichts_zum_absturz(self, regelordner):
        """Den 29.02.2026 gibt es nicht — `replace(year=…)` wirft dort."""
        kader = elf(spieler("Schalttag", geburt="29.02.2008", stand="2024-05-01T10:00:00+02:00"))
        namen = regeln_von(pruefe(bericht(kader), regelordner))
        assert "regel_fehlerhaft" not in namen
        assert "spielerfoto_aus_juniorenzeit" in namen

    def test_ein_altes_foto_wird_nur_einmal_gemeldet(self, regelordner):
        """Ein zwanzig Jahre altes Foto eines 40-Jährigen stammt zwangsläufig
        aus der Juniorenzeit. Zwei Befunde wären derselbe Vorwurf zweimal."""
        kader = elf(spieler("Uralt", geburt="01.01.1986", stand="2006-03-01T10:00:00+02:00"))
        namen = regeln_von(pruefe(bericht(kader), regelordner))
        assert "spielerfoto_zu_alt" in namen
        assert "spielerfoto_aus_juniorenzeit" not in namen

    def test_ohne_wissen_wird_nichts_gemeldet(self, regelordner):
        """Ältere gespeicherte Berichte kennen das Feld nicht.

        Sie dürfen nach einem Update nicht schlagartig als „alle Fotos fehlen"
        dastehen.
        """
        kader = [spieler(f"S{i}", zustand="") for i in range(11)]
        namen = regeln_von(pruefe(bericht(kader), regelordner))
        assert not [n for n in namen if n.startswith("spielerfoto")]

    def test_der_befund_nennt_den_paragrafen(self, regelordner):
        kader = elf(spieler("Schilde", zustand="fehlt"))
        treffer = befund(pruefe(bericht(kader), regelordner), "spielerfoto_fehlt")
        assert "67" in treffer.details.get("paragraf", "")


class TestWegeAusDemBefund:
    """Der Weg vom Hinweis über die Mahnung zum Sportgerichtsantrag.

    Gewünscht am 09.09.2026: „zuerst wird es ein Hinweis, dann wird es ein
    Mahnungsformular und im späteren Prozess sogar ein Sportgerichtsantrag."
    Die Regel bietet beide Wege an; welcher genommen wird, entscheidet der
    Staffelleiter — die Reihenfolge ist sein Verfahren, nicht das des
    Programms.
    """

    @pytest.fixture
    def geladen(self, regelordner):
        from homepi_pruefdienst.katalog import regeln as regeln_laden

        return {r.id: r for r in regeln_laden(regelordner).registry}

    @pytest.mark.parametrize(
        "kennung",
        ["spielerfoto_fehlt", "spielerfoto_zu_alt", "spielerfoto_aus_juniorenzeit"],
    )
    def test_beide_wege_stehen_offen(self, kennung, geladen):
        regel = geladen[kennung]
        assert regel.darf_mahnen, "kein Mahnungsformular möglich"
        assert regel.darf_vor_gericht, "kein Sportgerichtsantrag möglich"

    @pytest.mark.parametrize(
        "kennung",
        ["spielerfoto_fehlt", "spielerfoto_zu_alt", "spielerfoto_aus_juniorenzeit"],
    )
    def test_der_antrag_traegt_einen_grund(self, kennung, geladen):
        """Ohne Grund steht im Antrag an das Sportgericht kein Vorwurf."""
        assert geladen[kennung].grund.strip()

    @pytest.mark.parametrize(
        "kennung",
        ["spielerfoto_fehlt", "spielerfoto_zu_alt", "spielerfoto_aus_juniorenzeit"],
    )
    def test_das_ankreuzfeld_bleibt_dasselbe(self, kennung, geladen):
        """Das Formular des Verbandes führt genau ein Feld dafür."""
        assert geladen[kennung].bagatelle == "Spielerfotos"
