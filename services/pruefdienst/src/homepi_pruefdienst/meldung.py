"""Die Meldung einer Staffel — welche Mannschaften gemeldet sind.

Übernommen aus `D:/DevLibrary/StaffelPilot/src/automation/meisterschaft_parser.py`.
Hier steht nur das **Lesen der Tabelle**; wie man in DFBnet dorthin kommt,
steht in `dfbnet.py`. Diese Trennung ist keine Formsache: die Tabelle ist die
Stelle, die kaputtgeht, wenn DFBnet eine Spalte verschiebt, und hier ist sie
in Millisekunden prüfbar.

**Die Mannschaftsnummer wird nicht aus der Ms-Nr. genommen.** Die Ms-Nr. ist
die laufende Nummer der Meldung, nicht die zweite Mannschaft eines Vereins.
„SV Loschwitz 2" ist die Zweite, auch wenn sie in der Meldung an Stelle 7
steht — das Artefakt liest die Nummer aus dem Namen und tut das richtig
(`verein_und_nummer`).

> **Nicht gegen eine Aufnahme geprüft.** Von der Mannschaftsseite liegt hier
> kein aufgezeichnetes HTML vor, anders als beim Spielbericht. Die Tests
> beschreiben den Aufbau, wie die alte Anwendung ihn über eine Saison
> vorgefunden hat — sie beweisen nicht, dass DFBnet ihn heute noch liefert.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup


def ist_sg(ms_text: str) -> bool:
    """Ob in der Ms-Nr.-Spalte das Kürzel SG steht.

    Eine Spielgemeinschaft wird im Artefakt anders behandelt: bei ihr ist die
    geratene Zuordnung höherer Mannschaften unsicher, und das soll man sehen.
    """
    return "SG" in (ms_text or "").upper()


def verein_aus_zelle(zelle: Any) -> str:
    """Der Vereinsname aus der Verein-Spalte.

    DFBnet schreibt den vollen Namen in das `title`-Attribut und daneben die
    Vereinsnummer in ein eigenes `span`. Ohne `title` bleibt der sichtbare
    Text, und aus dem müssen die Ziffern heraus — sonst hieße der Verein
    „SV Loschwitz 02043701".
    """
    span = zelle.find("span", attrs={"title": True})
    if span:
        name = (span.get("title") or "").strip()
        if name:
            return name
    return re.sub(r"\d+", "", zelle.get_text(strip=True)).strip()


def mannschaften_lesen(html: str) -> list[dict[str, object]]:
    """Die Tabelle „Mannschaften" in die Sprache des Artefakts.

    Spalten, wie die alte Anwendung sie vorfand: (Aktion), Mannschaft, Ms-Nr.,
    Verein, und dahinter Sachen, die uns nichts angehen.

    `nummer` und `hoehere` bleiben leer: beide gehören dem Artefakt. Es rät
    die höheren Mannschaften aus den Namen und merkt sich, ob jemand das
    bestätigt hat — ein Prüflauf, der das überschreibt, nähme dem
    Staffelleiter seine Arbeit wieder weg.
    """
    suppe = BeautifulSoup(html or "", "lxml")
    tabelle = suppe.find("table")
    if tabelle is None:
        return []

    gefunden: list[dict[str, object]] = []
    for zeile in tabelle.find_all("tr"):
        zellen = zeile.find_all("td")
        if len(zellen) < 4:
            # Die Kopfzeile hat `th`, und eine Zeile mit drei Zellen ist
            # keine Mannschaft, sondern eine Zwischenüberschrift.
            continue
        name = zellen[1].get_text(strip=True)
        if not name:
            continue
        gefunden.append(
            {
                "name": name,
                "verein": verein_aus_zelle(zellen[3]),
                "ist_sg": ist_sg(zellen[2].get_text(strip=True)),
            }
        )
    return gefunden


#: Wie DFBnet die Mannschaftsart nennt, und was das Artefakt daraus macht.
#:
#: Die laengere Form zuerst: "Herren Ü35" faengt mit "Herren" an, und wer in
#: der falschen Reihenfolge prueft, macht aus jeder Ue35-Staffel eine
#: Herrenstaffel -- und liest dann deren Spiele.
_ALTERSKLASSEN: tuple[tuple[str, str], ...] = (
    ("herren ü35", "ue35"),
    ("herren u35", "ue35"),
    ("ü35", "ue35"),
    ("alte herren", "ue35"),
    ("herren", "maenner"),
    ("frauen", "frauen"),
    ("a-junioren", "a_junioren"),
    ("b-junioren", "b_junioren"),
    ("c-junioren", "c_junioren"),
)


def altersklasse_aus(mannschaftsart: str) -> str:
    """Die Altersklasse des Artefakts aus DFBnets Mannschaftsart.

    Leer, wenn keine passt. Leer heisst *nicht bekannt* und nicht "Herren":
    eine geratene Altersklasse liest beim naechsten Prueflauf die Spiele einer
    anderen Mannschaft, und das faellt erst an einem Befund auf, der zu
    niemandem gehoert.
    """
    text = (mannschaftsart or "").strip().lower()
    for muster, klasse in _ALTERSKLASSEN:
        if muster in text:
            return klasse
    return ""


def staffeln_lesen(
    ueberschriften: list[str], zeilen: list[list[str]], saison: str = ""
) -> list[dict[str, object]]:
    """Die Liste "Eigene Staffeln" in die Sprache des Artefakts.

    Spalten, am 21.10.2026 in der Spielplanbearbeitung abgelesen:
    (Aktion), Kennung, Mannschaftsart, Spielklasse, Gebiet, Bezeichnung,
    Rd, Nr, St.

    Nach den Ueberschriften und nicht nach festen Nummern -- aus demselben
    Grund wie in `spalte_mit`.

    **Die Legende wird nicht uebergeben.** Unter den Datenzeilen stehen im
    selben `tbody` drei Zeilen, die die Symbole erklaeren ("Staffel ansehen",
    "Rd Rundennummer", "Status"). Sie haben keinen Bearbeiten-Knopf; der
    Aufrufer reicht nur Zeilen herein, die einen haben. Hier faellt zusaetzlich
    alles weg, dem Kennung oder Spielklasse fehlt: eine Legendenzeile, die
    sich doch einmal durchmogelt, waere sonst eine Staffel ohne Spiele.
    """
    spalten = {
        name: spalte_mit(ueberschriften, name)
        for name in ("Kennung", "Mannschaftsart", "Spielklasse", "Gebiet", "Bezeichnung")
    }

    def zelle(zeile: list[str], name: str) -> str:
        nummer = spalten[name]
        return (zeile[nummer] if 0 <= nummer < len(zeile) else "").strip()

    gefunden: list[dict[str, object]] = []
    for zeile in zeilen:
        kennung = zelle(zeile, "Kennung")
        spielklasse = zelle(zeile, "Spielklasse")
        if not kennung or not spielklasse:
            continue
        # Eine Kennung ist eine Zahl. "Staffel ansehen" ist keine.
        if not kennung.isdigit():
            continue
        bezeichnung = zelle(zeile, "Bezeichnung")
        gefunden.append(
            {
                "kennung": kennung,
                "name": bezeichnung or spielklasse,
                "spielklasse": spielklasse,
                "mannschaftsart": zelle(zeile, "Mannschaftsart"),
                "altersklasse": altersklasse_aus(zelle(zeile, "Mannschaftsart")),
                "gebiet": zelle(zeile, "Gebiet"),
                "saison": saison,
                "spieltage": spieltage_aus(ueberschriften, zeile),
            }
        )
    return gefunden


def spalte_mit(ueberschriften: list[str], gesucht: str) -> int:
    """Die Nummer der Spalte mit dieser Ueberschrift, oder -1.

    Nach der Ueberschrift und nicht nach einer festen Nummer: die alte
    Anwendung zaehlte Spalten ab, und als DFBnet die Liste umbaute, stand in
    der siebten Spalte die Rundennummer. Aus "Rd 1" wurde "1 Spieltag", und
    die Staffel galt als einen Spieltag lang.
    """
    ziel = gesucht.strip().lower()
    for nummer, text in enumerate(ueberschriften):
        if (text or "").strip().lower() == ziel:
            return nummer
    return -1


def spieltage_aus(ueberschriften: list[str], zellen: list[str]) -> int:
    """Wie viele Spieltage die Saison hat. 0 heisst *nicht bekannt*.

    Ohne diese Zahl laesst sich die U23-Ausnahme nach Paragraf 68 (2) c) an
    den letzten vier Spieltagen nicht aufheben, und die Regel sagt das bei
    jedem Spiel. Sie mitzunehmen kostet nichts -- die Zeile steht ohnehin auf
    dem Schirm.

    **Geraten wird nichts.** Nennt die Liste keine Spalte "Spieltage", kommt
    0 zurueck, und die Zahl bleibt, wie sie im Artefakt steht. Am 19.09.2026
    nennt DFBnet dort: Kennung, Mannschaftsart, Spielklasse, Gebiet,
    Bezeichnung, Rd, Nr, St -- also keine.
    """
    spalte = spalte_mit(ueberschriften, "Spieltage")
    if spalte < 0 or spalte >= len(zellen):
        return 0
    treffer = re.search(r"\d+", zellen[spalte] or "")
    if not treffer:
        return 0
    zahl = int(treffer.group(0))
    # Das Artefakt nimmt 0 bis 99. Alles darueber ist keine Saisonlaenge.
    return zahl if 0 <= zahl <= 99 else 0
