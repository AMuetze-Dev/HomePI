"""Staffelleiter sehen nur ihre eigenen Staffeln -- und alles, was daran haengt.

Eine Staffel gehoert dem, der sie anlegt, wie eine Einstellung. Fuehren zwei
dieselbe Staffel in DFBnet, hat jeder seine eigene mit eigenen Berichten. Wer
wie viele hat, ist StaffelPilot egal.
"""

from __future__ import annotations

from typing import Any

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from .hilfen import (
    STAFFEL,
    aus_dfbnet,
    befund,
    dfbnet_zeile,
    einspielen,
    erste_zeile,
    erster_befund,
    konto_von,
    spiel,
    staffel_anlegen,
)

pytestmark = pytest.mark.integration


async def namen(client: AsyncClient) -> list[str]:
    return [s["name"] for s in (await client.get("/staffelpilot/staffeln")).json()]


async def erste_staffel(client: AsyncClient) -> dict[str, Any]:
    return dict((await client.get("/staffelpilot/staffeln")).json()[0])


async def voll(client: AsyncClient) -> dict[str, str]:
    """Eine Staffel mit allem, was daran haengen kann."""
    staffel_id = await staffel_anlegen(client, sportgericht="Sportgericht Dresden")
    antwort = await einspielen(
        client,
        staffel_id,
        spiel(
            spielnummer="633203177",
            befunde=[befund(weg="sportgericht")],
            karten=[{"person": "Max", "pass_nr": "P-1", "art": "Gelbe Karte"}],
        ),
    )
    assert antwort.status_code == 200, antwort.text
    spiel_id = (await erste_zeile(client))["id"]
    befund_id = (await erster_befund(client, spiel_id))["id"]
    vorgang = await client.post(f"/staffelpilot/befunde/{befund_id}/vorgang", json={})
    assert vorgang.status_code == 201, vorgang.text
    auftrag = await client.post("/staffelpilot/auftraege", json={"art": "pruflauf"})
    assert auftrag.status_code == 201, auftrag.text
    uebertragung = await client.post(
        "/staffelpilot/uebertragungen",
        json={"aktion": "prueferfreigabe", "referenz": spiel_id},
    )
    assert uebertragung.status_code == 201, uebertragung.text
    return {
        "staffel": staffel_id,
        "spiel": spiel_id,
        "befund": befund_id,
        "vorgang": vorgang.json()["id"],
        "auftrag": auftrag.json()["id"],
        "uebertragung": uebertragung.json()["id"],
    }


LISTEN = ["/", "/staffeln", "/befunde", "/vorgaenge", "/auftraege", "/karten?pass_nr=P-1"]

EINZELN: list[tuple[str, str, Any]] = [
    ("GET", "/staffeln/{staffel}/mannschaften", None),
    ("PUT", "/staffeln/{staffel}/mannschaften", {"mannschaften": []}),
    ("PATCH", "/staffeln/{staffel}", {"aktiv": False}),
    ("DELETE", "/staffeln/{staffel}", None),
    ("POST", "/import", {"staffel_id": "{staffel}", "spiele": []}),
    ("GET", "/spiele/{spiel}", None),
    ("POST", "/spiele/{spiel}/haken", None),
    ("DELETE", "/spiele/{spiel}/haken", None),
    ("POST", "/befunde/{befund}/entscheidung", {"art": "kenntnis"}),
    ("DELETE", "/befunde/{befund}/entscheidung", None),
    ("POST", "/befunde/{befund}/vorgang", {}),
    ("GET", "/vorgaenge/{vorgang}", None),
    ("PATCH", "/vorgaenge/{vorgang}", {"text": "fremd"}),
    ("POST", "/vorgaenge/{vorgang}/zustand", {"zustand": "versandt"}),
    ("DELETE", "/vorgaenge/{vorgang}", None),
    ("POST", "/vorgaenge/{vorgang}/fallanlage", None),
    ("POST", "/vorgaenge/{vorgang}/fallprobe", None),
    ("GET", "/vorgaenge/{vorgang}/mahnung.pdf", None),
    ("GET", "/vorgaenge/{vorgang}/mail", None),
    ("POST", "/auftraege", {"art": "pruflauf", "staffel_id": "{staffel}"}),
    ("GET", "/auftraege/{auftrag}", None),
    ("POST", "/auftraege/{auftrag}/fortschritt", {"schritt": "fremd"}),
    ("POST", "/auftraege/{auftrag}/abschluss", {"zustand": "abgebrochen"}),
    ("GET", "/auftraege/{auftrag}/ansichten", None),
    ("GET", "/auftraege/{auftrag}/ansicht/aktuell", None),
    ("POST", "/uebertragungen", {"aktion": "prueferfreigabe", "referenz": "{spiel}"}),
    ("POST", "/uebertragungen", {"aktion": "fallanlage", "referenz": "{vorgang}"}),
    ("POST", "/uebertragungen/wiederholen?uebertragung_id={uebertragung}", None),
    ("POST", "/uebertragungen/{uebertragung}/abschluss", {"zustand": "fertig"}),
]


