"""Die Entscheidungen dieses Artefakts.

REIN: keine Datenbank, kein await. Alles, was I/O macht, gehoert in
speicher.py.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import secrets
import uuid
import wave
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from homepi_core import ServiceError

from .schemas import (
    FORMAT,
    AufnahmeAusgabe,
    Einstellungen,
    EreignisEingang,
    FigurAusgabe,
    Knopf,
    Manifest,
    ManifestDatei,
    ManifestEinstellungen,
    ManifestFigur,
    ManifestKnopf,
)
from .spiele import spiel as finde_spiel
from .uid import UidUngueltig, normalisiere_uid

__all__ = ["UidUngueltig", "normalisiere_uid"]

#: Das Format, das die Firmware ohne Decoder abspielt. Der Browser rechnet
#: jede Aufnahme vor dem Hochladen darauf um.
ABTASTRATE = 22050
HOECHSTDAUER_S = 30


class Unbekannt(ServiceError):
    status = 404
    title = "Nicht gefunden"


class AufnahmeUnbekannt(ServiceError):
    status = 422
    title = "Aufnahme unbekannt"


class NameVergeben(ServiceError):
    status = 409
    title = "Bereits vergeben"


class AufnahmeUngueltig(ServiceError):
    status = 422
    title = "Aufnahme passt nicht"


class AufnahmeInGebrauch(ServiceError):
    status = 409
    title = "Aufnahme wird noch benutzt"


class SpielNichtVerfuegbar(ServiceError):
    status = 422
    title = "Spiel nicht verfügbar"


class GeraetNichtAngemeldet(ServiceError):
    status = 401
    title = "Gerät nicht angemeldet"


# --- Aufnahmen -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WavInfo:
    dauer_ms: int
    bytes: int
    sha256: str


def pruefe_wav(daten: bytes) -> WavInfo:
    """Nimmt nur, was der ESP ohne Umrechnung abspielen kann."""
    try:
        with wave.open(io.BytesIO(daten), "rb") as datei:
            kanaele = datei.getnchannels()
            breite = datei.getsampwidth()
            rate = datei.getframerate()
            frames = datei.getnframes()
    except (wave.Error, EOFError) as fehler:
        raise AufnahmeUngueltig("Das ist keine WAV-Datei.") from fehler

    if rate != ABTASTRATE:
        raise AufnahmeUngueltig(f"Die Aufnahme hat {rate} Hz, erwartet sind {ABTASTRATE} Hz.")
    if kanaele != 1:
        raise AufnahmeUngueltig("Die Aufnahme muss mono sein, sie hat mehrere Kanäle.")
    if breite != 2:
        raise AufnahmeUngueltig(f"Die Aufnahme hat {breite * 8} Bit, erwartet sind 16 Bit.")
    if frames == 0:
        raise AufnahmeUngueltig("Die Aufnahme ist leer.")
    dauer_ms = round(frames * 1000 / rate)
    if dauer_ms > HOECHSTDAUER_S * 1000:
        raise AufnahmeUngueltig(
            f"Die Aufnahme ist {dauer_ms // 1000} Sekunden lang, höchstens "
            f"{HOECHSTDAUER_S} Sekunden passen."
        )
    return WavInfo(dauer_ms=dauer_ms, bytes=len(daten), sha256=hashlib.sha256(daten).hexdigest())


def verwendungen(
    aufnahme_id: uuid.UUID, figuren: Sequence[FigurAusgabe], knoepfe: Sequence[Knopf]
) -> list[str]:
    wo = [f"Figur „{f.name}“" for f in figuren if aufnahme_id in (f.stimme, f.klang)]
    wo += [f"Knopf {k.nummer}" for k in knoepfe if k.klang == aufnahme_id]
    return wo


def pruefe_loeschbar(
    aufnahme_id: uuid.UUID, figuren: Sequence[FigurAusgabe], knoepfe: Sequence[Knopf]
) -> None:
    """Weg waere sie nur hier. Auf dem Geraet fehlte ploetzlich ein Klang,
    und niemand wuesste, warum Omas Figur stumm ist."""
    wo = verwendungen(aufnahme_id, figuren, knoepfe)
    if wo:
        raise AufnahmeInGebrauch(
            f"Die Aufnahme gehört noch zu {', '.join(wo)}. Erst dort eine andere wählen."
        )


def pruefe_aufnahmen_vorhanden(
    gewaehlt: Iterable[uuid.UUID | None], vorhanden: set[uuid.UUID]
) -> None:
    if any(a is not None and a not in vorhanden for a in gewaehlt):
        raise AufnahmeUnbekannt("Eine gewählte Aufnahme gibt es nicht mehr. Bitte neu wählen.")


# --- Einstellungen -------------------------------------------------------------


def pruefe_spielauswahl(einstellungen: Einstellungen) -> None:
    for kennung in einstellungen.spiele_aktiv:
        eintrag = finde_spiel(kennung)
        if eintrag is None:
            raise SpielNichtVerfuegbar(f"Ein Spiel „{kennung}“ gibt es nicht.")
        if not eintrag.bereit:
            raise SpielNichtVerfuegbar(
                f"„{eintrag.titel}“ ist geplant, das Gerät kann es noch nicht."
            )
    if einstellungen.startspiel not in einstellungen.spiele_aktiv:
        raise SpielNichtVerfuegbar("Das Startspiel muss eingeschaltet sein.")


# --- Manifest ------------------------------------------------------------------


def _text(kennung: uuid.UUID | None) -> str | None:
    return None if kennung is None else str(kennung)


def baue_manifest(
    einstellungen: Einstellungen,
    figuren: Sequence[FigurAusgabe],
    aufnahmen: Sequence[AufnahmeAusgabe],
) -> Manifest:
    """Was das Geraet wissen muss - und eine Pruefsumme darueber.

    Der Stand ist eine Pruefsumme und kein Zaehler: Speichern ohne Aenderung
    laesst ihn stehen, und kein Schreibweg kann vergessen, ihn zu erhoehen.
    """
    knoepfe = [
        ManifestKnopf(nummer=k.nummer, farbe=k.farbe, klang=_text(k.klang))
        for k in sorted(einstellungen.knoepfe, key=lambda k: k.nummer)
    ]
    figurliste = [
        ManifestFigur(
            uid=f.uid,
            name=f.name,
            art=f.art,
            farbe=f.farbe,
            form=f.form,
            menge=f.menge,
            stimme=_text(f.stimme),
            klang=_text(f.klang),
        )
        for f in sorted(figuren, key=lambda f: f.uid)
    ]
    benutzt = {k.klang for k in einstellungen.knoepfe} | {
        a for f in figuren for a in (f.stimme, f.klang)
    }
    dateien = [
        ManifestDatei(id=str(a.id), sha256=a.sha256, bytes=a.bytes, dauer_ms=a.dauer_ms)
        for a in sorted(aufnahmen, key=lambda a: str(a.id))
        if a.id in benutzt
    ]
    teil = ManifestEinstellungen(
        lautstaerke_max=einstellungen.lautstaerke_max,
        helligkeit_max=einstellungen.helligkeit_max,
        ruhe_nach_min=einstellungen.ruhe_nach_min,
        startspiel=einstellungen.startspiel,
        spiele_aktiv=list(einstellungen.spiele_aktiv),
        knoepfe=knoepfe,
    )
    inhalt = {
        "format": FORMAT,
        "einstellungen": teil.model_dump(),
        "figuren": [f.model_dump() for f in figurliste],
        "dateien": [d.model_dump() for d in dateien],
    }
    roh = json.dumps(inhalt, sort_keys=True, ensure_ascii=False).encode()
    stand = hashlib.sha256(roh).hexdigest()[:16]
    return Manifest(
        format=FORMAT, stand=stand, einstellungen=teil, figuren=figurliste, dateien=dateien
    )


# --- Ereignisse ----------------------------------------------------------------


def zeitpunkt(
    ereignis: EreignisEingang,
    *,
    start: int,
    jetzt_ms: int,
    empfangen: dt.datetime,
) -> dt.datetime | None:
    """Wann es geschah.

    Ohne Uhrzeit vom Geraet laesst es sich nur aus der Laufzeit des
    *laufenden* Starts zurueckrechnen. Ein frueherer Start hat eine eigene
    Laufzeit, die mit heute nichts zu tun hat.
    """
    if ereignis.zeit is not None:
        return ereignis.zeit
    ereignis_start = start if ereignis.start is None else ereignis.start
    if ereignis_start != start or ereignis.ms > jetzt_ms:
        return None
    return empfangen - dt.timedelta(milliseconds=jetzt_ms - ereignis.ms)


def beschreibe(
    art: str,
    *,
    knopf: int | None,
    uid: str | None,
    spiel: str | None,
    figurennamen: Mapping[str, str],
) -> str:
    """Ein Satz fuers Protokoll. Die Eltern lesen ihn, keine Entwickler."""

    def figur() -> str:
        if uid is not None and uid in figurennamen:
            return f"„{figurennamen[uid]}“"
        return f"Unbekannte Figur {uid}"

    match art:
        case "knopf":
            return f"Knopf {knopf} gedrückt"
        case "figur_auf":
            return f"{figur()} aufgelegt"
        case "figur_ab":
            return f"{figur()} weggenommen"
        case "spiel":
            eintrag = finde_spiel(spiel) if spiel else None
            return f"Spiel „{eintrag.titel if eintrag else spiel}“ gewählt"
        case "start":
            return "Gerät eingeschaltet"
        case "ruhe":
            return "Still geworden – niemand hat mehr gespielt"
        case _:
            return "Neuen Stand übernommen"


def unbekannte_figuren(
    gesehen: Iterable[tuple[str, dt.datetime | None]],
    bekannte: set[str],
    hoechstens: int = 10,
) -> list[tuple[str, dt.datetime | None]]:
    """Aufgelegte Tags, die noch keine Figur sind - der Weg zum Anlernen.

    Auflegen am Geraet, dann in der Liste anklicken: so muss niemand eine UID
    abtippen.
    """
    juengste: dict[str, dt.datetime | None] = {}
    for uid, wann in gesehen:
        if uid in bekannte:
            continue
        bisher = juengste.get(uid)
        if uid not in juengste or (wann is not None and (bisher is None or wann > bisher)):
            juengste[uid] = wann

    def schluessel(eintrag: tuple[str, dt.datetime | None]) -> tuple[int, float]:
        wann = eintrag[1]
        return (0, -wann.timestamp()) if wann is not None else (1, 0.0)

    return sorted(juengste.items(), key=schluessel)[:hoechstens]


# --- Geraete -------------------------------------------------------------------


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def neues_token() -> tuple[str, str]:
    """256 Zufallsbit. Gespeichert wird nur der Hash - wie beim Sitzungstoken.

    SHA-256 und nicht Argon2: ein Token aus Zufallsbits ist nicht ratbar, und
    das Geraet meldet sich bei jedem Ereignis an.
    """
    klartext = secrets.token_urlsafe(32)
    return klartext, token_hash(klartext)


def stand_aktuell(geraet: str | None, aktuell: str) -> bool | None:
    return None if geraet is None else geraet == aktuell


def token_aus_kopf(kopf: str | None) -> str | None:
    """``Authorization: Bearer <token>`` - alles andere ist keine Anmeldung."""
    if not kopf:
        return None
    teile = kopf.split()
    if len(teile) != 2 or teile[0].lower() != "bearer":
        return None
    return teile[1]


# --- Konflikte -----------------------------------------------------------------


def konfliktmeldung(datenbanktext: str, allgemein: str) -> str:
    """Sagt, welcher eindeutige Wert schon vergeben ist.

    Postgres nennt den verletzten Schluessel im Text, etwa
    ``kinderzimmer_figuren_uid_key``. Den Menschen interessiert nur, ob es der
    Name oder die UID war.
    """
    if "_uid_key" in datenbanktext:
        return "Diese UID gehört schon zu einer anderen Figur."
    if "_name_key" in datenbanktext or "_titel_key" in datenbanktext:
        return "Diesen Namen gibt es schon. Bitte einen anderen wählen."
    return allgemein
