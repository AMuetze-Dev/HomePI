"""Der Draht zum Artefakt. Hier fällt HTTP an, hier steht keine Entscheidung."""

from __future__ import annotations

from typing import Any

import httpx


class GatewayFehler(RuntimeError):
    """Das Artefakt hat anders geantwortet als erwartet."""


class Gateway:
    """Der Prüfdienst meldet sich wie jeder andere Benutzer an.

    Kein eigener Schlüssel, kein Sonderweg: er bekommt ein Konto mit der Rolle
    `verwalter` für `staffelpilot` und ein Sitzungscookie wie ein Mensch. So
    steht in jedem Zugriffsprotokoll, wer gearbeitet hat, und ein Konto, das
    abhandenkommt, lässt sich sperren wie jedes andere.
    """

    def __init__(self, basis: str, benutzer: str, passwort: str, zeit_s: float = 30.0) -> None:
        self._benutzer = benutzer
        self._passwort = passwort
        self._client = httpx.Client(base_url=basis.rstrip("/"), timeout=zeit_s)

    def __enter__(self) -> Gateway:
        return self

    def __exit__(self, *_: object) -> None:
        self.schliessen()

    def schliessen(self) -> None:
        self._client.close()

    # ── Anmeldung ─────────────────────────────────────────────────────────

    def anmelden(self) -> None:
        antwort = self._client.post(
            "/auth/anmelden", json={"name": self._benutzer, "passwort": self._passwort}
        )
        if antwort.status_code != 200:
            raise GatewayFehler(
                f"Anmeldung als {self._benutzer!r} gescheitert: "
                f"{antwort.status_code} {antwort.text[:200]}"
            )

    def _ruf(self, methode: str, pfad: str, **kwargs: Any) -> httpx.Response:
        """Ein Aufruf, und bei 401 genau ein zweiter.

        Eine Sitzung läuft nach vierzehn Tagen ab; ein Dienst, der Wochen
        läuft, trifft das. Einmal neu anmelden und wiederholen ist die ganze
        Behandlung — mehr wäre eine Schleife, die einen echten Fehler
        verschluckt.
        """
        antwort = self._client.request(methode, pfad, **kwargs)
        if antwort.status_code == 401:
            self.anmelden()
            antwort = self._client.request(methode, pfad, **kwargs)
        return antwort

    def _json(self, methode: str, pfad: str, **kwargs: Any) -> Any:
        antwort = self._ruf(methode, pfad, **kwargs)
        if antwort.status_code >= 400:
            raise GatewayFehler(f"{methode} {pfad}: {antwort.status_code} {antwort.text[:300]}")
        return antwort.json() if antwort.content else None

    # ── Aufträge ──────────────────────────────────────────────────────────

    def offener_auftrag(self) -> dict[str, Any] | None:
        return self._json("GET", "/staffelpilot/auftraege/offen")  # type: ignore[no-any-return]

    def fortschritt(self, auftrag_id: str, **felder: Any) -> None:
        self._json("POST", f"/staffelpilot/auftraege/{auftrag_id}/fortschritt", json=felder)

    def abschluss(self, auftrag_id: str, zustand: str, meldung: str = "") -> None:
        self._json(
            "POST",
            f"/staffelpilot/auftraege/{auftrag_id}/abschluss",
            json={"zustand": zustand, "meldung": meldung},
        )

    # ── Stammdaten ────────────────────────────────────────────────────────

    def staffeln(self) -> list[dict[str, Any]]:
        return self._json("GET", "/staffelpilot/staffeln")  # type: ignore[no-any-return]

    def staffel_aendern(self, staffel_id: str, felder: dict[str, Any]) -> dict[str, Any]:
        """Einzelne Felder einer Staffel. Ausgelassene bleiben stehen."""
        return self._json(  # type: ignore[no-any-return]
            "PATCH", f"/staffelpilot/staffeln/{staffel_id}", json=felder
        )

    def regeln(self) -> list[dict[str, Any]]:
        """Der Regelkatalog, wie er im Artefakt steht -- mit den Schaltern."""
        return self._json("GET", "/staffelpilot/regeln")  # type: ignore[no-any-return]

    def regelkatalog_setzen(self, regeln: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Melden, was es gibt.

        Vollstaendig und nicht als Aenderung: eine Regel, die es nicht mehr
        gibt, soll auch keinen Schalter mehr haben. Die Schalter der uebrigen
        bleiben stehen -- sie gehoeren dem Staffelleiter.
        """
        return self._json(  # type: ignore[no-any-return]
            "PUT", "/staffelpilot/regeln", json={"regeln": regeln}
        )

    def einstellungen(self) -> dict[str, Any]:
        return self._json("GET", "/staffelpilot/einstellungen")  # type: ignore[no-any-return]

    def karten(self, pass_nr: str, seit: object = None) -> list[dict[str, Any]]:
        """Die Karten einer Person. Der Speicher fuer Paragraf 58.

        Ohne Passnummer wird gar nicht gefragt: das Artefakt wuerde 422
        antworten, und ein Fehler im Protokoll waere hier eine Falschmeldung
        -- die Person hat schlicht keine Nummer im Bericht.
        """
        if not pass_nr:
            return []
        werte: dict[str, Any] = {"pass_nr": pass_nr}
        if seit is not None:
            werte["seit"] = str(seit)
        return self._json("GET", "/staffelpilot/karten", params=werte)  # type: ignore[no-any-return]

    def zugang(self) -> tuple[str, str]:
        """Die DFBnet-Zugangsdaten. Der einzige Ort, an dem sie herauskommen."""
        daten = self._json("POST", "/staffelpilot/zugang/abholen")
        return str(daten["benutzer"]), str(daten["passwort"])

    def einspielen(self, staffel_id: str, spiele: list[dict[str, Any]]) -> dict[str, Any]:
        return self._json(  # type: ignore[no-any-return]
            "POST",
            "/staffelpilot/import",
            json={"staffel_id": staffel_id, "spiele": spiele},
        )

    def mannschaften_setzen(
        self, staffel_id: str, mannschaften: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return self._json(  # type: ignore[no-any-return]
            "PUT",
            f"/staffelpilot/staffeln/{staffel_id}/mannschaften",
            json={"mannschaften": mannschaften},
        )

    # ── Übertragung ───────────────────────────────────────────────────────

    def uebertragung(self) -> dict[str, Any]:
        return self._json("GET", "/staffelpilot/uebertragungen")  # type: ignore[no-any-return]

    def uebertragung_uebernehmen(self) -> dict[str, Any] | None:
        """Die naechste offene Zeile - und sie gehoert dann uns.

        Uebernehmen und nicht nur lesen: sonst greifen zwei Dienste nach
        derselben Zeile und tragen dieselbe Freigabe zweimal ein.
        """
        return self._json("POST", "/staffelpilot/uebertragungen/naechste")  # type: ignore[no-any-return]

    def uebertragung_abschliessen(
        self, uebertragung_id: str, zustand: str, meldung: str = ""
    ) -> None:
        self._json(
            "POST",
            f"/staffelpilot/uebertragungen/{uebertragung_id}/abschluss",
            json={"zustand": zustand, "meldung": meldung},
        )
