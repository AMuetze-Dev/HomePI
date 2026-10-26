#!/usr/bin/env python3
"""Nachsehen, was StaffelPilot vorbereitet hat -- ohne irgendetwas zu tun.

Zwei Fragen beantwortet dieses Werkzeug, und beide **lesend**:

* ``mails``   -- was stünde in den Mails, die vorbereitet sind?
* ``faelle``  -- was ginge an DFBnet, wenn ein Fall angelegt würde?

**Es versendet nichts und legt nichts an.** Es ruft ausschließlich `GET`-Routen
auf; die einzige Ausnahme ist die Anmeldung, die eine Sitzung braucht. Wer die
Fallanlage wirklich ausprobieren will, nimmt ``probe`` -- das fordert einen
Auftrag an, der bis vor das Speichern geht.

Aufruf::

    python tools/nachsehen.py mails
    python tools/nachsehen.py faelle
    python tools/nachsehen.py probe <vorgang-id>

Die Zugangsdaten stehen in der Umgebung::

    HOMEPI_URL=http://127.0.0.1:18000   (Vorgabe)
    HOMEPI_BENUTZER=tester
    HOMEPI_PASSWORT=...

Warum ein eigenes Werkzeug und kein Test: ein Test prüft, ob etwas stimmt.
Hier geht es darum, **nachzulesen**, was wirklich dasteht -- vor einem
Schreiben, das an einen Verein oder ein Sportgericht geht, ist das keine
Bequemlichkeit.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

BASIS = os.environ.get("HOMEPI_URL", "http://127.0.0.1:18000").rstrip("/")
BENUTZER = os.environ.get("HOMEPI_BENUTZER", "")
PASSWORT = os.environ.get("HOMEPI_PASSWORT", "")

STRICH = "─" * 72

# Die Ausgabe ist deutsch und enthaelt Umlaute. Die Windows-Konsole steht per
# Vorgabe auf cp1252 und bricht sonst mitten im ersten Schreiben ab -- und das
# bei einem Werkzeug, das Schreiben an einen Verein anzeigen soll.
for _strom in (sys.stdout, sys.stderr):
    if hasattr(_strom, "reconfigure"):
        _strom.reconfigure(encoding="utf-8")


class Sitzung:
    """Eine angemeldete Sitzung. Mehr kann sie nicht."""

    def __init__(self) -> None:
        self._kekse = ""

    def anmelden(self) -> None:
        if not BENUTZER or not PASSWORT:
            raise SystemExit(
                "HOMEPI_BENUTZER und HOMEPI_PASSWORT fehlen.\n"
                "In der Entwicklungsumgebung:\n"
                "  HOMEPI_BENUTZER=tester HOMEPI_PASSWORT=... python tools/nachsehen.py mails"
            )
        _, self._kekse = self._ruf(
            "/auth/anmelden", {"name": BENUTZER, "passwort": PASSWORT}, "POST"
        )
        if not self._kekse:
            raise SystemExit("Die Anmeldung hat keine Sitzung ergeben.")

    def hole(self, pfad: str) -> Any:
        antwort, _ = self._ruf(pfad)
        return antwort

    def fordere(self, pfad: str) -> Any:
        """Die einzige Stelle, die etwas anlegt -- und nur einen Auftrag."""
        antwort, _ = self._ruf(pfad, {}, "POST")
        return antwort

    def _ruf(
        self, pfad: str, nutzlast: dict | None = None, methode: str = "GET"
    ) -> tuple[Any, str]:
        daten = json.dumps(nutzlast).encode("utf-8") if nutzlast is not None else None
        anfrage = urllib.request.Request(
            BASIS + pfad,
            data=daten,
            headers={
                **({"Content-Type": "application/json"} if daten is not None else {}),
                **({"Cookie": self._kekse} if self._kekse else {}),
            },
            method=methode,
        )
        try:
            with urllib.request.urlopen(anfrage, timeout=60) as antwort:
                text = antwort.read().decode("utf-8")
                setzer = antwort.headers.get_all("Set-Cookie") or []
        except urllib.error.HTTPError as fehler:
            raise SystemExit(
                f"{methode} {pfad} -> {fehler.code}\n{fehler.read().decode('utf-8', 'replace')}"
            ) from fehler
        except urllib.error.URLError as fehler:
            raise SystemExit(f"Unter {BASIS} läuft nichts ({fehler.reason}).") from fehler
        neue = "; ".join(s.split(";", 1)[0] for s in setzer)
        return (json.loads(text) if text else None), (neue or self._kekse)


def mails(sitzung: Sitzung) -> int:
    """Jeden Vorgang mit seinem Mailentwurf, Wort für Wort."""
    vorgaenge = sitzung.hole("/staffelpilot/vorgaenge") or []
    if not vorgaenge:
        print("Es ist kein Vorgang vorbereitet.")
        return 0

    for zeile in vorgaenge:
        voll = sitzung.hole(f"/staffelpilot/vorgaenge/{zeile['id']}")
        entwurf = sitzung.hole(f"/staffelpilot/vorgaenge/{zeile['id']}/mail")
        print(STRICH)
        print(f"{voll['art']:12s} {voll['aktenzeichen']:16s} {voll['zustand']}")
        if voll.get("dfbnet_aktenzeichen"):
            print(f"DFBnet-Akte: {voll['dfbnet_aktenzeichen']}")
        print(f"An:      {entwurf['empfaenger'] or '(kein Empfänger eingetragen)'}")
        print(f"Betreff: {entwurf['betreff']}")
        if entwurf["anhang"]:
            print(f"Anhang:  {entwurf['anhang']}")
        if entwurf["fehlende_felder"]:
            print(f"ES FEHLT: {', '.join(entwurf['fehlende_felder'])}")
        print()
        print(entwurf["text"])
    print(STRICH)
    print(f"{len(vorgaenge)} Vorgang/Vorgänge. Versendet wurde nichts.")
    return 0


def faelle(sitzung: Sitzung) -> int:
    """Was bei einer Fallanlage im DFBnet-Formular stünde."""
    vorgaenge = [
        v for v in (sitzung.hole("/staffelpilot/vorgaenge") or []) if v["art"] == "sportgericht"
    ]
    if not vorgaenge:
        print("Es ist kein Sportgerichtsfall vorbereitet.")
        return 0

    staffeln = {s["id"]: s for s in (sitzung.hole("/staffelpilot/staffeln") or [])}
    for zeile in vorgaenge:
        voll = sitzung.hole(f"/staffelpilot/vorgaenge/{zeile['id']}")
        spiel = sitzung.hole(f"/staffelpilot/spiele/{voll['spiel_id']}")
        staffel = staffeln.get(str(spiel["staffel_id"]), {})
        fehlt = [
            name
            for name, wert in (
                ("Spielkennung", spiel.get("spielnummer", "")),
                ("Saison", staffel.get("saison", "")),
                ("Gericht", staffel.get("sportgericht", "")),
                ("Tatbestand", voll.get("grund", "")),
            )
            if not str(wert).strip()
        ]
        print(STRICH)
        print(f"Vorgang {voll['aktenzeichen']} ({zeile['id']})")
        print(f"  Spielkennung: {spiel.get('spielnummer') or '(fehlt)'}")
        print(f"  Saison:       {staffel.get('saison') or '(fehlt)'}")
        print(f"  Gericht:      {staffel.get('sportgericht') or '(fehlt)'}")
        print(f"  Tatbestand:   {voll.get('grund') or '(fehlt)'}")
        print(f"  DFBnet-Akte:  {voll.get('dfbnet_aktenzeichen') or '(noch keine)'}")
        if fehlt:
            print(f"  ES FEHLT:     {', '.join(fehlt)} — so würde nichts angelegt.")
        else:
            print("  Vollständig. Zum Prüfen ohne Anlegen:")
            print(f"    python tools/nachsehen.py probe {zeile['id']}")
    print(STRICH)
    print("Angelegt wurde nichts.")
    return 0


def probe(sitzung: Sitzung, vorgang_id: str) -> int:
    """Die Fallanlage proben: derselbe Weg, und dann nicht speichern."""
    auftrag = sitzung.fordere(f"/staffelpilot/vorgaenge/{vorgang_id}/fallprobe")
    kennung = auftrag["id"]
    print(f"Probe angefordert: {kennung}")
    print("Der Prüfdienst geht bis vor das Speichern. Angelegt wird nichts.\n")

    for _ in range(120):
        time.sleep(3)
        stand = sitzung.hole(f"/staffelpilot/auftraege/{kennung}")
        letzte = (stand.get("protokoll") or [{}])[-1].get("text", "")
        print(f"  {stand['zustand']:12s} {stand.get('schritt', ''):28s} {letzte}")
        if stand["zustand"] not in ("angefordert", "laeuft"):
            print(f"\n{stand['zustand'].upper()}: {stand.get('meldung')}")
            return 0 if stand["zustand"] == "fertig" else 1
    print("\nDer Dienst hat sich den Auftrag nicht geholt. Läuft er?")
    return 1


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("mails", "faelle", "probe"):
        print(__doc__)
        return 2

    sitzung = Sitzung()
    sitzung.anmelden()

    if argv[1] == "mails":
        return mails(sitzung)
    if argv[1] == "faelle":
        return faelle(sitzung)
    if len(argv) < 3:
        print("Es fehlt die Kennung des Vorgangs.")
        return 2
    return probe(sitzung, argv[2])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
