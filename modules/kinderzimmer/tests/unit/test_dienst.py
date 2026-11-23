"""Reine Fachlogik - keine Datenbank, keine Fixtures, Millisekunden."""

from __future__ import annotations

import datetime as dt
import io
import uuid
import wave

import pytest

from homepi_kinderzimmer import dienst
from homepi_kinderzimmer.dienst import (
    AufnahmeInGebrauch,
    AufnahmeUngueltig,
    SpielNichtVerfuegbar,
    UidUngueltig,
)
from homepi_kinderzimmer.schemas import (
    AufnahmeAusgabe,
    Einstellungen,
    EreignisEingang,
    FigurAusgabe,
    Knopf,
)

JETZT = dt.datetime(2026, 11, 20, 9, 0, tzinfo=dt.UTC)


def wav(
    sekunden: float = 1.0,
    rate: int = 22050,
    kanaele: int = 1,
    breite: int = 2,
) -> bytes:
    puffer = io.BytesIO()
    with wave.open(puffer, "wb") as datei:
        datei.setnchannels(kanaele)
        datei.setsampwidth(breite)
        datei.setframerate(rate)
        datei.writeframes(b"\x00" * int(sekunden * rate) * kanaele * breite)
    return puffer.getvalue()


def aufnahme(**felder: object) -> AufnahmeAusgabe:
    werte: dict[str, object] = {
        "id": uuid.uuid4(),
        "titel": "Oma sagt Hallo",
        "art": "stimme",
        "dauer_ms": 1500,
        "bytes": 66000,
        "sha256": "a" * 64,
        "angelegt": JETZT,
    }
    werte.update(felder)
    return AufnahmeAusgabe.model_validate(werte)


def figur(**felder: object) -> FigurAusgabe:
    werte: dict[str, object] = {
        "id": uuid.uuid4(),
        "uid": "04A1B2C3D4E5F6",
        "name": "Oma",
        "art": "familie",
        "farbe": None,
        "form": None,
        "menge": None,
        "stimme": None,
        "klang": None,
    }
    werte.update(felder)
    return FigurAusgabe.model_validate(werte)


# --- UID ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("roh", "erwartet"),
    [
        ("04:a1:b2:c3:d4:e5:f6", "04A1B2C3D4E5F6"),
        ("04 A1 B2 C3", "04A1B2C3"),
        ("04-a1-b2-c3-d4-e5-f6-07-08-09", "04A1B2C3D4E5F6070809"),
        ("  04a1b2c3d4e5f6 ", "04A1B2C3D4E5F6"),
    ],
)
def test_uid_wird_einheitlich_geschrieben(roh: str, erwartet: str) -> None:
    """Der PN532 liefert Bytes, ein Handy zeigt 04:A1:..., jemand tippt
    klein - gemeint ist jedes Mal dieselbe Figur."""
    assert dienst.normalisiere_uid(roh) == erwartet


@pytest.mark.parametrize("roh", ["", "04A1B2", "04A1B2C3D4", "ZZA1B2C3", "04A1B2C3D4E5F60708"])
def test_falsche_uid_wird_abgelehnt(roh: str) -> None:
    with pytest.raises(UidUngueltig, match="Byte"):
        dienst.normalisiere_uid(roh)


# --- Aufnahmen -----------------------------------------------------------------


def test_passende_wav_wird_vermessen() -> None:
    daten = wav(sekunden=2.0)

    info = dienst.pruefe_wav(daten)

    assert info.dauer_ms == 2000
    assert info.bytes == len(daten)
    assert len(info.sha256) == 64


@pytest.mark.parametrize(
    ("daten", "grund"),
    [
        (b"kein wav", "keine WAV"),
        (wav(rate=44100), "22050"),
        (wav(kanaele=2), "mono"),
        (wav(breite=1), "16 Bit"),
        (wav(sekunden=31), "30 Sekunden"),
        (wav(sekunden=0), "leer"),
    ],
)
def test_unpassende_aufnahme_wird_mit_grund_abgelehnt(daten: bytes, grund: str) -> None:
    """Der ESP spielt die Samples ohne Decoder ab. Was hier durchrutscht,
    kommt dort als Rauschen oder gar nicht an."""
    with pytest.raises(AufnahmeUngueltig, match=grund):
        dienst.pruefe_wav(daten)


def test_benutzte_aufnahme_laesst_sich_nicht_loeschen() -> None:
    gemeint = uuid.uuid4()
    figuren = [figur(name="Oma", stimme=gemeint), figur(name="Kuh", uid="04A1B2C3")]
    knoepfe = [Knopf(nummer=2, klang=gemeint)]

    with pytest.raises(AufnahmeInGebrauch, match="Figur „Oma“, Knopf 2"):
        dienst.pruefe_loeschbar(gemeint, figuren, knoepfe)


def test_unbenutzte_aufnahme_darf_weg() -> None:
    dienst.pruefe_loeschbar(uuid.uuid4(), [figur()], [Knopf(nummer=1)])


