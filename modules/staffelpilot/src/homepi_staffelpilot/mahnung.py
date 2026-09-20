"""Das Mahnungsformular des Verbandes ausfüllen.

Übernommen aus `D:/DevLibrary/StaffelPilot/src/core/mahnung.py`.

Der Vordruck ist ein echtes AcroForm mit siebzehn benannten Feldern. Nichts
wird an geratenen Koordinaten gezeichnet — die Werte gehen in die Felder, die
der Verband definiert hat. Eine geänderte Fassung fällt deshalb **laut** auf
(unbekanntes Feld), statt Text in den falschen Kasten zu setzen.

**Hier wird nichts versendet.** Das gefüllte PDF geht an den Staffelleiter,
der es prüft und verschickt. Das ist die stehende Regel für alles, was dieses
Programm nach außen gibt.

Was fehlt, wird **benannt und nicht erfunden**: ein Schriftstück, das an einen
Verein geht, trägt keine Platzhalter.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader, PdfWriter

#: Der leere Vordruck, im Paket.
VORDRUCK = Path(__file__).resolve().parent / "vordrucke" / "Mahnungsformular_Bagatellsachen.pdf"

#: Ankreuzfeld -> der Tatbestand, für den es steht. Die Namen stammen aus dem
#: PDF selbst, die Wortlaute vom Formular.
BAGATELLE = {
    "Ordnungsdienst": "fehlende oder unzulässige Eintragung Leiter Ordnungsdienst",
    "Ordnerbuch": "fehlendes Ordnerbuch, sofern tatsächlich Ordner anwesend sind",
    "Unterschrift": "fehlende oder zu späte Bestätigung des elektr. Spielberichtsbogens",
    "Spielerfotos": "fehlende oder veraltete Spielerfotos gemäß §10a SpO SFV",
    "Check Box1": "fehlende Freigabe des Sammelspielberichts (E-, F- und G-Junioren)",
}

#: Welche Regel auf welches Kreuz führt.
#:
#: Die Liste des Verbandes ist **geschlossen**: eine Regel ohne Zuordnung
#: bekommt kein Kreuz. Ein geratenes Kreuz stünde auf einem Schriftstück, das
#: hinausgeht — und behauptete einen Tatbestand, den niemand geprüft hat.
#:
#: Die Kennungen sind die der Regeln, wie sie am Befund stehen.
REGEL_ZU_BAGATELLE = {
    # Ordnungsdienst -- § 59 (4) SpO SFV
    "order_manager_missing": "Ordnungsdienst",
    "order_manager_dual_role": "Ordnungsdienst",
    "order_manager_is_player": "Ordnungsdienst",
    "ordnungsdienst_fehlt": "Ordnungsdienst",
    # Bestaetigung des Spielberichts -- § 59 (17) SpO SFV
    "confirmation_missing": "Unterschrift",
    "confirmation_late": "Unterschrift",
    # Spielerfotos -- § 67 (2) und (3) SpO SFV
    "spielerfoto_fehlt": "Spielerfotos",
    "spielerfoto_zu_alt": "Spielerfotos",
    "spielerfoto_aus_juniorenzeit": "Spielerfotos",
}

#: Der Wert, den ein gesetztes Kreuz in diesem Formular trägt.
AN = "/Ja"
AUS = "/Off"


@dataclass
class Mahnung:
    """Alles, was auf dem Formular steht — schon in der Sprache des Verbands."""

    mannschaftsart: str = ""
    spielklasse: str = ""
    spieltag: str = ""
    staffelleiter: str = ""
    spielnummer: str = ""
    datum: str = ""
    uhrzeit: str = ""
    wettkampftyp: str = ""
    heim: str = ""
    gast: str = ""
    spielort: str = ""
    verein: str = ""
    #: Die Namen der Ankreuzfelder, die gesetzt werden.
    kreuze: set[str] = field(default_factory=set)

    def felder(self) -> dict[str, str]:
        return {
            "Mannschaftsart": self.mannschaftsart,
            "Spielklasse": self.spielklasse,
            "Spieltag": self.spieltag,
            "Staffelleiter": self.staffelleiter,
            "Spielnummer": self.spielnummer,
            "Datum": self.datum,
            "Uhrzeit": self.uhrzeit,
            "Wettkampftyp": self.wettkampftyp,
            "Mannschaft Heim": self.heim,
            "Mannschaft Auswärts": self.gast,
            "Spielort": self.spielort,
            "betreffender Verein": self.verein,
        }

    def fehlende_felder(self) -> list[str]:
        """Was der Staffelleiter noch von Hand eintragen muss.

        Gemeldet statt mit einem Platzhalter gefüllt: ein Formular, das an
        einen Verein geht, darf keine erfundenen Angaben tragen.
        """
        return [name for name, wert in self.felder().items() if not str(wert).strip()]


def kreuze_fuer(regeln: list[str]) -> set[str]:
    """Die Kästchen zu einer Menge von Regeln. Unbekannte werden übergangen."""
    return {REGEL_ZU_BAGATELLE[r] for r in regeln if r in REGEL_ZU_BAGATELLE}


def als_pdf(mahnung: Mahnung, vordruck: Path | None = None) -> bytes:
    """Das gefüllte Formular als PDF.

    Wirft, wenn der Vordruck fehlt oder ein Feld verloren hat — statt ein PDF
    zu liefern, in dem Werte stillschweigend unter den Tisch gefallen sind.
    """
    quelle = vordruck or VORDRUCK
    if not quelle.is_file():
        raise FileNotFoundError(
            f"Vordruck nicht gefunden: {quelle}. Die leere Vorlage gehört ins Paket."
        )

    leser = PdfReader(str(quelle))
    vorhanden = set(leser.get_fields() or {})
    werte = mahnung.felder()

    unbekannt = sorted((set(werte) | set(BAGATELLE)) - vorhanden)
    if unbekannt:
        raise ValueError(
            "Das Formular hat diese Felder nicht (mehr): "
            + ", ".join(unbekannt)
            + ". Vermutlich eine neue Fassung des Verbands."
        )

    schreiber = PdfWriter(clone_from=leser)
    schreiber.set_need_appearances_writer(True)
    for seite in schreiber.pages:
        schreiber.update_page_form_field_values(seite, werte)
        schreiber.update_page_form_field_values(
            seite,
            {name: (AN if name in mahnung.kreuze else AUS) for name in BAGATELLE},
        )

    puffer = io.BytesIO()
    schreiber.write(puffer)
    return puffer.getvalue()
