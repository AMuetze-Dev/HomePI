"""Einstellungen, Mannschaften und Schreiben - alles ohne Datenbank.

Die Entscheidungen hier sind rein, also kosten diese Tests nichts und laufen
bei jedem Speichern. Was eine Datenbank braucht, steht in tests/integration/.
"""

from __future__ import annotations

from datetime import date

import pytest

from homepi_staffelpilot import dienst

# ── Einstellungen ─────────────────────────────────────────────────────────


def test_leere_tabelle_gibt_die_voreinstellungen() -> None:
    """Eine frische Installation muss benutzbar sein, nicht erst eingerichtet."""
    werte = dienst.einstellungen_aus({})

    assert werte.pruefzeitraum_tage == 30
    assert werte.frist_tage == 14
    assert werte.staffelleiter == ""


def test_zahlen_kommen_als_zeichenkette_und_gehen_als_zahl() -> None:
    werte = dienst.einstellungen_aus({"pruefzeitraum_tage": "7", "frist_tage": "21"})

    assert werte.pruefzeitraum_tage == 7
    assert werte.frist_tage == 21


def test_leerer_wert_faellt_auf_die_voreinstellung_zurueck() -> None:
    """Ein geleertes Feld in der Oberflaeche ist kein Wunsch nach null Tagen."""
    assert dienst.einstellungen_aus({"pruefzeitraum_tage": "  "}).pruefzeitraum_tage == 30


def test_text_wird_getrimmt() -> None:
    assert dienst.einstellungen_aus({"staffelleiter": "  Aaron  "}).staffelleiter == "Aaron"


@pytest.mark.parametrize("wert", ["null", "12,5", "-"])
def test_was_keine_zahl_ist_wird_gesagt_und_nicht_geraten(wert: str) -> None:
    with pytest.raises(dienst.WertUnbrauchbar) as fehler:
        dienst.einstellungen_aus({"frist_tage": wert})

    assert "ganze Zahl" in str(fehler.value)


@pytest.mark.parametrize(("feld", "wert"), [("pruefzeitraum_tage", "0"), ("frist_tage", "365")])
def test_zahlen_ausserhalb_der_grenzen_werden_abgelehnt(feld: str, wert: str) -> None:
    """Null Tage Pruefzeitraum liefert stumm eine leere Liste - und dann sucht
    man den Fehler im Prueflauf statt in den Einstellungen."""
    with pytest.raises(dienst.WertUnbrauchbar):
        dienst.einstellungen_aus({feld: wert})


def test_unbekannter_schluessel_stoert_nicht() -> None:
    """Sonst haelt eine Einstellung, die es einmal gab, die Installation an."""
    assert dienst.einstellungen_aus({"von_frueher": "x"}).frist_tage == 14


# ── Mannschaften ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "verein", "nummer"),
    [
        ("SV Loschwitz", "SV Loschwitz", 1),
        ("SV Loschwitz 2", "SV Loschwitz", 2),
        ("SG Weixdorf 3", "SG Weixdorf", 3),
    ],
)
def test_nummer_aus_dem_namenszusatz(name: str, verein: str, nummer: int) -> None:
    assert dienst.verein_und_nummer(name) == (verein, nummer)


def test_eine_jahreszahl_ist_keine_mannschaftsnummer() -> None:
    """'Dresdner SC 1898' hat keine 1898 Mannschaften. Ohne diese Grenze waere
    die erste Mannschaft des Vereins eine 1898. und stuende unter allen."""
    assert dienst.verein_und_nummer("Dresdner SC 1898") == ("Dresdner SC 1898", 1)


def test_die_jahreszahl_stoert_die_echte_nummer_nicht() -> None:
    assert dienst.verein_und_nummer("Dresdner SC 1898 3") == ("Dresdner SC 1898", 3)


def test_hoehere_sind_die_kleineren_nummern_desselben_vereins() -> None:
    geraten = dienst.hoehere_raten(["SV Loschwitz", "SV Loschwitz 2", "SV Loschwitz 3"])

    assert geraten["SV Loschwitz"] == []
    assert geraten["SV Loschwitz 2"] == ["SV Loschwitz"]
    assert geraten["SV Loschwitz 3"] == ["SV Loschwitz", "SV Loschwitz 2"]


def test_ein_fremder_verein_zaehlt_nicht_als_hoeher() -> None:
    geraten = dienst.hoehere_raten(["SV Loschwitz 2", "SG Weixdorf"])

    assert geraten["SV Loschwitz 2"] == []