def test_unbekannte_aufnahme_wird_nicht_zugeordnet() -> None:
    bekannt = {uuid.uuid4()}
    fremd = uuid.uuid4()

    with pytest.raises(dienst.AufnahmeUnbekannt):
        dienst.pruefe_aufnahmen_vorhanden([fremd, None], bekannt)
    dienst.pruefe_aufnahmen_vorhanden([None, *bekannt], bekannt)


# --- Einstellungen -------------------------------------------------------------


def test_spielauswahl_mit_bereiten_spielen_geht_durch() -> None:
    dienst.pruefe_spielauswahl(Einstellungen(spiele_aktiv=["stimmen"], startspiel="stimmen"))


def test_geplantes_spiel_laesst_sich_nicht_einschalten() -> None:
    """Die Firmware kann es noch nicht - eingeschaltet waere es ein Knopf
    auf dem Elternpult, der nichts tut."""
    with pytest.raises(SpielNichtVerfuegbar, match="Kuckuck"):
        dienst.pruefe_spielauswahl(
            Einstellungen(spiele_aktiv=["stimmen", "kuckuck"], startspiel="stimmen")
        )


def test_unbekanntes_spiel_wird_abgelehnt() -> None:
    with pytest.raises(SpielNichtVerfuegbar, match="quatsch"):
        dienst.pruefe_spielauswahl(Einstellungen(spiele_aktiv=["quatsch"], startspiel="quatsch"))


def test_startspiel_muss_eingeschaltet_sein() -> None:
    with pytest.raises(SpielNichtVerfuegbar, match="Startspiel"):
        dienst.pruefe_spielauswahl(
            Einstellungen(spiele_aktiv=["stimmen"], startspiel="licht-und-klang")
        )


def test_knopf_darf_nicht_doppelt_vorkommen() -> None:
    with pytest.raises(ValueError, match="nur einmal"):
        Einstellungen(knoepfe=[Knopf(nummer=1), Knopf(nummer=1)])


# --- Manifest ------------------------------------------------------------------


def test_manifest_enthaelt_nur_benutzte_dateien() -> None:
    oma, muh, uebrig, glocke = aufnahme(), aufnahme(), aufnahme(), aufnahme(art="klang")
    figuren = [figur(stimme=oma.id, klang=muh.id)]
    einstellungen = Einstellungen(knoepfe=[Knopf(nummer=1, klang=glocke.id)])

    manifest = dienst.baue_manifest(einstellungen, figuren, [oma, muh, uebrig, glocke])

    assert {d.id for d in manifest.dateien} == {str(oma.id), str(muh.id), str(glocke.id)}
    assert manifest.format == 1
    assert manifest.figuren[0].stimme == str(oma.id)
    assert manifest.einstellungen.knoepfe[0].klang == str(glocke.id)


def test_stand_haengt_am_inhalt_nicht_an_der_reihenfolge() -> None:
    """Gleicher Inhalt, gleicher Stand - sonst glaubt das Geraet nach jedem
    Speichern an eine Aenderung und laedt alles neu."""
    a, b = figur(name="A", uid="04A1B2C3"), figur(name="B", uid="04A1B2C4")
    e = Einstellungen()

    assert dienst.baue_manifest(e, [a, b], []).stand == dienst.baue_manifest(e, [b, a], []).stand


def test_jede_aenderung_aendert_den_stand() -> None:
    e = Einstellungen()
    vorher = dienst.baue_manifest(e, [figur()], []).stand

    assert dienst.baue_manifest(e, [figur(name="Opa")], []).stand != vorher
    assert dienst.baue_manifest(Einstellungen(lautstaerke_max=41), [figur()], []).stand != vorher
    neue_datei = aufnahme(sha256="b" * 64)
    mit_datei = dienst.baue_manifest(e, [figur(stimme=neue_datei.id)], [neue_datei])
    assert mit_datei.stand != vorher


def test_stand_ist_kurz_und_lesbar() -> None:
    stand = dienst.baue_manifest(Einstellungen(), [], []).stand
    assert len(stand) == 16
    int(stand, 16)


# --- Ereignisse ----------------------------------------------------------------


def ereignis(**felder: object) -> EreignisEingang:
    werte: dict[str, object] = {"nr": 1, "ms": 1000, "art": "knopf", "knopf": 1}
    werte.update(felder)
    return EreignisEingang.model_validate(werte)


def test_uhrzeit_vom_geraet_gilt() -> None:
    zeit = dt.datetime(2026, 11, 20, 8, 15, tzinfo=dt.UTC)
    e = ereignis(zeit=zeit)

    assert dienst.zeitpunkt(e, start=3, jetzt_ms=9000, empfangen=JETZT) == zeit


def test_ohne_uhrzeit_wird_aus_der_laufzeit_zurueckgerechnet() -> None:
    """Vor dem ersten NTP-Abgleich kennt der ESP nur seine Laufzeit."""
    e = ereignis(ms=4000)

    ergebnis = dienst.zeitpunkt(e, start=3, jetzt_ms=10000, empfangen=JETZT)

    assert ergebnis == JETZT - dt.timedelta(seconds=6)


