"""Die Liste „Eigene Staffeln" lesen.

Die Zeilen sind echt: am 21.10.2026 in der Spielplanbearbeitung eines Kontos
mit drei Staffeln abgelesen, samt der Legende darunter.

Warum es diese Liste überhaupt gibt: die Staffeln von Hand einzutippen hat
genau die Tippfehler erzeugt, an denen die Prüfung dann scheiterte — eine
Spielklasse „Stadtliga C", die DFBnet nicht kennt, und eine Altersklasse, die
nicht zur Mannschaftsart passte. Ein Konto sieht ohnehin nur seine eigenen
Staffeln; sie abzuschreiben war nie nötig.
"""

from __future__ import annotations

import pytest

from homepi_pruefdienst.meldung import altersklasse_aus, staffeln_lesen

SPALTEN = [
    "",
    "Kennung",
    "Mannschaftsart",
    "Spielklasse",
    "Gebiet",
    "Bezeichnung",
    "Rd",
    "Nr",
    "St",
]

ZEILEN = [
    ["", "633203", "Herren", "Kreisliga C", "Kreis Dresden", "Brandible Stadtliga C", "1", "1", ""],
    [
        "",
        "633222",
        "Herren Ü35",
        "1.Kreisklasse",
        "Kreis Dresden",
        "1. Stadtklasse Ü35",
        "1",
        "1",
        "",
    ],
    [
        "",
        "633223",
        "Herren Ü35",
        "2.Kreisklasse",
        "Kreis Dresden",
        "2. Stadtklasse Ü35",
        "1",
        "1",
        "",
    ],
]

#: Was unter den Daten steht und keine ist. Dieselbe Tabelle, derselbe tbody.
LEGENDE = [
    ["", "Staffel ansehen", "", "Rd", "Rundennummer", "", "", "Angelegt", "", "", "freigegeben"],
    [
        "",
        "Staffel bearbeiten",
        "",
        "Nr",
        "Staffelnummer",
        "",
        "",
        "Mannschaften",
        "",
        "",
        "gespielt",
    ],
    [
        "",
        "Staffel auswählen",
        "",
        "St",
        "Status",
        "",
        "",
        "Spiele geplant",
        "",
        "",
        "abgeschlossen",
    ],
]


class TestDieListe:
    def test_drei_staffeln_kommen_an(self) -> None:
        assert len(staffeln_lesen(SPALTEN, ZEILEN)) == 3

    def test_spielklasse_und_bezeichnung_stehen_getrennt(self) -> None:
        """Die Bezeichnung trägt einen Sponsornamen, die Spielklasse nicht.

        Gesucht wird in der Spielberichtssuche über die **Spielklasse**; wer
        dort die Bezeichnung einsetzt, findet nichts.
        """
        erste = staffeln_lesen(SPALTEN, ZEILEN)[0]

        assert erste["spielklasse"] == "Kreisliga C"
        assert erste["name"] == "Brandible Stadtliga C"

    def test_die_kennung_kommt_mit(self) -> None:
        """Sie ist das einzig Stabile an einer Staffel: Namen ändern sich mit
        dem Sponsor."""
        assert [s["kennung"] for s in staffeln_lesen(SPALTEN, ZEILEN)] == [
            "633203",
            "633222",
            "633223",
        ]

    def test_die_altersklasse_folgt_der_mannschaftsart(self) -> None:
        klassen = [s["altersklasse"] for s in staffeln_lesen(SPALTEN, ZEILEN)]

        assert klassen == ["maenner", "ue35", "ue35"]

    def test_die_saison_wird_durchgereicht(self) -> None:
        """Sie steht nicht in der Tabelle, sondern in der Suchmaske."""
        assert staffeln_lesen(SPALTEN, ZEILEN, "26/27")[0]["saison"] == "26/27"

    def test_nach_ueberschrift_und_nicht_nach_spaltennummer(self) -> None:
        """Dieselbe Falle wie bei den Spieltagen: DFBnet baut die Liste um,
        und die vierte Spalte ist dann etwas anderes."""
        gedreht = ["", "Bezeichnung", "Spielklasse", "Mannschaftsart", "Kennung", "Gebiet"]
        zeile = ["", "1. Stadtklasse Ü35", "1.Kreisklasse", "Herren Ü35", "633222", "Kreis Dresden"]

        gelesen = staffeln_lesen(gedreht, [zeile])[0]

        assert gelesen["kennung"] == "633222"
        assert gelesen["spielklasse"] == "1.Kreisklasse"
        assert gelesen["altersklasse"] == "ue35"


class TestDieLegende:
    """Drei Zeilen unter den Daten, die erklären, was die Symbole bedeuten."""

    def test_sie_wird_nicht_zur_staffel(self) -> None:
        assert staffeln_lesen(SPALTEN, LEGENDE) == []

    def test_auch_zwischen_den_daten_nicht(self) -> None:
        gelesen = staffeln_lesen(SPALTEN, [*ZEILEN, *LEGENDE])

        assert len(gelesen) == 3
        assert all(str(s["kennung"]).isdigit() for s in gelesen)

    def test_eine_zeile_ohne_spielklasse_zaehlt_nicht(self) -> None:
        """Eine Staffel ohne Spielklasse waere eine, die nie Spiele findet."""
        ohne = ["", "633299", "Herren", "", "Kreis Dresden", "Irgendwas", "1", "1", ""]

        assert staffeln_lesen(SPALTEN, [ohne]) == []


class TestDieAltersklasse:
    @pytest.mark.parametrize(
        ("mannschaftsart", "erwartet"),
        [
            ("Herren", "maenner"),
            ("Herren Ü35", "ue35"),
            ("Alte Herren", "ue35"),
            ("Frauen", "frauen"),
            ("A-Junioren", "a_junioren"),
        ],
    )
    def test_sie_wird_uebersetzt(self, mannschaftsart: str, erwartet: str) -> None:
        assert altersklasse_aus(mannschaftsart) == erwartet

    def test_ue35_gewinnt_gegen_herren(self) -> None:
        """Die längere Form zuerst. Andersherum würde aus jeder Ü35-Staffel
        eine Herrenstaffel — und der Prüflauf läse deren Spiele."""
        assert altersklasse_aus("Herren Ü35") == "ue35"

    def test_eine_unbekannte_bleibt_leer(self) -> None:
        """Leer heißt *nicht bekannt* und nicht „Herren". Eine geratene
        Altersklasse liest die Spiele einer anderen Mannschaft, und das fällt
        erst an einem Befund auf, der zu niemandem gehört."""
        assert altersklasse_aus("Senioren Ü60") == ""
        assert altersklasse_aus("") == ""
