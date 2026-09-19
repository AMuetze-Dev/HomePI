"""Der Draht zum Artefakt — gegen einen nachgebauten Server.

`httpx` bringt dafür einen eigenen Transport mit: kein Port, kein Warten, und
trotzdem echte Anfragen mit echten Statuscodes.
"""

from __future__ import annotations

import httpx
import pytest

from homepi_pruefdienst.gateway import Gateway, GatewayFehler


def gateway(antwort: object, **rest: object) -> tuple[Gateway, list[httpx.Request]]:
    """Ein Gateway, dessen Gegenstelle mitschreibt.

    `antwort` ist entweder eine feste Antwort oder eine Funktion über die
    Anfrage — damit lässt sich auch das Verhalten über mehrere Aufrufe prüfen.
    """
    gesehen: list[httpx.Request] = []

    def handler(anfrage: httpx.Request) -> httpx.Response:
        gesehen.append(anfrage)
        if callable(antwort):
            return antwort(anfrage)
        return antwort  # type: ignore[return-value]

    verbindung = Gateway("http://artefakt", "dienst", "geheim", **rest)  # type: ignore[arg-type]
    verbindung._client = httpx.Client(
        base_url="http://artefakt", transport=httpx.MockTransport(handler)
    )
    return verbindung, gesehen


class TestAnmelden:
    def test_name_und_passwort_gehen_hin(self) -> None:
        dienst, gesehen = gateway(httpx.Response(200, json={}))

        dienst.anmelden()

        assert gesehen[0].url.path == "/auth/anmelden"
        assert b"geheim" in gesehen[0].content

    def test_eine_abgelehnte_anmeldung_sagt_wer(self) -> None:
        """Sonst steht im Protokoll ein 401 und niemand weiss, welches Konto."""
        dienst, _ = gateway(httpx.Response(401, text="nope"))

        with pytest.raises(GatewayFehler, match="dienst"):
            dienst.anmelden()


class TestSitzungLaeuftAb:
    def test_bei_401_wird_einmal_neu_angemeldet(self) -> None:
        """Eine Sitzung laeuft nach vierzehn Tagen ab; ein Dienst, der Wochen
        laeuft, trifft das."""
        zustand = {"angemeldet": False}

        def handler(anfrage: httpx.Request) -> httpx.Response:
            if anfrage.url.path == "/auth/anmelden":
                zustand["angemeldet"] = True
                return httpx.Response(200, json={})
            if not zustand["angemeldet"]:
                return httpx.Response(401, text="abgelaufen")
            return httpx.Response(200, json={"id": "a1"})

        dienst, gesehen = gateway(handler)

        assert dienst.offener_auftrag() == {"id": "a1"}
        assert [a.url.path for a in gesehen] == [
            "/staffelpilot/auftraege/offen",
            "/auth/anmelden",
            "/staffelpilot/auftraege/offen",
        ]

    def test_aber_nicht_zweimal(self) -> None:
        """Mehr waere eine Schleife, die einen echten Fehler verschluckt.

        Scheitert schon die neue Anmeldung, zeigt die Meldung dorthin und
        nicht auf den Aufruf, der sie ausgeloest hat - sonst sucht jemand den
        Fehler beim Prueflauf, und er steht beim Konto.
        """
        dienst, gesehen = gateway(httpx.Response(401, text="nein"))

        with pytest.raises(GatewayFehler, match="Anmeldung"):
            dienst.offener_auftrag()

        assert [a.url.path for a in gesehen] == [
            "/staffelpilot/auftraege/offen",
            "/auth/anmelden",
        ]


class TestAufrufe:
    def test_ein_fehler_nennt_pfad_und_antwort(self) -> None:
        dienst, _ = gateway(httpx.Response(409, text="Es läuft schon einer"))

        with pytest.raises(GatewayFehler, match="läuft schon einer"):
            dienst.fortschritt("a1", zeile="x")

    def test_eine_leere_antwort_ist_keine(self) -> None:
        """204 hat keinen Koerper - `json()` daran waere ein Fehler, den
        niemand gemacht hat."""
        dienst, _ = gateway(httpx.Response(204))

        assert dienst.abschluss("a1", "fertig") is None

    def test_der_zugang_kommt_als_paar(self) -> None:
        dienst, gesehen = gateway(
            httpx.Response(200, json={"benutzer": "sl42", "passwort": "geheim"})
        )

        assert dienst.zugang() == ("sl42", "geheim")
        assert gesehen[0].method == "POST", "ein Geheimnis gehört nicht in eine URL"

    def test_einspielen_schickt_staffel_und_spiele(self) -> None:
        dienst, gesehen = gateway(httpx.Response(200, json={"angelegt": 1}))

        dienst.einspielen("s1", [{"dfbnet_id": "M-1"}])

        assert b"s1" in gesehen[0].content
        assert b"M-1" in gesehen[0].content

    def test_mannschaften_gehen_als_ganzes(self) -> None:
        dienst, gesehen = gateway(httpx.Response(200, json=[]))

        dienst.mannschaften_setzen("s1", [{"name": "SV A"}])

        assert gesehen[0].method == "PUT"
        assert gesehen[0].url.path == "/staffelpilot/staffeln/s1/mannschaften"

    def test_der_uebertragungsstand_kommt_durch(self) -> None:
        dienst, _ = gateway(httpx.Response(200, json={"pausiert": True, "offen": 2}))

        assert dienst.uebertragung() == {"pausiert": True, "offen": 2}

    def test_eine_uebertragung_wird_einzeln_gemeldet(self) -> None:
        dienst, gesehen = gateway(httpx.Response(200, json={}))

        dienst.uebertragung_abschliessen("u1", "fehler", "Zeitüberschreitung")

        assert gesehen[0].url.path == "/staffelpilot/uebertragungen/u1/abschluss"
        assert b"Zeit" in gesehen[0].content


def test_der_client_wird_geschlossen() -> None:
    dienst, _ = gateway(httpx.Response(200, json={}))

    with dienst as offen:
        assert offen is dienst

    assert dienst._client.is_closed
