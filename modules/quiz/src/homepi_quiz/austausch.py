"""Kataloge hinein und hinaus.

REIN wie dienst.py: Bytes hinein, Fragen heraus. Keine Datenbank, kein
Netz - ein ZIP im Speicher zu lesen ist keine I/O, die einen Test langsam
macht.

Zwei Formate:

* **Battle.Net** - das, was das alte Projekt tatsaechlich speichert: ein ZIP
  mit ``quiz.json``, Bilder und Ton als Data-URL darin. (Das XML-Format aus
  der Spezifikation hat es nie ueber eine Beispieldatei hinaus geschafft.)
* **Eigenes Paket** - ``katalog.json`` plus ``medien/``, zum Sichern und
  Weitergeben. Was hinausgeht, kommt verlustfrei wieder herein.

Was nicht passt, bricht den Import nicht ab, sondern steht als Hinweis im
Ergebnis: Eine kaputte Frage von dreissig soll nicht die anderen
neunundzwanzig kosten. Was gar kein Paket ist, wird abgelehnt.

Bilder von fremden Adressen werden **nicht** geholt. Der Pi soll nicht auf
Zuruf einer hochgeladenen Datei ins Internet greifen.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import re
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from homepi_core import ServiceError
from pydantic import ValidationError

from . import dienst
from .schemas import (
    AuswahlDaten,
    BildauswahlDaten,
    BildOption,
    BuzzerDaten,
    FrageDaten,
    FrageEingabe,
    FreitextDaten,
    HotspotDaten,
    Option,
    Paar,
    SchaetzDaten,
    SortierDaten,
    ZahlDaten,
    Ziel,
    ZuordnenDaten,
)

#: Das echte Battle.Net-Quiz des Benutzers hat 7 MB - Bilder als Base64.
MAX_PAKET_BYTES = 64 * 1024 * 1024
#: Entpackt. Darueber ist es kein Quiz mehr, sondern ein Angriff.
MAX_ENTPACKT_BYTES = 256 * 1024 * 1024
MAX_EINTRAEGE = 500
MAX_FRAGEN = 300

FORMAT = "homepi-quiz"
VERSION = 1

ENDUNGEN = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/mp4": "m4a",
    "audio/webm": "webm",
}
_DATA_URL = re.compile(r"^data:([\w.+-]+/[\w.+-]+)(?:;[^,]*)?;base64,(.*)$", re.DOTALL)


class ImportUngueltig(ServiceError):
    status = 422
    title = "Import nicht möglich"


Medien = dict[str, tuple[str, bytes]]


@dataclass(slots=True)
class ImportFrage:
    eingabe: FrageEingabe
    #: ``bild``, ``ton``, ``option-<n>`` -> (MIME-Typ, Inhalt)
    medien: Medien = field(default_factory=dict)


@dataclass(slots=True)
class Paket:
    titel: str
    beschreibung: str
    fragen: list[ImportFrage]
    hinweise: list[str]


# ------------------------------------------------------------- Lesen


def lies_paket(roh: bytes) -> Paket:
    if len(roh) > MAX_PAKET_BYTES:
        raise ImportUngueltig(f"Die Datei ist größer als {MAX_PAKET_BYTES // (1024 * 1024)} MB.")
    if roh[:2] == b"PK":
        return _lies_zip(roh)
    if roh.lstrip()[:1] == b"{":
        daten = _json(roh)
        if daten.get("format") == FORMAT:
            return _lies_eigenes(daten, {})
        return _lies_battlenet(daten)
    raise ImportUngueltig("Das ist weder ein ZIP noch eine JSON-Datei.")


def _json(roh: bytes) -> dict[str, Any]:
    try:
        daten = json.loads(roh.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as fehler:
        raise ImportUngueltig(f"Die JSON-Datei ist nicht lesbar: {fehler}") from fehler
    if not isinstance(daten, dict):
        raise ImportUngueltig("Die JSON-Datei enthält kein Quiz.")
    return daten


def _lies_zip(roh: bytes) -> Paket:
    try:
        archiv = zipfile.ZipFile(io.BytesIO(roh))
    except zipfile.BadZipFile as fehler:
        raise ImportUngueltig("Das ZIP ist beschädigt.") from fehler
    with archiv:
        eintraege = archiv.infolist()
        if len(eintraege) > MAX_EINTRAEGE:
            raise ImportUngueltig(f"Das ZIP hat mehr als {MAX_EINTRAEGE} Dateien.")
        # Die Groessen stehen im Verzeichnis des ZIP. Geprueft wird vor dem
        # Entpacken - sonst waere die Pruefung erst nach dem Schaden fertig.
        if sum(e.file_size for e in eintraege) > MAX_ENTPACKT_BYTES:
            raise ImportUngueltig("Das ZIP ist entpackt zu groß.")
        namen = {e.filename for e in eintraege}

        def lies(name: str) -> bytes:
            try:
                return archiv.read(name)
            except (zipfile.BadZipFile, KeyError) as fehler:
                raise ImportUngueltig(f"„{name}“ im ZIP ist nicht lesbar.") from fehler

        if "katalog.json" in namen:
            daten = _json(lies("katalog.json"))
            medien = {n: lies(n) for n in namen if n.startswith("medien/")}
            return _lies_eigenes(daten, medien)
        if "quiz.json" in namen:
            return _lies_battlenet(_json(lies("quiz.json")))
        if any(n.endswith("questions.xml") for n in namen):
            raise ImportUngueltig(
                "XML-Kataloge aus der ersten Battle.Net-Fassung werden nicht übernommen. "
                "Gespeicherte Battle.Net-Quizze (mit quiz.json) gehen."
            )
        raise ImportUngueltig("Im ZIP fehlt quiz.json (Battle.Net) oder katalog.json.")


def _fragenliste(daten: dict[str, Any], schluessel: str) -> list[Any]:
    fragen = daten.get(schluessel)
    if not isinstance(fragen, list):
        raise ImportUngueltig("In der Datei steht keine Liste mit Fragen.")
    if len(fragen) > MAX_FRAGEN:
        raise ImportUngueltig(f"Mehr als {MAX_FRAGEN} Fragen in einem Katalog gehen nicht.")
    return fragen


def _titel(wert: object, ersatz: str) -> str:
    text = " ".join(str(wert or "").split())[:120]
    return text or ersatz


# ------------------------------------------------------------- Battle.Net


def _lies_battlenet(daten: dict[str, Any]) -> Paket:
    fragen = _fragenliste(daten, "questions")
    paket = Paket(
        titel=_titel(daten.get("title"), "Battle.Net-Quiz"),
        beschreibung=" ".join(str(daten.get("description") or "").split())[:500],
        fragen=[],
        hinweise=[],
    )
    for nummer, frage in enumerate(fragen, start=1):
        if not isinstance(frage, dict):
            paket.hinweise.append(f"Frage {nummer}: kein lesbarer Eintrag, übersprungen.")
            continue
        uebersetzt = _battlenet_frage(nummer, frage, paket.hinweise)
        if uebersetzt is not None:
            paket.fragen.append(uebersetzt)
    return paket


def _battlenet_frage(nummer: int, q: dict[str, Any], hinweise: list[str]) -> ImportFrage | None:
    typ = str(q.get("type") or "")
    uebersetzer = _BATTLENET.get(typ)
    if uebersetzer is None:
        hinweise.append(f"Frage {nummer}: Fragetyp „{typ}“ gibt es hier nicht, übersprungen.")
        return None
    try:
        daten = uebersetzer(q)
        eingabe = FrageEingabe(
            text=str(q.get("question") or "")[:500],
            kategorie=str(q.get("category") or "")[:60],
            punkte=_punkte(q.get("points")),
            zeitlimit=None,
            daten=daten,
        )
    except (ValidationError, ValueError, TypeError) as fehler:
        hinweise.append(f"Frage {nummer}: nicht übernommen ({_grund(fehler)}).")
        return None

    medien: Medien = {}
    _medium(nummer, "bild", q.get("imageData"), eingabe.daten, medien, hinweise)
    _fremdes_bild(nummer, q.get("imageUrl"), hinweise)
    _medium(nummer, "ton", q.get("audioData"), eingabe.daten, medien, hinweise)
    if isinstance(eingabe.daten, BildauswahlDaten):
        for index, option in enumerate(q.get("imageOptions") or []):
            if isinstance(option, dict):
                schluessel = f"option-{index}"
                _medium(
                    nummer, schluessel, option.get("imageData"), eingabe.daten, medien, hinweise
                )
                _fremdes_bild(nummer, option.get("imageUrl"), hinweise)
    return ImportFrage(eingabe=eingabe, medien=medien)


def _punkte(wert: object) -> int:
    zahl = _zahl_oder_none(wert)
    return 1 if zahl is None else min(100, max(1, int(zahl)))


def _grund(fehler: Exception) -> str:
    if isinstance(fehler, ValidationError):
        ersten = fehler.errors()[0]
        return str(ersten.get("msg", "ungültig")).removeprefix("Value error, ")
    return str(fehler)


def _zahl_oder_none(wert: object) -> float | None:
    try:
        return float(str(wert).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _bn_text(q: dict[str, Any]) -> FrageDaten:
    loesung = str(q.get("correctAnswerText") or "").strip()
    if q.get("textInputType") == "number":
        zahl = _zahl_oder_none(loesung)
        if zahl is not None:
            return ZahlDaten(loesung=zahl)
    return FreitextDaten(loesungen=[loesung] if loesung else [])


def _bn_auswahl(q: dict[str, Any]) -> FrageDaten:
    optionen = [
        Option(text=str(a.get("text") or ""), richtig=bool(a.get("isCorrect")))
        for a in q.get("answers") or []
        if isinstance(a, dict) and str(a.get("text") or "").strip()
    ]
    return AuswahlDaten(optionen=optionen)


def _bn_wahrfalsch(q: dict[str, Any]) -> FrageDaten:
    # Im Battle.Net-Editor ist 1 "Wahr" und 0 "Falsch" (TrueFalseEditor.tsx).
    wahr = q.get("correctAnswer") == 1
    return AuswahlDaten(
        optionen=[Option(text="Wahr", richtig=wahr), Option(text="Falsch", richtig=not wahr)]
    )


def _bn_schaetzung(q: dict[str, Any]) -> FrageDaten:
    return SchaetzDaten(
        minimum=q.get("sliderMin", 0),
        maximum=q.get("sliderMax", 100),
        schritt=q.get("sliderStep") or 1,
        loesung=q.get("sliderCorrectValue", 0),
        einheit=str(q.get("sliderUnit") or "")[:20],
    )


def _bn_hotspot(q: dict[str, Any]) -> FrageDaten:
    # Prozent von Breite und Hoehe wie hier. Battle.Net wertet einen Treffer
    # bis 10 % Abstand (scoring.service.ts), also wird das der Radius.
    x, y = _zahl_oder_none(q.get("hotspotX")), _zahl_oder_none(q.get("hotspotY"))
    if x is None or y is None:
        raise ValueError("keine Stelle im Bild gesetzt")
    return HotspotDaten(ziele=[Ziel(x=x, y=y, radius=_zahl_oder_none(q.get("tolerance")) or 10)])


def _bn_zuordnen(q: dict[str, Any]) -> FrageDaten:
    paare = [
        Paar(links=str(p.get("left") or ""), rechts=str(p.get("right") or ""))
        for p in q.get("matchingPairs") or []
        if isinstance(p, dict) and str(p.get("left") or "").strip()
    ]
    return ZuordnenDaten(paare=paare)


def _bn_bildauswahl(q: dict[str, Any]) -> FrageDaten:
    return BildauswahlDaten(
        optionen=[
            BildOption(text=str(o.get("alt") or "")[:80], richtig=bool(o.get("correct")))
            for o in q.get("imageOptions") or []
            if isinstance(o, dict)
        ]
    )


_BATTLENET: dict[str, Callable[[dict[str, Any]], FrageDaten]] = {
    "buzzer": lambda q: BuzzerDaten(loesung=str(q.get("correctAnswerText") or "")[:200]),
    "text": _bn_text,
    "multiple-choice": _bn_auswahl,
    "true-false": _bn_wahrfalsch,
    "sorting": lambda q: SortierDaten(elemente=[str(e) for e in q.get("sortingItems") or []]),
    "slider": _bn_schaetzung,
    "hotspot": _bn_hotspot,
    "matching": _bn_zuordnen,
    "image-choice": _bn_bildauswahl,
}


def _medium(
    nummer: int,
    schluessel: str,
    data_url: object,
    daten: FrageDaten,
    medien: Medien,
    hinweise: list[str],
) -> None:
    if not data_url:
        return
    art = "Ton" if schluessel == "ton" else "Bild"
    treffer = _DATA_URL.match(str(data_url))
    try:
        if treffer is None:
            raise ValueError("kein eingebettetes Bild")
        inhalt = base64.b64decode(treffer.group(2), validate=True)
        mime = (
            dienst.pruefe_bild(treffer.group(1), len(inhalt))
            if schluessel == "bild"
            else dienst.pruefe_medium(schluessel, daten, treffer.group(1), len(inhalt))
        )
    except (ValueError, binascii.Error, ServiceError) as fehler:
        hinweise.append(f"Frage {nummer}: {art} nicht übernommen ({fehler}).")
        return
    medien[schluessel] = (mime, inhalt)


def _fremdes_bild(nummer: int, adresse: object, hinweise: list[str]) -> None:
    if isinstance(adresse, str) and adresse.startswith(("http://", "https://")):
        hinweise.append(
            f"Frage {nummer}: Bild von {urlparse(adresse).hostname} nicht geholt - "
            "lade es im Katalog selbst hoch."
        )


# ------------------------------------------------------------- Eigenes Paket


def _lies_eigenes(daten: dict[str, Any], dateien: dict[str, bytes]) -> Paket:
    if daten.get("version") != VERSION:
        raise ImportUngueltig(f"Dieses Paket hat eine unbekannte Version ({daten.get('version')}).")
    paket = Paket(
        titel=_titel(daten.get("titel"), "Quiz"),
        beschreibung=str(daten.get("beschreibung") or "")[:500],
        fragen=[],
        hinweise=[],
    )
    for nummer, eintrag in enumerate(_fragenliste(daten, "fragen"), start=1):
        if not isinstance(eintrag, dict):
            paket.hinweise.append(f"Frage {nummer}: kein lesbarer Eintrag, übersprungen.")
            continue
        verweise = eintrag.pop("medien", {}) or {}
        try:
            eingabe = FrageEingabe.model_validate(eintrag)
        except ValidationError as fehler:
            paket.hinweise.append(f"Frage {nummer}: nicht übernommen ({_grund(fehler)}).")
            continue
        medien: Medien = {}
        for schluessel, verweis in verweise.items():
            inhalt = dateien.get(str(verweis))
            mime = _mime_aus_name(str(verweis))
            if inhalt is None or mime is None:
                paket.hinweise.append(f"Frage {nummer}: {verweis} fehlt im Paket.")
                continue
            medien[str(schluessel)] = (mime, inhalt)
        paket.fragen.append(ImportFrage(eingabe=eingabe, medien=medien))
    return paket


def _mime_aus_name(name: str) -> str | None:
    endung = name.rsplit(".", 1)[-1].lower()
    return next((mime for mime, e in ENDUNGEN.items() if e == endung), None)


def schreibe_paket(titel: str, beschreibung: str, fragen: Sequence[ImportFrage]) -> bytes:
    eintraege: list[dict[str, Any]] = []
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", compression=zipfile.ZIP_DEFLATED) as archiv:
        for nummer, frage in enumerate(fragen, start=1):
            eintrag = frage.eingabe.model_dump(mode="json")
            verweise: dict[str, str] = {}
            for schluessel, (mime, inhalt) in frage.medien.items():
                name = f"medien/{nummer}-{schluessel}.{ENDUNGEN.get(mime, 'bin')}"
                archiv.writestr(name, inhalt)
                verweise[schluessel] = name
            if verweise:
                eintrag["medien"] = verweise
            eintraege.append(eintrag)
        archiv.writestr(
            "katalog.json",
            json.dumps(
                {
                    "format": FORMAT,
                    "version": VERSION,
                    "titel": titel,
                    "beschreibung": beschreibung,
                    "fragen": eintraege,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return puffer.getvalue()
