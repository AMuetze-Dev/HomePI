"""Die Entscheidungen dieses Artefakts.

REIN: keine Datenbank, kein await, keine Fixtures. Genau deshalb laufen die
Tests dazu in Millisekunden - und nur deshalb benutzt man die rot-gruen-
Schleife wirklich. Alles, was I/O macht, gehoert in speicher.py.

Faustregel: Entscheidungen sind rein, Seiteneffekte sind dumm.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta

from homepi_core import ServiceError

from .schemas import Zusammenfassung


class StaffelUnbekannt(ServiceError):
    status = 404
    title = "Staffel unbekannt"


class SpielUnbekannt(ServiceError):
    status = 404
    title = "Spielbericht unbekannt"


class BefundUnbekannt(ServiceError):
    status = 404
    title = "Befund unbekannt"


class RegelUnbekannt(ServiceError):
    status = 404
    title = "Regel unbekannt"


class AuftragUnbekannt(ServiceError):
    status = 404
    title = "Auftrag unbekannt"


class SchonUnterwegs(ServiceError):
    status = 409
    title = "Es läuft schon einer"


class StaffelVergeben(ServiceError):
    status = 409
    title = "Staffel bereits angelegt"


class NochOffeneBefunde(ServiceError):
    status = 409
    title = "Es sind noch Befunde offen"


class GrundFehlt(ServiceError):
    status = 422
    title = "Begruendung fehlt"


class SchonHinaus(ServiceError):
    status = 409
    title = "Dazu ist schon ein Schreiben hinausgegangen"


@dataclass(frozen=True, slots=True)
class BefundSicht:
    """Das Wenige, das die Regeln von einem Befund brauchen.

    Ein eigener Typ und nicht die Tabelle: so bleiben die Entscheidungen ohne
    Datenbank testbar, und eine Spalte mehr in `modelle.py` zwingt niemanden,
    die Tests anzufassen.
    """

    schwere: str
    entscheidung: str
    regel: str = ""
    titel: str = ""
    #: Womit der Aufrufer die Zeile wiederfindet, nachdem `sortiert` sie
    #: umgestellt hat. Undurchsichtig fuer die Regeln - sie sehen nur hinein,
    #: wenn jemand etwas falsch macht. Ueber (regel, titel) ging es nicht:
    #: zwei Spieler ohne Foto in einem Spiel haben denselben.
    schluessel: str = ""


@dataclass(frozen=True, slots=True)
class SpielSicht:
    abgehakt: bool
    befunde: list[BefundSicht] = field(default_factory=list)


# ── Abhaken ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Abhakbar:
    """Als eigener Typ statt als bool, damit der Grund an der Entscheidung
    haengt und der Router ihn weiterreichen kann, ohne ihn zu erraten."""

    erlaubt: bool
    offen: int = 0
    grund: str = ""


def darf_abgehakt_werden(befunde: Iterable[BefundSicht]) -> Abhakbar:
    """Die eine Zusage dieses Artefakts: nichts uebersehen.

    Ein Spielbericht gilt erst als erledigt, wenn zu **jedem** Befund eine
    Entscheidung vorliegt - gleich welcher Schwere. Auch ein Hinweis will
    gesehen worden sein; genau dafuer gibt es 'zur Kenntnis genommen'.
    """
    offen = sum(1 for b in befunde if b.entscheidung == "offen")
    if not offen:
        return Abhakbar(True)
    wort = "Befund braucht" if offen == 1 else "Befunde brauchen"
    return Abhakbar(False, offen, f"{offen} {wort} noch eine Entscheidung")


# ── Entscheidung ──────────────────────────────────────────────────────────


def entscheidung_pruefen(art: str, grund: str) -> str:
    """Gibt den bereinigten Grund zurueck oder wirft.

    'verworfen' heisst: kein Verstoss. Das ist die einzige Entscheidung, die
    einen Befund aus der Bearbeitung nimmt - ohne Begruendung waere sie ein
    halbes Jahr spaeter nicht mehr nachvollziehbar, und genau danach fragt ein
    Verein.
    """
    bereinigt = grund.strip()
    if art == "verworfen" and not bereinigt:
        raise GrundFehlt("Zum Verwerfen eines Befundes gehört eine Begründung")
    return bereinigt


def darf_zurueckgenommen_werden(vorgang_zustand: str | None) -> None:
    """Eine Entscheidung zurueckzunehmen geht - solange nichts hinaus ist.

    Ein Entwurf laesst sich verwerfen, und danach ist der Befund wieder offen.
    Ein **versandtes** Schreiben nicht: der Verein hat es, und ein Befund, der
    hier wieder "offen" heisst, waere eine Akte, die dem widerspricht, was
    draussen steht. Erst den Vorgang zuruueckholen, dann den Befund.
    """
    if vorgang_zustand in ("versandt", "erledigt"):
        raise SchonHinaus(
            "Zu diesem Befund ist ein Schreiben versandt. Erst den Vorgang "
            "zurueck in den Entwurf stellen oder verwerfen."
        )


# ── Reihenfolge ───────────────────────────────────────────────────────────

#: Kritisch zuerst. Ein Feldverweis darf nicht unter zwanzig Hinweisen
#: verschwinden - das war der Grund, aus dem es diese Sortierung gibt.
_GEWICHT = {"kritisch": 0, "warnung": 1, "hinweis": 2}


def sortiert(befunde: Iterable[BefundSicht]) -> list[BefundSicht]:
    """Schwere zuerst, offene vor entschiedenen, sonst wie eingegangen.

    Stabil: sonst springen Befunde gleicher Schwere bei jedem Laden umher, und
    man verliert die Stelle, an der man gerade war.
    """
    return sorted(
        befunde,
        key=lambda b: (_GEWICHT.get(b.schwere, 9), 0 if b.entscheidung == "offen" else 1),
    )


# ── Faelligkeit ───────────────────────────────────────────────────────────


def ist_faellig(datum: date, heute: date, tage: int) -> bool:
    """Ob ein Spiel in den Pruefzeitraum faellt.

    Nach vorn ist die Grenze scharf: ein Spiel in der Zukunft ist noch nicht
    gespielt, und ein Befund darauf waere eine Erfindung.
    """
    if datum > heute:
        return False
    return (heute - datum).days <= tage


# ── Zusammenfassung ───────────────────────────────────────────────────────


def zusammenfassen(
    spiele: Iterable[SpielSicht], staffeln_aktiv: int, vorgaenge_entwurf: int = 0
) -> Zusammenfassung:
    liste = list(spiele)
    offene_befunde = [b for s in liste for b in s.befunde if b.entscheidung == "offen"]
    return Zusammenfassung(
        spiele=len(liste),
        offen=sum(1 for s in liste if not s.abgehakt),
        abgehakt=sum(1 for s in liste if s.abgehakt),
        befunde_offen=len(offene_befunde),
        # Nur was noch offen ist: ein entschiedener Feldverweis ist keine
        # offene Arbeit mehr und darf die Zahl auf der Kachel nicht dauerhaft
        # rot halten.
        befunde_kritisch=sum(1 for b in offene_befunde if b.schwere == "kritisch"),
        staffeln_aktiv=staffeln_aktiv,
        vorgaenge_entwurf=vorgaenge_entwurf,
    )


# ── Einstellungen ─────────────────────────────────────────────────────────


class WertUnbrauchbar(ServiceError):
    status = 422
    title = "Einstellung unbrauchbar"


@dataclass(frozen=True, slots=True)
class Einstellungen:
    """Was fuer die ganze Installation gilt.

    Als eigener Typ und nicht als dict: so steht jede Voreinstellung genau
    einmal da, und ein Tippfehler im Schluessel faellt beim Uebersetzen auf
    und nicht erst, wenn ein Schreiben ohne Absender herauskommt.
    """

    staffelleiter: str = ""
    verband: str = ""
    absender: str = ""
    #: Wie weit zurueck ein Spiel noch in den Pruefzeitraum faellt.
    pruefzeitraum_tage: int = 30
    #: Wie lange ein Verein Zeit bekommt, auf ein Schreiben zu antworten.
    frist_tage: int = 14


#: Die Zahlen mit ihren Grenzen. Unten schaerfer als noetig: ein
#: Pruefzeitraum von null Tagen liefert stumm eine leere Liste, und man sucht
#: den Fehler dann im Prueflauf statt in den Einstellungen.
_ZAHLEN = {"pruefzeitraum_tage": (1, 365), "frist_tage": (1, 90)}
_TEXTE = ("staffelleiter", "verband", "absender")


def einstellungen_aus(roh: Mapping[str, str]) -> Einstellungen:
    """Aus den rohen Zeichenketten der Tabelle geprueft Werte.

    Unbekannte Schluessel werden uebergangen und nicht bemaengelt: eine
    Einstellung, die es einmal gab, soll eine aeltere Installation nicht am
    Starten hindern.
    """
    felder: dict[str, object] = {s: roh.get(s, "").strip() for s in _TEXTE}
    for schluessel, (klein, gross) in _ZAHLEN.items():
        felder[schluessel] = _zahl(schluessel, roh.get(schluessel), klein, gross)
    return Einstellungen(**felder)  # type: ignore[arg-type]


def _zahl(schluessel: str, wert: str | None, klein: int, gross: int) -> int:
    vorgabe: int = getattr(Einstellungen(), schluessel)
    if wert is None or not str(wert).strip():
        return vorgabe
    try:
        zahl = int(str(wert).strip())
    except ValueError:
        raise WertUnbrauchbar(f"{schluessel!r} braucht eine ganze Zahl, nicht {wert!r}") from None
    if not klein <= zahl <= gross:
        raise WertUnbrauchbar(f"{schluessel!r} muss zwischen {klein} und {gross} liegen")
    return zahl


# ── Mannschaften ──────────────────────────────────────────────────────────

#: Bis hierhin ist eine angehaengte Zahl eine Mannschaftsnummer. Darueber ist
#: sie eine Jahreszahl im Vereinsnamen: "Dresdner SC 1898" hat keine 1898
#: Mannschaften. Kein Verein dieser Spielklassen hat mehr als zwanzig.
NUMMER_GRENZE = 20


def verein_und_nummer(name: str) -> tuple[str, int]:
    """'SV Loschwitz 2' -> ('SV Loschwitz', 2), 'Dresdner SC 1898' -> (.., 1)."""
    teile = name.strip().rsplit(" ", 1)
    if len(teile) == 2 and teile[1].isdigit():
        nummer = int(teile[1])
        if 1 <= nummer <= NUMMER_GRENZE:
            return teile[0].strip(), nummer
    return name.strip(), 1


def hoehere_raten(namen: Iterable[str]) -> dict[str, list[str]]:
    """Welche Mannschaft welcher desselben Vereins untersteht.

    Geraten aus dem Namenszusatz, und das ist genau das: geraten. Bei einer
    Spielgemeinschaft steht der Verein oft gar nicht im Namen, und dann ist
    das Ergebnis falsch. Deshalb ist es ein Vorschlag, den die Oberflaeche zur
    Bestaetigung vorlegt, und keine Wahrheit.
    """
    zerlegt = [(n, *verein_und_nummer(n)) for n in namen]
    return {
        name: sorted(anderer for anderer, v, nr in zerlegt if v == verein and nr < nummer)
        for name, verein, nummer in zerlegt
    }


def mannschaft_unsicher(ist_sg: bool, bestaetigt: bool) -> bool:
    """Ob die Zuordnung einen zweiten Blick wert ist.

    Eine Spielgemeinschaft traegt den Verein nicht im Namen -- der Schluss aus
    dem Namenszusatz greift dort ins Leere. Solange niemand hingesehen hat,
    ist das der Fall, der still das Falsche prueft.
    """
    return ist_sg and not bestaetigt


# ── Vorgaenge: Mahnung und Sportgerichtsfall ──────────────────────────────


class WegUnbekannt(ServiceError):
    status = 422
    title = "Unbekannter Weg"


class VorgangUnbekannt(ServiceError):
    status = 404
    title = "Vorgang unbekannt"


class VorgangVergeben(ServiceError):
    status = 409
    title = "Zu diesem Befund gibt es schon einen Vorgang"


class ZustandUnmoeglich(ServiceError):
    status = 409
    title = "Dieser Schritt ist von hier aus nicht möglich"


#: Was aus einem Befund werden kann. "kein" ist die Voreinstellung: die
#: meisten Befunde sind Hinweise und gehen nirgendwohin.
WEGE = ("kein", "mahnung", "sportgericht")

#: Vorwaerts und einmal zurueck. Weiter zurueck nicht: ein abgeschlossener
#: Vorgang, der wieder Entwurf wird, waere ein Schreiben, das ein Verein
#: schon in der Hand hat und das hier trotzdem als ungeschrieben gilt.
_ZUSTANDSWEGE: dict[str, tuple[str, ...]] = {
    "entwurf": ("versandt",),
    "versandt": ("erledigt", "entwurf"),
    "erledigt": ("versandt",),
}


def weg_pruefen(weg: str) -> str:
    if weg not in WEGE:
        raise WegUnbekannt(f"{weg!r} ist kein Weg; erlaubt sind {', '.join(WEGE)}")
    return weg


def art_aus_weg(weg: str) -> str:
    """Der Weg des Befundes bestimmt die Art des Vorgangs."""
    if weg_pruefen(weg) == "kein":
        raise WegUnbekannt("Zu einem Befund ohne Weg gehört kein Vorgang")
    return weg


def zustand_weiter(alt: str, neu: str) -> str:
    if neu not in _ZUSTANDSWEGE.get(alt, ()):
        moeglich = ", ".join(_ZUSTANDSWEGE.get(alt, ())) or "nichts"
        raise ZustandUnmoeglich(f"Von {alt!r} aus geht nur: {moeglich}")
    return neu


def aktenzeichen(saison: str, laufnummer: int) -> str:
    """Fortlaufend je Saison, gleich lang und damit sortierbar.

    Der Schraegstrich der Saison wird zum Bindestrich: das Aktenzeichen steht
    auch in Dateinamen, und ein Schraegstrich ist dort ein Verzeichnis.
    """
    kern = saison.strip().replace("/", "-") or "ohne-saison"
    return f"{kern}-{laufnummer:04d}"


#: Der Halbgeviertstrich zwischen Heim und Gast. So steht die Paarung auf
#: jedem Spielberichtsbogen. `ruff` haelt ihn fuer einen verunglueckten
#: Bindestrich; er ist keiner, und ein Bindestrich saehe neben einem Namen
#: wie "Meissen-West" nach einer Worttrennung aus.
STRICH = " – "  # noqa: RUF001 - genau dieses Zeichen ist gemeint


@dataclass(frozen=True, slots=True)
class Schreiben:
    empfaenger: str
    betreff: str
    text: str


@dataclass(frozen=True, slots=True)
class Anlass:
    """Woraus ein Schreiben entsteht - alles, was darin vorkommt.

    Ein Typ statt zwoelf Parameter: die Reihenfolge von zwoelf gleichartigen
    Zeichenketten verwechselt man, und heim und gast zu vertauschen faellt in
    keinem Test auf, der nur zaehlt.
    """

    staffel: str
    saison: str
    heim: str
    gast: str
    spieldatum: date
    dfbnet_id: str
    titel: str
    sachverhalt: str
    verein: str
    betroffener: str
    grund: str


def _tag(datum: date) -> str:
    return datum.strftime("%d.%m.%Y")


def vorgang_entwurf(
    art: str, anlass: Anlass, einstellungen: Einstellungen, heute: date
) -> Schreiben:
    """Der Entwurf, Wort fuer Wort aus der Vorlage.

    **Kein erzeugter Text.** Gleiche Eingabe, gleicher Ausgang - das ist der
    Grund, aus dem hier eine Vorlage steht und kein Sprachmodell: ein
    Schreiben an einen Verein muss ein halbes Jahr spaeter noch erklaerbar
    sein, und zwar Satz fuer Satz.

    **Und es geht hier auch nichts hinaus.** Der Text landet in der
    Oberflaeche, wird von dort kopiert und von einem Menschen abgeschickt.
    """
    frist = heute + timedelta(days=einstellungen.frist_tage)
    partie = f"{anlass.heim}{STRICH}{anlass.gast}"
    kopf = (
        f"Spiel:        {partie}\n"
        f"Spieltag:     {_tag(anlass.spieldatum)}\n"
        f"Spielnummer:  {anlass.dfbnet_id}\n"
        f"Staffel:      {anlass.staffel} ({anlass.saison})"
    )
    unterschrift = (
        "Mit freundlichen Grüßen\n"
        f"{einstellungen.staffelleiter or '(Staffelleiter in den Einstellungen eintragen)'}\n"
        f"Staffelleiter {anlass.staffel}"
        + (f"\n{einstellungen.verband}" if einstellungen.verband else "")
    )
    betroffen = anlass.betroffener or anlass.verein

    if art == "mahnung":
        betreff = f"Mahnung {partie} am {_tag(anlass.spieldatum)}"
        text = (
            "Sehr geehrte Damen und Herren,\n\n"
            "bei der Prüfung des Spielberichts wurde Folgendes festgestellt:\n\n"
            f"{kopf}\n\n"
            f"Feststellung: {anlass.titel}\n"
            f"{anlass.sachverhalt}\n\n"
            f"Betroffen:    {betroffen}\n"
            f"Grund:        {anlass.grund}\n\n"
            f"Wir bitten um Abstellung und um eine Stellungnahme bis zum {_tag(frist)}.\n\n"
            f"{unterschrift}"
        )
    else:
        betreff = f"Antrag an das Sportgericht{STRICH}{partie} am {_tag(anlass.spieldatum)}"
        text = (
            "Antrag auf Eröffnung eines Verfahrens\n\n"
            f"{kopf}\n\n"
            f"Betroffener:  {betroffen}\n"
            f"Verein:       {anlass.verein}\n"
            f"Tatbestand:   {anlass.titel}\n"
            f"Grund:        {anlass.grund}\n\n"
            f"Sachverhalt:\n{anlass.sachverhalt}\n\n"
            f"Die Stellungnahme des Vereins wird bis zum {_tag(frist)} erbeten.\n\n"
            f"{unterschrift}"
        )
    return Schreiben(empfaenger=einstellungen.absender, betreff=betreff, text=text)


# ── Auftraege ─────────────────────────────────────────────────────────────

# Welche Arten es gibt, steht als `AuftragArt` in schemas.py und wird von
# Pydantic geprueft, bevor irgendetwas hier ankommt. Eine zweite Liste an
# dieser Stelle waere dieselbe Tatsache doppelt -- und irgendwann verschieden.

#: Solange einer davon offen ist, wird kein zweiter angenommen.
OFFENE_ZUSTAENDE = ("angefordert", "laeuft")

#: Der Weg eines Auftrags. Nur vorwaerts: ein beendeter Lauf laesst sich nicht
#: fortsetzen, er wird neu angefordert.
_AUFTRAGSWEGE: dict[str, tuple[str, ...]] = {
    # "fertig" gleich von hier aus: ein Prueflauf, fuer den es nichts zu
    # pruefen gibt, ist fertig, ohne je einen Schritt gemeldet zu haben.
    "angefordert": ("laeuft", "fertig", "abgebrochen", "gescheitert"),
    "laeuft": ("fertig", "abgebrochen", "gescheitert"),
    "fertig": (),
    "abgebrochen": (),
    "gescheitert": (),
}


def darf_angefordert_werden(offene: int) -> None:
    """Einer nach dem anderen.

    Es gibt genau eine DFBnet-Sitzung. Zwei Laeufe gleichzeitig hiessen zwei
    Browser an derselben Anmeldung, und der zweite wirft den ersten hinaus -
    mitten in einem halb gelesenen Spielbericht.
    """
    if offene:
        raise SchonUnterwegs("Es ist bereits ein Auftrag unterwegs. Erst abwarten oder abbrechen.")


def auftrag_weiter(alt: str, neu: str) -> str:
    if neu not in _AUFTRAGSWEGE.get(alt, ()):
        moeglich = ", ".join(_AUFTRAGSWEGE.get(alt, ())) or "nichts"
        raise ZustandUnmoeglich(f"Von {alt!r} aus geht nur: {moeglich}")
    return neu


def ist_beendet(zustand: str) -> bool:
    return not _AUFTRAGSWEGE.get(zustand, ())


def darf_fortschreiben(zustand: str) -> None:
    """Ein beendeter Auftrag nimmt nichts mehr an.

    Eine spaete Meldung eines Dienstes, der sich schon abgemeldet hat, wuerde
    sonst den Endstand ueberschreiben -- und im Protokoll staende nach
    "fertig" noch, was er angeblich gerade tut.
    """
    if ist_beendet(zustand):
        raise ZustandUnmoeglich(f"Der Auftrag ist {zustand}; er nimmt nichts mehr an")


def fortschritt_pruefen(wert: int) -> int:
    """Zwischen 0 und 100.

    Abgeschnitten statt abgelehnt: ein Dienst, der sich verrechnet, soll
    deswegen nicht mitten im Lauf stehenbleiben -- die Zahl ist eine Anzeige,
    kein Ergebnis.
    """
    return max(0, min(100, wert))