def test_aus_einem_frueheren_start_ohne_uhrzeit_ist_die_zeit_unbekannt() -> None:
    """Die Laufzeit eines vergangenen Starts sagt nichts ueber heute."""
    e = ereignis(ms=4000, start=3)

    assert dienst.zeitpunkt(e, start=4, jetzt_ms=10000, empfangen=JETZT) is None


def test_nachgereichtes_aus_dem_laufenden_start_wird_zurueckgerechnet() -> None:
    e = ereignis(ms=4000, start=4)

    ergebnis = dienst.zeitpunkt(e, start=4, jetzt_ms=10000, empfangen=JETZT)

    assert ergebnis == JETZT - dt.timedelta(seconds=6)


def test_laufzeit_aus_der_zukunft_wird_nicht_geglaubt() -> None:
    e = ereignis(ms=20000)

    assert dienst.zeitpunkt(e, start=3, jetzt_ms=10000, empfangen=JETZT) is None


NAMEN = {"04A1B2C3D4E5F6": "Oma"}


@pytest.mark.parametrize(
    ("felder", "text"),
    [
        ({"art": "knopf", "knopf": 2}, "Knopf 2 gedrückt"),
        ({"art": "figur_auf", "uid": "04A1B2C3D4E5F6"}, "„Oma“ aufgelegt"),
        ({"art": "figur_ab", "uid": "04A1B2C3D4E5F6"}, "„Oma“ weggenommen"),
        ({"art": "figur_auf", "uid": "04FFFFFF"}, "Unbekannte Figur 04FFFFFF aufgelegt"),
        ({"art": "spiel", "spiel": "stimmen"}, "Spiel „Vertraute Stimmen“ gewählt"),
        ({"art": "spiel", "spiel": "weg"}, "Spiel „weg“ gewählt"),
        ({"art": "start"}, "Gerät eingeschaltet"),
        ({"art": "ruhe"}, "Still geworden – niemand hat mehr gespielt"),
        ({"art": "abgleich"}, "Neuen Stand übernommen"),
    ],
)
def test_protokoll_spricht_in_saetzen(felder: dict[str, object], text: str) -> None:
    assert (
        dienst.beschreibe(
            str(felder["art"]),
            knopf=felder.get("knopf"),  # type: ignore[arg-type]
            uid=felder.get("uid"),  # type: ignore[arg-type]
            spiel=felder.get("spiel"),  # type: ignore[arg-type]
            figurennamen=NAMEN,
        )
        == text
    )


def test_unbekannte_figuren_neueste_zuerst_ohne_doppelte() -> None:
    frueh, spaet = JETZT - dt.timedelta(hours=1), JETZT
    gesehen = [("04AAAAAA", frueh), ("04BBBBBB", spaet), ("04AAAAAA", frueh), ("04CCCCCC", None)]

    ergebnis = dienst.unbekannte_figuren(gesehen, bekannte={"04BBBBBB"})

    assert ergebnis == [("04AAAAAA", frueh), ("04CCCCCC", None)]


def test_unbekannte_figuren_nimmt_den_juengsten_zeitpunkt() -> None:
    frueh, spaet = JETZT - dt.timedelta(hours=1), JETZT
    gesehen = [("04AAAAAA", frueh), ("04AAAAAA", spaet)]

    assert dienst.unbekannte_figuren(gesehen, bekannte=set()) == [("04AAAAAA", spaet)]


# --- Geraete -------------------------------------------------------------------


def test_token_ist_lang_und_nur_als_hash_gespeichert() -> None:
    klartext, hashwert = dienst.neues_token()

    assert len(klartext) >= 40
    assert hashwert == dienst.token_hash(klartext)
    assert klartext not in hashwert


def test_zwei_tokens_sind_verschieden() -> None:
    assert dienst.neues_token()[0] != dienst.neues_token()[0]


@pytest.mark.parametrize(
    ("geraet", "aktuell", "erwartet"),
    [(None, "abc", None), ("abc", "abc", True), ("alt", "abc", False)],
)
def test_stand_des_geraets(geraet: str | None, aktuell: str, erwartet: bool | None) -> None:
    assert dienst.stand_aktuell(geraet, aktuell) is erwartet


@pytest.mark.parametrize(
    ("kopf", "erwartet"),
    [
        ("Bearer abc123", "abc123"),
        ("bearer   abc123 ", "abc123"),
        ("Basic abc123", None),
        ("Bearer", None),
        ("", None),
        (None, None),
    ],
)
def test_token_aus_dem_kopf(kopf: str | None, erwartet: str | None) -> None:
    assert dienst.token_aus_kopf(kopf) == erwartet


# --- Konflikte -----------------------------------------------------------------


def test_konflikt_bei_der_uid_wird_beim_namen_genannt() -> None:
    """Die Datenbank sagt, welcher Schluessel doppelt ist - der Mensch soll
    nicht raten muessen, ob es der Name oder die UID war."""
    text = 'duplicate key value violates unique constraint "kinderzimmer_figuren_uid_key"'

    assert "UID" in dienst.konfliktmeldung(text, "allgemein")
    assert "Namen" in dienst.konfliktmeldung(text.replace("uid", "name"), "allgemein")
    assert dienst.konfliktmeldung("irgendwas", "allgemein") == "allgemein"
