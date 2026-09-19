# ═══════════════════════════════════════════════════════════════════════════
#  Widerspricht sich der Spielbericht selbst?
#
#  DIESE DATEI DARF GEÄNDERT WERDEN. Sie gehört Ihnen, nicht dem Programm.
#  Ein Update von StaffelPilot fasst sie nicht an.
#
#  Zwei Prüfungen ohne Paragrafen: sie halten den Bogen gegen sich selbst.
#  Beide hängen an etwas, das sonst still danebengeht — ein falsch
#  eingetragenes Ergebnis wandert ungeprüft in die Tabelle, und eine Karte,
#  die keiner Person gehört, zählt für niemanden.
#
#  Vokabeln: docs/regelwerk-vokabeln.md
# ═══════════════════════════════════════════════════════════════════════════


@regel(  # noqa: F821 - vom Lader gestellt
    id="ergebnis_widerspricht_toren",
    name="Ergebnis passt nicht zur Torfolge",
    schwere="warnung",
    weg="hinweis",
    paragraf="—",
    beschreibung=(
        "Das eingetragene Ergebnis stimmt nicht mit den Treffern im "
        "Spielverlauf überein. Eines von beiden ist falsch — und das Ergebnis "
        "geht in die Tabelle."
    ),
)
def ergebnis(spiel, melde):
    eingetragen = spiel.ergebnis_tore
    if eingetragen is None:
        return

    # Kein Treffer im Verlauf heißt: der Bogen ist an dieser Stelle leer. Das
    # als 0:0 zu lesen und gegen das Ergebnis zu halten, meldete jedes Spiel,
    # dessen Spielverlauf noch niemand ausgefüllt hat.
    if not spiel.tore:
        return

    # Nach einem Abbruch oder einem Nichtantreten gilt die Wertung, nicht die
    # Torfolge — dort ist der Unterschied der Normalfall.
    if spiel.vorkommnis_genannt("abbruch", "nicht angetreten", "nichtantreten"):
        return

    # Im Pokal kann ein Elfmeterschießen im Ergebnis stehen, dessen Schützen
    # nicht als Tore im Verlauf auftauchen.
    if spiel.ist_pokalspiel:
        return

    # Verglichen wird die GESAMTZAHL der Tore, nicht die Verteilung auf die
    # Mannschaften. Grund ist das Eigentor: DFBnet führt den Treffer bei der
    # Mannschaft des Schützen, gezählt wird er für die andere. Im Spiel
    # SG Gittersee – SG Weixdorf 3 vom 30.08.2026 steht deshalb 2:0 im
    # Ergebnis und je ein Tor pro Seite im Verlauf — beides richtig.
    #
    # Der Preis: ein vertauschtes Ergebnis (0:2 statt 2:0) fällt hier nicht
    # auf. Das ließe sich erst prüfen, wenn der Spielverlauf das Eigentor als
    # solches ausliest; dafür fehlt bisher ein echtes Beispiel im HTML.
    eingetragen_gesamt = eingetragen[0] + eingetragen[1]
    gezaehlt_gesamt = ANZAHL(spiel.tore)  # noqa: F821
    if eingetragen_gesamt == gezaehlt_gesamt:
        return

    melde(
        f"Eingetragen ist {eingetragen[0]} : {eingetragen[1]}, also "
        f"{eingetragen_gesamt} Tore — im Spielverlauf stehen "
        f"{gezaehlt_gesamt}.",
        ergebnis=f"{eingetragen[0]} : {eingetragen[1]}",
        tore_im_ergebnis=eingetragen_gesamt,
        tore_im_verlauf=gezaehlt_gesamt,
    )


@regel(  # noqa: F821
    id="karte_ohne_person",
    name="Karte lässt sich niemandem zuordnen",
    schwere="warnung",
    weg="hinweis",
    paragraf="—",
    beschreibung=(
        "Im Spielverlauf steht eine Karte für einen Namen, den die "
        "Aufstellung nicht kennt. Diese Karte zählt für niemanden — auch "
        "nicht im Verwarnungszähler."
    ),
)
def karte_ohne_person(spiel, melde):
    # Der Verwarnungszähler hängt an der Passnummer, und die kommt aus der
    # Aufstellung. Steht der Name im Spielverlauf anders geschrieben als dort,
    # findet ihn niemand: die Karte ist auf dem Bogen zu sehen, in der
    # Zählung aber nicht. Die fünfte Verwarnung nach § 58 (2) a) käme dann
    # nie — ein Fehler, der sich über die ganze Saison hält und den niemand
    # bemerkt, weil nichts gemeldet wird.
    bekannt = {
        " ".join((p.name or "").split()).casefold()
        for elf in spiel.mannschaften
        for p in elf.alle_personen
    }

    for karte in spiel.alle_karten:
        name = " ".join((karte.person or "").split()).casefold()
        if not name or name in bekannt:
            continue
        melde(
            # Einfache Anführungszeichen: das schließende deutsche
            # Anführungszeichen würde eine mit " begonnene Zeichenkette hier
            # beenden. Genau daran sind in der Regelwerk-Nacht vier Dateien
            # zerbrochen.
            f'Die {karte.art} für „{karte.person}" steht im Spielverlauf, '
            'aber dieser Name kommt in keiner Aufstellung vor. Die Karte '
            'wird deshalb nicht gezählt.',
            person=karte.person,
            mannschaft=karte.mannschaft,
            art=karte.art,
        )
