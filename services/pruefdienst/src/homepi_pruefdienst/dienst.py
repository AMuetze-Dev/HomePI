"""Die Entscheidungen des Prüfdienstes.

REIN: kein Browser, kein HTTP, kein Warten. Genau deshalb lässt sich hier in
Millisekunden prüfen, was sonst nur ein echter DFBnet-Lauf zeigen würde — und
genau hier steckt das, was erfahrungsgemäß kaputtgeht: das Zerlegen einer
Tabellenzeile.

Alles, was I/O macht, steht in gateway.py und dfbnet.py.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

#: Ein Datum, wie DFBnet es in die Tabelle schreibt.
_DATUM = re.compile(r"(\d{2})\.(\d{2})\.(\d{2,4})")

#: Ein Ergebnis: "2 : 1", auch ohne Leerzeichen.
_ERGEBNIS = re.compile(r"^\s*(\d+)\s*:\s*(\d+)\s*$")

#: Was in einer Zeile steht, aber keine Mannschaft ist. Der zweite Strich ist
#: ein Halbgeviertstrich -- DFBnet benutzt beide, und `ruff` haelt den zweiten
#: fuer einen verunglueckten ersten.
_KEINE_MANNSCHAFT = {"-", "–", ":", ""}  # noqa: RUF001


@dataclass(frozen=True, slots=True)
class Spielzeile:
    """Ein Spiel, wie es aus der Trefferliste kommt."""

    dfbnet_id: str
    datum: dt.date | None
    heim: str
    gast: str
    ergebnis: str
    status: str = ""

    @property
    def gespielt(self) -> bool:
        """Ob das Spiel schon stattgefunden hat.

        Am Ergebnis und nicht am Datum: ein Spiel von heute Vormittag hat
        abends einen fertigen Bericht, eines von heute Abend noch keinen. Das
        Datum kann beides nicht unterscheiden, die Ergebnisspalte schon --
        sie bleibt leer, bis der Schiedsrichter freigibt.
        """
        return any(z.isdigit() for z in self.ergebnis)

    @property
    def brauchbar(self) -> bool:
        """Ohne Datum und ohne Paarung ist die Zeile kein Spiel.

        Lieber überspringen als einen Bericht mit leeren Feldern anlegen: der
        stünde in der Warteschlange und niemand wüsste, wozu er gehört.
        """
        return self.datum is not None and bool(self.heim) and bool(self.gast)


def datum_lesen(text: str) -> dt.date | None:
    """'13.09.2026' oder '13.09.26' — oder None.

    Zweistellige Jahre werden ins 21. Jahrhundert gelegt: DFBnet führt keine
    Spiele aus den Neunzigern, und ein Bericht von 1926 wäre ein Datumsfehler,
    den niemand bemerkt.
    """
    treffer = _DATUM.search(text or "")
    if treffer is None:
        return None
    tag, monat, jahr = (int(teil) for teil in treffer.groups())
    if jahr < 100:
        jahr += 2000
    try:
        return dt.date(jahr, monat, tag)
    except ValueError:
        # 31.02. gibt es, im Kopf einer Tabelle und nirgends sonst.
        return None


def zeile_zerlegen(zellen: list[str], kennung: str) -> Spielzeile:
    """Aus den Zellen einer Trefferzeile ein Spiel machen.

    Die Spalten von DFBnet haben sich schon einmal verschoben, deshalb wird
    nicht auf Positionen gezählt, sondern gesucht: das Datum am Muster, das
    Ergebnis am Muster, und die Mannschaften **um das Ergebnis herum**. Heim
    steht links davon, Gast rechts.

    Fehlt das Ergebnis — ein Spiel ohne eingetragenes Resultat —, bleiben die
    beiden längsten Textzellen als Paarung übrig. Das ist geraten und deshalb
    an `brauchbar` erkennbar, wenn es misslingt.
    """
    sauber = [(z or "").strip() for z in zellen]

    datum = None
    for zelle in sauber:
        datum = datum_lesen(zelle)
        if datum is not None:
            break

    ergebnis = ""
    stelle = -1
    for i, zelle in enumerate(sauber):
        if _ERGEBNIS.match(zelle):
            ergebnis = zelle.replace(" ", "").replace(":", " : ")
            stelle = i
            break

    heim, gast = _paarung(sauber, stelle)

    return Spielzeile(
        dfbnet_id=kennung,
        datum=datum,
        heim=heim,
        gast=gast,
        ergebnis=ergebnis,
        status=sauber[-1] if sauber else "",
    )


def _ist_mannschaft(text: str) -> bool:
    if text in _KEINE_MANNSCHAFT or len(text) <= 2 or text.isdigit():
        return False
    # "13.09.2026 15:00" ist laenger als zwei Zeichen und trotzdem keine
    # Mannschaft.
    return datum_lesen(text) is None


def _paarung(zellen: list[str], stelle: int) -> tuple[str, str]:
    """Heim und Gast — in beiden Anordnungen, die DFBnet schon hatte.

    Heute stehen **beide** Mannschaften links vom Ergebnis
    (``… Heim - Gast 2:1 …``), frueher stand es dazwischen
    (``… Heim 2:1 Gast …``). Wo die Zellen liegen, entscheidet also der
    Fall — und nicht eine Spaltennummer, die beim naechsten Umbau wieder
    falsch ist.
    """
    davor = [z for z in zellen[:stelle] if _ist_mannschaft(z)] if stelle >= 0 else []
    danach = [z for z in zellen[stelle + 1 :] if _ist_mannschaft(z)] if stelle >= 0 else []

    # Erst der haeufige Fall, und zwar an der Anzahl **vor** dem Ergebnis
    # erkannt: was danach steht, ist meist der Status ("freigegeben"), und der
    # sieht von aussen aus wie ein Vereinsname.
    if len(davor) >= 2:
        # Beide davor: die dem Ergebnis naechste ist der Gast.
        return davor[-2], davor[-1]

    if davor and danach:
        # Das Ergebnis steht zwischen den Mannschaften.
        return davor[-1], danach[0]

    # Kein Ergebnis in der Zeile - dann bleibt die Reihenfolge im Text.
    namen = davor if stelle >= 0 else [z for z in zellen if _ist_mannschaft(z)]
    return tuple([*namen, "", ""][:2])  # type: ignore[return-value]


class StaffelNichtGefunden(RuntimeError):
    """DFBnet hat diese Staffel nicht angeboten.

    Ein eigener Fehler, weil er anders behandelt gehoert als ein Absturz: der
    Lauf geht mit der naechsten Staffel weiter, aber diese hier gilt **nicht**
    als geprueft. Sie stillschweigend zu ueberspringen sah aus wie "keine
    Spiele im Zeitraum".
    """


@dataclass(frozen=True, slots=True)
class Staffelkennung:
    """Was DFBnet braucht, um genau diese Staffel zu zeigen.

    Vier Felder statt eines Namens, und jedes hat einen Grund:

    * `spielklasse` ist der Text, unter dem DFBnet sie fuehrt
      ("3.Kreisliga (C)"). Der Name des Staffelleiters ("Stadtliga C") steht
      dort nicht.
    * `altersklasse` entscheidet die Mannschaftsart -- Herren und Ue35 teilen
      sich dieselben Spielklassennamen, und ohne sie liest ein Ue35-Lauf die
      Herrenspiele.
    * `saison` steht in DFBnet auf der laufenden; wer die vorige prueft, muss
      sie umstellen.
    """

    name: str
    spielklasse: str = ""
    altersklasse: str = ""
    saison: str = ""

    @property
    def kandidaten(self) -> list[str]:
        """Was in den Feldern Spielklasse und Staffel zu versuchen ist.

        Die Spielklasse zuerst: sie ist die Schreibweise von DFBnet. Der Name
        ist der Rueckfall fuer Staffeln, die dort genauso heissen.
        """
        gesehen: list[str] = []
        for text in (self.spielklasse, self.name):
            text = (text or "").strip()
            if text and text not in gesehen:
                gesehen.append(text)
        return gesehen


def kennung_aus(staffel: dict[str, object]) -> Staffelkennung:
    """Die Staffel des Artefakts als das, was der Leser braucht."""
    return Staffelkennung(
        name=str(staffel.get("name") or ""),
        spielklasse=str(staffel.get("spielklasse") or ""),
        altersklasse=str(staffel.get("altersklasse") or ""),
        saison=str(staffel.get("saison") or ""),
    )


def kennung_aus_href(href: str) -> str:
    """Die DFBnet-Kennung steckt im Link auf den Bericht.

    Sie ist der Schlüssel, unter dem das Artefakt den Bericht wiederfindet —
    ein zweiter Prüflauf desselben Spiels darf ihn nicht verdoppeln.

    **Zwei Schreibweisen, und beide zählen.** In der Trefferliste steht
    `/match-report/report/<kennung>`; öffnet man den Bericht, wird daraus
    `/match-report/report-details/<andere kennung>`. Die zweite ist die, nach
    der die Aufstellungsschnittstelle fragt — ohne sie antwortet DFBnet mit
    404, und der Kader bleibt leer.
    """
    treffer = re.search(r"/match-report/report(?:-details)?/([^/?#]+)", href or "")
    return treffer.group(1) if treffer else (href or "")


#: Die Adresse einer Spielberichtsseite. Uebernommen aus
#: `src/automation/freigabe.py` der alten Anwendung.
BERICHT_ADRESSE = (
    "https://www.dfbnet.org/sbo-mobile/v2/#/match-report/report/{kennung}?dmg_company=DFBNET"
)


def bericht_adresse(kennung: str) -> str:
    """Wo der Bericht zu dieser Kennung steht.

    Hier und nicht im Browser-Leser, damit sich nachlesen laesst, wohin der
    Dienst geht -- ohne Playwright zu starten.
    """
    return BERICHT_ADRESSE.format(kennung=kennung)


# ── Der Zeitraum ──────────────────────────────────────────────────────────


def zeitraum(heute: dt.date, tage: int) -> tuple[dt.date, dt.date]:
    """Von wann bis wann gesucht wird.

    Bis **heute** und nicht weiter: ein Spiel in der Zukunft ist nicht
    gespielt, und ein Befund darauf wäre eine Erfindung. Dieselbe Regel steht
    im Artefakt als `ist_faellig`; hier spart sie den Abruf.
    """
    return heute - dt.timedelta(days=max(1, tage)), heute


def als_dfbnet_datum(tag: dt.date) -> str:
    return tag.strftime("%d.%m.%Y")


# ── Fortschritt ───────────────────────────────────────────────────────────


def fortschritt(erledigt: int, gesamt: int) -> int:
    """In Prozent, zwischen 0 und 99.

    Nie 100: die Hundert setzt der Abschluss. Ein Balken, der voll ist und
    trotzdem weiterläuft, ist die Anzeige, der man beim nächsten Mal nicht
    mehr glaubt.
    """
    if gesamt <= 0:
        return 0
    return max(0, min(99, round(erledigt / gesamt * 100)))


def fortschritt_im_schritt(schritt: int, schritte: int, erledigt: int, gesamt: int) -> int:
    """Wie weit ein Lauf ist, wenn ein Schritt selbst lange dauert.

    Eine Staffel mit achtzig Spielberichten braucht eine Viertelstunde. Ein
    Balken, der dabei auf demselben Wert steht, sieht aus wie ein Dienst, der
    haengt -- und das ist die Anzeige, nach der jemand den Lauf abbricht,
    kurz bevor er fertig ist.
    """
    if schritte <= 0:
        return 0
    anteil = (erledigt / gesamt) if gesamt > 0 else 0.0
    return fortschritt(round((schritt + anteil) * 100), schritte * 100)


# ── Warten ────────────────────────────────────────────────────────────────

#: Ohne Arbeit wird der Abstand groesser, aber nie groesser als das.
LEERLAUF_GRENZE_S = 30.0


def wartezeit(leerlaufrunden: int, grundtakt: float = 2.0) -> float:
    """Je länger nichts kommt, desto seltener wird gefragt.

    Ein Dienst, der im Sekundentakt fragt, hält den Pi wach und die Datenbank
    beschäftigt — für nichts. Nach einer Handvoll leerer Runden reicht alle
    halbe Minute.
    """
    if leerlaufrunden <= 0:
        return grundtakt
    return float(min(LEERLAUF_GRENZE_S, grundtakt * (2 ** min(leerlaufrunden, 5))))


# ── Was der Dienst tun darf ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Erlaubnis:
    """Zwei Schalter, und beide müssen an sein.

    Der eine steht im Artefakt (die Pause), der andere in der Umgebung dieses
    Dienstes. Eine Prüferfreigabe ist eine Handlung in DFBnet, die ein Verein
    sieht; sie soll nicht passieren, weil ein Container gestartet wurde.
    """

    pausiert: bool
    darf_schreiben: bool

    @property
    def uebertraegt(self) -> bool:
        return self.darf_schreiben and not self.pausiert

    @property
    def grund(self) -> str:
        if not self.darf_schreiben:
            return "PRUEFDIENST_DARF_SCHREIBEN steht nicht auf 1"
        if self.pausiert:
            return "die Übertragung ist im Artefakt angehalten"
        return ""


# ── Das Ergebnis eines Laufs ──────────────────────────────────────────────


@dataclass(slots=True)
class Ausbeute:
    """Was ein Lauf eingesammelt hat."""

    spiele: list[dict[str, object]] = field(default_factory=list)
    uebersprungen: int = 0
    befunde: int = 0

    def aufnehmen(
        self,
        zeile: Spielzeile,
        befunde: list[dict[str, object]] | None = None,
        karten: list[dict[str, object]] | None = None,
        wettbewerb: str = "",
        kopfdaten: dict[str, str] | None = None,
    ) -> None:
        if not zeile.brauchbar:
            self.uebersprungen += 1
            return
        assert zeile.datum is not None
        self.spiele.append(
            {
                "dfbnet_id": zeile.dfbnet_id,
                "datum": zeile.datum.isoformat(),
                "heim": zeile.heim,
                "gast": zeile.gast,
                "ergebnis": zeile.ergebnis,
                # Karten sind keine Befunde, sondern das Gedaechtnis fuer
                # Paragraf 58 -- die fuenfte Verwarnung sperrt.
                "karten": karten or [],
                "wettbewerb": wettbewerb,
                # Was das Mahnungsformular verlangt. Leer heisst: nicht
                # bekannt -- das Artefakt ueberschreibt dann nichts.
                **(kopfdaten or {}),
                # Leer, solange die Regelprüfung nicht portiert ist. Das ist
                # die ehrliche Aussage: der Bericht ist da, geprüft ist er
                # nicht. Der Beispiel-Leser füllt es, damit sich die
                # Oberfläche durchklicken lässt.
                "befunde": befunde or [],
            }
        )
        self.befunde += len(befunde or [])
