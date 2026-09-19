"""Der Spielbericht, so wie eine Regel ihn sieht.

Warum es diese Schicht gibt
---------------------------
Der Extractor liefert `MatchReport` — englische Feldnamen, Rohtexte, Daten als
Zeichenketten, Geburtsdaten unaufgelöst. Damit lässt sich eine Regel schreiben,
aber nur von jemandem, der den Extractor kennt.

Hier steht dasselbe Spiel noch einmal, in der Sprache der Spielordnung:
deutsche Bezeichner, Daten als `date`, Alter ausgerechnet, Karten bei der
Person. Eine Regel soll aussehen wie der Satz, den sie prüft — nicht wie eine
Auswertung.

Alles ist **schreibgeschützt**. Eine Regel liest und meldet; sie ändert nichts
am Spielbericht. Ein Regelwerk, das den Bericht verändern kann, ist eines, bei
dem die Reihenfolge der Regeln plötzlich zählt.

Teure Werte (Alter, Einsätze in höheren Mannschaften) werden erst beim ersten
Zugriff berechnet und dann behalten — eine Regel, die `spieler.alter` in einer
Schleife liest, soll das Geburtsdatum nicht fünfzigmal zerlegen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import cached_property

#: Stichtag der U23-Ausnahme nach § 68 (2) c) SpO: „am 1. Juli das 23.
#: Lebensjahr noch nicht vollendet". Nicht der Spieltag — wer im Oktober 23
#: wird, ist die ganze Saison über U23.
STICHTAG_MONAT, STICHTAG_TAG = 7, 1

#: § 68 (2) b): „in mindestens 50 % der bisherigen Pflichtspiele".
STAMMSPIELER_QUOTE = 0.5

#: § 68 (2) b): „nach dem fünften Pflichtspiel der höherklassigen Mannschaft".
#: Vorher gibt es keine Stammspieler in diesem Sinne.
STAMMSPIELER_AB_SPIEL = 5

#: § 67 (3) b): „Im Erwachsenenbereich: alle 10 Jahre."
FOTO_HOECHSTALTER = 10

#: DFBnet schreibt "Sa., 13.06.26", die Datenbank "2026-06-13". Beides muss
#: gelesen werden — ein Datum, das nicht verstanden wird, ist ein Alter, das
#: nicht bekannt ist, und damit eine Regel, die schweigt.
_DATUMSFORMATE = ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y")


def datum_lesen(wert: str | date | None) -> date | None:
    """Ein Datum aus dem, was DFBnet liefert. `None`, wenn es keins ist."""
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    text = (wert or "").strip()
    if not text:
        return None
    # Wochentag abschneiden: "Sa., 13.06.26" ist das übliche Format im
    # Spielbericht, und ohne diese Zeile versteht der Leser kein einziges
    # echtes Spieldatum.
    if "," in text:
        text = text.split(",", 1)[1].strip()
    # Uhrzeit hinter dem Datum abschneiden: "2026-06-13 15:00".
    text = text.split(" ")[0].split("T")[0]
    for form in _DATUMSFORMATE:
        try:
            return datetime.strptime(text, form).date()
        except ValueError:
            continue
    return None


#: Erkennt die Altersklasse in einer Spielklassenbezeichnung.
#:
#: DFBnet schreibt sie mit: „2. Stadtklasse Ü35", „1. Stadtklasse Ü35", und in
#: den Kurzformen der Freundschaftsspiele „FS/HÜ35/K-FS/DD/1" gegenüber
#: „FS/H/K-FS/DD/1" für die Herren. Ohne Marke gilt die Spielklasse als
#: Herren- bzw. Frauenklasse.
_UE_MUSTER = re.compile(r"[ÜU]\s?(\d{2})\b")


def altersklasse_der_spielklasse(spielklasse: str) -> str:
    """ "ue35" aus „2. Stadtklasse Ü35"; "" für Herren und Frauen.

    Nur das große Ü zählt, nicht das U: „U23" wäre eine Junioren-, keine
    Seniorenklasse, und „U 19" darf hier nicht als Ü19 durchgehen.
    """
    text = spielklasse or ""
    treffer = re.search(r"Ü\s?(\d{2})\b", text)
    return f"ue{treffer.group(1)}" if treffer else ""


def _norm_name(name: str) -> str:
    """Zum Vergleich zweier Mannschaftsnamen aus verschiedenen Tabellen."""
    return " ".join((name or "").split()).casefold()


#: § 58 (2) trennt „Pokal- und sonstige Pflichtspiele", § 58 (2) c) nennt das
#: Meisterschaftsturnier gesondert. DFBnet nennt den Wettbewerb im Klartext
#: („Kreispokal Herren"), nicht die Kategorie.
def wettbewerbskategorie(wettbewerb: str) -> str:
    text = (wettbewerb or "").lower()
    if "turnier" in text:
        return "Turnier"
    if "pokal" in text:
        return "Pokal"
    # Alles Übrige zählt als Meisterschaft — das ist der Regelfall, und ein
    # unbekannter Wettbewerbsname darf nicht dazu führen, dass gar nicht
    # gezählt wird.
    return "Meisterschaft"


def _jahre_zwischen(geboren: date, stichtag: date) -> int:
    jahre = stichtag.year - geboren.year
    if (stichtag.month, stichtag.day) < (geboren.month, geboren.day):
        jahre -= 1
    return jahre


@dataclass(frozen=True)
class Karte:
    """Eine Karte aus dem Spielverlauf."""

    art: str = ""  #: "Gelbe Karte", "Gelb-Rote Karte", "Rote Karte"
    minute: int | None = None
    person: str = ""
    mannschaft: str = ""
    grund: str = ""
    #: "spieler" oder "betreuer" — § 58 nennt beide gleichrangig.
    personenart: str = "spieler"

    @property
    def ist_gelb(self) -> bool:
        return "gelb" in self.art.lower() and "rot" not in self.art.lower()

    @property
    def ist_gelb_rot(self) -> bool:
        art = self.art.lower()
        return "gelb" in art and "rot" in art

    @property
    def ist_rot(self) -> bool:
        art = self.art.lower()
        return "rot" in art and "gelb" not in art


@dataclass(frozen=True)
class Einsatz:
    """Ein Einsatz derselben Person in dieser Saison, aus der Historie."""

    #: DFBnet-Kennung des Spiels. Nur damit laesst sich das Spiel, das gerade
    #: geprueft wird, aus der eigenen Historie heraushalten - es steht dort
    #: mit drin, und ohne die Kennung zaehlte es sich selbst mit.
    spielkennung: str = ""
    datum: date | None = None
    heim: str = ""
    gast: str = ""
    spielklasse: str = ""
    wettbewerb: str = ""
    minuten: int = 0
    spieltag: int | None = None

    @property
    def altersklasse(self) -> str:
        """„ue35" für eine Ü-Spielklasse, "" für Herren und Frauen.

        § 68 (2) a) und b) gelten je Altersklasse. Ohne diese Unterscheidung
        zählt ein Ü35-Spiel als Einsatz „oben" in einer Herrenstaffel — und
        die beiden Mannschaften stehen nicht über- und untereinander, sondern
        nebeneinander.
        """
        return altersklasse_der_spielklasse(self.spielklasse)

    def war_bei(self, mannschaft: str) -> bool:
        return mannschaft in (self.heim, self.gast)

    @property
    def gespielt(self) -> bool:
        """Auf dem Bogen zu stehen ist kein Einsatz. § 68 zählt Einsätze."""
        return self.minuten > 0


@dataclass(frozen=True)
class Tor:
    """Ein Treffer aus dem Spielverlauf."""

    minute: int | None = None
    mannschaft: str = ""
    schuetze: str = ""


@dataclass(frozen=True)
class Wechsel:
    """Eine Ein- und Auswechslung aus dem Spielverlauf.

    § 59 (7) begrenzt die Zahl der *Wechselspieler*, nicht die der Vorgänge:
    unterhalb der Kreisoberligen darf wieder eingewechselt werden, und wer
    zweimal kommt, ist eine Person.
    """

    minute: int | None = None
    mannschaft: str = ""
    kommt: str = ""
    geht: str = ""


@dataclass
class Person:
    """Ein Spieler oder ein Betreuer, mit dem, was die Regeln brauchen."""

    name: str = ""
    pass_nr: str = ""
    trikot: str = ""
    geburtsdatum: date | None = None
    #: "startelf", "bank", "nicht_im_kader" — oder bei Betreuern "betreuer".
    aufstellung: str = ""
    #: § 59 (18) nimmt Torhüter von der Nummernregel aus — sie dürfen mit zwei
    #: Rückennummern vermerkt sein.
    ist_torwart: bool = False
    rollen: tuple[str, ...] = ()
    kennzeichen: tuple[str, ...] = ()  #: DFBnet-Badges, kleingeschrieben
    karten: tuple[Karte, ...] = ()
    einsaetze: tuple[Einsatz, ...] = ()
    #: Spielerfoto, § 67 (2) und (3). "" heißt: nicht bekannt — siehe
    #: `hat_foto`. Roh, damit `hat_foto` die einzige Stelle bleibt, an der aus
    #: dem Zustand eine Aussage wird.
    _foto_zustand: str = field(default="", repr=False)
    #: Wann das Foto hinterlegt wurde. Der einzige Anhaltspunkt für sein Alter.
    foto_stand: date | None = None
    #: § 55 (1): „Der Spielführer ist auf dem Spielbericht zu benennen."
    ist_spielfuehrer: bool = False
    #: Was DFBnet über den Einsatz sagt: "starting_eleven", "bench",
    #: "substituted_in", "substituted_out" — oder "" bei älteren Berichten.
    _einsatzart: str = field(default="", repr=False)
    #: Altersklasse der Staffel, in der geprüft wird. § 68 (2) begrenzt seine
    #: Wartefrist und seine Stammspielergrenze auf „diese Altersklasse".
    _altersklasse: str = field(default="", repr=False)
    # ------------------------------------------------------------ Spielrecht
    # Was DFBnet in der Aufstellung über das Spielrecht führt. Überall gilt:
    # `None` heißt nicht bekannt, nicht „fehlt". Ältere gespeicherte Berichte
    # und die DOM-Rückfallebene kennen diese Felder nicht.
    #: Spielrecht für genau diese Mannschaft, § 56 (1).
    spielrecht_mannschaft: bool | None = None
    #: Spielrecht für diesen Verein, § 56 (3).
    spielrecht_verein: bool | None = None
    #: Ab wann Pflichtspiele erlaubt sind — nach einem Vereinswechsel liegt
    #: dieses Datum in der Zukunft, solange die Wartefrist läuft.
    pflichtspielrecht_ab: date | None = None
    #: Ab wann Meisterschaftsspiele erlaubt sind.
    meisterschaftsrecht_ab: date | None = None
    #: Gar kein Meisterschaftsspielrecht.
    ohne_meisterschaftsrecht: bool | None = None
    #: Gastspielgenehmigung, § 67 (1) — nur für Freundschaftsspiele.
    gastspielrecht: bool | None = None
    #: Zweitspielrecht, §§ 67a bis 67c.
    zweitspielrecht: bool | None = None
    #: DFBnets eigener Sperrvermerk zur Aufstellung, im Klartext. Leer heißt
    #: hier tatsächlich „kein Vermerk" — anders als bei den Feldern darüber
    #: liefert DFBnet ihn zu jeder Aufstellung mit.
    sperrvermerk: str = ""
    #: Wird vom Spiel gesetzt, damit `alter` ohne Argument funktioniert.
    _spieltag: date | None = field(default=None, repr=False)
    #: Zugang zu dem, was über dieses Spiel hinausgeht — Verwarnungszähler,
    #: Sperren. Nur lesend, siehe `auskunft.py`.
    _auskunft: object | None = field(default=None, repr=False)
    #: Wettbewerbskategorie dieses Spiels, weil § 58 (2) danach trennt.
    _wettbewerb: str = field(default="Meisterschaft", repr=False)

    # ------------------------------------------------------------------ Alter
    def alter_am(self, stichtag: date | None) -> int | None:
        """Vollendete Lebensjahre am Stichtag, oder `None` ohne Geburtsdatum."""
        if self.geburtsdatum is None or stichtag is None:
            return None
        return _jahre_zwischen(self.geburtsdatum, stichtag)

    @cached_property
    def alter(self) -> int | None:
        """Alter am Spieltag. Der übliche Fall."""
        return self.alter_am(self._spieltag)

    @cached_property
    def alter_am_1_juli(self) -> int | None:
        """Alter am Stichtag der U23-Ausnahme, § 68 (2) c).

        Der 1. Juli *dieser* Saison: liegt das Spiel im Frühjahr, ist es der
        1. Juli des Vorjahres. Am Spieltag zu messen wäre der häufigste Weg,
        die Regel um ein Jahr zu verfehlen.
        """
        if self._spieltag is None:
            return None
        jahr = self._spieltag.year
        if (self._spieltag.month, self._spieltag.day) < (STICHTAG_MONAT, STICHTAG_TAG):
            jahr -= 1
        return self.alter_am(date(jahr, STICHTAG_MONAT, STICHTAG_TAG))

    @property
    def geburtsdatum_plausibel(self) -> bool:
        """Ein Geburtsdatum in der Zukunft ist ein Tippfehler, kein Kind."""
        return self.alter is None or self.alter >= 0

    @property
    def wurde_eingesetzt(self) -> bool:
        """Ob diese Person am Spiel teilgenommen hat.

        § 68 (2) a) spricht vom „Einsatz", § 68 (2) b) davon, dass Stammspieler
        „eingesetzt werden". Wer auf der Bank sitzt und nicht kommt, ist nicht
        eingesetzt — die Regel greift erst mit der Einwechslung.

        Gemeldet am 06.09.2026 zu SG Weixdorf 3 – Dresdner SC 1898 3: ein
        Spieler auf der Bank wurde als Einsatz vor Ablauf der Wartefrist
        gemeldet, obwohl er nicht gespielt hat.

        Ohne Angabe wird von einem Einsatz ausgegangen. Ältere gespeicherte
        Berichte führen den Status nicht, und dort still aufzuhören zu prüfen
        wäre der schlechtere Fehler: ein Falschbefund fällt auf, ein fehlender
        nicht.
        """
        return self._einsatzart != "bench"

    def andere_einsaetze_am(
        self,
        tag: date | None,
        ohne_kennung: str = "",
        heim: str = "",
        gast: str = "",
    ) -> tuple[Einsatz, ...]:
        """Andere Spiele, in denen diese Person an diesem Tag gespielt hat.

        Für § 56 (6). „Gespielt" heißt: mit Spielminuten — auf dem Bogen zu
        stehen ist kein Einsatz.

        Das gerade geprüfte Spiel steht in der eigenen Historie mit drin und
        muss heraus. Über die Kennung allein geht das nicht: der Spielbericht
        führt die Spielnummer aus der Spielliste (`633203004`), die Historie
        die technische Kennung des Spiels (`031DHM04MS…`). Die beiden treffen
        sich nie — deshalb zusätzlich über Tag und Paarung, und deshalb hatte
        die erste Fassung jeden Spieler doppelt gezählt.
        """
        if tag is None:
            return ()

        def gleiche_paarung(e: Einsatz) -> bool:
            if not (heim or gast):
                return False
            return _norm_name(e.heim) == _norm_name(heim) and _norm_name(e.gast) == _norm_name(gast)

        return tuple(
            e
            for e in self.einsaetze
            if e.datum == tag
            and e.gespielt
            and not (ohne_kennung and e.spielkennung == ohne_kennung)
            and not gleiche_paarung(e)
        )

    # ------------------------------------------------------------ Spielerfoto
    @property
    def hat_foto(self) -> bool | None:
        """Ob ein Spielerfoto hinterlegt ist. `None` heißt: nicht bekannt.

        Nicht bekannt ist der Normalfall bei allem, was nicht aus der
        Aufstellungs-API stammt — ältere gespeicherte Berichte, die
        DOM-Rückfallebene, ein Konto ohne Berechtigung, alle Betreuer. Eine
        Regel, die `None` wie `False` behandelt, meldet Unwissen als Verstoß.
        """
        if self._foto_zustand == "vorhanden":
            return True
        if self._foto_zustand == "fehlt":
            return False
        return None

    @property
    def foto_alter(self) -> int | None:
        """Vollendete Jahre seit der Aufnahme des Fotos, am Spieltag."""
        if self.foto_stand is None or self._spieltag is None:
            return None
        return _jahre_zwischen(self.foto_stand, self._spieltag)

    # `erwachsen_seit` und `foto_aus_juniorenzeit` standen bis zum 09.09.2026
    # hier. Beide trugen eine Altersgrenze — also eine Regel, keine Angabe aus
    # dem Spielbericht. Sie stehen jetzt in `config/regeln/60_spielerfoto.py`,
    # wo sie geändert werden können, ohne das Programm anzufassen.

    # ------------------------------------------------------------- Kennzeichen
    def hat_kennzeichen(self, *teile: str) -> bool:
        """Ob eines der DFBnet-Badges einen dieser Textteile enthält."""
        return any(teil.lower() in k for teil in teile for k in self.kennzeichen)

    @property
    def ist_stammspieler(self) -> bool:
        """Nur das Kennzeichen aus DFBnet.

        Es ist **kein Verstoß**, sondern die Feststellung, dass für diese
        Person eine Obergrenze gilt — § 68 (2) b). Wer daraus einen Befund je
        Spieler macht, meldet jede Woche die halbe Mannschaft.
        """
        return self.hat_kennzeichen("stammspieler")

    @property
    def ist_u23_gekennzeichnet(self) -> bool:
        return self.hat_kennzeichen("u23", "u-23")

    # ----------------------------------------------------- Verwarnungen, Sperren
    def verwarnungen(self, wettbewerb: str = "") -> int | None:
        """Verwarnungen dieser Person in diesem Spieljahr.

        `None` heißt „nicht bekannt" — keine Datenbank, keine Passnummer.
        Ausdrücklich nicht 0: das wäre die Behauptung, es gebe keine, und eine
        Regel, die daraufhin schweigt, sähe aus, als hätte sie geprüft.

        Ohne Angabe gilt die Wettbewerbskategorie dieses Spiels. § 58 (2)
        trennt Pokal und übrige Pflichtspiele, also ist die Angabe Teil der
        Frage und nicht bloß ein Filter.
        """
        if self._auskunft is None or not self.pass_nr:
            return None
        return self._auskunft.verwarnungen(self.pass_nr, wettbewerb or self._wettbewerb)

    def letzte_sperre(self, wettbewerb: str = "") -> date | None:
        """Wann diese Person zuletzt eine Sperre verwirkt hat."""
        if self._auskunft is None or not self.pass_nr:
            return None
        return self._auskunft.letzte_sperre(self.pass_nr, wettbewerb or self._wettbewerb)

    def verwarnungen_seit_sperre(self, wettbewerb: str = "") -> int | None:
        """Verwarnungen seit der letzten verwirkten Sperre.

        § 58 (2) b): „Erhält eine Spielerin/ein Spieler … nach einer verwirkten
        Sperre 5 weitere Verwarnungen, so ist sie/er … gesperrt. Es ergibt sich
        ein Rhythmus von 5 – 10 – 15 usw."

        Der Zähler beginnt also nach jeder Sperre von vorn. Wer stattdessen bei
        10 und 15 prüft, meldet nach der zweiten Sperre zu früh und nach der
        dritten gar nicht mehr.
        """
        if self._auskunft is None or not self.pass_nr:
            return None
        kategorie = wettbewerb or self._wettbewerb
        seit = self._auskunft.letzte_sperre(self.pass_nr, kategorie)
        return self._auskunft.verwarnungen(self.pass_nr, kategorie, seit)

    # ---------------------------------------------------------------- Einsätze
    def einsaetze_bei(self, mannschaften) -> list[Einsatz]:
        """Gespielte Einsätze bei einer dieser Mannschaften, vor dem Spieltag.

        **Nur in der Altersklasse dieser Staffel.** § 68 (2) a) verlangt die
        Wartefrist für „Pflichtspiele unterklassiger Mannschaften *dieser
        Altersklasse* ihres Vereines", § 68 (2) b) begrenzt die Stammspieler
        „einer höherklassigen Mannschaft *dieser Altersklasse* des Vereins".

        Ein Ü35-Spiel löst also für die Herren keine Wartefrist aus: die
        beiden Mannschaften stehen nicht über- und untereinander, sondern
        nebeneinander. Gemeldet am 06.09.2026 zu SG Weixdorf 3 – Dresdner SC
        1898 3.
        """
        namen = {mannschaften} if isinstance(mannschaften, str) else set(mannschaften)
        return [
            e
            for e in self.einsaetze
            if e.gespielt
            and any(e.war_bei(n) for n in namen)
            and e.altersklasse == self._altersklasse
            and (self._spieltag is None or (e.datum and e.datum < self._spieltag))
        ]

    def letzter_einsatz_bei(self, mannschaften) -> date | None:
        daten = [e.datum for e in self.einsaetze_bei(mannschaften) if e.datum]
        return max(daten) if daten else None

    def spiele_der_hoeheren(self, mannschaften) -> int:
        """Wie viele Pflichtspiele jene Mannschaft **bisher** hatte.

        Steht nicht im Spielbericht, also geschätzt aus dem, was da ist: dem
        höchsten gesehenen Spieltag und der Zahl der eigenen Einsätze. Beides
        ist eine Untergrenze, und beide zusammen sind die beste verfügbare.

        Ausdrücklich **nicht** die Saisonlänge der Staffel. Das ist die Zahl
        aller Spieltage, nicht der bisherigen — sie einzusetzen macht aus fünf
        von fünf Spielen „5 von 26" und damit aus jedem Stammspieler einen
        Nicht-Stammspieler. Da `spieltage` erst seit „Initialisieren" gefüllt
        wird, hätte genau dieser Knopf die Obergrenze stillgelegt.
        """
        einsaetze = self.einsaetze_bei(mannschaften)
        if not einsaetze:
            return 0
        spieltage = [e.spieltag for e in einsaetze if e.spieltag]
        return max(len(einsaetze), max(spieltage) if spieltage else 0)

    def einsatzquote_bei(self, mannschaften) -> float:
        """Anteil der bisherigen Spiele jener Mannschaft mit eigenem Einsatz.

        § 68 (2) b): Stammspieler ist, wer „in mindestens 50 % der bisherigen
        Pflichtspiele des laufenden Spieljahres" der höherklassigen Mannschaft
        eingesetzt war.
        """
        gesamt = self.spiele_der_hoeheren(mannschaften)
        return len(self.einsaetze_bei(mannschaften)) / gesamt if gesamt else 0.0

    def ist_stammspieler_bei(self, mannschaften) -> bool:
        """§ 68 (2) b) gerechnet, statt am DFBnet-Kennzeichen abgelesen.

        Die Schwelle „nach dem fünften Pflichtspiel der höherklassigen
        Mannschaft" gehört zur Definition: vorher gibt es keine Stammspieler in
        diesem Sinne, und an Spieltag 2 eine Quote von 100 % zu melden hieße,
        eine Zahl auszuweisen, die noch nichts bedeuten kann.
        """
        return (
            self.spiele_der_hoeheren(mannschaften) >= STAMMSPIELER_AB_SPIEL
            and self.einsatzquote_bei(mannschaften) >= STAMMSPIELER_QUOTE
        )

    def tage_seit_einsatz_bei(self, mannschaften) -> int | None:
        """Tage zwischen jenem Einsatz und diesem Spiel.

        § 68 (2) a): „Der dem Spieltag folgende Tag ist der erste Tag der
        Wartefrist." Der Tag nach einem Einsatz am Samstag ist also Tag 1, und
        ein Spiel am folgenden Mittwoch liegt bei 4 Tagen.
        """
        letzter = self.letzter_einsatz_bei(mannschaften)
        if letzter is None or self._spieltag is None:
            return None
        return (self._spieltag - letzter).days


@dataclass
class Mannschaft:
    """Eine der beiden Mannschaften dieses Spiels."""

    name: str = ""
    ist_heim: bool = False
    startelf: tuple[Person, ...] = ()
    bank: tuple[Person, ...] = ()
    nicht_im_kader: tuple[Person, ...] = ()
    betreuer: tuple[Person, ...] = ()
    #: Mannschaften desselben Vereins, die höherklassig spielen. Kommt aus der
    #: Staffelverwaltung, nicht aus dem Spielbericht.
    hoehere: tuple[str, ...] = ()
    #: Ein- und Auswechslungen dieser Mannschaft, § 59 (7).
    wechsel: tuple[Wechsel, ...] = ()

    @property
    def wechselspieler(self) -> tuple[str, ...]:
        """Wer eingewechselt wurde, jede Person einmal.

        § 59 (7) begrenzt die Zahl der Wechselspieler. Wer nach einer
        Auswechslung wiederkommt — unterhalb der Kreisoberligen zulässig —
        ist derselbe Wechselspieler und darf nicht doppelt zählen.
        """
        gesehen: list[str] = []
        for w in self.wechsel:
            name = (w.kommt or "").strip()
            if name and name not in gesehen:
                gesehen.append(name)
        return tuple(gesehen)

    @property
    def spieler(self) -> tuple[Person, ...]:
        """Wer eingesetzt war: Startelf und Bank. Nicht der Rest des Kaders."""
        return self.startelf + self.bank

    @property
    def alle_personen(self) -> tuple[Person, ...]:
        """Spieler und Betreuer — § 58 nennt beide gleichrangig."""
        return self.spieler + self.betreuer

    def mit_rolle(self, *rollen: str) -> list[Person]:
        gesucht = {r.lower() for r in rollen}
        return [
            p
            for p in self.alle_personen
            if any(any(g in r.lower() for g in gesucht) for r in p.rollen)
        ]

    @property
    def karten(self) -> list[Karte]:
        return [k for p in self.alle_personen for k in p.karten]


@dataclass(frozen=True)
class Staffel:
    """Die Konfiguration der Staffel, in der geprüft wird."""

    name: str = ""
    altersklasse: str = ""  #: "maenner", "frauen", "ue32", "ue35", "ue40"
    saison: str = ""
    spieltage: int = 0
    hoehere_mannschaften: tuple[str, ...] = ()

    # Was hier NICHT mehr steht, seit dem 06.09.2026: die Altersuntergrenze
    # des Kreises, die Zahl der zugelassenen Spieler darunter und die
    # Obergrenze für Stammspieler. Das waren keine Angaben zur Staffel wie
    # die Sportrichter-Mail, sondern die Regeln selbst — sie stehen jetzt in
    # `config/regeln/10_altersklassen.py` und `20_stammspieler.py`, neben dem
    # Satz der Spielordnung, den sie umsetzen.

    @property
    def ist_ue(self) -> bool:
        return self.altersklasse.lower().startswith("ue")

    @property
    def mindestalter(self) -> int | None:
        """Aus „ue35" wird 35. `None` für Herren und Frauen."""
        if not self.ist_ue:
            return None
        try:
            return int(self.altersklasse[2:])
        except ValueError:
            return None


