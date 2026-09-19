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
