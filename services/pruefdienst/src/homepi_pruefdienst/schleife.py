"""Der Ablauf: warten, einen Auftrag nehmen, ihn abarbeiten, melden.

Der Dienst hält nichts fest. Sein Gedächtnis ist der Auftrag im Artefakt —
stirbt der Container mitten im Lauf, steht dort, wie weit er kam, und der
nächste Start findet ihn wieder. Genau dafür ist ein Auftrag ein Datensatz
und kein Thread.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any

from . import dienst, fallanlage, katalog, regeln
from .auskunft import GatewayAuskunft
from .gateway import Gateway, GatewayFehler
from .leser import BeispielLeser, Leser
from .regelwerk.ordner import regelordner

logger = logging.getLogger(__name__)


class Prueflauf:
    """Ein Durchgang durch die Aufträge und die Übertragungen."""

    def __init__(self, gateway: Gateway, leser: Leser, darf_schreiben: bool = False) -> None:
        self._gateway = gateway
        self._leser = leser
        self._darf_schreiben = darf_schreiben
        # Ob jemand zusieht. Steht in den Einstellungen und wird je Lauf neu
        # gelesen -- vor dem Anmelden ist es aus, denn ohne Seite gibt es auch
        # nichts zu fotografieren.
        self._zuschauen = False

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
            if art == "staffeln":
                self._staffeln_holen(kennung)
            elif art == "initialisierung":
                self._initialisieren(kennung, auftrag.get("staffel_id"))
            else:
                self._pruefen(kennung, auftrag.get("staffel_id"))
        except Exception as fehler:
            # Jeder Fehler landet am Auftrag und nicht nur im Protokoll des
            # Containers: der Staffelleiter sieht sonst eine Anzeige, die
            # stehenbleibt, und weiß nicht, warum.
            logger.exception("Auftrag %s gescheitert", kennung)
            # Zuerst das Bild, dann die Meldung: beim Abschluss schliesst der
            # Leser seinen Browser, und danach gibt es nichts mehr zu
            # fotografieren. Genau dieses Bild beantwortet die Frage, an der
            # ohne Bildschirm niemand weiterkam -- woran es lag.
            self._zusehen(kennung, f"Gescheitert: {fehler}"[:200], art="fehler")
            self._melden_dass_gescheitert(kennung, fehler)
        finally:
            self._leser.schliessen()

    def _zusehen(self, kennung: str, schritt: str, art: str = "aktuell") -> None:
        """Ein Abbild der Seite ans Artefakt, fuer das Vorschaufenster.

        Nur wenn der Schalter "Beim Pruefen zusehen" an ist. Er hiess einmal
        "browser_sichtbar" und meinte ein echtes Fenster; im Container gibt es
        keinen Bildschirm, und auf Windows soll dieser Dienst nicht laufen
        muessen. Also wird die Seite fotografiert statt gezeigt.

        Fehler bleiben folgenlos. Ein Prueflauf, der am Zusehen scheitert,
        waere die schlechteste aller Hilfestellungen.
        """
        if not self._zuschauen:
            return
        try:
            self._gateway.ansicht(kennung, art, self._leser.abbild(), schritt)
        except Exception:
            logger.warning("Das Zusehen ist gescheitert", exc_info=True)

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

    def _regeln_spiegeln(self, kennung: str) -> None:
        """Die Regeldateien aus dem Artefakt in den eigenen Ordner schreiben.

        **Der Quelltext im Artefakt ist die Wahrheit, der Ordner die Kopie.**
        Vorher lagen die Pruefungen nur in einem Band am Dienst; wer sie
        aendern wollte, brauchte eine Konsole auf dem Pi.

        Geschrieben wird nur, was sich geaendert hat -- und entfernt, was im
        Artefakt nicht mehr steht oder dort abgeschaltet ist. Eine Datei, die
        im Ordner liegengeblieben ist, waere eine Regel, die laeuft, obwohl
        niemand sie mehr fuehrt.

        Die mitgelieferten Vorlagen bleiben unberuehrt: sie tragen keine
        Entsprechung im Artefakt, solange sie niemand hochgeladen hat, und sie
        hier wegzuraeumen hiesse, das Regelwerk beim ersten Lauf zu leeren.
        """
        try:
            verzeichnis = self._gateway.regeldateien()
        except GatewayFehler:
            logger.exception("Die Regeldateien liessen sich nicht holen")
            # Nur hier zurueck: das Artefakt war nicht erreichbar, und dann
            # ist auch das Buch unten nicht zu beurteilen.
            return

        # **Kein frueher Ausstieg bei leerer Liste.** Wer seine letzte eigene
        # Regeldatei loescht, soll sie auch aus dem Ordner los sein -- mit
        # einem `return` an dieser Stelle laege die Kopie fuer immer da und
        # liefe bei jedem Lauf mit.
        ordner = regelordner()
        ordner.mkdir(parents=True, exist_ok=True)
        gefuehrt = {str(d.get("name") or "") for d in verzeichnis}
        geschrieben = 0

        for eintrag in verzeichnis:
            name = str(eintrag.get("name") or "")
            if not name:
                continue
            ziel = ordner / name
            if not eintrag.get("aktiv"):
                # Abgeschaltet heisst: liegt im Artefakt, laeuft hier nicht.
                ziel.unlink(missing_ok=True)
                continue
            try:
                inhalt = str(self._gateway.regeldatei(str(eintrag["id"])).get("inhalt") or "")
            except GatewayFehler:
                logger.exception("Regeldatei %s liess sich nicht holen", name)
                continue
            if ziel.exists() and ziel.read_text(encoding="utf-8") == inhalt:
                continue
            ziel.write_text(inhalt, encoding="utf-8")
            geschrieben += 1

        # Was das Artefakt einmal geschrieben hat und jetzt nicht mehr fuehrt,
        # muss weg -- sonst laeuft eine geloeschte Regel weiter.
        #
        # Welche das sind, steht in einem eigenen Verzeichnis im Ordner: ohne
        # das liesse sich eine geloeschte Datei nicht von einer der
        # mitgelieferten Vorlagen unterscheiden, und ein Aufraeumen leerte
        # beim ersten Lauf das ganze Regelwerk. Der Unterstrich haelt es vom
        # Lader fern.
        buch = ordner / "_aus_artefakt.json"
        try:
            vorher = set(json.loads(buch.read_text(encoding="utf-8"))) if buch.is_file() else set()
        except (OSError, ValueError):
            logger.warning("Das Verzeichnis der gespiegelten Regeln ist unlesbar")
            vorher = set()

        for name in sorted(vorher - gefuehrt):
            (ordner / name).unlink(missing_ok=True)
            logger.info("Regeldatei %s entfernt -- das Artefakt fuehrt sie nicht mehr", name)

        buch.write_text(json.dumps(sorted(gefuehrt), ensure_ascii=False), encoding="utf-8")

        if geschrieben:
            logger.info("%d Regeldatei(en) aus dem Artefakt geschrieben", geschrieben)
            self._gateway.fortschritt(
                kennung, zeile=f"{geschrieben} Regeldatei(en) aus dem Artefakt übernommen"
            )

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

    def _mannschaften_von(self, staffel: dict[str, Any]) -> list[dict[str, Any]]:
        """Die Meldung dieser Staffel -- für § 68 die halbe Miete.

        Geht es schief, wird trotzdem geprüft: der Übersetzer erschließt die
        höheren Mannschaften dann aus den Namen. Schlechter als die gepflegte
        Liste, aber besser als gar keine Wartefristprüfung.
        """
        try:
            return list(self._gateway.mannschaften(str(staffel["id"])))
        except Exception:
            logger.exception("Die Mannschaften zu %s liessen sich nicht lesen", staffel["name"])
            return []

    def _pruefung_zu(
        self,
        zeile: dienst.Spielzeile,
        staffel: dict[str, Any],
        auskunft: GatewayAuskunft | None,
        abgeschaltet: set[str],
        mannschaften: list[dict[str, Any]],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], str, dict[str, str]]:
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
            return self._leser.befunde_zu(zeile), [], "Meisterschaft", {}

        if not zeile.gespielt:
            # Das Spiel läuft erst noch: es gibt keinen Bericht, und ihn zu
            # öffnen kostet eine Minute Warten auf eine Seite, die leer bleibt.
            # Am Spieltag ist das der Normalfall und keine Warnung.
            logger.info("Spiel %s ist noch nicht gespielt", zeile.dfbnet_id)
            return [], [], "", {}

        bericht = self._leser.bericht(zeile.dfbnet_id)
        if bericht is None:
            return regeln.nicht_gelesen("der Prüfdienst hat ihn nicht bekommen"), [], "", {}

        befunde = regeln.befunde_aus(bericht, abgeschaltet) + katalog.befunde_aus(
            bericht,
            katalog.staffelangabe(staffel, mannschaften),
            auskunft=auskunft,
            abgeschaltet=abgeschaltet,
        )
        if not regeln.aufstellung_bekannt(bericht.home_squad):
            # Ohne Kader schweigen Spielrecht, Spielerfoto und Ordnungsdienst.
            # Ein Spiel, das nur deshalb sauber aussieht, ist die
            # gefährlichste Zeile in der Warteschlange.
            befunde += regeln.ohne_aufstellung()
        return (
            befunde,
            regeln.karten_aus(bericht),
            bericht.meta.competition,
            regeln.kopfdaten_aus(bericht),
        )

    def _anmelden(self, kennung: str) -> None:
        self._gateway.fortschritt(
            kennung, schritt="Melde mich bei DFBnet an", zeile="Hole die Zugangsdaten"
        )
        # Vor dem Anmelden, denn dabei entsteht der Browser: der Schalter aus
        # den Einstellungen gilt ab dem naechsten Lauf und nicht erst nach
        # einem Neustart des Dienstes.
        gewuenscht = bool(self._gateway.einstellungen().get("browser_sichtbar"))
        self._leser.sichtbar = gewuenscht
        # Derselbe Schalter steuert das Vorschaufenster: wer zusehen will,
        # bekommt Abbilder -- im Container ist das die einzige Art zuzusehen.
        self._zuschauen = gewuenscht

        benutzer, passwort = self._gateway.zugang()
        self._leser.anmelden(benutzer, passwort)

        # **Nach** dem Anmelden, denn erst dabei entsteht der Browser. Vorher
        # waere es eine Zusage, die der Lauf im Container nicht halten kann:
        # dort gibt es keinen Bildschirm, Chromium faellt auf unsichtbar
        # zurueck, und in der Oberflaeche stuende trotzdem "sichtbar".
        if gewuenscht:
            if getattr(self._leser, "sichtbar_misslungen", False):
                self._gateway.fortschritt(
                    kennung,
                    zeile=(
                        "Kein Fenster: der Dienst laeuft ohne Bildschirm (Container). "
                        "Es wird unsichtbar geprueft."
                    ),
                )
            else:
                self._gateway.fortschritt(kennung, zeile="Der Browser ist sichtbar")

        self._gateway.fortschritt(kennung, zeile=f"Angemeldet als {benutzer}")
        self._zusehen(kennung, "Angemeldet")

    def _staffeln_holen(self, kennung: str) -> None:
        """Die eigenen Staffeln aus DFBnet uebernehmen.

        Der kuerzeste Auftrag von allen: anmelden, eine Liste lesen,
        einspielen. Er ersetzt das Abschreiben von Hand -- und genau daran war
        die Pruefung gescheitert, mit einer Spielklasse, die DFBnet nicht
        kennt.

        Eine leere Liste ist **kein** Erfolg. Sie hiesse, das Konto fuehre
        keine Staffeln, und das naechste Einspielen loeschte nichts, aber der
        Staffelleiter stuende vor einer Anzeige, die nichts sagt.
        """
        self._anmelden(kennung)
        verband = str(self._gateway.einstellungen().get("verband") or "")

        # Die Saison aus einer vorhandenen Staffel, sonst keine: ohne Angabe
        # bleibt DFBnets eigene Vorauswahl stehen, und die steht auf der
        # laufenden. Eine geratene Jahreszahl waere schlechter als keine.
        saison = next(
            (str(s.get("saison") or "") for s in self._gateway.staffeln() if s.get("saison")), ""
        )

        self._gateway.fortschritt(
            kennung, schritt="Hole die eigenen Staffeln", fortschritt=40, zeile="Suche in DFBnet"
        )
        gefunden = self._leser.eigene_staffeln(saison, verband)
        if not gefunden:
            raise RuntimeError(
                "DFBnet hat unter 'Eigene Staffeln' keine einzige geliefert. "
                "Sieht dieses Konto wirklich eigene Staffeln, und stimmt die "
                "Saison?"
            )

        self._gateway.fortschritt(
            kennung,
            fortschritt=80,
            zeile="Gefunden: " + ", ".join(str(s.get("name") or "?") for s in gefunden),
        )
        antwort = self._gateway.staffeln_aus_dfbnet(gefunden)
        angelegt = int(antwort.get("angelegt") or 0)
        aktualisiert = int(antwort.get("aktualisiert") or 0)
        self._gateway.abschluss(
            kennung,
            "fertig",
            f"{angelegt} angelegt, {aktualisiert} aufgefrischt",
        )

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
        # Erst spiegeln, dann melden: der Katalog entsteht aus den Dateien
        # im Ordner, und eine frisch hochgeladene Regel soll schon in diesem
        # Lauf zaehlen.
        self._regeln_spiegeln(kennung)
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
                # Die Suchmaske steht noch, samt dem, was in den Auswahlfeldern
                # stand. Genau dieses Bild beantwortet die Frage, woran es lag:
                # welche Spielklasse DFBnet anbot und welche gesucht wurde.
                self._zusehen(kennung, f"{name} nicht gefunden"[:200], art="fehler")
                continue

            # Erst jetzt, nicht vor dem Abruf: vorher stuende auf dem Bild noch
            # die Seite der vorigen Staffel -- unter dem Namen der naechsten.
            self._zusehen(kennung, f"Trefferliste {name}"[:200])

            # Was der Staffelleiter schon freigegeben hat, wird nicht noch
            # einmal gelesen: "Prueferfreigabe" ist der Stand, den **seine**
            # Freigabe setzt. Ein Bericht in diesem Stand ist bearbeitet, und
            # ihn erneut einzuspielen setzte abgehakte Spiele zurueck in die
            # Warteschlange.
            #
            # Nur dieser eine Stand. "Schiedsrichterfreigabe" und "In
            # Nacherfassung" warten noch auf ihn, und ein **leerer** Stand
            # heisst *nicht bekannt* -- der wird geprueft, nicht uebersprungen.
            bearbeitet = [z for z in zeilen if dienst.schon_bearbeitet(z.status)]
            if bearbeitet:
                zeilen = [z for z in zeilen if not dienst.schon_bearbeitet(z.status)]
                self._gateway.fortschritt(
                    kennung,
                    zeile=(
                        f"{name}: {len(bearbeitet)} Bericht(e) mit Prüferfreigabe "
                        "übersprungen — die sind schon bearbeitet"
                    ),
                )

            mannschaften = self._mannschaften_von(staffel)

            if zeilen:
                self._gateway.fortschritt(
                    kennung, zeile=f"{name}: {len(zeilen)} Spielbericht(e) im Zeitraum"
                )

            ausbeute = dienst.Ausbeute()
            for nummer, zeile in enumerate(zeilen):
                gefunden, karten, wettbewerb, kopfdaten = self._pruefung_zu(
                    zeile, staffel, auskunft, abgeschaltet, mannschaften
                )
                ausbeute.aufnehmen(zeile, gefunden, karten, wettbewerb, kopfdaten)
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

        gemacht = 0
        while (zeile := self._gateway.uebertragung_uebernehmen()) is not None:
            geklappt, meldung = self._eintragen(zeile)
            self._gateway.uebertragung_abschliessen(
                str(zeile["id"]), "fertig" if geklappt else "fehler", meldung[:900]
            )
            gemacht += 1
        logger.info("%d Übertragung(en) abgearbeitet", gemacht)
        return gemacht > 0

    def _eintragen(self, zeile: dict[str, Any]) -> tuple[bool, str]:
        """Eine vorgemerkte Handlung in DFBnet ausführen.

        **Hier verlässt die Software das eigene Netz.** Dass sie es darf, hat
        `_uebertragungen` schon geprüft: beide Schalter an.

        Mit den Beispieldaten wird es simuliert -- und das steht an jeder
        Zeile. Nur so lässt sich der Weg bis zum Freigeben durchklicken, ohne
        einen Verband anzufassen.
        """
        aktion = str(zeile.get("aktion") or "")
        if isinstance(self._leser, BeispielLeser):
            return True, "Simuliert — es war kein Browser bei DFBnet"

        if aktion == "fallanlage":
            return self._fall_anlegen(zeile)

        if aktion != "prueferfreigabe":
            # Eine Zeile auf "fertig" zu setzen, ohne dass etwas passiert ist,
            # wäre die schlimmste aller Auskünfte.
            return False, f"Die Aktion {aktion!r} ist noch nicht portiert"

        spiel_id = str(zeile.get("spiel_id") or zeile.get("referenz") or "")
        if not spiel_id:
            return False, "Zu dieser Übertragung steht kein Spiel"

        try:
            spiel = self._gateway.spiel(spiel_id)
        except Exception as fehler:
            logger.exception("Spiel %s liess sich nicht lesen", spiel_id)
            return False, f"Das Spiel liess sich nicht lesen: {fehler}"

        if not self._trefferliste_fuer(spiel):
            return False, "Der Spielbericht steht nicht in der Trefferliste von DFBnet"

        return self._leser.freigeben(str(spiel["dfbnet_id"]))

    def _fall_anlegen(self, zeile: dict[str, Any]) -> tuple[bool, str]:
        """Einen Sportgerichtsfall in DFBnet anlegen.

        **Die folgenreichste Handlung dieses Dienstes.** Sie eröffnet ein
        Verfahren gegen eine benannte Person. Vorgemerkt wird sie nur über
        einen eigenen Knopf am Vorgang, nie nebenbei beim Abhaken -- das
        Artefakt hat dort schon geprüft, dass die Pflichtangaben da sind.

        Hier wird trotzdem nochmal gelesen statt verlassen: zwischen Vormerken
        und Anlegen liegen Minuten bis Tage, und der Tatbestand, der im
        Verfahren steht, soll der sein, der jetzt am Vorgang steht.
        """
        vorgang_id = str(zeile.get("referenz") or "")
        spiel_id = str(zeile.get("spiel_id") or "")
        if not vorgang_id or not spiel_id:
            return False, "Zu dieser Übertragung fehlt der Vorgang oder das Spiel"

        try:
            vorgang = self._gateway.vorgang(vorgang_id)
            spiel = self._gateway.spiel(spiel_id)
            staffeln = {str(s["id"]): s for s in self._gateway.staffeln()}
        except Exception as fehler:
            logger.exception("Die Angaben zum Fall liessen sich nicht lesen")
            return False, f"Die Angaben zum Fall liessen sich nicht lesen: {fehler}"

        staffel = staffeln.get(str(spiel.get("staffel_id")))
        if staffel is None:
            return False, "Zu diesem Spiel gibt es keine Staffel mehr"

        anlage = fallanlage.Anlage(
            spielkennung=str(spiel.get("spielnummer") or ""),
            saison=str(staffel.get("saison") or ""),
            gericht=str(staffel.get("sportgericht") or ""),
            tatbestand=str(vorgang.get("grund") or ""),
        )
        fehlt = anlage.fehlende_felder()
        if fehlt:
            # Dieselbe Liste wie im Artefakt. Dass sie hier erneut geprüft
            # wird, ist Absicht: die Angaben können sich seit dem Vormerken
            # geändert haben, und ein Browser soll gar nicht erst starten.
            return False, "Es fehlt noch: " + ", ".join(fehlt) + "."

        try:
            ergebnis = self._leser.fall_anlegen(anlage)
        except fallanlage.FallanlageFehler as fehler:
            logger.warning("Fallanlage gescheitert: %s", fehler)
            return False, str(fehler)
        except Exception as fehler:  # pragma: no cover - unerwartet
            logger.exception("Fallanlage gescheitert")
            return False, f"Die Fallanlage ist gescheitert: {fehler}"
        return ergebnis.erfolg, ergebnis.meldung

    def _trefferliste_fuer(self, spiel: dict[str, Any]) -> bool:
        """DFBnet auf den Spieltag dieses Berichts stellen.

        Der Bericht wird über den Verweis in der Trefferliste geöffnet -- über
        seine Adresse angesprungen bleibt er leer. Also muss die Liste her, die
        ihn enthält: dieselbe Staffel, derselbe Tag.
        """
        staffeln = [s for s in self._gateway.staffeln() if str(s["id"]) == str(spiel["staffel_id"])]
        if not staffeln:
            logger.warning("Zur Übertragung gibt es keine Staffel mehr")
            return False

        tag = dt.date.fromisoformat(str(spiel["datum"]))
        zeilen = self._leser.spiele(dienst.kennung_aus(staffeln[0]), tag, tag)
        return any(z.dfbnet_id == str(spiel["dfbnet_id"]) for z in zeilen)
