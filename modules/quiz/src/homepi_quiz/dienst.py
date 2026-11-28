"""Die Entscheidungen dieses Artefakts.

REIN: keine Datenbank, kein await, keine Fixtures. Genau deshalb laufen die
Tests dazu in Millisekunden - und nur deshalb benutzt man die rot-gruen-
Schleife wirklich. Alles, was I/O macht, gehoert in speicher.py.

Drei Dinge entscheidet diese Datei, und an allen dreien haengt, dass ein
oeffentliches Quiz nicht zum Selbstbedienungsladen wird:

* **Wem ein Name gehoert.** Ein Name ist je Runde einmal vergeben, und zwar
  nach dem, was das Auge sieht: ``ANNA`` und ``anna`` sind derselbe, ein
  vorgesetztes Nullbreitenzeichen macht keinen neuen.
* **Was die Spieler sehen.** Die Loesung erst nach dem Aufloesen, die
  Reihenfolge beim Sortieren nicht ueber die Kennungen der Elemente.
* **Wann geantwortet werden darf.** Der Server entscheidet ueber Frist und
  Buzzer-Reihenfolge, nicht die Uhr des Handys.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import math
import random
import re
import secrets
import unicodedata
import uuid
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

from homepi_core import ServiceError
from homepi_core.auth.passwoerter import token_stimmt

from .schemas import (
    AntwortEingabe,
    AuswahlDaten,
    BildauswahlDaten,
    BildDaten,
    BuzzerDaten,
    Element,
    FrageAusgabe,
    FrageDaten,
    FreitextDaten,
    HotspotDaten,
    Loesung,
    OeffentlicheFrage,
    Phase,
    Rundenstatus,
    SchaetzDaten,
    SortierDaten,
    ZahlDaten,
    ZuordnenDaten,
)

K = TypeVar("K", bound=Hashable)

# ------------------------------------------------------------- Fehler


class NameUngueltig(ServiceError):
    status = 422
    title = "Name ungültig"


class NameVergeben(ServiceError):
    status = 409
    title = "Name vergeben"


class RundeVoll(ServiceError):
    status = 409
    title = "Runde voll"


class RundeUnbekannt(ServiceError):
    status = 404
    title = "Runde unbekannt"


class KatalogUnbekannt(ServiceError):
    status = 404
    title = "Katalog unbekannt"


class FrageUnbekannt(ServiceError):
    status = 404
    title = "Frage unbekannt"


class SpielerUnbekannt(ServiceError):
    status = 404
    title = "Spieler unbekannt"


class AntwortUnbekannt(ServiceError):
    status = 404
    title = "Antwort unbekannt"


class BildFehlt(ServiceError):
    status = 404
    title = "Kein Bild"


class NichtBeigetreten(ServiceError):
    status = 401
    title = "Nicht beigetreten"


class WiederkehrUngueltig(ServiceError):
    status = 403
    title = "Wiederkehrcode ungültig"


class AktionNichtMoeglich(ServiceError):
    status = 409
    title = "Gerade nicht möglich"


class AntwortNichtMoeglich(ServiceError):
    status = 409
    title = "Antwort nicht möglich"


class AntwortUngueltig(ServiceError):
    status = 422
    title = "Antwort ungültig"


class BildUngueltig(ServiceError):
    status = 422
    title = "Bild ungültig"


class ReihenfolgeUngueltig(ServiceError):
    status = 422
    title = "Reihenfolge ungültig"


class KatalogInBenutzung(ServiceError):
    status = 409
    title = "Katalog in Benutzung"


class KatalogLeer(ServiceError):
    status = 409
    title = "Katalog leer"


# ------------------------------------------------------------- Spielernamen

MAX_NAMENSLAENGE = 24
#: Eine Runde ist ein Abend mit Freunden oder Kollegen, kein Stadion. Die
#: Grenze haelt eine oeffentliche Seite davon ab, mit Namen geflutet zu werden.
MAX_SPIELER = 100


def pruefe_spielername(name: str) -> tuple[str, str]:
    """Liefert ``(anzeige, schluessel)``.

    Der Schluessel ist das, was eindeutig sein muss. NFKC und ``casefold``
    statt ``lower``: so sind auch ``Strauß`` und ``STRAUSS`` derselbe Name,
    und ein Name aus Vollbreiten-Buchstaben ist kein neuer.
    """
    anzeige = " ".join(name.split())
    if not anzeige:
        raise NameUngueltig("Bitte gib einen Namen ein.")
    if len(anzeige) > MAX_NAMENSLAENGE:
        raise NameUngueltig(f"Ein Name hat höchstens {MAX_NAMENSLAENGE} Zeichen.")
    # Kategorie C: Steuer-, Format- und unbelegte Zeichen. Darunter die
    # Nullbreitenzeichen, mit denen sich ein Doppelgaenger bauen liesse, der
    # auf der Tafel genauso aussieht wie das Original.
    if any(unicodedata.category(zeichen).startswith("C") for zeichen in anzeige):
        raise NameUngueltig("Der Name enthält unsichtbare Zeichen.")
    return anzeige, unicodedata.normalize("NFKC", anzeige).casefold()


def pruefe_beitritt(status: Rundenstatus, *, offen: bool, wiederkehr: bool = False) -> None:
    """Wer noch hinein darf.

    Die Leitung kann den Beitritt schliessen - eine oeffentliche Seite mit
    einem Code am Beamer ist sonst offen fuer jeden, der ihn abfotografiert.
    Wer mit einem Wiederkehrcode kommt, war schon dabei und darf zurueck.
    """
    if status == "beendet":
        raise AktionNichtMoeglich("Diese Runde ist schon beendet.")
    if not offen and not wiederkehr:
        raise AktionNichtMoeglich("Die Spielleitung hat den Beitritt geschlossen.")


class TeamUngueltig(ServiceError):
    status = 422
    title = "Team ungültig"


class TeamUnbekannt(ServiceError):
    status = 404
    title = "Team unbekannt"


class TeamVergeben(ServiceError):
    status = 409
    title = "Team vergeben"


def pruefe_teamwahl(teams: set[uuid.UUID], gewaehlt: uuid.UUID | None) -> None:
    """Mit Teams spielt niemand allein - ohne Teams spielt niemand in einem."""
    if not teams:
        if gewaehlt is not None:
            raise TeamUngueltig("In dieser Runde gibt es keine Teams.")
        return
    if gewaehlt is None:
        raise TeamUngueltig("Bitte wähle ein Team.")
    if gewaehlt not in teams:
        raise TeamUngueltig("Dieses Team gibt es in der Runde nicht.")


def pruefe_teamwechsel(status: Rundenstatus) -> None:
    """Selbst wechseln nur vor dem Start - danach wanderten Punkte mit."""
    if status != "lobby":
        raise AktionNichtMoeglich("Das Team lässt sich nur vor dem Start wechseln.")


@dataclass(frozen=True, slots=True)
class Teamrang:
    id: uuid.UUID
    name: str
    punkte: int
    rang: int
    mitglieder: int


def teamrangliste(
    teams: Sequence[tuple[uuid.UUID, str]],
    mitglieder: Iterable[tuple[uuid.UUID | None, int]],
) -> list[Teamrang]:
    """Die Summe der Mitglieder. Bewusst nicht der Schnitt: ein Team, das
    mehr Leute mitbringt, bringt auch mehr Antworten - und ein Schnitt
    bestrafte jeden, der dazukommt und bei der ersten Frage noch null hat."""
    summen = {team_id: [0, 0] for team_id, _ in teams}
    for team_id, punkte in mitglieder:
        if team_id in summen:
            summen[team_id][0] += punkte
            summen[team_id][1] += 1
    namen = dict(teams)
    plaetze = rangliste((tid, namen[tid], summe) for tid, (summe, _) in summen.items())
    return [
        Teamrang(
            id=platz.schluessel,  # type: ignore[arg-type]
            name=platz.name,
            punkte=platz.punkte,
            rang=platz.rang,
            mitglieder=summen[platz.schluessel][1],  # type: ignore[index]
        )
        for platz in plaetze
    ]


def wiederkehr_erlaubt(
    gespeicherter_hash: str | None,
    gueltig_bis: dt.datetime | None,
    code: str,
    jetzt: dt.datetime,
) -> bool:
    """Ob ein Spieler mit dem Code der Leitung an seinen Namen zurueckkommt.

    Ohne diesen Weg hiesse ein verlorenes Cookie: Name weg, Punkte weg. Und
    ein Weg ueber den Namen allein - so, wie es das alte Battle.Net machte -
    hiesse: jeder kann unter jedem Namen weiterspielen.
    """
    if gespeicherter_hash is None or not wiederkehr_gilt(gueltig_bis, jetzt):
        return False
    return token_stimmt(gespeicherter_hash, normalisiere_wiederkehrcode(code))


def pruefe_spielerzahl(anzahl: int) -> None:
    if anzahl >= MAX_SPIELER:
        raise RundeVoll(f"Diese Runde hat schon {MAX_SPIELER} Spieler.")


# ------------------------------------------------------------- Codes

#: Ohne 0/O, 1/I/L - ein Code wird von der Leinwand abgetippt oder
#: vorgelesen, und genau dort entstehen die Verwechslungen.
CODEALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODELAENGE = 6
_CODEMUSTER = re.compile(r"^[A-Z0-9]{6}$")

WIEDERKEHR_DAUER = dt.timedelta(minutes=15)


def neuer_rundencode() -> str:
    return "".join(secrets.choice(CODEALPHABET) for _ in range(CODELAENGE))


def normalisiere_code(code: str) -> str:
    """So, wie der Code eingetippt wird: klein, mit Leerzeichen, mit Strich."""
    roh = re.sub(r"[\s-]", "", code).upper()
    if not _CODEMUSTER.match(roh):
        raise RundeUnbekannt("Zu diesem Code gibt es keine Runde.")
    return roh


def neuer_wiederkehrcode() -> str:
    """Acht Zeichen, rund 40 Bit. Mehr braucht es nicht: der Code gilt eine
    Viertelstunde und genau einmal."""
    zeichen = "".join(secrets.choice(CODEALPHABET) for _ in range(8))
    return f"{zeichen[:4]}-{zeichen[4:]}"


def normalisiere_wiederkehrcode(code: str) -> str:
    roh = re.sub(r"[^0-9A-Za-z]", "", code).upper()
    return f"{roh[:4]}-{roh[4:]}" if len(roh) == 8 else roh


def wiederkehr_gueltig_bis(jetzt: dt.datetime) -> dt.datetime:
    return jetzt + WIEDERKEHR_DAUER


def wiederkehr_gilt(gueltig_bis: dt.datetime | None, jetzt: dt.datetime) -> bool:
    return gueltig_bis is not None and jetzt <= gueltig_bis


# ------------------------------------------------------------- Ablauf

#: Wer bei null abschickt, kommt einen Moment spaeter an. Ohne Kulanz
#: verlöre ausgerechnet der Knappe seine Antwort.
KULANZ = dt.timedelta(milliseconds=1500)


def naechste_phase(status: Rundenstatus, phase: Phase, aktion: str) -> Phase:
    """Der Zustandsautomat einer Frage.

    ``waehlen`` geht jederzeit: die Leitung soll eine Frage ueberspringen oder
    wiederholen koennen, ohne erst aufzuloesen.
    """
    if status == "beendet":
        raise AktionNichtMoeglich("Die Runde ist beendet.")
    if aktion == "waehlen":
        return "bereit"
    if aktion == "beenden":
        return "aufgeloest" if phase in ("offen", "gesperrt") else phase
    if phase == "keine":
        raise AktionNichtMoeglich("Es ist noch keine Frage gewählt.")

    erlaubt: dict[str, tuple[tuple[Phase, ...], Phase, str]] = {
        "zeigen": (("bereit",), "offen", "Die Frage wird schon gezeigt."),
        "sperren": (("offen",), "gesperrt", "Die Frage ist nicht offen."),
        "oeffnen": (("gesperrt",), "offen", "Die Frage ist nicht gesperrt."),
        "aufloesen": (("offen", "gesperrt"), "aufgeloest", "Die Frage ist schon aufgelöst."),
    }
    if aktion not in erlaubt:
        raise AktionNichtMoeglich(f"Unbekannte Aktion „{aktion}“.")
    von, nach, grund = erlaubt[aktion]
    if phase not in von:
        if aktion == "aufloesen" and phase == "bereit":
            raise AktionNichtMoeglich("Die Frage wurde noch nicht gezeigt.")
        raise AktionNichtMoeglich(grund)
    return nach


def phase_nach_wahl(*, erledigt: bool) -> Phase:
    """Eine schon aufgeloeste Frage kommt aufgeloest zurueck: wer zur
    vorigen Frage blaettert, will die Loesung zeigen und nicht die Punkte des
    Abends neu verteilen."""
    return "aufgeloest" if erledigt else "bereit"


#: Das Handy fragt jede Sekunde nach. Jede Abfrage als Schreibzugriff waeren
#: bei zwanzig Spielern zwanzig Updates je Sekunde - fuer eine Anzeige
#: "zuletzt gesehen", die auf zehn Sekunden genau reicht.
GESEHEN_TAKT = dt.timedelta(seconds=10)
VERBUNDEN_FENSTER = dt.timedelta(seconds=45)


def gesehen_aktualisieren(zuletzt: dt.datetime | None, jetzt: dt.datetime) -> bool:
    return zuletzt is None or jetzt - zuletzt >= GESEHEN_TAKT


def verbunden(zuletzt: dt.datetime, jetzt: dt.datetime) -> bool:
    return jetzt - zuletzt <= VERBUNDEN_FENSTER


def braucht_bild(daten: FrageDaten) -> bool:
    return isinstance(daten, BildDaten | HotspotDaten)


def pruefe_zeigbar(frage: FrageAusgabe) -> None:
    if braucht_bild(frage.daten) and not frage.hat_bild:
        raise AktionNichtMoeglich("Diese Frage braucht ein Bild. Lade im Katalog eines hoch.")
    if isinstance(frage.daten, BildauswahlDaten):
        fehlend = [
            i + 1 for i in range(len(frage.daten.optionen)) if f"option-{i}" not in frage.medien
        ]
        if fehlend:
            raise AktionNichtMoeglich(
                f"Zu Antwort {', '.join(map(str, fehlend))} fehlt noch das Bild."
            )


def frist_fuer(zeitlimit: int | None, timer: bool, jetzt: dt.datetime) -> dt.datetime | None:
    if not timer or zeitlimit is None:
        return None
    return jetzt + dt.timedelta(seconds=zeitlimit)


def pruefe_antwort_erlaubt(
    status: Rundenstatus,
    phase: Phase,
    typ: str,
    frist: dt.datetime | None,
    jetzt: dt.datetime,
) -> None:
    if status != "laeuft":
        raise AntwortNichtMoeglich("Die Runde läuft gerade nicht.")
    if typ == "buzzer":
        raise AntwortNichtMoeglich("Bei dieser Frage zählt der Buzzer, nicht die Eingabe.")
    if phase != "offen":
        raise AntwortNichtMoeglich(
            "Die Eingabe ist gesperrt." if phase == "gesperrt" else "Gerade ist keine Frage offen."
        )
    if frist is not None and jetzt > frist + KULANZ:
        raise AntwortNichtMoeglich("Die Zeit ist abgelaufen.")


# ------------------------------------------------------------- Antworten


def _zahl(wert: float) -> str:
    """Deutsch, ohne ueberfluessige Nachkommastellen: 16, 2,5, 3,75."""
    return f"{wert:g}".replace(".", ",")


def _mit_einheit(wert: float, einheit: str) -> str:
    return f"{_zahl(wert)} {einheit}".strip()


def _vergleich(text: str) -> str:
    return unicodedata.normalize("NFKC", " ".join(text.split())).casefold()


def elementkennung(frage_id: uuid.UUID, index: int) -> str:
    """Kennung eines Sortier-Elements, die nichts ueber seinen Platz verraet.

    Mit dem Index als Kennung stuende die Loesung im Netzwerkverkehr: das
    Element ``0`` gehoert nach vorn.
    """
    return "e" + hashlib.sha256(f"{frage_id}:{index}".encode()).hexdigest()[:9]


def rechtskennung(frage_id: uuid.UUID, index: int) -> str:
    """Wie ``elementkennung``, fuer die rechte Seite beim Zuordnen - mit
    eigenem Salz, damit sich beide Typen nicht ineinander verraten."""
    return "r" + hashlib.sha256(f"{frage_id}:rechts:{index}".encode()).hexdigest()[:9]


def pruefe_antwort(
    daten: FrageDaten, eingabe: AntwortEingabe, frage_id: uuid.UUID | None = None
) -> dict[str, object]:
    """Prueft die Eingabe gegen den Fragetyp und gibt den Wert zurueck, der
    gespeichert wird - nur das Feld, auf das es ankommt."""
    if isinstance(daten, FreitextDaten | BildDaten):
        text = " ".join((eingabe.text or "").split())
        if not text:
            raise AntwortUngueltig("Bitte gib eine Antwort ein.")
        return {"text": text}
    if isinstance(daten, ZahlDaten):
        if eingabe.zahl is None or not math.isfinite(eingabe.zahl):
            raise AntwortUngueltig("Bitte gib eine Zahl ein.")
        return {"zahl": eingabe.zahl}
    if isinstance(daten, SchaetzDaten):
        if eingabe.zahl is None or not math.isfinite(eingabe.zahl):
            raise AntwortUngueltig("Bitte schätze einen Wert.")
        if not daten.minimum <= eingabe.zahl <= daten.maximum:
            raise AntwortUngueltig(
                f"Der Wert muss zwischen {_zahl(daten.minimum)} und {_zahl(daten.maximum)} liegen."
            )
        return {"zahl": eingabe.zahl}
    if isinstance(daten, AuswahlDaten | BildauswahlDaten):
        auswahl = sorted(set(eingabe.auswahl or []))
        if not auswahl:
            raise AntwortUngueltig("Bitte wähle eine Antwort.")
        if any(not 0 <= i < len(daten.optionen) for i in auswahl):
            raise AntwortUngueltig("Diese Antwort gibt es nicht.")
        if not _mehrfach(daten) and len(auswahl) > 1:
            raise AntwortUngueltig("Hier ist genau eine Antwort richtig.")
        return {"auswahl": auswahl}
    if isinstance(daten, HotspotDaten):
        if eingabe.x is None or eingabe.y is None:
            raise AntwortUngueltig("Bitte tippe auf das Bild.")
        return {"x": eingabe.x, "y": eingabe.y}
    if isinstance(daten, SortierDaten):
        erwartet = {
            elementkennung(frage_id or uuid.UUID(int=0), i) for i in range(len(daten.elemente))
        }
        reihenfolge = eingabe.reihenfolge or []
        if len(reihenfolge) != len(erwartet) or set(reihenfolge) != erwartet:
            raise AntwortUngueltig("Bitte bring alle Elemente in eine Reihenfolge.")
        return {"reihenfolge": list(reihenfolge)}
    if isinstance(daten, ZuordnenDaten):
        return {"zuordnung": _pruefe_zuordnung(daten, eingabe, frage_id or uuid.UUID(int=0))}
    raise AntwortUngueltig("Bei dieser Frage wird gebuzzert, nicht geschrieben.")


def _pruefe_zuordnung(
    daten: ZuordnenDaten, eingabe: AntwortEingabe, frage_id: uuid.UUID
) -> dict[str, str]:
    zuordnung = eingabe.zuordnung or {}
    erlaubt = {rechtskennung(frage_id, i) for i in range(len(daten.paare))}
    zeilen = {str(i) for i in range(len(daten.paare))}
    if set(zuordnung) != zeilen or not set(zuordnung.values()) <= erlaubt:
        raise AntwortUngueltig("Bitte ordne jedem Eintrag ein Gegenstück zu.")
    if len(set(zuordnung.values())) != len(zuordnung):
        raise AntwortUngueltig("Jedes Gegenstück passt nur einmal.")
    return dict(sorted(zuordnung.items(), key=lambda paar: int(paar[0])))


def _optionstext(daten: AuswahlDaten | BildauswahlDaten, index: int) -> str:
    text = daten.optionen[index].text
    return text or f"Bild {index + 1}"


def anzeige(daten: FrageDaten, wert: Mapping[str, object], frage_id: uuid.UUID) -> str:
    """Eine Antwort als Text - fuer die Liste der Leitung."""
    if isinstance(daten, ZahlDaten | SchaetzDaten):
        zahl = wert.get("zahl")
        return _mit_einheit(float(zahl), daten.einheit) if isinstance(zahl, int | float) else ""
    if isinstance(daten, AuswahlDaten | BildauswahlDaten):
        indizes = _indizes(wert.get("auswahl"))
        return ", ".join(_optionstext(daten, i) for i in indizes if 0 <= i < len(daten.optionen))
    if isinstance(daten, ZuordnenDaten):
        rechts = {rechtskennung(frage_id, i): p.rechts for i, p in enumerate(daten.paare)}
        zuordnung = wert.get("zuordnung")
        if not isinstance(zuordnung, dict):
            return ""
        return ", ".join(
            f"{daten.paare[int(links)].links} → {rechts.get(str(kennung), '?')}"
            for links, kennung in zuordnung.items()
            if str(links).isdigit() and int(links) < len(daten.paare)
        )
    if isinstance(daten, HotspotDaten):
        x, y = wert.get("x"), wert.get("y")
        if isinstance(x, int | float) and isinstance(y, int | float):
            return f"Klick bei {_zahl(round(x))} % / {_zahl(round(y))} %"
        return ""
    if isinstance(daten, SortierDaten):
        texte = {elementkennung(frage_id, i): t for i, t in enumerate(daten.elemente)}
        return " → ".join(texte.get(str(k), "?") for k in _liste(wert.get("reihenfolge")))
    text = wert.get("text")
    return text if isinstance(text, str) else ""


def _indizes(wert: object) -> list[int]:
    return [i for i in wert if isinstance(i, int)] if isinstance(wert, list) else []


def _liste(wert: object) -> list[object]:
    return list(wert) if isinstance(wert, list) else []


def _richtige(daten: AuswahlDaten | BildauswahlDaten) -> list[int]:
    # Je Typ ausgeschrieben: die Optionen beider Typen haben ``richtig``,
    # aber ihre Listen sind verschiedene Typen, und der gemeinsame Obertyp
    # kennt das Feld nicht.
    if isinstance(daten, AuswahlDaten):
        return [i for i, option in enumerate(daten.optionen) if option.richtig]
    return [i for i, bild in enumerate(daten.optionen) if bild.richtig]


def _mehrfach(daten: AuswahlDaten | BildauswahlDaten) -> bool:
    return len(_richtige(daten)) > 1


# ------------------------------------------------------------- Bewertung


@dataclass(frozen=True, slots=True)
class Bewertung:
    """``punkte=None``: nicht automatisch bewertbar, die Leitung entscheidet."""

    punkte: int | None
    richtig: bool | None


def _runde_auf(wert: float) -> int:
    """Kaufmaennisch. ``round`` rundet 2,5 auf 2 - am Quizabend unerklaerlich."""
    return math.floor(wert + 0.5)


def _anteil(punkte: int, anteil: float, richtig: bool) -> Bewertung:
    return Bewertung(_runde_auf(punkte * max(0.0, anteil)), richtig)


def bewerte[K: Hashable](
    daten: FrageDaten,
    punkte: int,
    antworten: Mapping[K, Mapping[str, object]],
    frage_id: uuid.UUID,
) -> dict[K, Bewertung]:
    """Punkte je Spieler fuer eine aufgeloeste Frage.

    Buzzerfragen fehlen hier mit Absicht: dort urteilt die Leitung, wer dran
    war, und nicht der Vergleich zweier Zeichenketten.
    """
    if isinstance(daten, BuzzerDaten):
        return {}
    if isinstance(daten, SchaetzDaten):
        return _bewerte_schaetzung(daten, punkte, antworten)
    return {
        spieler: _bewerte_eine(daten, punkte, wert, frage_id) for spieler, wert in antworten.items()
    }


def _bewerte_eine(
    daten: FrageDaten, punkte: int, wert: Mapping[str, object], frage_id: uuid.UUID
) -> Bewertung:
    if isinstance(daten, FreitextDaten | BildDaten):
        if not daten.loesungen:
            return Bewertung(None, None)
        text = wert.get("text")
        treffer = isinstance(text, str) and _vergleich(text) in {
            _vergleich(loesung) for loesung in daten.loesungen
        }
        return Bewertung(punkte if treffer else 0, treffer)
    if isinstance(daten, ZahlDaten):
        zahl = wert.get("zahl")
        treffer = isinstance(zahl, int | float) and abs(zahl - daten.loesung) <= daten.toleranz
        return Bewertung(punkte if treffer else 0, treffer)
    if isinstance(daten, AuswahlDaten | BildauswahlDaten):
        return _bewerte_auswahl(daten, punkte, set(_indizes(wert.get("auswahl"))))
    if isinstance(daten, ZuordnenDaten):
        zuordnung = wert.get("zuordnung")
        zugeordnet = zuordnung if isinstance(zuordnung, dict) else {}
        stimmt = sum(
            1
            for i in range(len(daten.paare))
            if zugeordnet.get(str(i)) == rechtskennung(frage_id, i)
        )
        return _anteil(punkte, stimmt / len(daten.paare), stimmt == len(daten.paare))
    if isinstance(daten, HotspotDaten):
        x, y = wert.get("x"), wert.get("y")
        treffer = (
            isinstance(x, int | float)
            and isinstance(y, int | float)
            and any(math.hypot(x - z.x, y - z.y) <= z.radius for z in daten.ziele)
        )
        return Bewertung(punkte if treffer else 0, treffer)
    if isinstance(daten, SortierDaten):
        richtig = [elementkennung(frage_id, i) for i in range(len(daten.elemente))]
        gegeben = _liste(wert.get("reihenfolge"))
        stimmt = sum(1 for a, b in zip(richtig, gegeben, strict=False) if a == b)
        return _anteil(punkte, stimmt / len(richtig), stimmt == len(richtig))
    return Bewertung(None, None)


def _bewerte_auswahl(
    daten: AuswahlDaten | BildauswahlDaten, punkte: int, gewaehlt: set[int]
) -> Bewertung:
    richtige = set(_richtige(daten))
    if not _mehrfach(daten):
        treffer = gewaehlt == richtige
        return Bewertung(punkte if treffer else 0, treffer)
    # +1 je richtige, -1 je falsche, nie unter null - umgerechnet auf die
    # Punkte der Frage, damit "punkte" auch hier die Hoechstzahl ist.
    plus = len(gewaehlt & richtige)
    minus = len(gewaehlt - richtige)
    return _anteil(punkte, (plus - minus) / len(richtige), gewaehlt == richtige)


def _bewerte_schaetzung[K: Hashable](
    daten: SchaetzDaten, punkte: int, antworten: Mapping[K, Mapping[str, object]]
) -> dict[K, Bewertung]:
    abstaende: dict[K, float] = {}
    for spieler, wert in antworten.items():
        zahl = wert.get("zahl")
        abstaende[spieler] = (
            abs(zahl - daten.loesung) if isinstance(zahl, int | float) else math.inf
        )
    if not abstaende:
        return {}
    bester = min(abstaende.values())
    return {
        spieler: Bewertung(punkte, True) if abstand == bester else Bewertung(0, False)
        for spieler, abstand in abstaende.items()
    }


# ------------------------------------------------------------- Buzzer

Urteil = str  # "wartet" | "richtig" | "falsch"


def buzzer_dran[K: Hashable](druecke: Sequence[tuple[K, Urteil]]) -> K | None:
    """Der Erste, der noch nicht falsch lag. Die Reihenfolge ist die des
    Servers - wer zuerst ankam, nicht wessen Handy die frühere Uhrzeit hat."""
    return next((spieler for spieler, urteil in druecke if urteil == "wartet"), None)


def pruefe_buzzer_erlaubt(
    status: Rundenstatus,
    phase: Phase,
    typ: str,
    *,
    schon_gedrueckt: bool,
    team_schon_gedrueckt: bool = False,
) -> None:
    if status != "laeuft" or typ != "buzzer":
        raise AntwortNichtMoeglich("Bei dieser Frage gibt es keinen Buzzer.")
    if phase != "offen":
        raise AntwortNichtMoeglich("Der Buzzer ist gerade gesperrt.")
    if schon_gedrueckt:
        raise AntwortNichtMoeglich("Du hast schon gebuzzert.")
    # Mit Teams drueckt jedes Team einmal - wie am Buzzerpult in der Show.
    # Sonst haette das groesste Team die meisten Finger am Knopf.
    if team_schon_gedrueckt:
        raise AntwortNichtMoeglich("Dein Team hat schon gebuzzert.")


def pruefe_buzzer_urteil(typ: str, phase: Phase, dran: object | None) -> None:
    if typ != "buzzer":
        raise AktionNichtMoeglich("Das ist keine Buzzerfrage.")
    if phase not in ("offen", "gesperrt"):
        raise AktionNichtMoeglich("Die Frage ist nicht offen.")
    if dran is None:
        raise AktionNichtMoeglich("Gerade ist niemand dran.")


# ------------------------------------------------------------- Rangliste


@dataclass(frozen=True, slots=True)
class Rang:
    schluessel: Hashable
    name: str
    punkte: int
    rang: int


def rangliste(eintraege: Iterable[tuple[Hashable, str, int]]) -> list[Rang]:
    """Gleiche Punkte, gleicher Platz - und der naechste Platz zaehlt weiter
    (1, 2, 2, 4), wie bei jeder Siegerehrung."""
    sortiert = sorted(eintraege, key=lambda e: (-e[2], e[1].casefold()))
    plaetze: list[Rang] = []
    for index, (schluessel, name, punkte) in enumerate(sortiert):
        rang = plaetze[-1].rang if plaetze and plaetze[-1].punkte == punkte else index + 1
        plaetze.append(Rang(schluessel, name, punkte, rang))
    return plaetze


# ------------------------------------------------------------- Oeffentliche Sicht


def gemischt(frage_id: uuid.UUID, elemente: Sequence[str]) -> list[Element]:
    """Immer dieselbe Mischung je Frage - sonst sprang die Liste bei jedem
    Abruf, und das Handy pollt jede Sekunde. Nie die richtige Reihenfolge."""
    liste = [Element(kennung=elementkennung(frage_id, i), text=t) for i, t in enumerate(elemente)]
    return _mischen(frage_id, liste)


def _gemischt_rechts(frage_id: uuid.UUID, texte: Sequence[str]) -> list[Element]:
    liste = [Element(kennung=rechtskennung(frage_id, i), text=t) for i, t in enumerate(texte)]
    return _mischen(frage_id, liste)


def _mischen(frage_id: uuid.UUID, liste: list[Element]) -> list[Element]:
    gemischte = list(liste)
    random.Random(str(frage_id)).shuffle(gemischte)
    if gemischte == liste and len(liste) > 1:
        gemischte = gemischte[1:] + gemischte[:1]
    return gemischte


def loesung(daten: FrageDaten, frage_id: uuid.UUID) -> Loesung:
    if isinstance(daten, FreitextDaten | BildDaten):
        if not daten.loesungen:
            return Loesung(anzeige="Bewertet die Spielleitung")
        return Loesung(anzeige=" / ".join(daten.loesungen), texte=list(daten.loesungen))
    if isinstance(daten, ZahlDaten):
        text = _mit_einheit(daten.loesung, daten.einheit)
        if daten.toleranz:
            text += f" (± {_zahl(daten.toleranz)})"
        return Loesung(anzeige=text, zahl=daten.loesung, toleranz=daten.toleranz)
    if isinstance(daten, SchaetzDaten):
        return Loesung(anzeige=_mit_einheit(daten.loesung, daten.einheit), zahl=daten.loesung)
    if isinstance(daten, AuswahlDaten | BildauswahlDaten):
        richtige = _richtige(daten)
        return Loesung(
            anzeige=", ".join(_optionstext(daten, i) for i in richtige), optionen=richtige
        )
    if isinstance(daten, ZuordnenDaten):
        return Loesung(
            anzeige=", ".join(f"{p.links} → {p.rechts}" for p in daten.paare),
            zuordnung={str(i): rechtskennung(frage_id, i) for i in range(len(daten.paare))},
        )
    if isinstance(daten, HotspotDaten):
        return Loesung(anzeige="Die markierte Stelle im Bild", ziele=list(daten.ziele))
    if isinstance(daten, SortierDaten):
        return Loesung(
            anzeige=" → ".join(daten.elemente),
            reihenfolge=[elementkennung(frage_id, i) for i in range(len(daten.elemente))],
        )
    return Loesung(anzeige=daten.loesung or "Bewertet die Spielleitung")


def oeffentliche_frage(
    frage: FrageAusgabe, index: int, anzahl: int, phase: Phase
) -> OeffentlicheFrage:
    """Die Frage fuer Spieler und Tafel.

    In ``bereit`` steht nur da, dass gleich etwas kommt - die Leitung waehlt
    die Frage oft, bevor sie den Raum zur Ruhe gebracht hat.
    """
    sicht = OeffentlicheFrage(
        nummer=index + 1,
        anzahl=anzahl,
        kategorie=frage.kategorie,
        typ=frage.daten.typ,
        punkte=frage.punkte,
        text=None,
        hat_bild=frage.hat_bild,
        hat_ton="ton" in frage.medien,
    )
    if phase == "bereit":
        return sicht

    daten = frage.daten
    sicht.text = frage.text
    if isinstance(daten, AuswahlDaten):
        sicht.optionen = [option.text for option in daten.optionen]
        sicht.mehrfach = _mehrfach(daten)
    elif isinstance(daten, SortierDaten):
        sicht.elemente = gemischt(frage.id, daten.elemente)
    elif isinstance(daten, SchaetzDaten):
        sicht.minimum, sicht.maximum, sicht.schritt = daten.minimum, daten.maximum, daten.schritt
        sicht.einheit = daten.einheit
    elif isinstance(daten, ZahlDaten):
        sicht.einheit = daten.einheit
    elif isinstance(daten, ZuordnenDaten):
        sicht.links = [paar.links for paar in daten.paare]
        sicht.rechts = _gemischt_rechts(frage.id, [paar.rechts for paar in daten.paare])
    elif isinstance(daten, BildauswahlDaten):
        sicht.bildoptionen = [option.text for option in daten.optionen]
        sicht.mehrfach = _mehrfach(daten)
    if phase == "aufgeloest":
        sicht.loesung = loesung(daten, frage.id)
    return sicht


# ------------------------------------------------------------- Bilder und Kataloge

#: Ein Handyfoto, ordentlich verkleinert. Groesser wird es auf dem Pi und
#: auf zwanzig Handys gleichzeitig zaeh.
MAX_BILD_BYTES = 3 * 1024 * 1024
#: Kein SVG: es kann Skript enthalten.
BILDFORMATE = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


def pruefe_bild_vorhanden(hat_bild: bool) -> None:
    if not hat_bild:
        raise AktionNichtMoeglich("Diese Frage hat kein Bild.")


def bild_oeffentlich(phase: Phase, sichtbar: bool) -> bool:
    """Vor dem Zeigen bleibt das Bild verborgen: oft ist es schon die halbe
    Antwort."""
    return sichtbar and phase in ("offen", "gesperrt", "aufgeloest")


def pruefe_bild(mime: str, groesse: int) -> str:
    art = mime.split(";")[0].strip().lower()
    if art not in BILDFORMATE:
        raise BildUngueltig("Erlaubt sind PNG, JPEG, WebP und GIF.")
    if groesse <= 0:
        raise BildUngueltig("Die Datei ist leer.")
    if groesse > MAX_BILD_BYTES:
        raise BildUngueltig(f"Ein Bild darf höchstens {MAX_BILD_BYTES // (1024 * 1024)} MB haben.")
    return art


class MediumUngueltig(ServiceError):
    status = 422
    title = "Medium ungültig"


MAX_TON_BYTES = 8 * 1024 * 1024
TONFORMATE = frozenset({"audio/mpeg", "audio/ogg", "audio/wav", "audio/mp4", "audio/webm"})
_OPTION = re.compile(r"^option-(\d)$")


def pruefe_medium(schluessel: str, daten: FrageDaten, mime: str, groesse: int) -> str:
    """Ein weiteres Medium an der Frage: ein Ton zum Abspielen durch die
    Leitung oder ein Bild je Antwort der Bildauswahl."""
    if schluessel == "ton":
        art = mime.split(";")[0].strip().lower()
        if art not in TONFORMATE:
            raise BildUngueltig("Erlaubt sind MP3, OGG, WAV, M4A und WebM.")
        if groesse <= 0:
            raise BildUngueltig("Die Datei ist leer.")
        if groesse > MAX_TON_BYTES:
            raise BildUngueltig(
                f"Ein Ton darf höchstens {MAX_TON_BYTES // (1024 * 1024)} MB haben."
            )
        return art
    treffer = _OPTION.match(schluessel)
    if (
        treffer is None
        or not isinstance(daten, BildauswahlDaten)
        or int(treffer.group(1)) >= len(daten.optionen)
    ):
        raise MediumUngueltig(f"Ein Medium „{schluessel}“ gibt es bei dieser Frage nicht.")
    return pruefe_bild(mime, groesse)


def medium_oeffentlich(schluessel: str, phase: Phase) -> bool:
    """Ton und Antwortbilder gehoeren zur gezeigten Frage - vorher nicht."""
    return phase in ("offen", "gesperrt", "aufgeloest")


def pruefe_reihenfolge(vorhanden: Sequence[uuid.UUID], neu: Sequence[uuid.UUID]) -> None:
    if len(neu) != len(vorhanden) or set(neu) != set(vorhanden):
        raise ReihenfolgeUngueltig("Die neue Reihenfolge muss jede Frage genau einmal nennen.")


def pruefe_katalog_loeschbar(laufende_runden: int) -> None:
    if laufende_runden:
        raise KatalogInBenutzung("Mit diesem Katalog läuft noch eine Runde. Beende sie zuerst.")


def pruefe_katalog_spielbar(anzahl_fragen: int) -> None:
    if anzahl_fragen == 0:
        raise KatalogLeer("Der Katalog hat noch keine Fragen.")


# ------------------------------------------------------------- Ergebnistabelle


def csv_zelle(wert: str) -> str:
    """Ein Spielername wie ``=HYPERLINK(...)`` waere in Excel eine Formel - und
    die Spielernamen tippt hier jeder, der den Code kennt. Ein vorangestelltes
    Hochkomma macht daraus Text. Zahlen bleiben Zahlen."""
    if wert[:1] in ("=", "+", "@", "\t", "\r") or (wert[:1] == "-" and not _ist_zahl(wert)):
        return "'" + wert
    return wert


def _ist_zahl(wert: str) -> bool:
    try:
        float(wert.replace(",", "."))
    except ValueError:
        return False
    return True


def ergebnistabelle(
    fragen: Sequence[str],
    spieler: Sequence[tuple[str, str | None, int, Sequence[int | None]]],
) -> list[list[str]]:
    """Eine Zeile je Spieler, eine Spalte je gespielter Frage.

    ``spieler`` kommt schon in der Reihenfolge der Rangliste; der Platz wird
    hier vergeben, mit geteilten Plaetzen wie auf der Tafel.
    """
    kopf = ["Platz", "Name", "Team", "Gesamt"] + [
        f"{i}: {text}" for i, text in enumerate(fragen, start=1)
    ]
    plaetze = rangliste((index, name, gesamt) for index, (name, _, gesamt, _) in enumerate(spieler))
    rang_von = {platz.schluessel: platz.rang for platz in plaetze}
    zeilen = [kopf]
    for index, (name, team, gesamt, je_frage) in enumerate(spieler):
        zeilen.append(
            [str(rang_von[index]), name, team or "", str(gesamt)]
            + ["" if p is None else str(p) for p in je_frage]
        )
    return zeilen


def als_csv(zeilen: Sequence[Sequence[str]]) -> str:
    """Semikolon und BOM: so oeffnet ein deutsches Excel die Datei mit einem
    Doppelklick richtig - mit Komma laege alles in Spalte A, ohne BOM stuenden
    statt Umlauten Zeichensalat."""
    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", lineterminator="\n")
    for zeile in zeilen:
        schreiber.writerow([csv_zelle(zelle) for zelle in zeile])
    return "\ufeff" + puffer.getvalue()


# ------------------------------------------------------------- Moderation ohne Konto
#
# Jeder darf eine Runde starten und leiten - ohne Konto. Was ihn als Leitung
# ausweist, ist ein Moderatorcode: einmal angezeigt, nur als Hash gespeichert,
# im Cookie mitgefuehrt und als QR-Code zum Wiedereinstieg auf einem anderen
# Geraet. 16 Zeichen aus 31 sind rund 80 Bit - mehr als genug fuer etwas, das
# nur eine Runde beherrscht und nach zwei Tagen Ruhe verschwindet.


class KatalogNichtFrei(ServiceError):
    status = 403
    title = "Katalog nicht freigegeben"


class ZuVieleRunden(ServiceError):
    status = 429
    title = "Zu viele Runden"


class PaketZuGross(ServiceError):
    status = 413
    title = "Datei zu groß"


class LeitungVerweigert(ServiceError):
    status = 401
    title = "Keine Leitung"


#: So viele Runden ohne Konto gleichzeitig. Die Seite ist aus dem Internet
#: erreichbar; ohne Grenze fuellte ein Skript die Datenbank des Pi.
MAX_RUNDEN_OHNE_KONTO = 40
#: Ein eigenes Quiz ohne Konto. Das echte Battle.Net-Quiz hat 7 MB.
MAX_EIGENES_PAKET = 20 * 1024 * 1024
#: Ohne Aktivitaet so lange, dann wird aufgeraeumt (Entscheidung 2026-11-28).
RUHEZEIT = dt.timedelta(hours=48)
#: Aktivitaet wird hoechstens so oft geschrieben - fuer eine Frist von zwei
#: Tagen reicht es auf fuenf Minuten genau.
AKTIVITAET_TAKT = dt.timedelta(minutes=5)


def neuer_moderatorcode() -> str:
    zeichen = "".join(secrets.choice(CODEALPHABET) for _ in range(16))
    return "-".join(zeichen[i : i + 4] for i in range(0, 16, 4))


def normalisiere_moderatorcode(code: str) -> str:
    roh = re.sub(r"[^0-9A-Za-z]", "", code).upper()
    return "-".join(roh[i : i + 4] for i in range(0, len(roh), 4))


def leitung_erlaubt(*, mit_recht: bool, gespeicherter_hash: str | None, token: str | None) -> bool:
    """Leiten darf, wer ein Recht auf das Artefakt hat - oder den Code dieser
    einen Runde kennt."""
    if mit_recht:
        return True
    if gespeicherter_hash is None or not token:
        return False
    return token_stimmt(gespeicherter_hash, normalisiere_moderatorcode(token))


def pruefe_startkatalog(*, freigegeben: bool, mit_recht: bool) -> None:
    """Ohne Konto nur aus freigegebenen Katalogen: wer leitet, sieht die
    Loesungen, und ein nicht freigegebener Katalog ist vielleicht der vom
    naechsten Quizabend."""
    if not freigegeben and not mit_recht:
        raise KatalogNichtFrei("Dieser Katalog ist nicht für alle freigegeben.")


def pruefe_neue_runde(offene_ohne_konto: int) -> None:
    if offene_ohne_konto >= MAX_RUNDEN_OHNE_KONTO:
        raise ZuVieleRunden(
            "Gerade laufen zu viele Runden ohne Konto. Versuch es später noch einmal."
        )


def pruefe_eigenes_paket(groesse: int) -> None:
    if groesse > MAX_EIGENES_PAKET:
        raise PaketZuGross(
            f"Ein eigenes Quiz darf höchstens {MAX_EIGENES_PAKET // (1024 * 1024)} MB haben."
        )


def runde_abgelaufen(zuletzt_aktiv: dt.datetime, jetzt: dt.datetime) -> bool:
    return jetzt - zuletzt_aktiv > RUHEZEIT


def aufraeumgrenze(jetzt: dt.datetime) -> dt.datetime:
    return jetzt - RUHEZEIT


def aktivitaet_merken(zuletzt: dt.datetime | None, jetzt: dt.datetime) -> bool:
    return zuletzt is None or jetzt - zuletzt >= AKTIVITAET_TAKT