def eingesetzt(wert: Any, ids: dict[str, str]) -> Any:
    if isinstance(wert, str):
        return wert.format(**ids)
    if isinstance(wert, dict):
        return {k: eingesetzt(v, ids) for k, v in wert.items()}
    return wert


class TestSichtbarkeit:
    @pytest.mark.parametrize("pfad", LISTEN)
    async def test_listen_enthalten_nichts_fremdes(
        self, client: AsyncClient, verwalterin: AsyncClient, pfad: str
    ) -> None:
        await voll(client)

        assert (await client.get(f"/staffelpilot{pfad}")).json() != []
        assert (await verwalterin.get(f"/staffelpilot{pfad}")).json() == []

    async def test_zahlen_zaehlen_nichts_fremdes(
        self, client: AsyncClient, verwalterin: AsyncClient
    ) -> None:
        ids = await voll(client)

        zusammen = (await verwalterin.get("/staffelpilot/zusammenfassung")).json()
        assert set(zusammen.values()) == {0}
        ergebnisse = (await verwalterin.get("/staffelpilot/ergebnisse")).json()
        assert [ergebnisse[k] for k in ("befunde", "spiele", "vorgaenge")] == [0, 0, 0]
        assert (await verwalterin.get("/staffelpilot/einrichtung")).json()["staffeln"] == 0
        stand = (await verwalterin.get("/staffelpilot/uebertragungen")).json()
        assert stand["offen"] == 0

        # Auch nicht, wenn die fremde Staffel ausdruecklich genannt ist.
        for pfad in ("/", "/befunde"):
            antwort = await verwalterin.get(
                f"/staffelpilot{pfad}", params={"staffel_id": ids["staffel"]}
            )
            assert antwort.json() == []

    async def test_der_offene_auftrag_ist_der_eigene(
        self, client: AsyncClient, verwalterin: AsyncClient
    ) -> None:
        await voll(client)

        assert (await client.get("/staffelpilot/auftraege/offen")).json() is not None
        assert (await verwalterin.get("/staffelpilot/auftraege/offen")).json() is None

    @pytest.mark.parametrize(("methode", "pfad", "koerper"), EINZELN)
    async def test_einzelnes_fremdes_gibt_es_nicht(
        self,
        client: AsyncClient,
        verwalterin: AsyncClient,
        methode: str,
        pfad: str,
        koerper: Any,
    ) -> None:
        """404 und nicht 403: dass es etwas gibt, ist auch schon eine Auskunft."""
        ids = await voll(client)

        antwort = await verwalterin.request(
            methode, f"/staffelpilot{pfad.format(**ids)}", json=eingesetzt(koerper, ids)
        )

        assert antwort.status_code == 404, antwort.text

    async def test_auch_kein_bild_in_einen_fremden_lauf(
        self, client: AsyncClient, verwalterin: AsyncClient
    ) -> None:
        ids = await voll(client)

        antwort = await verwalterin.put(
            f"/staffelpilot/auftraege/{ids['auftrag']}/ansicht/aktuell",
            content=b"\xff\xd8\xff\xe0bild",
        )

        assert antwort.status_code == 404, antwort.text

    async def test_niemand_schaut_durch_fremde_augen(
        self, client: AsyncClient, verwalterin: AsyncClient
    ) -> None:
        antwort = await verwalterin.get(
            "/staffelpilot/staffeln", params={"konto": await konto_von(client)}
        )

        assert antwort.status_code == 403

    async def test_beispieldaten_anderer_bleiben_stehen(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        await client.put("/staffelpilot/einstellungen", json={"beispieldaten": True})
        staffel_id = await staffel_anlegen(client)
        await einspielen(client, staffel_id, spiel("DEMO-1"))

        assert (await zweite.get("/staffelpilot/beispieldaten")).json()["anzahl"] == 0
        assert (await zweite.delete("/staffelpilot/beispieldaten")).json()["entfernt"] == 0
        assert (await client.get("/staffelpilot/beispieldaten")).json()["anzahl"] == 1


class TestEigeneStaffeln:
    async def test_sie_gehoert_dem_der_sie_anlegt(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        await staffel_anlegen(client)

        assert await namen(client) == ["Stadtliga C"]
        assert await namen(zweite) == []

    async def test_sie_gehoert_dem_der_sie_holt(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        await aus_dfbnet(pruefdienst, client)

        assert await namen(client) == ["Stadtliga C"]
        assert await namen(zweite) == []

    async def test_zwei_mit_derselben_staffel_haben_jeder_seine(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        """Ein Zweierteam: dieselbe Kennung in DFBnet, und trotzdem zwei
        Staffeln, denn jeder stellt seine anders ein."""
        for c in (client, zweite):
            stand = await aus_dfbnet(pruefdienst, c)
            assert stand["angelegt"] == 1
        seine, ihre = [(await erste_staffel(c))["id"] for c in (client, zweite)]
        assert seine != ihre

        await client.patch(
            f"/staffelpilot/staffeln/{seine}", json={"sportgericht": "Dresden", "aktiv": False}
        )
        await einspielen(client, seine, spiel())

        andere = await erste_staffel(zweite)
        assert (andere["sportgericht"], andere["aktiv"]) == ("", True)
        assert (await zweite.get("/staffelpilot/")).json() == []

    async def test_dasselbe_spiel_entscheidet_jeder_fuer_sich(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        for c in (client, zweite):
            await einspielen(c, await staffel_anlegen(c), spiel(befunde=[befund()]))
        seins, ihres = [(await erste_zeile(c))["id"] for c in (client, zweite)]
        befund_id = (await erster_befund(client, seins))["id"]

        await client.post(
            f"/staffelpilot/befunde/{befund_id}/entscheidung", json={"art": "kenntnis"}
        )

        assert (await erster_befund(zweite, ihres))["entscheidung"] == "offen"

    async def test_zweimal_holen_aendert_nichts(
        self, client: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        await aus_dfbnet(pruefdienst, client)
        stand = await aus_dfbnet(pruefdienst, client)

        assert (stand["angelegt"], stand["aktualisiert"]) == (0, 1)
        assert await namen(client) == ["Stadtliga C"]

    async def test_eine_fremde_namensgleiche_wird_nicht_angefasst(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        """Von Hand angelegt und ohne Kennung: frueher haette der Abgleich ueber
        den Namen sie gefunden."""
        await staffel_anlegen(client)

        await aus_dfbnet(pruefdienst, zweite)

        assert (await erste_staffel(client))["dfbnet_kennung"] == ""

    async def test_denselben_namen_gibt_man_sich_nicht_zweimal(self, client: AsyncClient) -> None:
        await staffel_anlegen(client)

        antwort = await client.post("/staffelpilot/staffeln", json=STAFFEL)

        assert antwort.status_code == 409
        assert "gibt es bereits" in antwort.json()["detail"]

    async def test_einen_fremden_namen_schon(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        await staffel_anlegen(client)
        ihre = await staffel_anlegen(zweite, name="Stadtliga A")

        antwort = await zweite.patch(f"/staffelpilot/staffeln/{ihre}", json=STAFFEL)

        assert antwort.status_code == 200, antwort.text

    async def test_loeschen_nimmt_nur_die_eigene(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        for c in (client, zweite):
            await aus_dfbnet(pruefdienst, c)

        await client.delete(f"/staffelpilot/staffeln/{(await erste_staffel(client))['id']}")

        assert await namen(client) == []
        assert await namen(zweite) == ["Stadtliga C"]

    async def test_holen_darf_nur_der_pruefdienst(self, verwalterin: AsyncClient) -> None:
        antwort = await verwalterin.put(
            "/staffelpilot/staffeln/aus-dfbnet", json={"staffeln": [dfbnet_zeile()]}
        )

        assert antwort.status_code == 403

    async def test_ein_leser_legt_keine_an(self, leser: AsyncClient) -> None:
        assert (await leser.post("/staffelpilot/staffeln", json=STAFFEL)).status_code == 403


class TestJeKonto:
    async def test_einstellungen(self, client: AsyncClient, zweite: AsyncClient) -> None:
        await client.put(
            "/staffelpilot/einstellungen", json={"staffelleiter": "Aaron", "pruefzeitraum_tage": 7}
        )

        fremde = (await zweite.get("/staffelpilot/einstellungen")).json()
        assert fremde["staffelleiter"] == ""
        assert fremde["pruefzeitraum_tage"] == 30

    async def test_ein_langer_folgesatz_passt(self, client: AsyncClient) -> None:
        satz = "x" * 2000

        antwort = await client.put("/staffelpilot/einstellungen", json={"folgesatz": satz})

        assert antwort.json()["folgesatz"] == satz

    async def test_saetze(self, client: AsyncClient, zweite: AsyncClient) -> None:
        regel = {"schluessel": "rote_karte", "name": "Rote Karte", "weg": "mahnung"}
        await client.put("/staffelpilot/regeln", json={"regeln": [regel]})
        r = (await client.get("/staffelpilot/regeln")).json()[0]

        await client.patch(f"/staffelpilot/regeln/{r['id']}", json={"sachverhalt": "Mein Satz."})

        assert (await client.get("/staffelpilot/regeln")).json()[0]["sachverhalt"] == "Mein Satz."
        assert (await zweite.get("/staffelpilot/regeln")).json()[0]["sachverhalt"] == ""

    async def test_das_schreiben_nimmt_die_eigenen_saetze(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        regel = {"schluessel": "rote_karte", "name": "Rote Karte", "weg": "mahnung"}
        await client.put("/staffelpilot/regeln", json={"regeln": [regel]})
        r = (await client.get("/staffelpilot/regeln")).json()[0]
        texte = []
        for c, satz, name in (
            (client, "Satz von ihm.", "Aaron A."),
            (zweite, "Satz von ihr.", "Erika M."),
        ):
            await c.patch(f"/staffelpilot/regeln/{r['id']}", json={"sachverhalt": satz})
            await c.put("/staffelpilot/einstellungen", json={"staffelleiter": name})
            await einspielen(c, await staffel_anlegen(c), spiel(befunde=[befund(weg="mahnung")]))
            befund_id = (await erster_befund(c, (await erste_zeile(c))["id"]))["id"]
            vorgang = await c.post(f"/staffelpilot/befunde/{befund_id}/vorgang", json={})
            texte.append(vorgang.json()["text"])

        seiner, ihrer = texte
        assert "Satz von ihm." in seiner and "Aaron A." in seiner
        assert "Satz von ihr." in ihrer and "Erika M." in ihrer
        assert "ihm" not in ihrer and "Aaron" not in ihrer

    async def test_jeder_zaehlt_seine_aktenzeichen(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        """Eine Luecke verriete, wie viele Schreiben andere verschicken."""
        nummern = []
        for c in (client, zweite):
            await einspielen(c, await staffel_anlegen(c), spiel(befunde=[befund(weg="mahnung")]))
            befund_id = (await erster_befund(c, (await erste_zeile(c))["id"]))["id"]
            vorgang = await c.post(f"/staffelpilot/befunde/{befund_id}/vorgang", json={})
            nummern.append(vorgang.json()["aktenzeichen"])

        assert nummern[0] == nummern[1]

    async def test_die_pause(self, client: AsyncClient, zweite: AsyncClient) -> None:
        await client.post("/staffelpilot/uebertragungen/pause", json={"pausiert": False})

        assert (await client.get("/staffelpilot/uebertragungen")).json()["pausiert"] is False
        assert (await zweite.get("/staffelpilot/uebertragungen")).json()["pausiert"] is True


@pytest.fixture
def schluessel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAFFELPILOT_SCHLUESSEL", Fernet.generate_key().decode())


@pytest.mark.usefixtures("schluessel")
class TestZugang:
    async def test_jeder_hat_seinen_eigenen(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        for c, name in ((client, "a"), (zweite, "b")):
            antwort = await c.put(
                "/staffelpilot/zugang", json={"benutzer": name, "passwort": f"geheim-{name}"}
            )
            assert antwort.status_code == 204, antwort.text

        assert (await client.get("/staffelpilot/zugang")).json()["benutzer"] == "a"
        assert (await zweite.get("/staffelpilot/zugang")).json()["benutzer"] == "b"
        geholt = await pruefdienst.post(
            "/staffelpilot/zugang/abholen", params={"konto": await konto_von(zweite)}
        )
        assert geholt.json() == {"benutzer": "b", "passwort": "geheim-b"}

    async def test_loeschen_nimmt_nur_den_eigenen(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        for c in (client, zweite):
            await c.put("/staffelpilot/zugang", json={"benutzer": "x", "passwort": "y"})

        await zweite.delete("/staffelpilot/zugang")

        assert (await client.get("/staffelpilot/zugang")).json()["gespeichert"] is True
        assert (await zweite.get("/staffelpilot/zugang")).json()["gespeichert"] is False

    async def test_kein_mensch_holt_ein_passwort_ab(
        self, client: AsyncClient, verwalterin: AsyncClient
    ) -> None:
        """Auch nicht das eigene, und auch kein Verwalter."""
        await client.put("/staffelpilot/zugang", json={"benutzer": "x", "passwort": "y"})

        assert (await client.post("/staffelpilot/zugang/abholen")).status_code == 403
        fremd = await verwalterin.post(
            "/staffelpilot/zugang/abholen", params={"konto": await konto_von(client)}
        )
        assert fremd.status_code == 403

    async def test_der_pruefdienst_sagt_fuer_wen(self, pruefdienst: AsyncClient) -> None:
        antwort = await pruefdienst.post("/staffelpilot/zugang/abholen")

        assert antwort.status_code == 422
        assert "Konto" in antwort.json()["detail"]

    async def test_ein_leser_hinterlegt_keinen(self, leser: AsyncClient) -> None:
        antwort = await leser.put("/staffelpilot/zugang", json={"benutzer": "x", "passwort": "y"})

        assert antwort.status_code == 403


class TestPruefdienst:
    """Er muss alles erreichen -- und im Lauf nur, was dem Anforderer gehoert."""

    async def test_er_sieht_alles(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        await staffel_anlegen(client)
        await staffel_anlegen(zweite, name="Stadtliga A")

        assert await namen(pruefdienst) == ["Stadtliga A", "Stadtliga C"]

    async def test_fuer_ein_konto_sieht_er_dessen_staffeln(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        await staffel_anlegen(client)
        await staffel_anlegen(zweite, name="Stadtliga A")

        antwort = await pruefdienst.get(
            "/staffelpilot/staffeln", params={"konto": await konto_von(zweite)}
        )

        assert [s["name"] for s in antwort.json()] == ["Stadtliga A"]

    async def test_fuer_ein_konto_liest_er_dessen_einstellungen(
        self, client: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        await client.put("/staffelpilot/einstellungen", json={"pruefzeitraum_tage": 7})

        antwort = await pruefdienst.get(
            "/staffelpilot/einstellungen", params={"konto": await konto_von(client)}
        )

        assert antwort.json()["pruefzeitraum_tage"] == 7

    async def test_einen_lauf_fuehrt_er_zu_ende(
        self, client: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        staffel_id = await staffel_anlegen(client)
        auftrag = (await client.post("/staffelpilot/auftraege", json={})).json()

        offen = (await pruefdienst.get("/staffelpilot/auftraege/offen")).json()
        assert offen["id"] == auftrag["id"]
        assert offen["konto"] == await konto_von(client)
        fuer = {"konto": offen["konto"]}
        eingespielt = await pruefdienst.post(
            "/staffelpilot/import",
            params=fuer,
            json={"staffel_id": staffel_id, "spiele": [spiel()]},
        )
        assert eingespielt.status_code == 200, eingespielt.text
        ende = await pruefdienst.post(
            f"/staffelpilot/auftraege/{auftrag['id']}/abschluss",
            params=fuer,
            json={"zustand": "fertig"},
        )
        assert ende.status_code == 200, ende.text
        assert len((await client.get("/staffelpilot/")).json()) == 1


class TestAuftraege:
    async def test_jeder_hat_seinen_eigenen_offenen(
        self, client: AsyncClient, zweite: AsyncClient
    ) -> None:
        erster = await client.post("/staffelpilot/auftraege", json={})
        zweiter = await zweite.post("/staffelpilot/auftraege", json={})

        assert (erster.status_code, zweiter.status_code) == (201, 201)
        assert (await zweite.post("/staffelpilot/auftraege", json={})).status_code == 409

    async def test_wer_wartet_sieht_wie_viele_vor_ihm_sind(
        self, client: AsyncClient, zweite: AsyncClient, verwalterin: AsyncClient
    ) -> None:
        for c in (client, zweite, verwalterin):
            await c.post("/staffelpilot/auftraege", json={})

        for c, davor in ((client, 0), (zweite, 1), (verwalterin, 2)):
            offen = (await c.get("/staffelpilot/auftraege/offen")).json()
            assert offen["vor_dir"] == davor

    async def test_der_pruefdienst_nimmt_den_aeltesten(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        erster = (await client.post("/staffelpilot/auftraege", json={})).json()["id"]
        zweiter = (await zweite.post("/staffelpilot/auftraege", json={})).json()["id"]

        assert (await pruefdienst.get("/staffelpilot/auftraege/offen")).json()["id"] == erster
        await client.post(
            f"/staffelpilot/auftraege/{erster}/abschluss", json={"zustand": "abgebrochen"}
        )
        assert (await pruefdienst.get("/staffelpilot/auftraege/offen")).json()["id"] == zweiter

    async def test_ein_leser_fordert_nichts_an(self, leser: AsyncClient) -> None:
        assert (await leser.post("/staffelpilot/auftraege", json={})).status_code == 403


class TestUebertragungen:
    async def _vorgemerkt(self, client: AsyncClient, nummer: str) -> str:
        staffel_id = await staffel_anlegen(client, name=f"Staffel {nummer}")
        await einspielen(client, staffel_id, spiel(nummer))
        spiel_id = str((await erste_zeile(client))["id"])
        antwort = await client.post(f"/staffelpilot/spiele/{spiel_id}/haken")
        assert antwort.status_code == 200, antwort.text
        return spiel_id

    async def _freigeben(self, client: AsyncClient) -> None:
        await client.post("/staffelpilot/uebertragungen/pause", json={"pausiert": False})

    async def _naechste(self, pruefdienst: AsyncClient, **params: str) -> Any:
        antwort = await pruefdienst.post("/staffelpilot/uebertragungen/naechste", params=params)
        assert antwort.status_code == 200, antwort.text
        return antwort.json()

    async def _gescheitert(self, pruefdienst: AsyncClient, uebertragung_id: str) -> None:
        antwort = await pruefdienst.post(
            f"/staffelpilot/uebertragungen/{uebertragung_id}/abschluss",
            json={"zustand": "fehler", "meldung": "Passwort falsch"},
        )
        assert antwort.status_code == 200, antwort.text

    async def test_hinaus_geht_nur_wer_freigegeben_hat(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        await self._vorgemerkt(client, "1")
        ihres = await self._vorgemerkt(zweite, "2")
        await self._freigeben(zweite)

        stand = (await pruefdienst.get("/staffelpilot/uebertragungen")).json()
        assert (stand["pausiert"], stand["offen"]) == (False, 1)
        naechste = await self._naechste(pruefdienst)
        assert naechste["spiel_id"] == ihres
        assert naechste["konto"] == await konto_von(zweite)
        assert await self._naechste(pruefdienst) is None

    async def test_hat_niemand_freigegeben_ist_es_angehalten(
        self, client: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        await self._vorgemerkt(client, "1")

        stand = (await pruefdienst.get("/staffelpilot/uebertragungen")).json()
        assert (stand["pausiert"], stand["offen"]) == (True, 0)
        assert await self._naechste(pruefdienst) is None

    async def test_je_konto_der_reihe_nach(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        """Damit der Pruefdienst sich nicht nach jeder Zeile ummelden muss."""
        await self._vorgemerkt(client, "1")
        ihres = await self._vorgemerkt(zweite, "2")
        for c in (client, zweite):
            await self._freigeben(c)

        zeile = await self._naechste(pruefdienst, konto=await konto_von(zweite))

        assert zeile["spiel_id"] == ihres

    async def test_alle_wiederholen_meint_die_eigenen(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        await self._vorgemerkt(client, "1")
        await self._freigeben(client)
        await self._gescheitert(pruefdienst, (await self._naechste(pruefdienst))["id"])

        await zweite.post("/staffelpilot/uebertragungen/wiederholen")

        assert (await client.get("/staffelpilot/uebertragungen")).json()["fehler"] == 1


class TestRegelsatz:
    async def test_es_gilt_der_satz_dessen_der_prueft(
        self, client: AsyncClient, zweite: AsyncClient, pruefdienst: AsyncClient
    ) -> None:
        regel = {"schluessel": "rote_karte", "name": "Rote Karte"}
        await client.put("/staffelpilot/regeln", json={"regeln": [regel]})
        r = (await client.get("/staffelpilot/regeln")).json()[0]
        await zweite.patch(f"/staffelpilot/regeln/{r['id']}", json={"aktiv": False})

        ihrer, seiner = [
            (
                await pruefdienst.get(
                    "/staffelpilot/regelsatz", params={"konto": await konto_von(c)}
                )
            ).json()
            for c in (zweite, client)
        ]

        assert (ihrer["staffelleiter"], ihrer["aus"]) == ("Erika Muster", ["rote_karte"])
        assert seiner["aus"] == []

    async def test_der_katalog_gehoert_niemandem_und_ist_verwaltersache(
        self, zweite: AsyncClient
    ) -> None:
        antwort = await zweite.put("/staffelpilot/regeln", json={"regeln": []})

        assert antwort.status_code == 403
