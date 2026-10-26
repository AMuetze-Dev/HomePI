"""Die Mail, die einen Sportgerichtsfall begleitet.

Übernommen aus `D:/DevLibrary/StaffelPilot/src/core/sportrichtermail.py` und
`tests/test_sportrichtermail.py`. Der Wortlaut stammt vom Staffelleiter
(30.08.2026); zwei Schreibfehler sind berichtigt, Aufbau, Reihenfolge der
Kerndaten und Tonfall sind seine.

**Nichts wird formuliert und nichts erzeugt.** Derselbe Tatbestand muss jedes
Mal dasselbe Schreiben ergeben — dieses kann vor dem Sportgericht landen.

**Und nichts wird versendet.** Siehe `test_kein_mailversand.py`.
"""

from __future__ import annotations

import pytest

from homepi_staffelpilot import sportrichtermail as mail

FALL = mail.Fall(
    aktenzeichen="00042-26/27-SPG_DD",
    verein="SV Pillnitz",
    angeklagter="Redlingshöfer, Tom",
    grund="Feldverweis aufgrund Beleidigung",
    anlagen="Sonderbericht des Schiedsrichters",
    hinweis="Ich habe bisher keine Stellungnahmen angefordert.",
)


class TestBetreff:
    def test_er_traegt_aktenzeichen_verein_und_person(self) -> None:
        # Die eckigen Klammern gehören dazu: so sortiert der Sportrichter
        # seine Eingänge.
        assert mail.betreff(FALL) == "[00042-26/27-SPG_DD], SV Pillnitz, Redlingshöfer, Tom"

    def test_er_bleibt_einzeilig(self) -> None:
        """Ein Betreff kann keinen Zeilenumbruch halten -- was eingegeben
        wurde, wird zu einer Zeile."""
        zerrissen = mail.Fall(
            aktenzeichen="00042-26/27-SPG_DD",
            verein="SV\nPillnitz",
            angeklagter="Redlingshöfer,\n  Tom",
            grund="egal",
        )

        assert "\n" not in mail.betreff(zerrissen)
        assert mail.betreff(zerrissen).endswith("SV Pillnitz, Redlingshöfer, Tom")


class TestText:
    def test_er_faengt_mit_der_anrede_an(self) -> None:
        assert mail.text(FALL).startswith("Guten Tag,\n\n")

    def test_er_nennt_die_person_im_ersten_satz(self) -> None:
        assert "des Spielers Redlingshöfer, Tom" in mail.text(FALL)

    def test_die_kerndaten_stehen_in_dieser_reihenfolge(self) -> None:
        # Die Reihenfolge ist die des Staffelleiters. Sie zu ändern hieße, ein
        # Schreiben zu ändern, das jemand seit Jahren so verschickt.
        text = mail.text(FALL)
        stellen = [
            text.index("Aktenzeichen:"),
            text.index("Verein:"),
            text.index("Spieler:"),
            text.index("Grund:"),
            text.index("Anlagen:"),
        ]

        assert stellen == sorted(stellen)

    def test_ohne_anlagen_faellt_die_zeile_weg(self) -> None:
        """Eine leere Anlagenzeile liest sich wie "ich habe es vergessen"."""
        ohne = mail.Fall(**{**FALL.__dict__, "anlagen": ""})

        assert "Anlagen:" not in mail.text(ohne)

    def test_ohne_hinweis_faellt_der_absatz_weg(self) -> None:
        ohne = mail.Fall(**{**FALL.__dict__, "hinweis": ""})

        assert "Hinweis:" not in mail.text(ohne)

    def test_er_endet_nach_dem_hinweis(self) -> None:
        """Kein Gruß am Ende -- so war es entschieden."""
        assert mail.text(FALL).rstrip().endswith("angefordert.")

    def test_gleiche_eingabe_gleicher_text(self) -> None:
        # Der ganze Grund, aus dem hier eine Vorlage steht und kein
        # Sprachmodell.
        assert mail.text(FALL) == mail.text(FALL)


class TestVollstaendigkeit:
    @pytest.mark.parametrize(
        "feld,name",
        [
            ("aktenzeichen", "Aktenzeichen"),
            ("verein", "Verein"),
            ("angeklagter", "Angeklagter"),
            ("grund", "Grund"),
        ],
    )
    def test_was_fehlt_wird_benannt(self, feld: str, name: str) -> None:
        luecke = mail.Fall(**{**FALL.__dict__, feld: "   "})

        assert luecke.fehlende_felder() == [name]
        assert luecke.vollstaendig is False

    def test_vollstaendig_heisst_nichts_fehlt(self) -> None:
        assert FALL.vollstaendig is True
        assert FALL.fehlende_felder() == []


class TestAktenzeichen:
    @pytest.mark.parametrize(
        "wert",
        ["00042-26/27-SPG_DD", "1234-25/26-SPG", "123456-26/27-SPG_DD"],
    )
    def test_so_schreibt_der_verband_es(self, wert: str) -> None:
        assert mail.Fall(aktenzeichen=wert).aktenzeichen_plausibel is True

    @pytest.mark.parametrize("wert", ["", "26/27", "42", "00042-2627-SPG", "abc-26/27-SPG"])
    def test_was_keines_ist_faellt_auf(self, wert: str) -> None:
        assert mail.Fall(aktenzeichen=wert).aktenzeichen_plausibel is False

    def test_es_ist_eine_warnung_und_keine_sperre(self) -> None:
        """Der Verband darf das Format ändern. Ein Fall, den StaffelPilot
        wegen eines Bindestrichs nicht mehr herausgibt, wäre schlimmer als
        eine ungewohnte Nummer."""
        fremd = mail.Fall(**{**FALL.__dict__, "aktenzeichen": "SPG-2026-0042"})

        assert fremd.aktenzeichen_plausibel is False
        assert fremd.vollstaendig is True
        assert "SPG-2026-0042" in mail.betreff(fremd)
