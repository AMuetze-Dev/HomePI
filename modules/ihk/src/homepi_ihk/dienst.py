"""Die Entscheidungen dieses Artefakts - der Rechenkern der IHK-Bewertung.

REIN: keine Datenbank, kein await, keine Fixtures. Portiert aus
``ExamManager V2/src/lib/scoring.ts``; die Unit-Tests rechnen dieselben echten
Altprüfungen nach wie dort.

Bewertungslogik in Kürze:
  - Dokumentation 100 P über 7 Sektionen und 38 Kriterien. Sektion 5 hat
    eine Mängel-Zeile von -2 bis 0, die in die erreichten Punkte einfließt,
    nicht in das Maximum.
  - Präsentation und Fachgespräch 100 P über 5 Sektionen. Unterkriterien auf
    der Skala {1; 0,75; 0,5; 0,25; 0}; vorgeschlagen wird
    ``round(max * Mittelwert)``, die Sektionspunkte setzt der Prüfer.
  - Note aus der 0-100-Tabelle der Vorlage.
  - Gesamt = (Teil 1 * 20 + Teil 2) / 100 mit Teil 2 aus drei schriftlichen
    Bereichen und dem Projekt; Ergänzungsprüfung in genau einem Bereich.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Literal

from homepi_core import ServiceError

from .katalog import KATALOG, NOTEN, Knoten, Sektion, blaetter

# ── Fehler ───────────────────────────────────────────────────────────────────


class TagUnbekannt(ServiceError):
    status = 404
    title = "Prüfungstag unbekannt"


class PrueflingUnbekannt(ServiceError):
    status = 404
    title = "Prüfling unbekannt"


class DokumentUnbekannt(ServiceError):
    status = 404
    title = "Dokument unbekannt"


class KriteriumUnbekannt(ServiceError):
    status = 422
    title = "Kriterium unbekannt"


class PunkteUnzulaessig(ServiceError):
    status = 422
    title = "Punktzahl nicht zulässig"


class ZeitschrittUnzulaessig(ServiceError):
    status = 409
    title = "Zeitmessung passt nicht"


class KeinPdf(ServiceError):
    status = 415
    title = "Kein PDF"


class DokumentZuGross(ServiceError):
    status = 413
    title = "Dokument zu groß"


# ── Noten ────────────────────────────────────────────────────────────────────


def runde(wert: float) -> int:
    """Excel-ROUND: halb weg von null. Pythons round() rundet zur geraden Zahl."""
    return int(math.copysign(math.floor(abs(wert) + 0.5), wert))


def note_fuer(punkte: float | None) -> float | None:
    if punkte is None:
        return None
    return NOTEN.tabelle[min(100, max(0, runde(punkte)))]


def ist_grenzfall(punkte: float | None) -> bool:
    return punkte is not None and runde(punkte) in NOTEN.grenzfaelle


@dataclass(frozen=True, slots=True)
class Notenband:
    von: int
    bis: int
    note: int


def notenbaender() -> list[Notenband]:
    """Punktebereiche je ganzer Note, wie neben dem Punkteübertrag gedruckt."""
    baender: list[Notenband] = []
    for punkte in range(100, -1, -1):
        note = runde(NOTEN.tabelle[punkte])
        if baender and baender[-1].note == note:
            baender[-1] = replace(baender[-1], bis=punkte)
        else:
            baender.append(Notenband(punkte, punkte, note))
    return baender


@dataclass(frozen=True, slots=True)
class Notenstufe:
    """Wo eine Punktzahl steht - und wie weit es nach oben und unten ist."""

    punkte: int
    note: float
    ganze_note: int
    grenzfall: bool
    #: die nächstbessere ganze Note, None bei der 1
    bessere_note: int | None
    #: Punkte bis dorthin
    fehlen: int | None
    #: Punkte über der Untergrenze dieser Note; 0 heißt: ein Punkt weniger,
    #: und es ist die nächstschlechtere
    puffer: int


def notenstufe(punkte: int) -> Notenstufe:
    if not 0 <= punkte <= 100:
        raise PunkteUnzulaessig(f"Punkte gehen von 0 bis 100, nicht {punkte}")
    baender = notenbaender()
    index = next(i for i, b in enumerate(baender) if b.bis <= punkte <= b.von)
    band = baender[index]
    besser = baender[index - 1] if index > 0 else None
    return Notenstufe(
        punkte=punkte,
        note=NOTEN.tabelle[punkte],
        ganze_note=band.note,
        grenzfall=ist_grenzfall(punkte),
        bessere_note=besser.note if besser else None,
        fehlen=besser.bis - punkte if besser else None,
        puffer=punkte - band.bis,
    )


# ── Blöcke ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Block:
    """Ein Bemerkungsfeld. ``id`` ist der erste Knoten und Schlüssel der Bemerkung."""

    id: str
    knoten: tuple[Knoten, ...]


def bloecke(sektion: Sektion) -> list[Block]:
    """Wie die verbundenen Zellen der Bemerkungsspalte im Original.

    Die Sektionsüberschrift hat ein eigenes Feld, jede Gruppe deckt sich und
    ihre Kinder ab, und aufeinanderfolgende Einzelkriterien teilen sich eins.
    Formular und Ausdruck benutzen dieselbe Aufteilung.
    """
    ergebnis: list[Block] = [Block(sektion.id, ())]
    lauf: list[Knoten] | None = None
    for kind in sektion.kinder:
        if kind.art == "group":
            if lauf is not None:
                ergebnis.append(Block(lauf[0].id, tuple(lauf)))
                lauf = None
            ergebnis.append(Block(kind.id, (kind, *kind.kinder)))
        elif lauf is not None:
            lauf.append(kind)
        else:
            lauf = [kind]
    if lauf is not None:
        ergebnis.append(Block(lauf[0].id, tuple(lauf)))
    return ergebnis


DOKU_BLOECKE = frozenset(b.id for s in KATALOG.doku for b in bloecke(s))
DOKU_BLAETTER = {b.id: b for b in KATALOG.doku_blaetter}
PRAESI_BLAETTER = {b.id: b for b in KATALOG.praesi_blaetter}
PRAESI_SEKTIONEN = {s.id: s for s in KATALOG.praesentation}


# ── Dokumentation ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SektionErgebnis:
    id: str
    nr: str
    label: str
    max: int
    wert: int | None
    vollstaendig: bool
    vorschlag: int | None = None


@dataclass(frozen=True, slots=True)
class TeilErgebnis:
    sektionen: list[SektionErgebnis]
    gesamt: int | None
    note: float | None
    grenzfall: bool
    fehlend: list[str]


def _summe(werte: list[int]) -> int | None:
    return sum(werte) if werte else None


def berechne_doku(punkte: Mapping[str, int | None]) -> TeilErgebnis:
    """Wie die Vorlage: Eine Sektionssumme erscheint mit dem ersten Kriterium,
    die Gesamtpunktzahl erst, wenn jede Sektion etwas hat."""
    fehlend: list[str] = []
    sektionen = []
    for sektion in KATALOG.doku:
        gefuellt: list[int] = []
        for blatt in blaetter(sektion):
            wert = punkte.get(blatt.id)
            if wert is None:
                fehlend.append(blatt.id)
            else:
                gefuellt.append(wert)
        sektionen.append(
            SektionErgebnis(
                id=sektion.id,
                nr=sektion.nr,
                label=sektion.label,
                max=sektion.max,
                wert=_summe(gefuellt),
                vollstaendig=len(gefuellt) == len(blaetter(sektion)),
            )
        )
    return _teil(sektionen, fehlend)


def _teil(sektionen: list[SektionErgebnis], fehlend: list[str]) -> TeilErgebnis:
    werte = [s.wert for s in sektionen]
    gesamt = sum(w for w in werte if w is not None) if None not in werte else None
    return TeilErgebnis(sektionen, gesamt, note_fuer(gesamt), ist_grenzfall(gesamt), fehlend)


def berechne_praesentation(
    skala: Mapping[str, float | None], punkte: Mapping[str, int | None]
) -> TeilErgebnis:
    """Vorschlag ``round(max * Mittelwert)``; zählen tut die gesetzte Punktzahl."""
    fehlend: list[str] = []
    sektionen = []
    for sektion in KATALOG.praesentation:
        bewertet = [w for b in blaetter(sektion) if (w := skala.get(b.id)) is not None]
        vorschlag = runde(sektion.max * sum(bewertet) / len(bewertet)) if bewertet else None
        wert = punkte.get(sektion.id)
        if wert is None:
            fehlend.append(sektion.id)
        sektionen.append(
            SektionErgebnis(
                id=sektion.id,
                nr=sektion.nr,
                label=sektion.label,
                max=sektion.max,
                wert=wert,
                vollstaendig=len(bewertet) == len(blaetter(sektion)) and wert is not None,
                vorschlag=vorschlag,
            )
        )
    return _teil(sektionen, fehlend)


# ── Gesamtergebnis ───────────────────────────────────────────────────────────

MepBereich = Literal["planen_softwareprodukt", "algorithmen", "wiso"]


@dataclass(frozen=True, slots=True)
class Mep:
    bereich: MepBereich
    punkte: int


@dataclass(frozen=True, slots=True)
class Teilnoten:
    teil1: int | None = None
    planen_softwareprodukt: int | None = None
    algorithmen: int | None = None
    wiso: int | None = None
    mep: Mep | None = None

    def schriftlich(self, bereich: str) -> int | None:
        wert: int | None = getattr(self, bereich)
        return wert


@dataclass(frozen=True, slots=True)
class BereichErgebnis:
    id: str
    label: str
    gewicht: int
    schriftlich: int | None
    muendlich: int | None
    wert: int | None


@dataclass(frozen=True, slots=True)
class GesamtErgebnis:
    projekt: int | None
    bereiche: list[BereichErgebnis]
    teil1: int | None
    teil2: int | None
    gesamt: int | None
    note: float | None
    grenzfall: bool
    fehlend: list[str]


def mep_anwenden(schriftlich: int, muendlich: int) -> int:
    """Ergänzungsprüfung: schriftlich zählt doppelt, mündlich einfach."""
    return runde((2 * schriftlich + muendlich) / 3)


def _gesamt(t: Teilnoten, doku: int | None, praesi: int | None, mit_mep: bool) -> GesamtErgebnis:
    schema = KATALOG.gesamt
    fehlend: list[str] = []

    projekt = (
        runde((doku * 50 + praesi * 50) / schema.projekt_divisor)
        if doku is not None and praesi is not None
        else None
    )
    if projekt is None:
        fehlend.append("projekt")

    bereiche = []
    for spec in schema.bereiche:
        schriftlich = t.schriftlich(spec.id)
        angewandt = mit_mep and t.mep is not None and t.mep.bereich == spec.id
        muendlich = t.mep.punkte if angewandt and t.mep is not None else None
        wert = (
            mep_anwenden(schriftlich, muendlich)
            if schriftlich is not None and muendlich is not None
            else schriftlich
        )
        if wert is None:
            fehlend.append(spec.id)
        bereiche.append(
            BereichErgebnis(spec.id, spec.label, spec.gewicht, schriftlich, muendlich, wert)
        )

    if t.teil1 is None:
        fehlend.append("teil1")

    # Die gewichtete Summe von Teil 2 bleibt für das Gesamtergebnis ungerundet -
    # die Vorlage rundet nur die angezeigte Teil-2-Zahl.
    werte = [b.wert for b in bereiche]
    teil2_gewichtet = (
        sum((b.wert or 0) * b.gewicht for b in bereiche) + projekt * schema.projekt_gewicht
        if projekt is not None and None not in werte
        else None
    )
    teil2 = runde(teil2_gewichtet / schema.teil2_divisor) if teil2_gewichtet is not None else None
    gesamt = (
        runde((t.teil1 * schema.teil1_gewicht + teil2_gewichtet) / schema.gesamt_divisor)
        if teil2_gewichtet is not None and t.teil1 is not None
        else None
    )
    return GesamtErgebnis(
        projekt=projekt,
        bereiche=bereiche,
        teil1=t.teil1,
        teil2=teil2,
        gesamt=gesamt,
        note=note_fuer(gesamt),
        grenzfall=ist_grenzfall(gesamt),
        fehlend=fehlend,
    )


def berechne_gesamt(
    teilnoten: Teilnoten, doku: int | None, praesentation: int | None
) -> tuple[GesamtErgebnis, GesamtErgebnis | None]:
    """Ergebnis ohne und - wenn eine Ergänzungsprüfung eingetragen ist - mit ihr,
    damit ihre Wirkung sichtbar ist, bevor man sich für eine entscheidet."""
    ohne = _gesamt(teilnoten, doku, praesentation, mit_mep=False)
    mit = _gesamt(teilnoten, doku, praesentation, mit_mep=True) if teilnoten.mep else None
    return ohne, mit


# ── Bewertung ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Bewertung:
    """Ein Datensatz je Prüfling. Fehlende Schlüssel heißen: noch nicht bewertet."""

    doku: dict[str, int] = field(default_factory=dict)
    doku_bemerkungen: dict[str, str] = field(default_factory=dict)
    praesi_skala: dict[str, float] = field(default_factory=dict)
    praesi_punkte: dict[str, int] = field(default_factory=dict)
    praesi_bemerkungen: dict[str, str] = field(default_factory=dict)
    #: wird nie gedruckt
    notizen: str = ""
    fragen: str = ""

    def als_dict(self) -> dict[str, Any]:
        return {
            "doku": dict(self.doku),
            "doku_bemerkungen": dict(self.doku_bemerkungen),
            "praesi_skala": dict(self.praesi_skala),
            "praesi_punkte": dict(self.praesi_punkte),
            "praesi_bemerkungen": dict(self.praesi_bemerkungen),
            "notizen": self.notizen,
            "fragen": self.fragen,
        }

    @classmethod
    def aus_dict(cls, roh: Mapping[str, Any]) -> Bewertung:
        return cls(
            doku={k: int(v) for k, v in roh.get("doku", {}).items()},
            doku_bemerkungen=dict(roh.get("doku_bemerkungen", {})),
            praesi_skala={k: float(v) for k, v in roh.get("praesi_skala", {}).items()},
            praesi_punkte={k: int(v) for k, v in roh.get("praesi_punkte", {}).items()},
            praesi_bemerkungen=dict(roh.get("praesi_bemerkungen", {})),
            notizen=str(roh.get("notizen", "")),
            fragen=str(roh.get("fragen", "")),
        )


def _bereich_text(knoten: Knoten) -> str:
    grenze = knoten.max or 0
    unten, oben = (grenze, 0) if grenze < 0 else (0, grenze)
    return f"{unten} bis {oben}"


def _pruefe_doku(kennung: str, wert: int) -> None:
    blatt = DOKU_BLAETTER.get(kennung)
    if blatt is None:
        raise KriteriumUnbekannt(f"'{kennung}' ist kein bewertbares Kriterium der Dokumentation")
    grenze = blatt.max or 0
    unten, oben = (grenze, 0) if grenze < 0 else (0, grenze)
    if not unten <= wert <= oben:
        raise PunkteUnzulaessig(
            f"„{blatt.label}“ erlaubt {_bereich_text(blatt)} Punkte, nicht {wert}"
        )


def _pruefe_skala(kennung: str, wert: float) -> None:
    blatt = PRAESI_BLAETTER.get(kennung)
    if blatt is None:
        raise KriteriumUnbekannt(f"'{kennung}' ist kein Unterkriterium der Präsentation")
    if wert not in NOTEN.skala:
        raise PunkteUnzulaessig(
            f"„{blatt.label}“ wird mit 1; 0,75; 0,5; 0,25 oder 0 bewertet, nicht {wert}"
        )


def _pruefe_sektion(kennung: str, wert: int) -> None:
    sektion = PRAESI_SEKTIONEN.get(kennung)
    if sektion is None:
        raise KriteriumUnbekannt(f"'{kennung}' ist keine Sektion der Präsentation")
    if not 0 <= wert <= sektion.max:
        raise PunkteUnzulaessig(
            f"„{sektion.label}“ erlaubt 0 bis {sektion.max} Punkte, nicht {wert}"
        )


def _pruefe_bemerkung(gueltig: frozenset[str] | Mapping[str, object], kennung: str) -> None:
    if kennung not in gueltig:
        raise KriteriumUnbekannt(f"Zu '{kennung}' gibt es kein Bemerkungsfeld")


def _zahlen[W: (int, float)](
    alt: dict[str, W], neu: Mapping[str, W | None] | None, pruefe: Any
) -> dict[str, W]:
    ergebnis = dict(alt)
    for kennung, wert in (neu or {}).items():
        if wert is None:
            ergebnis.pop(kennung, None)
        else:
            pruefe(kennung, wert)
            ergebnis[kennung] = wert
    return ergebnis


def _texte(
    alt: dict[str, str], neu: Mapping[str, str | None] | None, gueltig: Any
) -> dict[str, str]:
    ergebnis = dict(alt)
    for kennung, text in (neu or {}).items():
        _pruefe_bemerkung(gueltig, kennung)
        if text is None or not text.strip():
            ergebnis.pop(kennung, None)
        else:
            ergebnis[kennung] = text
    return ergebnis


def aendere_bewertung(
    bewertung: Bewertung,
    *,
    doku: Mapping[str, int | None] | None = None,
    doku_bemerkungen: Mapping[str, str | None] | None = None,
    praesi_skala: Mapping[str, float | None] | None = None,
    praesi_punkte: Mapping[str, int | None] | None = None,
    praesi_bemerkungen: Mapping[str, str | None] | None = None,
    notizen: str | None = None,
    fragen: str | None = None,
) -> Bewertung:
    """Teiländerung: Genannte Schlüssel werden gesetzt, ``None`` entfernt sie,
    alles Ungenannte bleibt stehen. Jeder Wert wird gegen den Katalog geprüft."""
    return Bewertung(
        doku=_zahlen(bewertung.doku, doku, _pruefe_doku),
        doku_bemerkungen=_texte(bewertung.doku_bemerkungen, doku_bemerkungen, DOKU_BLOECKE),
        praesi_skala=_zahlen(bewertung.praesi_skala, praesi_skala, _pruefe_skala),
        praesi_punkte=_zahlen(bewertung.praesi_punkte, praesi_punkte, _pruefe_sektion),
        praesi_bemerkungen=_texte(
            bewertung.praesi_bemerkungen, praesi_bemerkungen, PRAESI_SEKTIONEN
        ),
        notizen=bewertung.notizen if notizen is None else notizen,
        fragen=bewertung.fragen if fragen is None else fragen,
    )


@dataclass(frozen=True, slots=True)
class Fortschritt:
    """Wie weit ein Prüfling bewertet ist - für die Übersicht."""

    doku_bewertet: int
    doku_kriterien: int
    praesi_bewertet: int
    praesi_sektionen: int


def fortschritt(bewertung: Bewertung) -> Fortschritt:
    doku = berechne_doku(bewertung.doku)
    praesi = berechne_praesentation(bewertung.praesi_skala, bewertung.praesi_punkte)
    return Fortschritt(
        doku_bewertet=len(DOKU_BLAETTER) - len(doku.fehlend),
        doku_kriterien=len(DOKU_BLAETTER),
        praesi_bewertet=len(PRAESI_SEKTIONEN) - len(praesi.fehlend),
        praesi_sektionen=len(PRAESI_SEKTIONEN),
    )


# ── Zeitmessung ──────────────────────────────────────────────────────────────

Zeitaktion = Literal["praesentation_starten", "fachgespraech_starten", "beenden", "zuruecksetzen"]


@dataclass(frozen=True, slots=True)
class Zeiten:
    """Alle Dauern entstehen aus Zeitstempeln, nie aus Hochzählen - Browser
    drosseln Timer im Hintergrund, und so übersteht die Messung einen Neustart."""

    praesi_start: datetime | None = None
    praesi_ende: datetime | None = None
    fg_start: datetime | None = None
    fg_ende: datetime | None = None


def zeit_schritt(zeiten: Zeiten, aktion: Zeitaktion, jetzt: datetime) -> Zeiten:
    if aktion == "zuruecksetzen":
        return Zeiten()
    if aktion == "praesentation_starten":
        if zeiten.praesi_start is not None:
            raise ZeitschrittUnzulaessig("Die Präsentation läuft bereits oder ist vorbei")
        return replace(zeiten, praesi_start=jetzt)
    laeuft_praesi = zeiten.praesi_start is not None and zeiten.praesi_ende is None
    if aktion == "fachgespraech_starten":
        if not laeuft_praesi:
            raise ZeitschrittUnzulaessig("Das Fachgespräch beginnt, wenn die Präsentation läuft")
        # Präsentation endet im selben Augenblick, in dem das Gespräch beginnt.
        return replace(zeiten, praesi_ende=jetzt, fg_start=jetzt)
    if zeiten.fg_start is None or zeiten.fg_ende is not None:
        raise ZeitschrittUnzulaessig("Beenden lässt sich nur ein laufendes Fachgespräch")
    return replace(zeiten, fg_ende=jetzt)


# ── Dokumente ────────────────────────────────────────────────────────────────

#: Projektdokumentationen sind selten über 10 MB. 50 MB lässt Platz für
#: eingescannte Anlagen, ohne dass ein Irrläufer die Datenbank füllt.
MAX_DOKUMENT_BYTES = 50 * 1024 * 1024


def pruefe_dokument(dateiname: str, daten: bytes) -> str:
    """Nimmt ein PDF an und gibt den bereinigten Dateinamen zurück."""
    if len(daten) > MAX_DOKUMENT_BYTES:
        raise DokumentZuGross(
            f"Das Dokument hat {len(daten) // (1024 * 1024)} MB, erlaubt sind "
            f"{MAX_DOKUMENT_BYTES // (1024 * 1024)} MB"
        )
    if not daten.startswith(b"%PDF"):
        raise KeinPdf("Die Datei ist kein PDF. Bitte die Dokumentation als PDF hochladen")
    # Pfadanteile fallen weg, egal von welchem System sie kommen.
    name = PureWindowsPath(PurePosixPath(dateiname.strip()).name).name.strip()[:200]
    if not name:
        return "dokument.pdf"
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"


# ── Korrekturbogen ───────────────────────────────────────────────────────────

ZeilenArt = Literal["sektion", "gruppe", "kriterium", "summe"]


@dataclass(frozen=True, slots=True)
class BogenZeile:
    id: str
    art: ZeilenArt
    text: str
    max: str
    ist: str
    #: ``None`` heißt: Die Bemerkung der Zeile darüber reicht bis hierher.
    bemerkung: str | None
    spanne: int = 1
    einzug: int = 0


@dataclass(frozen=True, slots=True)
class Uebertrag:
    text: str
    max: str
    ist: str


@dataclass(frozen=True, slots=True)
class Bogen:
    name: str
    ident: str
    korrektor: str
    zeilen: list[BogenZeile]
    uebertrag: list[Uebertrag]
    summe: str
    notenschluessel: list[Notenband]


def _zahl(wert: int | None) -> str:
    return "" if wert is None else str(wert)


def korrekturbogen(name: str, ident: str, korrektor: str, bewertung: Bewertung) -> Bogen:
    """Druckbereich A1:L80 der Vorlage. Notizen und die Note stehen nicht darauf -
    die Vorlage hält beide ebenfalls aus dem Druckbereich heraus."""
    ergebnis = berechne_doku(bewertung.doku)
    zeilen: list[BogenZeile] = []

    def summe_von(knoten: Knoten) -> int | None:
        werte = [bewertung.doku[b.id] for b in blaetter(knoten) if b.id in bewertung.doku]
        return _summe(werte)

    for sektion, s_erg in zip(KATALOG.doku, ergebnis.sektionen, strict=True):
        for block in bloecke(sektion):
            bemerkung = bewertung.doku_bemerkungen.get(block.id, "")
            if not block.knoten:
                zeilen.append(
                    BogenZeile(
                        id=sektion.id,
                        art="sektion",
                        text=f"{sektion.nr}.  {sektion.label}",
                        max=str(sektion.max),
                        ist=_zahl(s_erg.wert),
                        bemerkung=bemerkung,
                    )
                )
                continue
            verschachtelt = block.knoten[0].art == "group"
            for index, knoten in enumerate(block.knoten):
                gruppe = knoten.art == "group"
                zeilen.append(
                    BogenZeile(
                        id=knoten.id,
                        art="gruppe" if gruppe else "kriterium",
                        text=knoten.label,
                        max=_zahl(knoten.max),
                        ist=_zahl(summe_von(knoten) if gruppe else bewertung.doku.get(knoten.id)),
                        bemerkung=bemerkung if index == 0 else None,
                        spanne=len(block.knoten) if index == 0 else 1,
                        einzug=2 if verschachtelt and not gruppe else 1,
                    )
                )

    summe = _zahl(ergebnis.gesamt)
    zeilen.append(BogenZeile("summe", "summe", "SUMME:", "100", summe, ""))
    return Bogen(
        name=name,
        ident=ident,
        korrektor=korrektor,
        zeilen=zeilen,
        uebertrag=[
            Uebertrag(f"{s.nr}. {s.label}", str(s.max), _zahl(s.wert)) for s in ergebnis.sektionen
        ],
        summe=summe,
        notenschluessel=notenbaender(),
    )


def bogen_dateiname(name: str, datum: str) -> str:
    teile = re.sub(r"[^\w]+|_+", "_", name).strip("_")
    return f"{datum}_{teile}_Korrekturbogen.pdf"
