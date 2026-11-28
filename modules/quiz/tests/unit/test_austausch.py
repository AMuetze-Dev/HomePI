"""Kataloge hinein und hinaus - Battle.Net und das eigene Paket, ohne Datenbank."""

from __future__ import annotations

import base64
import io
import json
import struct
import zipfile
import zlib
from typing import Any

import pytest

from homepi_quiz import austausch
from homepi_quiz.schemas import (
    AuswahlDaten,
    BildauswahlDaten,
    BuzzerDaten,
    FrageEingabe,
    FreitextDaten,
    HotspotDaten,
    SchaetzDaten,
    SortierDaten,
    ZahlDaten,
    ZuordnenDaten,
)


def _png() -> bytes:
    def stueck(art: bytes, daten: bytes) -> bytes:
        return (
            struct.pack(">I", len(daten))
            + art
            + daten
            + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)
        )

    roh = b"\x00\xff\x00\x00"
    return (
        b"\x89PNG\r\n\x1a\n"
        + stueck(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + stueck(b"IDAT", zlib.compress(roh))
        + stueck(b"IEND", b"")
    )


PNG = _png()
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 32


def _data_url(mime: str, inhalt: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(inhalt).decode()}"


def _battlenet(fragen: list[dict[str, Any]], **mehr: Any) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as paket:
        paket.writestr(
            "quiz.json",
            json.dumps({"title": "Testquiz", "description": "Test1", "questions": fragen, **mehr}),
        )
    return puffer.getvalue()


BATTLENET = [
    {
        "type": "buzzer",
        "question": "Wie hoch ist der Eiffelturm?",
        "correctAnswerText": "330m",
        "points": 5,
        "imageUrl": "https://images.example.org/eiffel.jpg",
    },
    {
        "type": "text",
        "question": "Wie alt ist mein Hund?",
        "correctAnswerText": "3",
        "points": 3,
        "textInputType": "number",
    },
    {"type": "text", "question": "Hauptstadt?", "correctAnswerText": "Paris", "points": 1},
    {
        "type": "multiple-choice",
        "question": "Welches Geschlecht?",
        "answers": [
            {"id": "a1", "text": "Junge", "isCorrect": False},
            {"id": "a2", "text": "Mädchen", "isCorrect": False},
            {"id": "a3", "text": "Egal", "isCorrect": True},
            {"id": "a4", "text": "", "isCorrect": False},
        ],
        "points": 2,
    },
    {"type": "true-false", "question": "Haben wir 2025?", "correctAnswer": 1, "points": 2},
    {"type": "sorting", "question": "Sortiere", "sortingItems": ["1", "3", "4", "6"], "points": 5},
    {
        "type": "slider",
        "question": "Wie alt?",
        "sliderMin": 55,
        "sliderMax": 100,
        "sliderStep": 1,
        "sliderUnit": "Jahre",
        "sliderCorrectValue": 86,
        "points": 5,
    },
    {
        "type": "hotspot",
        "question": "Triff das Kreuz",
        "imageData": _data_url("image/png", PNG),
        "hotspotX": 36.45,
        "hotspotY": 13.2,
        "points": 5,
    },
    {
        "type": "matching",
        "question": "Ordne zu",
        "matchingPairs": [
            {"id": "p1", "left": "A", "right": "1"},
            {"id": "p2", "left": "B", "right": "2"},
        ],
        "points": 5,
    },
    {
        "type": "image-choice",
        "question": "Welche Karte?",
        "audioData": _data_url("audio/mpeg", MP3),
        "imageOptions": [
            {"alt": "Option A", "correct": True, "imageData": _data_url("image/png", PNG)},
            {"alt": "Option B", "correct": False, "imageData": _data_url("image/png", PNG)},
        ],
        "points": 2,
    },
]


class TestBattleNet:
    def test_alle_fragetypen_kommen_an(self) -> None:
        paket = austausch.lies_paket(_battlenet(BATTLENET))

        assert paket.titel == "Testquiz"
        assert paket.beschreibung == "Test1"
        daten = [f.eingabe.daten for f in paket.fragen]
        assert [type(d) for d in daten] == [
            BuzzerDaten,
            ZahlDaten,
            FreitextDaten,
            AuswahlDaten,
            AuswahlDaten,
            SortierDaten,
            SchaetzDaten,
            HotspotDaten,
            ZuordnenDaten,
            BildauswahlDaten,
        ]

    def test_felder_werden_richtig_uebersetzt(self) -> None:
        fragen = austausch.lies_paket(_battlenet(BATTLENET)).fragen

        assert fragen[0].eingabe.daten == BuzzerDaten(loesung="330m")
        assert fragen[0].eingabe.punkte == 5
        assert fragen[1].eingabe.daten == ZahlDaten(loesung=3)
        assert fragen[2].eingabe.daten == FreitextDaten(loesungen=["Paris"])
        auswahl = fragen[3].eingabe.daten
        assert isinstance(auswahl, AuswahlDaten)
        assert [(o.text, o.richtig) for o in auswahl.optionen] == [
            ("Junge", False),
            ("Mädchen", False),
            ("Egal", True),
        ], "Leere Antworten aus dem Editor fallen weg"
        wahr = fragen[4].eingabe.daten
        assert isinstance(wahr, AuswahlDaten)
        assert [(o.text, o.richtig) for o in wahr.optionen] == [("Wahr", True), ("Falsch", False)]
        assert fragen[6].eingabe.daten == SchaetzDaten(
            minimum=55, maximum=100, schritt=1, loesung=86, einheit="Jahre"
        )
        hotspot = fragen[7].eingabe.daten
        assert isinstance(hotspot, HotspotDaten)
        assert (hotspot.ziele[0].x, hotspot.ziele[0].y, hotspot.ziele[0].radius) == (
            36.45,
            13.2,
            10,
        ), "Battle.Net wertet in 10 % Abstand"

    def test_bilder_und_ton_aus_data_urls(self) -> None:
        fragen = austausch.lies_paket(_battlenet(BATTLENET)).fragen

        assert fragen[7].medien == {"bild": ("image/png", PNG)}
        assert fragen[9].medien == {
            "ton": ("audio/mpeg", MP3),
            "option-0": ("image/png", PNG),
            "option-1": ("image/png", PNG),
        }

    def test_externe_bilder_werden_nicht_geholt_aber_genannt(self) -> None:
        paket = austausch.lies_paket(_battlenet(BATTLENET))

        assert paket.fragen[0].medien == {}
        assert any("images.example.org" in h and "Frage 1" in h for h in paket.hinweise)

    def test_unbekannter_typ_wird_uebersprungen_und_genannt(self) -> None:
        paket = austausch.lies_paket(
            _battlenet([{"type": "tanzen", "question": "?"}, BATTLENET[2]])
        )
        assert len(paket.fragen) == 1
        assert any("tanzen" in h for h in paket.hinweise)

    def test_kaputte_frage_wird_uebersprungen_und_genannt(self) -> None:
        paket = austausch.lies_paket(
            _battlenet([{"type": "multiple-choice", "question": "?", "answers": []}])
        )
        assert paket.fragen == []
        assert paket.hinweise and "Frage 1" in paket.hinweise[0]

    def test_ungueltiges_bild_faellt_weg(self) -> None:
        frage = {**BATTLENET[2], "imageData": _data_url("image/svg+xml", b"<svg/>")}
        paket = austausch.lies_paket(_battlenet([frage]))
        assert paket.fragen[0].medien == {}
        assert any("Bild" in h for h in paket.hinweise)

    def test_text_ohne_loesung_wird_von_hand_bewertet(self) -> None:
        paket = austausch.lies_paket(_battlenet([{"type": "text", "question": "Warum?"}]))
        assert paket.fragen[0].eingabe.daten == FreitextDaten(loesungen=[])

    def test_auch_als_nacktes_json(self) -> None:
        roh = json.dumps({"title": "Roh", "questions": [BATTLENET[2]]}).encode()
        assert austausch.lies_paket(roh).titel == "Roh"


class TestEigenesPaket:
    def test_hin_und_zurueck_ohne_verlust(self) -> None:
        fragen = austausch.lies_paket(_battlenet(BATTLENET)).fragen

        roh = austausch.schreibe_paket("Kneipenquiz", "Freitag", fragen)
        wieder = austausch.lies_paket(roh)

        assert (wieder.titel, wieder.beschreibung) == ("Kneipenquiz", "Freitag")
        assert [f.eingabe for f in wieder.fragen] == [f.eingabe for f in fragen]
        assert [f.medien for f in wieder.fragen] == [f.medien for f in fragen]
        assert wieder.hinweise == []

    def test_dateinamen_im_paket_sind_lesbar(self) -> None:
        frage = austausch.ImportFrage(
            eingabe=FrageEingabe(text="?", daten=FreitextDaten(loesungen=["x"])),
            medien={"bild": ("image/png", PNG)},
        )
        with zipfile.ZipFile(io.BytesIO(austausch.schreibe_paket("T", "", [frage]))) as paket:
            assert sorted(paket.namelist()) == ["katalog.json", "medien/1-bild.png"]


class TestSchutz:
    def test_weder_zip_noch_json(self) -> None:
        with pytest.raises(austausch.ImportUngueltig, match="ZIP"):
            austausch.lies_paket(b"\x00\x01kein paket")

    def test_zip_ohne_katalog(self) -> None:
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w") as paket:
            paket.writestr("irgendwas.txt", "x")
        with pytest.raises(austausch.ImportUngueltig, match=r"quiz\.json"):
            austausch.lies_paket(puffer.getvalue())

    def test_xml_der_ersten_fassung_wird_erkannt(self) -> None:
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w") as paket:
            paket.writestr("questions.xml", "<quiz/>")
        with pytest.raises(austausch.ImportUngueltig, match="XML"):
            austausch.lies_paket(puffer.getvalue())

    def test_zipbombe_wird_nicht_entpackt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(austausch, "MAX_ENTPACKT_BYTES", 1000)
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w", compression=zipfile.ZIP_DEFLATED) as paket:
            paket.writestr("quiz.json", " " * 5000)
        with pytest.raises(austausch.ImportUngueltig, match="groß"):
            austausch.lies_paket(puffer.getvalue())

    def test_zu_grosse_datei(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(austausch, "MAX_PAKET_BYTES", 10)
        with pytest.raises(austausch.ImportUngueltig, match="MB"):
            austausch.lies_paket(b"{" + b" " * 20 + b"}")

    def test_kaputtes_json(self) -> None:
        with pytest.raises(austausch.ImportUngueltig, match="JSON"):
            austausch.lies_paket(b"{nicht json")

    def test_ohne_fragenliste(self) -> None:
        with pytest.raises(austausch.ImportUngueltig, match="Fragen"):
            austausch.lies_paket(json.dumps({"title": "x"}).encode())

    def test_zu_viele_fragen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(austausch, "MAX_FRAGEN", 1)
        with pytest.raises(austausch.ImportUngueltig, match="Fragen"):
            austausch.lies_paket(_battlenet([BATTLENET[2], BATTLENET[2]]))

    def test_kaputte_data_url(self) -> None:
        frage = {**BATTLENET[2], "imageData": "data:image/png;base64,###"}
        paket = austausch.lies_paket(_battlenet([frage]))
        assert paket.fragen[0].medien == {}
        assert paket.hinweise