def test_eine_spielgemeinschaft_bleibt_unsicher_bis_jemand_hinsieht() -> None:
    """Der Verein steht bei einer SG nicht im Namen - der Schluss aus dem
    Namenszusatz greift ins Leere, und ein falscher Schluss faellt nicht laut
    auf, sondern prueft still das Falsche."""
    assert dienst.mannschaft_unsicher(ist_sg=True, bestaetigt=False)
    assert not dienst.mannschaft_unsicher(ist_sg=True, bestaetigt=True)
    assert not dienst.mannschaft_unsicher(ist_sg=False, bestaetigt=False)


# ── Wege und Zustaende ────────────────────────────────────────────────────


def test_ein_unbekannter_weg_wird_abgelehnt() -> None:
    with pytest.raises(dienst.WegUnbekannt):
        dienst.weg_pruefen("sportgerich")


def test_zu_einem_befund_ohne_weg_gehoert_kein_vorgang() -> None:
    """Die meisten Befunde sind Hinweise. Fuer sie ein Schreiben anzubieten
    hiesse, dem Staffelleiter Arbeit vorzuschlagen, die es nicht gibt."""
    with pytest.raises(dienst.WegUnbekannt):
        dienst.art_aus_weg("kein")


@pytest.mark.parametrize("weg", ["mahnung", "sportgericht"])
def test_der_weg_bestimmt_die_art(weg: str) -> None:
    assert dienst.art_aus_weg(weg) == weg


@pytest.mark.parametrize(
    ("alt", "neu"),
    [("entwurf", "versandt"), ("versandt", "erledigt"), ("versandt", "entwurf")],
)
def test_erlaubte_schritte(alt: str, neu: str) -> None:
    assert dienst.zustand_weiter(alt, neu) == neu


def test_ein_erledigter_vorgang_wird_nicht_wieder_entwurf() -> None:
    """Er waere ein Schreiben, das ein Verein in der Hand hat und das hier
    trotzdem als ungeschrieben gilt."""
    with pytest.raises(dienst.ZustandUnmoeglich):
        dienst.zustand_weiter("erledigt", "entwurf")


def test_der_unmoegliche_schritt_sagt_was_ginge() -> None:
    with pytest.raises(dienst.ZustandUnmoeglich) as fehler:
        dienst.zustand_weiter("entwurf", "erledigt")

    assert "versandt" in str(fehler.value)


# ── Aktenzeichen ──────────────────────────────────────────────────────────


def test_aktenzeichen_sortiert_und_traegt_die_saison() -> None:
    assert dienst.aktenzeichen("26/27", 7) == "26-27-0007"
    assert dienst.aktenzeichen("26/27", 7) < dienst.aktenzeichen("26/27", 12)


def test_aktenzeichen_ohne_saison_faellt_nicht_um() -> None:
    assert dienst.aktenzeichen("", 1) == "ohne-saison-0001"


# ── Das Schreiben ─────────────────────────────────────────────────────────


def _anlass(**felder: object) -> dienst.Anlass:
    vorgabe: dict[str, object] = {
        "staffel": "3.Kreisliga C",
        "saison": "26/27",
        "heim": "SG Gittersee",
        "gast": "SV Fortschritt",
        "spieldatum": date(2026, 9, 13),
        "dfbnet_id": "M-1",
        "titel": "Feldverweis auf Dauer",
        "sachverhalt": "Feldverweis in Minute 71.",
        "verein": "SG Gittersee",
        "betroffener": "Max Müller",
        "grund": "Tätlichkeit",
    }
    return dienst.Anlass(**{**vorgabe, **felder})  # type: ignore[arg-type]


EINSTELLUNGEN = dienst.Einstellungen(
    staffelleiter="Aaron Mütze", verband="Kreisverband Dresden", frist_tage=14
)


def test_die_mahnung_nennt_spiel_person_und_frist() -> None:
    schreiben = dienst.vorgang_entwurf("mahnung", _anlass(), EINSTELLUNGEN, heute=date(2026, 9, 15))

    assert "SG Gittersee" in schreiben.betreff
    assert "13.09.2026" in schreiben.text
    assert "Max Müller" in schreiben.text
    assert "29.09.2026" in schreiben.text
    assert "Aaron Mütze" in schreiben.text


def test_der_sportgerichtsfall_ist_ein_antrag_und_keine_mahnung() -> None:
    schreiben = dienst.vorgang_entwurf(
        "sportgericht", _anlass(), EINSTELLUNGEN, heute=date(2026, 9, 15)
    )

    assert "Sportgericht" in schreiben.betreff
    assert "Antrag auf Eröffnung" in schreiben.text
    assert "Tätlichkeit" in schreiben.text


def test_derselbe_anlass_gibt_denselben_text() -> None:
    """Der Kern der Sache: hier wird nichts erzeugt, hier wird eingesetzt.

    Ein Schreiben an einen Verein muss ein halbes Jahr spaeter Satz fuer Satz
    erklaerbar sein - und das ist es nur, wenn es reproduzierbar ist.
    """
    zweimal = [
        dienst.vorgang_entwurf("mahnung", _anlass(), EINSTELLUNGEN, date(2026, 9, 15)).text
        for _ in range(2)
    ]

    assert zweimal[0] == zweimal[1]


