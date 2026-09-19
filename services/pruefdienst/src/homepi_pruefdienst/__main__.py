"""Der Einstieg: Umgebung lesen, Schleife drehen, sauber aufhören."""

from __future__ import annotations

import logging
import os
import signal
import sys
import time

import httpx

from .dienst import wartezeit
from .gateway import Gateway, GatewayFehler
from .leser import BeispielLeser, Leser
from .schleife import Prueflauf

logger = logging.getLogger("homepi.pruefdienst")


def _ja(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "ja", "yes", "on"}


class Stopp:
    """SIGTERM heißt: die laufende Runde zu Ende, dann Schluss.

    Mitten im Lauf abzubrechen hieße, einen Auftrag auf „läuft" stehen zu
    lassen. Docker gibt zehn Sekunden; eine Runde ist kürzer.
    """

    def __init__(self) -> None:
        self.gewuenscht = False
        for zeichen in (signal.SIGTERM, signal.SIGINT):
            signal.signal(zeichen, self._merken)

    def _merken(self, *_: object) -> None:
        logger.info("Abbruch gewünscht — die laufende Runde wird noch beendet")
        self.gewuenscht = True


def _leser() -> Leser:
    """Welcher Leser gilt. Der Demo-Leser ist die Voreinstellung.

    Wer nichts sagt, bekommt den, der nirgends anklopft. Ein Dienst, der beim
    ersten Start ungefragt einen Browser nach DFBnet schickt, ist eine
    Überraschung zu viel.
    """
    if os.environ.get("PRUEFDIENST_LESER", "demo").strip().lower() == "dfbnet":
        from .dfbnet import DfbnetLeser

        logger.info("Leser: DFBnet (echter Browser)")
        return DfbnetLeser(sichtbar=_ja("PRUEFDIENST_BROWSER_SICHTBAR"))

    logger.info("Leser: Beispieldaten — es wird nichts von DFBnet geholt")
    return BeispielLeser()


def _warten(stopp: Stopp, sekunden: float) -> None:
    """Warten, aber auf ein SIGTERM hören."""
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende and not stopp.gewuenscht:
        time.sleep(min(0.5, ende - time.monotonic()))


def _anmelden_bis_es_klappt(gateway: Gateway, stopp: Stopp, benutzer: str, basis: str) -> bool:
    """Warten statt abstürzen.

    Das Gateway ist beim Start vielleicht noch nicht da, und das Konto wird
    manchmal erst danach angelegt. Ein Container, der deswegen in einer
    Neustartschleife hängt, füllt das Protokoll mit Abstürzen und verdeckt
    damit den einen Satz, auf den es ankommt: **warum** die Anmeldung nicht
    geht. Der steht hier, einmal, und dann wird gewartet.
    """
    versuche = 0
    while not stopp.gewuenscht:
        try:
            gateway.anmelden()
            logger.info("Am Gateway angemeldet als %s (%s)", benutzer, basis)
            return True
        except (GatewayFehler, httpx.HTTPError) as fehler:
            if versuche == 0:
                logger.error("Anmeldung geht nicht: %s", fehler)
                logger.error(
                    "Konto anlegen:  homepi benutzer anlegen %s "
                    "--artefakt staffelpilot --rolle verwalter --passwort-stdin",
                    benutzer,
                )
            versuche += 1
            _warten(stopp, wartezeit(versuche))
    return False


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    basis = os.environ.get("HOMEPI_URL", "http://gateway:8000")
    benutzer = os.environ.get("PRUEFDIENST_BENUTZER", "")
    passwort = os.environ.get("PRUEFDIENST_PASSWORT", "")
    if not benutzer or not passwort:
        logger.error(
            "PRUEFDIENST_BENUTZER und PRUEFDIENST_PASSWORT fehlen. Ohne Konto "
            "kommt der Dienst an kein Artefakt — StaffelPilot ist geschützt."
        )
        return 2

    darf_schreiben = _ja("PRUEFDIENST_DARF_SCHREIBEN")
    if not darf_schreiben:
        logger.info(
            "PRUEFDIENST_DARF_SCHREIBEN steht nicht auf 1: es wird nichts in DFBnet eingetragen."
        )

    stopp = Stopp()
    leerlauf = 0

    with Gateway(basis, benutzer, passwort) as gateway:
        if not _anmelden_bis_es_klappt(gateway, stopp, benutzer, basis):
            return 0
        lauf = Prueflauf(gateway, _leser(), darf_schreiben=darf_schreiben)

        while not stopp.gewuenscht:
            try:
                leerlauf = 0 if lauf.runde() else leerlauf + 1
            except GatewayFehler:
                # Das Artefakt ist gerade nicht da - neu starten hilft nicht,
                # warten schon.
                logger.exception("Das Artefakt antwortet nicht")
                leerlauf += 1

            _warten(stopp, wartezeit(leerlauf))

    logger.info("Beendet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
