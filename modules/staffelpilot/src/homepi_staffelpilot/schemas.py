"""Der Vertrag nach aussen.

Was hier steht, landet im OpenAPI-Schema - und damit in der generischen
Ansicht des Frontends und in jedem erzeugten Client. Aenderungen hier sind
Aenderungen an der Schnittstelle.

Die Begriffe kommen aus der Spielordnung und bleiben deutsch: ein Staffelleiter
liest 'Befund' und 'abhaken', nicht 'finding' und 'acknowledge'.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Ein Name aus Leerzeichen ist kein Name. min_length greift erst nach dem
# Trimmen - deshalb der Validator, nicht nur die Laengenangabe.
NameFeld = Annotated[str, Field(min_length=1, max_length=120)]
KurzFeld = Annotated[str, Field(max_length=120)]

#: Wie schwer ein Befund wiegt. Diese Reihenfolge ist auch die Sortierung in
#: der Oberflaeche - kritisch zuerst, weil ein Feldverweis nicht unter zwanzig
#: Hinweisen verschwinden darf.
Schwere = Literal["kritisch", "warnung", "hinweis"]

#: Was der Staffelleiter mit einem Befund gemacht hat. 'offen' blockiert das
#: Abhaken des Spiels - das ist die ganze Zusage dieses Artefakts.
Entscheidung = Literal["offen", "kenntnis", "verworfen"]

#: Altersklassen nach SpO SFV, soweit sie in einem Kreis vorkommen.
Altersklasse = Literal["maenner", "frauen", "ue32", "ue35", "ue40", "ue50"]

#: Wohin ein Befund fuehrt, wenn er stehen bleibt. Der Prueflauf sagt es beim
#: Einspielen - dieses Artefakt kennt die Spielordnung nicht und soll sie auch
#: nicht kennen. "kein" ist die Voreinstellung und der haeufigste Fall.
Weg = Literal["kein", "mahnung", "sportgericht"]

#: Die Art eines Vorgangs. Dieselben Woerter wie beim Weg, ohne "kein": ein
#: Vorgang ohne Weg waere ein Schreiben ohne Anlass.
VorgangArt = Literal["mahnung", "sportgericht"]

#: Wo ein Vorgang steht. "versandt" heisst: ein Mensch hat ihn abgeschickt.
#: Dieses Programm verschickt nichts.
VorgangZustand = Literal["entwurf", "versandt", "erledigt"]


def _getrimmt(wert: object) -> object:
    return wert.strip() if isinstance(wert, str) else wert


# ── Staffel ───────────────────────────────────────────────────────────────


class StaffelAnlegen(BaseModel):
    name: NameFeld
    altersklasse: Altersklasse
    spielklasse: NameFeld
    saison: Annotated[str, Field(max_length=10)] = ""
    #: 0 heisst *nicht bekannt*. Siehe `modelle.Staffel.spieltage`.
    spieltage: Annotated[int, Field(ge=0, le=99)] = 0
    aktiv: bool = True

    @field_validator("name", "spielklasse", "saison", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class StaffelAendern(BaseModel):
    """Alles, was sich an einer Staffel aendern laesst.

    Ausgelassene Felder bleiben stehen. Name und Spielklasse stehen auch in
    DFBnet - wer sie hier aendert, sollte wissen, dass der naechste Abgleich
    ueber den Namen sucht.
    """

    name: NameFeld | None = None
    altersklasse: Altersklasse | None = None
    spielklasse: NameFeld | None = None
    saison: Annotated[str, Field(max_length=10)] | None = None
    spieltage: Annotated[int, Field(ge=0, le=99)] | None = None
    aktiv: bool | None = None

    @field_validator("name", "spielklasse", "saison", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class StaffelAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    altersklasse: Altersklasse
    spielklasse: str
    saison: str
    spieltage: int
    aktiv: bool


# ── Befund ────────────────────────────────────────────────────────────────


class BefundEingang(BaseModel):
    """Ein Befund, wie ihn ein Prueflauf einreicht."""

    regel: NameFeld
    schwere: Schwere
    titel: NameFeld
    text: Annotated[str, Field(max_length=2000)] = ""
    person: KurzFeld = ""
    mannschaft: KurzFeld = ""
    #: Wohin der Befund fuehrt. Der Prueflauf weiss es; hier wird es nur
    #: mitgefuehrt, damit die Oberflaeche den passenden Knopf anbietet.
    weg: Weg = "kein"

    @field_validator("regel", "titel", "text", "person", "mannschaft", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class BefundAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    regel: str
    schwere: Schwere
    titel: str
    text: str
    person: str
    mannschaft: str
    entscheidung: Entscheidung
    grund: str
    weg: Weg
    #: Die Kennung des Vorgangs, falls schon einer angelegt wurde. So sieht
    #: die Oberflaeche ohne zweiten Aufruf, ob der Knopf "Entwurf" noch
    #: anzubieten ist.
    vorgang_id: uuid.UUID | None = None


class EntscheidungSetzen(BaseModel):
    """'kenntnis' heisst: gesehen, mehr passiert nicht. 'verworfen' heisst:
    kein Verstoss - und das braucht eine Begruendung, weil es die einzige
    Entscheidung ist, die einen Befund aus der Bearbeitung nimmt."""

    art: Literal["kenntnis", "verworfen"]
    grund: Annotated[str, Field(max_length=500)] = ""

    @field_validator("grund", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


# ── Spielbericht ──────────────────────────────────────────────────────────


class KarteEingang(BaseModel):
    """Eine Karte, wie sie ein Prueflauf einreicht.

    Sie wird **nicht umgedeutet**: `art` ist die Schreibweise von DFBnet. Was
    eine Gelb-Rote Karte auslaest, steht in den Regeln, nicht hier.
    """

    person: KurzFeld = ""
    pass_nr: Annotated[str, Field(max_length=40)] = ""
    art: KurzFeld = ""
    minute: Annotated[str, Field(max_length=10)] = ""
    mannschaft: KurzFeld = ""

    @field_validator("person", "pass_nr", "art", "minute", "mannschaft", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class KarteAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    datum: dt.date
    wettbewerb: str
    person: str
    pass_nr: str
    art: str
    minute: str
    mannschaft: str
    #: Die Kennung des Spiels. Zwei Karten desselben Spiels gehoeren zusammen:
    #: nach § 58 (1) c) ist die gelbe Karte eines Spiels mit Gelb-Rot
    #: "verbraucht" und zaehlt nicht mit.
    spielbericht_id: uuid.UUID


class SpielEingang(BaseModel):
    """Ein geprueftes Spiel, wie es ein Prueflauf einreicht.

    `dfbnet_id` ist der Schluessel: derselbe Bericht darf mehrfach eingereicht
    werden, ohne sich zu verdoppeln.
    """

    dfbnet_id: NameFeld
    datum: dt.date
    heim: NameFeld
    gast: NameFeld
    ergebnis: KurzFeld = ""
    befunde: list[BefundEingang] = Field(default_factory=list)
    #: Die Karten dieses Spiels. Sie sind keine Befunde, sondern das
    #: Gedaechtnis fuer § 58: die fuenfte Verwarnung sperrt.
    karten: list[KarteEingang] = Field(default_factory=list)
    #: Der Wettbewerb dieses Spiels, wie DFBnet ihn nennt. Pokal und
    #: Meisterschaft werden nach § 58 (2) getrennt gezaehlt.
    wettbewerb: KurzFeld = ""

    @field_validator("dfbnet_id", "heim", "gast", "ergebnis", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class ImportAuftrag(BaseModel):
    """Der Weg, auf dem Daten hereinkommen.

    Bewusst ein eigener Endpunkt und kein interner Aufruf: die
    DFBnet-Automation faehrt minutenlang einen Browser und gehoert deshalb in
    einen eigenen Dienst (docs/06-artefakte.md). Sie schiebt dann hier herein,
    ohne dass sich an diesem Artefakt etwas aendert.
    """

    staffel_id: uuid.UUID
    spiele: list[SpielEingang]


class ImportErgebnis(BaseModel):
    angelegt: int
    aktualisiert: int
    befunde: int


class SpielAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    staffel_id: uuid.UUID
    dfbnet_id: str
    datum: dt.date
    heim: str
    gast: str
    ergebnis: str
    abgehakt: bool
    abgehakt_am: dt.datetime | None
    befunde: list[BefundAusgabe]


class SpielZeile(BaseModel):
    """Eine Zeile der Warteschlange, ohne die Befunde selbst.

    Dreissig Spiele mit je zehn Befunden waeren ein Vielfaches an Daten fuer
    eine Ansicht, die nur Zaehler zeigt.
    """

    id: uuid.UUID
    dfbnet_id: str
    datum: dt.date
    heim: str
    gast: str
    ergebnis: str
    abgehakt: bool
    offene_befunde: int
    kritische_befunde: int
    #: Ob das Spiel im Pruefzeitraum liegt. Berechnet, nicht gespeichert -
    #: sonst waere der Wert am Tag nach dem Schreiben falsch.
    faellig: bool


class Zusammenfassung(BaseModel):
    """Was auf der Kachel und im Seitenkopf steht."""

    spiele: int
    offen: int
    abgehakt: int
    befunde_offen: int
    befunde_kritisch: int
    staffeln_aktiv: int
    #: Entwuerfe, die noch niemand abgeschickt hat. Sie sind der Teil der
    #: Arbeit, den man am leichtesten liegen laesst.
    vorgaenge_entwurf: int = 0


# ── Einstellungen ─────────────────────────────────────────────────────────


class EinstellungenAusgabe(BaseModel):
    """Was fuer die ganze Installation gilt.

    Die Voreinstellungen stehen in `dienst.Einstellungen` und nicht hier:
    sonst gaebe es zwei Stellen, an denen 30 Tage steht, und irgendwann zwei
    verschiedene Zahlen.
    """

    staffelleiter: str
    verband: str
    absender: str
    pruefzeitraum_tage: int
    frist_tage: int
    uebertragung_pausiert: bool
    browser_sichtbar: bool


class EinstellungenSetzen(BaseModel):
    """Nur die Felder, die gesetzt werden sollen.

    Ein ausgelassenes Feld bleibt, wie es war. Ein Dialog, der offen stand,
    waehrend woanders etwas geschrieben wurde, schreibt sonst einen alten Wert
    zurueck.
    """

    staffelleiter: KurzFeld | None = None
    verband: KurzFeld | None = None
    absender: Annotated[str, Field(max_length=200)] | None = None
    pruefzeitraum_tage: Annotated[int, Field(ge=1, le=365)] | None = None
    frist_tage: Annotated[int, Field(ge=1, le=90)] | None = None
    uebertragung_pausiert: bool | None = None
    #: Beim Pruefen zusehen. Siehe `dienst.Einstellungen.browser_sichtbar`.
    browser_sichtbar: bool | None = None

    @field_validator("staffelleiter", "verband", "absender", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


# ── Mannschaften ──────────────────────────────────────────────────────────


class MannschaftEingang(BaseModel):
    """Eine Mannschaft, wie sie aus DFBnet kommt oder von Hand berichtigt wird."""

    name: NameFeld
    verein: KurzFeld = ""
    nummer: Annotated[int, Field(ge=0, le=99)] = 0
    ist_sg: bool = False
    #: Leer heisst nicht "keine hoeheren", sondern "noch nicht gesagt": beim
    #: Einspielen wird dann geraten. Wer ausdruecklich keine will, setzt
    #: zusaetzlich `bestaetigt`.
    hoehere: list[KurzFeld] = Field(default_factory=list)
    bestaetigt: bool = False

    @field_validator("name", "verein", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class MannschaftAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    verein: str
    nummer: int
    ist_sg: bool
    hoehere: list[str]
    bestaetigt: bool
    #: Berechnet, nicht gespeichert: ob die geratene Zuordnung einen zweiten
    #: Blick wert ist. Eine gespeicherte Spalte waere nach jeder Aenderung an
    #: der Regel falsch.
    unsicher: bool


class MannschaftenSetzen(BaseModel):
    """Die vollstaendige Liste einer Staffel.

    Vollstaendig und nicht als Aenderung: DFBnet liefert die Meldung als
    Ganzes, und eine Mannschaft, die darin fehlt, ist zurueckgezogen worden.
    """

    mannschaften: list[MannschaftEingang]


# ── Vorgaenge ─────────────────────────────────────────────────────────────


class VorgangAnlegen(BaseModel):
    """Was der Staffelleiter beisteuert, bevor der Entwurf entsteht.

    Alles ist freiwillig: fehlt der Verein, wird die Mannschaft des Befundes
    genommen, fehlt der Grund, der Titel. Ein Entwurf, der an einem leeren
    Feld scheitert, waere ein Entwurf, den niemand anfaengt.
    """

    verein: KurzFeld = ""
    betroffener: KurzFeld = ""
    grund: Annotated[str, Field(max_length=500)] = ""
    empfaenger: Annotated[str, Field(max_length=200)] = ""

    @field_validator("verein", "betroffener", "grund", "empfaenger", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class VorgangAendern(BaseModel):
    """Der Text gehoert dem Staffelleiter.

    Die Vorlage liefert einen Anfang, kein Ergebnis. Wer den Text hier
    ueberschreibt, behaelt ihn: ein spaeteres Neuerzeugen gibt es bewusst
    nicht, es wuerde stillschweigend eine Formulierung loeschen, die jemand
    sich ueberlegt hat.
    """

    empfaenger: Annotated[str, Field(max_length=200)] | None = None
    betreff: Annotated[str, Field(max_length=200)] | None = None
    text: str | None = None

    @field_validator("empfaenger", "betreff", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class ZustandSetzen(BaseModel):
    zustand: VorgangZustand


class VorgangAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    befund_id: uuid.UUID
    art: VorgangArt
    aktenzeichen: str
    verein: str
    betroffener: str
    grund: str
    empfaenger: str
    betreff: str
    text: str
    zustand: VorgangZustand
    versandt_am: dt.datetime | None


class VorgangZeile(BaseModel):
    """Die Liste. Ohne den Text - der ist lang und wird erst beim Oeffnen
    gebraucht."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    befund_id: uuid.UUID
    art: VorgangArt
    aktenzeichen: str
    verein: str
    betroffener: str
    betreff: str
    zustand: VorgangZustand


