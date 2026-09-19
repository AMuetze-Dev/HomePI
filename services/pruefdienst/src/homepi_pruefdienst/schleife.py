"""Der Ablauf: warten, einen Auftrag nehmen, ihn abarbeiten, melden.

Der Dienst hält nichts fest. Sein Gedächtnis ist der Auftrag im Artefakt —
stirbt der Container mitten im Lauf, steht dort, wie weit er kam, und der
nächste Start findet ihn wieder. Genau dafür ist ein Auftrag ein Datensatz
und kein Thread.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from . import dienst, regeln
from .gateway import Gateway, GatewayFehler
from .leser import BeispielLeser, Leser

logger = logging.getLogger(__name__)


class Prueflauf:
    """Ein Durchgang durch die Aufträge und die Übertragungen."""

    def __init__(self, gateway: Gateway, leser: Leser, darf_schreiben: bool = False) -> None:
        self._gateway = gateway
        self._leser = leser
        self._darf_schreiben = darf_schreiben

    # ── Eine Runde ────────────────────────────────────────────────────────

    def runde(self) -> bool:
        """Einmal nachsehen. Gibt zurück, ob es etwas zu tun gab.

        Der Rückgabewert steuert nur, wie lange bis zum nächsten Mal gewartet
        wird — er ist kein Erfolg: ein gescheiterter Auftrag war auch Arbeit.
        """
        gearbeitet = False

        auftrag = self._gateway.offener_auftrag()
        if auftrag is not None:
            self._auftrag(auftrag)
            gearbeitet = True

        if self._uebertragungen():
            gearbeitet = True

        return gearbeitet

    # ── Ein Auftrag ───────────────────────────────────────────────────────

    def _auftrag(self, auftrag: dict[str, Any]) -> None:
        kennung = str(auftrag["id"])
        art = str(auftrag["art"])
        logger.info("Auftrag %s (%s) übernommen", kennung, art)

        try:
            if art == "initialisierung":
                self._initialisieren(kennung, auftrag.get("staffel_id"))
            else:
                self._pruefen(kennung, auftrag.get("staffel_id"))
        except Exception as fehler:
            # Jeder Fehler landet am Auftrag und nicht nur im Protokoll des
            # Containers: der Staffelleiter sieht sonst eine Anzeige, die
            # stehenbleibt, und weiß nicht, warum.
            logger.exception("Auftrag %s gescheitert", kennung)
            self._melden_dass_gescheitert(kennung, fehler)
        finally:
            self._leser.schliessen()

    def _melden_dass_gescheitert(self, kennung: str, fehler: Exception) -> None:
        try:
            self._gateway.abschluss(kennung, "gescheitert", str(fehler)[:900])
        except GatewayFehler:
            # Wenn nicht einmal das Melden geht, ist das Artefakt weg. Dann
            # bleibt der Auftrag offen stehen, und der nächste Start sieht ihn.
            logger.exception("Der Abschluss von %s liess sich nicht melden", kennung)

    def _staffeln(self, staffel_id: object) -> list[dict[str, Any]]:
        """Die eine Staffel, oder alle aktiven."""
        alle = self._gateway.staffeln()
        if staffel_id:
            return [s for s in alle if str(s["id"]) == str(staffel_id)]
        return [s for s in alle if s.get("aktiv")]

    def _befunde_zu(self, zeile: dienst.Spielzeile) -> list[dict[str, object]]:
        """Den Bericht holen und die Regeln darüber laufen lassen.

        Kommt keiner, gibt es **eine Warnung und keine leere Liste**: ein
        Spiel ohne Befunde sieht in der Warteschlange aus wie eines, das
        geprüft und sauber war.
        """
        if isinstance(self._leser, BeispielLeser):
            return self._leser.befunde_zu(zeile)
        bericht = self._leser.bericht(zeile.dfbnet_id)
        if bericht is None:
            return regeln.nicht_gelesen("der Prüfdienst hat ihn nicht bekommen")
        return regeln.befunde_aus(bericht)

    def _anmelden(self, kennung: str) -> None:
        self._gateway.fortschritt(
            kennung, schritt="Melde mich bei DFBnet an", zeile="Hole die Zugangsdaten"
        )
        benutzer, passwort = self._gateway.zugang()
        self._leser.anmelden(benutzer, passwort)
        self._gateway.fortschritt(kennung, zeile=f"Angemeldet als {benutzer}")

    def _pruefen(self, kennung: str, staffel_id: object) -> None:
        staffeln = self._staffeln(staffel_id)
        if not staffeln:
            self._ohne_staffel(kennung, "prüfen")
            return

        self._anmelden(kennung)

        werte = self._gateway.einstellungen()
        von, bis = dienst.zeitraum(dt.date.today(), int(werte["pruefzeitraum_tage"]))
        self._gateway.fortschritt(
            kennung,
            zeile=f"Zeitraum {dienst.als_dfbnet_datum(von)} bis {dienst.als_dfbnet_datum(bis)}",
        )

        gepruefte = befunde = 0
        for i, staffel in enumerate(staffeln):
            name = str(staffel["name"])
            self._gateway.fortschritt(
                kennung,
                schritt=f"Lese {name}",
                fortschritt=dienst.fortschritt(i, len(staffeln)),
            )

            ausbeute = dienst.Ausbeute()
            for zeile in self._leser.spiele(name, von, bis):
                ausbeute.aufnehmen(zeile, self._befunde_zu(zeile))

            if ausbeute.uebersprungen:
                self._gateway.fortschritt(
                    kennung,
                    zeile=f"{name}: {ausbeute.uebersprungen} Zeile(n) ohne Datum übersprungen",
                )

            if ausbeute.spiele:
                ergebnis = self._gateway.einspielen(str(staffel["id"]), ausbeute.spiele)
                gepruefte += len(ausbeute.spiele)
                befunde += ausbeute.befunde
                self._gateway.fortschritt(
                    kennung,
                    gepruefte=gepruefte,
                    befunde=befunde,
                    zeile=(
                        f"{name}: {ergebnis['angelegt']} neu, "
                        f"{ergebnis['aktualisiert']} aufgefrischt, "
                        f"{ausbeute.befunde} Befunde"
                    ),
                )
            else:
                self._gateway.fortschritt(kennung, zeile=f"{name}: nichts im Zeitraum")

        self._gateway.abschluss(kennung, "fertig")

    def _ohne_staffel(self, kennung: str, tun: str) -> None:
        """Kein Fehler, aber auch keine stille Null.

        Ein Lauf, der "fertig, 0 geprüft" meldet, sieht aus wie einer, der
        nichts gefunden hat. Wer keine Staffel angelegt hat, soll lesen, dass
        genau das der Grund ist -- und zwar in der Liste und nicht nur im
        Protokoll.
        """
        meldung = (
            f"Keine aktive Staffel — es gibt nichts zu {tun}. Erst unter 'Staffeln' eine anlegen."
        )
        self._gateway.fortschritt(kennung, zeile=meldung)
        self._gateway.abschluss(kennung, "fertig", meldung)

    def _initialisieren(self, kennung: str, staffel_id: object) -> None:
        staffeln = self._staffeln(staffel_id)
        if not staffeln:
            self._ohne_staffel(kennung, "holen")
            return

        self._anmelden(kennung)

        gesamt = 0
        for i, staffel in enumerate(staffeln):
            name = str(staffel["name"])
            self._gateway.fortschritt(
                kennung,
                schritt=f"Hole die Meldung zu {name}",
                fortschritt=dienst.fortschritt(i, len(staffeln)),
            )
            mannschaften = self._leser.mannschaften(name)
            if mannschaften:
                self._gateway.mannschaften_setzen(str(staffel["id"]), mannschaften)
                gesamt += len(mannschaften)
                self._gateway.fortschritt(
                    kennung, zeile=f"{name}: {len(mannschaften)} Mannschaften übernommen"
                )
            else:
                # Eine leere Meldung ueberschreibt nichts - und darf deshalb
                # auch nicht wie ein Erfolg aussehen.
                self._gateway.fortschritt(
                    kennung, zeile=f"{name}: nichts gemeldet, nichts geändert"
                )

        meldung = (
            f"{gesamt} Mannschaften übernommen"
            if gesamt
            else "Es kam keine Meldung — nichts geändert"
        )
        self._gateway.abschluss(kennung, "fertig", meldung)

    # ── Die Übertragung ───────────────────────────────────────────────────

    def _uebertragungen(self) -> bool:
        """Was nach DFBnet hinaus soll — wenn es denn darf.

        **Zwei Schalter, und beide müssen an sein.** Der eine steht im
        Artefakt, der andere in der Umgebung dieses Dienstes. Eine
        Prüferfreigabe ist eine Handlung, die ein Verein sieht; sie soll nicht
        passieren, weil ein Container gestartet wurde.
        """
        stand = self._gateway.uebertragung()
        erlaubnis = dienst.Erlaubnis(
            pausiert=bool(stand["pausiert"]), darf_schreiben=self._darf_schreiben
        )
        offen = int(stand["offen"])

        if not offen:
            return False

        if not erlaubnis.uebertraegt:
            logger.info(
                "%d Übertragung(en) warten, es geht nichts hinaus: %s",
                offen,
                erlaubnis.grund,
            )
            return False

        if not isinstance(self._leser, BeispielLeser):
            # Das Eintragen in DFBnet ist nicht portiert. Eine Zeile auf
            # "fertig" zu setzen, ohne dass etwas passiert ist, waere die
            # schlimmste aller Auskuenfte.
            logger.warning(
                "%d Übertragung(en) warten. Das Eintragen in DFBnet ist noch "
                "nicht portiert; sie bleiben stehen.",
                offen,
            )
            return False

        # Mit dem Beispiel-Leser wird es **simuliert** -- und das steht an
        # jeder Zeile. Nur so laesst sich der Weg bis zum Freigeben einmal
        # durchklicken, ohne einen Verband anzufassen.
        gemacht = 0
        while (zeile := self._gateway.uebertragung_uebernehmen()) is not None:
            self._gateway.uebertragung_abschliessen(
                str(zeile["id"]),
                "fertig",
                "Simuliert — es war kein Browser bei DFBnet",
            )
            gemacht += 1
        logger.info("%d Übertragung(en) simuliert abgeschlossen", gemacht)
        return gemacht > 0
