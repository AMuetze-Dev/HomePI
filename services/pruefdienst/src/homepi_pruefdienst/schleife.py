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

from . import dienst, katalog, regeln
from .auskunft import GatewayAuskunft
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

    def _katalog_melden(self, kennung: str) -> set[str]:
        """Was geprüft wird, dem Artefakt sagen -- und holen, was aus ist.

        Einmal je Lauf und nicht beim Start des Dienstes: wer eine Regeldatei
        ändert, sieht die neue Regel im nächsten Lauf in der Übersicht, ohne
        etwas neu zu starten.

        Geht es schief, läuft der Prüflauf trotzdem. Die Übersicht ist dann
        veraltet; das ist ärgerlich, aber kein Grund, achtzig Spielberichte
        ungeprüft zu lassen.
        """
        try:
            gemeldet = regeln.katalog() + katalog.katalog()
            stand = self._gateway.regelkatalog_setzen(gemeldet)
        except Exception:
            logger.exception("Der Regelkatalog liess sich nicht melden")
            self._gateway.fortschritt(
                kennung, zeile="Der Regelkatalog liess sich nicht melden -- geprüft wird trotzdem"
            )
            return set()

        aus = {str(r["schluessel"]) for r in stand if not r.get("aktiv", True)}
        if aus:
            # Nicht verschweigen: eine abgeschaltete Regel ist nicht dasselbe
            # wie eine, die nichts gefunden hat.
            self._gateway.fortschritt(
                kennung, zeile=f"{len(aus)} von {len(stand)} Regeln sind abgeschaltet"
            )
        return aus

    def _pruefung_zu(
        self,
        zeile: dienst.Spielzeile,
        staffel: dict[str, Any],
        auskunft: GatewayAuskunft | None,
        abgeschaltet: set[str],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], str]:
        """Den Bericht holen, prüfen — und sagen, was er enthielt.

        Zurück kommen drei Dinge: die Befunde, die **Karten** und der
        Wettbewerb. Die Karten sind kein Befund; sie sind das Gedächtnis für
        § 58, und ohne sie meldet die Regel bei jeder gelben Karte, dass sie
        nicht zählen kann.

        Kommt kein Bericht, gibt es **eine Warnung und keine leere Liste**:
        ein Spiel ohne Befunde sieht in der Warteschlange aus wie eines, das
        geprüft und sauber war.
        """
        if isinstance(self._leser, BeispielLeser):
            return self._leser.befunde_zu(zeile), [], "Meisterschaft"

        bericht = self._leser.bericht(zeile.dfbnet_id)
        if bericht is None:
            if not zeile.gespielt:
                # Das Spiel läuft erst noch. Dass es dazu keinen Bericht gibt,
                # ist der Normalfall am Spieltag und keine Warnung -- sonst
                # stünden in der Warteschlange jede Woche so viele Warnungen,
                # wie am Wochenende Spiele angesetzt sind.
                logger.info("Spiel %s ist noch nicht gespielt", zeile.dfbnet_id)
                return [], [], ""
            return regeln.nicht_gelesen("der Prüfdienst hat ihn nicht bekommen"), [], ""

        befunde = regeln.befunde_aus(bericht, abgeschaltet) + katalog.befunde_aus(
            bericht,
            katalog.staffelangabe(staffel),
            auskunft=auskunft,
            abgeschaltet=abgeschaltet,
        )
        if not regeln.aufstellung_bekannt(bericht.home_squad):
            # Ohne Kader schweigen Spielrecht, Spielerfoto und Ordnungsdienst.
            # Ein Spiel, das nur deshalb sauber aussieht, ist die
            # gefährlichste Zeile in der Warteschlange.
            befunde += regeln.ohne_aufstellung()
        return befunde, regeln.karten_aus(bericht), bericht.meta.competition

    def _anmelden(self, kennung: str) -> None:
        self._gateway.fortschritt(
            kennung, schritt="Melde mich bei DFBnet an", zeile="Hole die Zugangsdaten"
        )
        # Vor dem Anmelden, denn dabei entsteht der Browser: der Schalter aus
        # den Einstellungen gilt ab dem naechsten Lauf und nicht erst nach
        # einem Neustart des Dienstes.
        self._leser.sichtbar = bool(self._gateway.einstellungen().get("browser_sichtbar"))
        if self._leser.sichtbar:
            self._gateway.fortschritt(kennung, zeile="Der Browser ist sichtbar")

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

        # Der Verwarnungszaehler nach Paragraf 58. Einer je Lauf, damit die
        # Karten einer Person einmal geholt werden und nicht je Spiel neu.
        auskunft = GatewayAuskunft(self._gateway, regeln.saisonbeginn(bis.strftime("%d.%m.%Y")))
        abgeschaltet = self._katalog_melden(kennung)

        gepruefte = befunde = 0
        nicht_geprueft: list[str] = []
        for i, staffel in enumerate(staffeln):
            name = str(staffel["name"])
            self._gateway.fortschritt(
                kennung,
                schritt=f"Lese {name}",
                fortschritt=dienst.fortschritt(i, len(staffeln)),
            )

            try:
                zeilen = self._leser.spiele(dienst.kennung_aus(staffel), von, bis)
            except dienst.StaffelNichtGefunden as fehler:
                # Nicht weiterwerfen: die anderen Staffeln sollen laufen. Aber
                # auch nicht verschweigen -- diese hier ist ungeprueft, und das
                # sieht sonst aus wie "keine Spiele im Zeitraum".
                nicht_geprueft.append(name)
                self._gateway.fortschritt(kennung, zeile=f"{name}: {fehler}")
                logger.error("Staffel %s wurde nicht geprueft: %s", name, fehler)
                continue

            if zeilen:
                self._gateway.fortschritt(
                    kennung, zeile=f"{name}: {len(zeilen)} Spielbericht(e) im Zeitraum"
                )

            ausbeute = dienst.Ausbeute()
            for nummer, zeile in enumerate(zeilen):
                gefunden, karten, wettbewerb = self._pruefung_zu(
                    zeile, staffel, auskunft, abgeschaltet
                )
                ausbeute.aufnehmen(zeile, gefunden, karten, wettbewerb)
                # Je Bericht eine Meldung: ein Lauf ueber achtzig Berichte
                # dauert eine Viertelstunde, und ein Balken, der dabei steht,
                # sieht aus wie ein Dienst, der haengt.
                self._gateway.fortschritt(
                    kennung,
                    fortschritt=dienst.fortschritt_im_schritt(
                        i, len(staffeln), nummer + 1, len(zeilen)
                    ),
                    zeile=(
                        f"{nummer + 1}/{len(zeilen)} "
                        f"{'gelesen' if zeile.gespielt else 'noch nicht gespielt'}: "
                        f"{zeile.heim} gegen {zeile.gast}"
                    ),
                )

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

        if nicht_geprueft:
            # Nicht "fertig": der Lauf hat nicht getan, wofuer er angefordert
            # wurde. Ein gruener Haken ueber einer halben Pruefung ist die
            # gefaehrlichste Auskunft, die diese Anzeige geben kann.
            self._gateway.abschluss(
                kennung,
                "gescheitert",
                "Nicht geprüft, weil DFBnet sie nicht angeboten hat: " + ", ".join(nicht_geprueft),
            )
            return

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

        # Der Verband steht in den Einstellungen: DFBnet sucht danach, und ein
        # fest verdrahtetes "Saechsischer Fussball-Verband" faende fuer jeden
        # anderen Kreisverband nichts und meldete nur, die Staffel sei nicht da.
        verband = str(self._gateway.einstellungen().get("verband") or "")

        gesamt = 0
        nicht_gefunden: list[str] = []
        for i, staffel in enumerate(staffeln):
            name = str(staffel["name"])
            self._gateway.fortschritt(
                kennung,
                schritt=f"Hole die Meldung zu {name}",
                fortschritt=dienst.fortschritt(i, len(staffeln)),
            )
            try:
                mannschaften = self._leser.mannschaften(dienst.kennung_aus(staffel), verband)
            except dienst.StaffelNichtGefunden as fehler:
                nicht_gefunden.append(name)
                self._gateway.fortschritt(kennung, zeile=f"{name}: {fehler}")
                logger.error("Meldung zu %s nicht geholt: %s", name, fehler)
                continue
            # Die Spieltage stehen in der Meisterschaftsliste, an der die
            # Initialisierung ohnehin vorbeikommt. Ohne sie meldet die Regel
            # `spieltage_unbekannt` bei **jedem** Spiel, dass die U23-Ausnahme
            # an den letzten vier Spieltagen nicht aufgehoben werden kann.
            spieltage = int(getattr(self._leser, "spieltage", 0) or 0)
            if spieltage and spieltage != int(staffel.get("spieltage") or 0):
                self._gateway.staffel_aendern(str(staffel["id"]), {"spieltage": spieltage})
                self._gateway.fortschritt(
                    kennung, zeile=f"{name}: {spieltage} Spieltage übernommen"
                )

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

        if nicht_gefunden:
            self._gateway.abschluss(
                kennung,
                "gescheitert",
                "In DFBnet nicht gefunden: " + ", ".join(nicht_gefunden),
            )
            return

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