# ── Regelkatalog ──────────────────────────────────────────────────────────


class RegelEingang(BaseModel):
    """Eine Regel, wie sie der Prüfdienst meldet."""

    schluessel: NameFeld
    name: NameFeld
    beschreibung: Annotated[str, Field(max_length=1000)] = ""
    schwere: Schwere = "hinweis"
    weg: Weg = "kein"

    @field_validator("schluessel", "name", "beschreibung", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class RegelkatalogSetzen(BaseModel):
    """Der Katalog als Ganzes.

    Vollstaendig und nicht als Aenderung: eine Regel, die der Pruefdienst
    nicht mehr kennt, gibt es nicht mehr, und sie in der Liste stehen zu
    lassen hiesse, einen Schalter anzubieten, der nichts mehr schaltet.
    """

    regeln: list[RegelEingang]


class RegelAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    schluessel: str
    name: str
    beschreibung: str
    schwere: Schwere
    weg: Weg
    aktiv: bool


class RegelUmschalten(BaseModel):
    aktiv: bool


# ── Alle Befunde auf einmal ───────────────────────────────────────────────


class BefundZeile(BaseModel):
    """Ein Befund mit dem Spiel, zu dem er gehoert.

    Die Warteschlange fragt Spiel fuer Spiel; diese Liste beantwortet die
    andere Frage: "was ist in dieser Saison alles aufgelaufen". Dafuer muss
    das Spiel mit an der Zeile stehen, sonst ist eine Zeile nicht zuzuordnen.
    """

    id: uuid.UUID
    spiel_id: uuid.UUID
    staffel_id: uuid.UUID
    dfbnet_id: str
    datum: dt.date
    heim: str
    gast: str
    regel: str
    schwere: Schwere
    titel: str
    person: str
    mannschaft: str
    entscheidung: Entscheidung
    grund: str
    weg: Weg
    vorgang_id: uuid.UUID | None = None


# ── Aufträge ──────────────────────────────────────────────────────────────

#: Was ein Auftrag tut. `pruflauf` prüft Spielberichte, `initialisierung`
#: holt die Saisondaten einer Staffel aus DFBnet.
AuftragArt = Literal["pruflauf", "initialisierung"]

#: Wo er steht. Nur vorwärts — ein beendeter Lauf wird neu angefordert, nicht
#: fortgesetzt.
AuftragZustand = Literal["angefordert", "laeuft", "fertig", "abgebrochen", "gescheitert"]


class AuftragAnfordern(BaseModel):
    """Ohne `staffel_id` gilt der Auftrag für alle aktiven Staffeln."""

    art: AuftragArt = "pruflauf"
    staffel_id: uuid.UUID | None = None


class Protokollzeile(BaseModel):
    zeit: str
    text: str


class AuftragAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    art: AuftragArt
    staffel_id: uuid.UUID | None
    zustand: AuftragZustand
    schritt: str
    fortschritt: int
    gepruefte: int
    befunde: int
    meldung: str
    protokoll: list[Protokollzeile]
    gestartet_am: dt.datetime | None
    beendet_am: dt.datetime | None
    angelegt: dt.datetime


class AuftragZeile(BaseModel):
    """Die Liste. Ohne Protokoll — das ist lang und erst beim Öffnen nötig."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    art: AuftragArt
    staffel_id: uuid.UUID | None
    zustand: AuftragZustand
    schritt: str
    fortschritt: int
    gepruefte: int
    befunde: int
    meldung: str
    gestartet_am: dt.datetime | None
    beendet_am: dt.datetime | None
    angelegt: dt.datetime


class Fortschritt(BaseModel):
    """Was der Prüfdienst meldet, während er läuft.

    Alles freiwillig: ein Dienst, der nur den Schritt weiterschreibt, soll
    nicht auch noch Zahlen mitschicken müssen, die sich nicht geändert haben.
    """

    schritt: KurzFeld | None = None
    fortschritt: int | None = None
    gepruefte: Annotated[int, Field(ge=0)] | None = None
    befunde: Annotated[int, Field(ge=0)] | None = None
    #: Eine Zeile fürs Protokoll. Angehängt, nie ersetzt.
    zeile: Annotated[str, Field(max_length=500)] | None = None

    @field_validator("schritt", "zeile", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class Abschluss(BaseModel):
    """Wie ein Auftrag endet. `gescheitert` braucht eine Meldung."""

    zustand: Literal["fertig", "gescheitert", "abgebrochen"]
    meldung: Annotated[str, Field(max_length=1000)] = ""

    @field_validator("meldung", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


# ── Übertragung nach DFBnet ───────────────────────────────────────────────

#: Was in DFBnet einzutragen wäre. `prueferfreigabe` gibt einen geprüften
#: Bericht frei, `fallanlage` legt einen Sportgerichtsfall an.
#:
#: **Kein Mailversand.** Die alte Software kannte dafür einen fünften
#: Auftragstyp; hier gibt es ihn nicht. Schreiben werden vorbereitet und von
#: einem Menschen abgeschickt — siehe `Vorgang`.
UebertragungAktion = Literal["prueferfreigabe", "fallanlage"]

UebertragungZustand = Literal["offen", "laeuft", "fertig", "fehler"]


class UebertragungEinreihen(BaseModel):
    """Idempotent über `(aktion, referenz)`.

    Abhaken, Haken entfernen und wieder abhaken darf keine zwei Freigaben
    erzeugen. Eine gescheiterte Zeile wird dabei zurückgesetzt — das zweite
    Abhaken ist der Staffelleiter, der es noch einmal versucht.
    """

    aktion: UebertragungAktion
    referenz: NameFeld
    spiel_id: uuid.UUID | None = None

    @field_validator("referenz", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class UebertragungAusgabe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    aktion: UebertragungAktion
    referenz: str
    spiel_id: uuid.UUID | None
    zustand: UebertragungZustand
    versuche: int
    letzter_fehler: str
    erledigt_am: dt.datetime | None
    angelegt: dt.datetime


class UebertragungStand(BaseModel):
    """Was die Warteschlange tut — für den Streifen über der Liste."""

    pausiert: bool
    offen: int
    laeuft: int
    fertig: int
    fehler: int
    #: Nur die gescheiterten, ausgeschrieben. Sie sind das Einzige, wozu
    #: jemand etwas tun muss.
    fehlerhafte: list[UebertragungAusgabe]


class UebertragungAbschluss(BaseModel):
    zustand: Literal["fertig", "fehler"]
    meldung: Annotated[str, Field(max_length=1000)] = ""

    @field_validator("meldung", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class Pause(BaseModel):
    pausiert: bool


# ── DFBnet-Zugang ─────────────────────────────────────────────────────────


class ZugangSetzen(BaseModel):
    """Was der Staffelleiter einträgt. Das Passwort kommt nie zurück."""

    benutzer: NameFeld
    passwort: Annotated[str, Field(min_length=1, max_length=200)]

    @field_validator("benutzer", mode="before")
    @classmethod
    def _trimmen(cls, wert: object) -> object:
        return _getrimmt(wert)


class ZugangStand(BaseModel):
    """Ob etwas hinterlegt ist, und für wen — mehr verrät diese Antwort nicht."""

    gespeichert: bool
    benutzer: str
    #: Ob ein Schlüssel in der Umgebung steht. Ohne ihn lässt sich nichts
    #: ablegen, und das soll die Oberfläche sagen können, bevor jemand tippt.
    schluessel_vorhanden: bool


class ZugangGeheim(BaseModel):
    """Die Antwort für den Prüfdienst — und nur für ihn.

    Der einzige Ort, an dem das Passwort wieder herauskommt. Der Endpunkt
    dazu verlangt die Rolle `verwalter`.
    """

    benutzer: str
    passwort: str


# ── Ergebnisse: die Auswertung ────────────────────────────────────────────


class Posten(BaseModel):
    """Eine Zeile der Auswertung."""

    name: str
    anzahl: int
    offen: int


class Auswertung(BaseModel):
    """Was in dieser Saison aufgelaufen ist, gruppiert.

    Die drei Schweren stehen immer alle da, auch mit null: „keine
    kritischen" ist eine Aussage, eine fehlende Zeile nicht.
    """

    befunde: int
    offen: int
    spiele: int
    abgehakt: int
    vorgaenge: int
    nach_schwere: list[Posten]
    nach_regel: list[Posten]
    nach_mannschaft: list[Posten]
    nach_monat: list[Posten]