@dataclass
class Spiel:
    """Ein Spielbericht, wie eine Regel ihn liest."""

    heim: str = ""
    gast: str = ""
    datum: date | None = None
    anstoss: datetime | None = None
    spieltag: int | None = None
    spielklasse: str = ""
    wettbewerb: str = ""
    spielkennung: str = ""
    ergebnis: str = ""
    #: Was im Fragebogen „Besondere Vorkommnisse" angekreuzt wurde. Nur die
    #: angekreuzten Felder — die Beschriftungen des leeren Fragebogens nennen
    #: Gewalthandlung, Diskriminierung und Spielabbruch und machten früher aus
    #: jedem Spielbericht einen kritischen Befund.
    vorkommnisse: tuple[str, ...] = ()
    #: Freitext des Schiedsrichters zu den Vorkommnissen.
    vorkommnisse_text: str = ""
    heim_mannschaft: Mannschaft = field(default_factory=Mannschaft)
    gast_mannschaft: Mannschaft = field(default_factory=Mannschaft)
    staffel: Staffel = field(default_factory=Staffel)
    #: Die Treffer aus dem Spielverlauf.
    tore: tuple[Tor, ...] = ()
    #: **Alle** Karten des Spielverlaufs, auch die, zu denen sich in der
    #: Aufstellung niemand findet. `karten` entsteht aus den Personen und
    #: enthält gerade diese nicht — und eine Karte, die keiner Person gehört,
    #: zählt für niemanden.
    alle_karten: tuple[Karte, ...] = ()

    @property
    def mannschaften(self) -> tuple[Mannschaft, Mannschaft]:
        return (self.heim_mannschaft, self.gast_mannschaft)

    @property
    def karten(self) -> list[Karte]:
        return self.heim_mannschaft.karten + self.gast_mannschaft.karten

    @property
    def spieltage_bis_ende(self) -> int | None:
        """Wie viele Spieltage nach diesem noch kommen, dieser mitgezählt.

        § 68 (2) c) hebt die U23-Ausnahme „an den letzten vier Spieltagen der
        unterklassigen Mannschaft" auf — das ist `spieltage_bis_ende <= 4`.

        `None`, wenn Spieltag oder Saisonlänge fehlen. Eine Regel, die das für
        0 hält, hebt die Ausnahme in jedem Spiel auf.
        """
        if not self.spieltag or not self.staffel.spieltage:
            return None
        return self.staffel.spieltage - self.spieltag + 1

    @property
    def ergebnis_tore(self) -> tuple[int, int] | None:
        """Das Ergebnis in Zahlen, oder `None`, wenn es nicht lesbar ist.

        DFBnet schreibt „2 : 1"; bei einer Wertung ohne Spiel steht dort auch
        schon mal Text. Was nicht gelesen werden kann, wird nicht geraten.
        """
        teile = (self.ergebnis or "").replace("-", ":").split(":")
        if len(teile) != 2:
            return None
        try:
            return int(teile[0].strip()), int(teile[1].strip())
        except ValueError:
            return None

    @property
    def tore_je_mannschaft(self) -> tuple[int, int]:
        """Treffer aus dem Spielverlauf, heim und gast."""
        heim = sum(1 for t in self.tore if t.mannschaft == self.heim_mannschaft.name)
        gast = sum(1 for t in self.tore if t.mannschaft == self.gast_mannschaft.name)
        return heim, gast

    def andere_einsaetze(self, person) -> tuple[Einsatz, ...]:
        """Andere Spiele dieser Person am selben Kalendertag, § 56 (6).

        Dieses Spiel ist ausgenommen — über die Kennung und über die Paarung,
        weil Spielbericht und Einsatzhistorie zwei verschiedene Kennungen für
        dasselbe Spiel führen.
        """
        return person.andere_einsaetze_am(self.datum, self.spielkennung, self.heim, self.gast)

    @property
    def ist_freundschaftsspiel(self) -> bool:
        """Ob dies ein Freundschaftsspiel ist.

        Getrennt von `wettbewerbskategorie` gehalten: die kennt nur Pokal,
        Turnier und Meisterschaft, und alles Unbekannte fällt dort auf
        Meisterschaft zurück — richtig für den Verwarnungszähler, falsch für
        Vorschriften, die Pflichtspiele von Freundschaftsspielen trennen
        (§ 59 (7), § 67 (1)).
        """
        return "freundschaft" in (self.wettbewerb or "").lower()

    @property
    def wettbewerbskategorie(self) -> str:
        """„Meisterschaft", „Pokal" oder „Turnier" — wonach § 58 (2) trennt."""
        return wettbewerbskategorie(self.wettbewerb)

    def vorkommnis_genannt(self, *begriffe: str) -> list[str]:
        """Angekreuzte Vorkommnisse, die einen dieser Begriffe enthalten."""
        gesucht = [b.lower() for b in begriffe]
        return [v for v in self.vorkommnisse if any(b in v.lower() for b in gesucht)]

    @property
    def ist_pokalspiel(self) -> bool:
        """§ 58 (2) trennt Pokal- von übrigen Pflichtspielen."""
        return self.wettbewerbskategorie == "Pokal"