def test_ohne_betroffenen_steht_der_verein_da() -> None:
    schreiben = dienst.vorgang_entwurf(
        "mahnung", _anlass(betroffener=""), EINSTELLUNGEN, date(2026, 9, 15)
    )

    assert "Betroffen:    SG Gittersee" in schreiben.text


def test_ohne_staffelleiter_steht_ein_hinweis_statt_einer_leerzeile() -> None:
    """Eine leere Unterschriftszeile faellt beim Ueberfliegen nicht auf - und
    das Schreiben geht ohne Absender hinaus."""
    schreiben = dienst.vorgang_entwurf(
        "mahnung", _anlass(), dienst.Einstellungen(), date(2026, 9, 15)
    )

    assert "Staffelleiter in den Einstellungen eintragen" in schreiben.text


def test_die_frist_folgt_den_einstellungen() -> None:
    schreiben = dienst.vorgang_entwurf(
        "mahnung", _anlass(), dienst.Einstellungen(frist_tage=7), date(2026, 9, 15)
    )

    assert "22.09.2026" in schreiben.text


def test_die_paarung_traegt_einen_halbgeviertstrich() -> None:
    """Ein Bindestrich saehe neben "Meissen-West" nach einer Worttrennung aus."""
    schreiben = dienst.vorgang_entwurf(
        "mahnung",
        _anlass(gast="SV Fortschritt Meißen-West"),
        EINSTELLUNGEN,
        date(2026, 9, 15),
    )

    assert "SG Gittersee – SV Fortschritt Meißen-West" in schreiben.text  # noqa: RUF001


# ── Der Satz zum Vergehen ───────────────────────────────────────────


def test_die_mahnung_nennt_den_paragrafen_zum_vergehen() -> None:
    """Der Unterschied zwischen einer Notiz und einem Schreiben des Verbandes.

    Der Prüflauf schreibt "Kein Leiter Ordnungsdienst angegeben." — richtig,
    aber das ist die Sprache der Prüfung. Im Brief steht der Paragraf.
    """
    schreiben = dienst.vorgang_entwurf(
        "mahnung",
        _anlass(regel="order_manager_missing", verein="SV Loschwitz", betroffener=""),
        EINSTELLUNGEN,
        date(2026, 9, 15),
    )

    assert "kein Leiter Ordnungsdienst" in schreiben.text
    assert "§ 53" in schreiben.text
    assert "Sportgericht" in schreiben.text  # der Folgesatz


def test_die_einzelheiten_des_befundes_stehen_im_satz() -> None:
    schreiben = dienst.vorgang_entwurf(
        "mahnung",
        _anlass(
            regel="confirmation_late",
            verein="SV Loschwitz",
            einzelheiten={"signed_at": "22:35", "deadline": "20:14"},
        ),
        EINSTELLUNGEN,
        date(2026, 9, 15),
    )

    assert "erst am 22:35" in schreiben.text
    assert "(20:14)" in schreiben.text


def test_ohne_einzelheiten_bleibt_kein_angefangener_satz_stehen() -> None:
    """Dieselbe Regel, nur ohne Zeitstempel — und ohne "erst am " ins Leere."""
    schreiben = dienst.vorgang_entwurf(
        "mahnung",
        _anlass(regel="confirmation_late", verein="SV Loschwitz"),
        EINSTELLUNGEN,
        date(2026, 9, 15),
    )

    assert "erst am" not in schreiben.text
    assert "durch SV Loschwitz und damit nach Ablauf der Frist bestätigt." in schreiben.text


def test_eine_regel_ohne_vorlage_behaelt_den_text_des_befundes() -> None:
    """Kein Schreiben ohne Sachverhalt — lieber der Satz der Prüfung."""
    schreiben = dienst.vorgang_entwurf(
        "mahnung", _anlass(regel="gibt_es_nicht"), EINSTELLUNGEN, date(2026, 9, 15)
    )

    assert "Feldverweis in Minute 71." in schreiben.text


def test_der_sportgerichtsantrag_nimmt_denselben_satz() -> None:
    schreiben = dienst.vorgang_entwurf(
        "sportgericht",
        _anlass(regel="order_manager_is_player", betroffener="Max Müller"),
        EINSTELLUNGEN,
        date(2026, 9, 15),
    )

    assert "Max Müller gleichzeitig als Leiter Ordnungsdienst" in schreiben.text
    # Ein Antrag ist keine Mahnung: der Folgesatz gehört nicht hinein.
    assert "weiterer Verstoß dieser Mannschaft" not in schreiben.text
