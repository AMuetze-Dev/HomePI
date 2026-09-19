"""Die Tabelle „Mannschaften" — der Aufbau, wie die alte Anwendung ihn fand.

**Das HTML hier ist nachgebaut, nicht aufgezeichnet.** Anders als beim
Spielbericht liegt von dieser Seite keine Aufnahme vor. Diese Tests halten
also fest, *was der Leser tut*, und nicht, *dass DFBnet das noch so liefert* —
der Unterschied ist wichtig, wenn hier eines Tages alles grün ist und die
Initialisierung trotzdem nichts findet.

Was sie trotzdem wert sind: die drei Stellen, an denen die alte Anwendung
Arbeit stecken hat — der volle Vereinsname aus dem `title`, die Vereinsnummer,
die nicht in den Namen gehört, und das SG-Kürzel in der Ms-Nr.-Spalte.
"""

from __future__ import annotations

from homepi_pruefdienst import meldung

TABELLE = """
<table class="listtable">
  <tr><th></th><th>Mannschaft</th><th>Ms-Nr.</th><th>Verein</th><th>SZ</th></tr>
  <tr>
    <td><button title="bearbeiten"></button></td>
    <td>SV Loschwitz</td>
    <td>1</td>
    <td><span title="SV Loschwitz 1950 e.V.">SV Loschwitz</span>
        <span class="dfb-label">02043701</span></td>
    <td>11</td>
  </tr>
  <tr>
    <td><button title="bearbeiten"></button></td>
    <td>SG Gittersee/Coschütz</td>
    <td>7 SG</td>
    <td><span class="dfb-label">02043799</span>SG Gittersee</td>
    <td>11</td>
  </tr>
</table>
"""


class TestTabelle:
    def test_beide_mannschaften_kommen_an(self) -> None:
        gelesen = meldung.mannschaften_lesen(TABELLE)

        assert [m["name"] for m in gelesen] == ["SV Loschwitz", "SG Gittersee/Coschütz"]

    def test_der_volle_vereinsname_steht_im_title(self) -> None:
        """Im sichtbaren Text steht die Kurzform; das Schreiben an den Verein
        soll aber nicht an eine Kurzform gehen."""
        gelesen = meldung.mannschaften_lesen(TABELLE)

        assert gelesen[0]["verein"] == "SV Loschwitz 1950 e.V."

    def test_ohne_title_bleibt_der_text_und_die_nummer_faellt_weg(self) -> None:
        """Sonst hieße der Verein „SG Gittersee 02043799"."""
        gelesen = meldung.mannschaften_lesen(TABELLE)

        assert gelesen[1]["verein"] == "SG Gittersee"

    def test_die_spielgemeinschaft_wird_erkannt(self) -> None:
        gelesen = meldung.mannschaften_lesen(TABELLE)

        assert gelesen[0]["ist_sg"] is False
        assert gelesen[1]["ist_sg"] is True

    def test_die_ms_nummer_wird_nicht_zur_mannschaftsnummer(self) -> None:
        """Die 7 ist die laufende Nummer der Meldung, nicht die siebte
        Mannschaft. Die Nummer liest das Artefakt aus dem Namen."""
        gelesen = meldung.mannschaften_lesen(TABELLE)

        assert all("nummer" not in m for m in gelesen)


class TestNachsichtig:
    def test_ohne_tabelle_kommt_nichts(self) -> None:
        assert meldung.mannschaften_lesen("<html><body>nichts</body></html>") == []

    def test_leeres_html_faellt_nicht_um(self) -> None:
        assert meldung.mannschaften_lesen("") == []

    def test_eine_zu_kurze_zeile_wird_uebergangen(self) -> None:
        html = "<table><tr><td>a</td><td>b</td><td>c</td></tr></table>"

        assert meldung.mannschaften_lesen(html) == []

    def test_eine_zeile_ohne_namen_zaehlt_nicht(self) -> None:
        """Eine Mannschaft ohne Namen stünde in der Liste und niemand wüsste,
        wer sie ist."""
        html = "<table><tr><td>x</td><td></td><td>3</td><td>SV Irgendwo</td></tr></table>"

        assert meldung.mannschaften_lesen(html) == []


class TestVereinsZelle:
    def test_ein_leerer_title_gilt_nicht_als_name(self) -> None:
        """Sonst hiesse der Verein gar nichts, obwohl er sichtbar dasteht."""
        html = (
            "<table><tr><td>x</td><td>SV Loschwitz</td><td>1</td>"
            "<td><span title=''>SV Loschwitz</span>"
            "<span class='dfb-label'>02043701</span></td></tr></table>"
        )

        assert meldung.mannschaften_lesen(html)[0]["verein"] == "SV Loschwitz"


class TestEinzelteile:
    def test_sg_wird_unabhaengig_von_der_schreibweise_erkannt(self) -> None:
        assert meldung.ist_sg("7 sg") is True
        assert meldung.ist_sg("7") is False
        assert meldung.ist_sg("") is False
