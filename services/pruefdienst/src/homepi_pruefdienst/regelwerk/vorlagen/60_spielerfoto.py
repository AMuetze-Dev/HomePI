# ═══════════════════════════════════════════════════════════════════════════
#  Spielerfotos — vorhanden und aktuell
#  Grundlage: § 56 (1), § 67 (2) und § 67 (3) Spielordnung SFV
#
#  DIESE DATEI DARF GEÄNDERT WERDEN. Sie gehört Ihnen, nicht dem Programm.
#  Ein Update von StaffelPilot fasst sie nicht an.
#
#  Warum das überhaupt prüfbar ist: DFBnet liefert zu jedem Spieler der
#  Aufstellung ein Foto samt Zeitstempel — oder eben keins. Im Spielbericht
#  selbst steht davon nichts; die Angabe kommt aus der Aufstellungsschnittstelle.
#
#  Auf dem Mahnungsformular des Verbandes gibt es dafür ein eigenes Feld:
#  „fehlende oder veraltete Spielerfotos". Alle drei Regeln kreuzen es an.
#
#  Vokabeln: docs/regelwerk-vokabeln.md
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────
#  AB WANN JEMAND IM HERRENBEREICH SPIELEN DARF
#
#  § 42 (1) SpO SFV: "Herrenspieler sind Spieler, die das 18. Lebensjahr
#  vollendet haben."
#  § 42 (6) SpO SFV: "A-Junioren sind nach Vollendung des 18. Lebensjahres
#  spielberechtigt für alle Herrenmannschaften."
#
#  Ab diesem Tag kann der Wechsel in den Erwachsenenbereich erfolgen. Ein Foto,
#  das älter ist, stammt deshalb sicher aus der Juniorenzeit — und genau das
#  ist es, was § 67 (3) a) erneuert sehen will.
#
#  Bis zum 09.09.2026 stand hier der 1. Juli des Jahres, in dem der Spieler 19
#  wird: das Ende der A-Junioren nach § 42 (3) a). Das war das *späteste*
#  Datum, nicht das früheste — ein Foto vom 18. Geburtstag bis zu jenem Juli
#  konnte längst ein Herrenfoto sein und wurde trotzdem gemeldet.
#
#  Die Zahl steht hier und nicht im Programm. Sonst wäre sie festgeschrieben,
#  während die Regel darüber anpassbar heißt.
# ─────────────────────────────────────────────────────────────────────────

ERWACHSEN_AB_ALTER = 18


def erwachsen_seit(spieler):
    """Der früheste Tag, an dem dieser Spieler bei den Herren spielen durfte.

    Sein 18. Geburtstag. `None`, solange kein Geburtsdatum bekannt ist — dann
    schweigt die Regel, statt zu raten.
    """
    geburt = spieler.geburtsdatum
    if geburt is None:
        return None
    jahr = geburt.year + ERWACHSEN_AB_ALTER
    try:
        return geburt.replace(year=jahr)
    except ValueError:
        # Der 29. Februar. In einem Nicht-Schaltjahr gibt es den Tag nicht;
        # dann gilt der 28. Ohne diese Zeile stolpert die Regel über jeden
        # Spieler, der an einem Schalttag geboren ist.
        return geburt.replace(year=jahr, day=28)


@regel(  # noqa: F821 - vom Lader gestellt
    id="spielerfoto_fehlt",
    name="Spielerfoto fehlt",
    schwere="warnung",
    # „beides": das Mahnungsformular und der Sportgerichtsantrag stehen beide
    # offen. Welcher Weg genommen wird, entscheidet der Staffelleiter — die
    # Eskalation vom Hinweis über die Mahnung zum Antrag ist sein Verfahren,
    # nicht das des Programms.
    weg="beides",
    bagatelle="Spielerfotos",
    grund="Einsatz ohne hinterlegtes Spielerfoto",
    paragraf="§ 67 (2) SpO SFV",
    beschreibung=(
        "Für einen eingesetzten Spieler ist in DFBnet kein Foto hinterlegt. "
        "Ohne Lichtbild ist die Spielberechtigung nach § 56 (1) nicht "
        "überprüfbar."
    ),
)
def foto_fehlt(spiel, melde):
    # § 56 (1): "Als Nachweis gilt die Spielberechtigungsliste im DFBnet-Modul
    # SpielPLUS (Spielbericht Online) mit Lichtbild der Spielerin/des Spielers."
    # Ohne Bild kann der Gegner am Spieltag niemanden identifizieren.
    #
    # Gemeldet wird nur, wer eingesetzt war — Startelf und Bank. Wer gar nicht
    # im Kader stand, hat an diesem Tag niemandem etwas nachweisen müssen.
    for elf in spiel.mannschaften:
        ohne = [s for s in elf.spieler if s.hat_foto is False]
        for spieler in ohne:
            melde(
                f"Für {spieler.name} ({spieler.pass_nr}) ist in DFBnet kein "
                "Spielerfoto hinterlegt.",
                person=spieler.name,
                mannschaft=elf.name,
                pass_nr=spieler.pass_nr,
            )


@regel(  # noqa: F821
    id="spielerfoto_zu_alt",
    name="Spielerfoto älter als zehn Jahre",
    schwere="hinweis",
    weg="beides",
    bagatelle="Spielerfotos",
    grund="Spielerfoto seit mehr als zehn Jahren nicht erneuert",
    paragraf="§ 67 (3) b) SpO SFV",
    beschreibung=(
        "Im Erwachsenenbereich ist das Spielerfoto mindestens alle zehn Jahre "
        "zu erneuern."
    ),
)
def foto_zu_alt(spiel, melde):
    # § 67 (3): "Die Aktualität der Spielerfotos für die elektronische
    # Spielerlaubnis ist von den Vereinen in regelmäßigen Abständen zu
    # überprüfen und bei Bedarf entsprechend zu aktualisieren. […]
    # b) Im Erwachsenenbereich: alle 10 Jahre."
    #
    # "alle 10 Jahre" heißt: bei genau zehn ist die Frist erreicht, nicht
    # überschritten. Deshalb `>` und nicht `>=`.
    for elf in spiel.mannschaften:
        for spieler in elf.spieler:
            if spieler.foto_alter is None:
                continue
            if spieler.foto_alter > 10:
                melde(
                    f"Das Spielerfoto von {spieler.name} ({spieler.pass_nr}) "
                    f"ist vom {spieler.foto_stand.strftime('%d.%m.%Y')} und "
                    f"damit {spieler.foto_alter} Jahre alt.",
                    person=spieler.name,
                    mannschaft=elf.name,
                    pass_nr=spieler.pass_nr,
                    foto_stand=spieler.foto_stand.strftime("%d.%m.%Y"),
                    foto_alter=spieler.foto_alter,
                )


@regel(  # noqa: F821
    id="spielerfoto_aus_juniorenzeit",
    name="Spielerfoto stammt aus der Juniorenzeit",
    schwere="hinweis",
    weg="beides",
    bagatelle="Spielerfotos",
    grund="Spielerfoto nach dem Wechsel in den Erwachsenenbereich nicht erneuert",
    paragraf="§ 67 (3) a) SpO SFV",
    beschreibung=(
        "Beim Wechsel aus dem Junioren- in den Erwachsenenbereich ist ein "
        "neues Foto zu erstellen. Die Grenze ist der 18. Geburtstag "
        "(§ 42 (1) und (6)) — nicht die U23."
    ),
)
def foto_aus_juniorenzeit(spiel, melde):
    # § 67 (3) a), zweiter Spiegelstrich: "beim Wechsel aus dem Junioren- in
    # den Erwachsenenbereich (nach A-Jun./B-Juniorinnen)".
    #
    # Wann das frühestens sein kann, steht oben bei `erwachsen_seit`: mit dem
    # 18. Geburtstag (§ 42 (1) und (6)). Ein älteres Foto ist deshalb sicher
    # eines aus der Juniorenzeit.
    #
    # Was der Spielbericht NICHT hergibt: ob der Spieler tatsächlich schon
    # gewechselt ist. Ein 18-Jähriger kann weiter A-Junior sein und nach
    # § 56 (5) bei den Herren aushelfen. Deshalb bleibt dieser Befund ein
    # Hinweis und keine Feststellung — er nennt eine Tatsache über das Foto,
    # die Bewertung bleibt beim Staffelleiter.
    #
    # Ausdrücklich NICHT 23. Die U23 steht in § 68 (2) c) und ist die
    # Stammspielerregel; mit dem Passbild hat sie nichts zu tun.
    #
    # Diese Regel greift dort, wo die Zehnjahresregel noch nicht greift: ein
    # Spieler von 24 mit einem Foto aus seinem 17. Lebensjahr fällt sonst erst
    # mit 27 auf. Ist das Foto ohnehin über zehn Jahre alt, meldet die Regel
    # darüber — zwei Befunde wären derselbe Vorwurf zweimal.
    # Ein Befund je Mannschaft, nicht je Spieler. Am 2. Spieltag 2026/27
    # betraf das über neun Spiele hinweg 20 Personen — als 20 Einzelbefunde
    # hätten sie die beiden Spieler ohne Foto zugedeckt. Wer die Namen
    # braucht, hat sie im Befund.
    for elf in spiel.mannschaften:
        betroffen = []
        for spieler in elf.spieler:
            grenze = erwachsen_seit(spieler)
            if grenze is None or spieler.foto_stand is None:
                continue
            # Ein Foto ab dem 18. Geburtstag kann bereits ein Herrenfoto sein.
            # Ob es eines ist, sagt der Spielbericht nicht — also wird es nicht
            # behauptet.
            if spieler.foto_stand >= grenze:
                continue
            # Vor dem 18. Geburtstag kann der Wechsel nicht stattgefunden
            # haben; die Pflicht aus § 67 (3) a) entsteht erst mit ihm. Ohne
            # diese Zeile meldet die Regel jeden jungen Spieler zu früh, und
            # das auf jedem Spielbericht neu.
            if spiel.datum is None or spiel.datum < grenze:
                continue
            if spieler.foto_alter is not None and spieler.foto_alter > 10:
                continue
            betroffen.append(
                f"{spieler.name} (Foto vom "
                f"{spieler.foto_stand.strftime('%d.%m.%Y')})"
            )

        if betroffen:
            liste = ", ".join(SORTIERT(betroffen))  # noqa: F821
            melde(
                f"{ANZAHL(betroffen)} Spieler mit einem Foto aus der "  # noqa: F821
                f"Juniorenzeit: {liste}. Beim Wechsel in den "
                "Erwachsenenbereich ist ein neues Foto zu erstellen.",
                mannschaft=elf.name,
                anzahl=ANZAHL(betroffen),  # noqa: F821
                spieler=liste,
            )


# Nicht geprüft, weil aus einem Spielbericht nicht ablesbar:
#
# § 67 (3) a), erster Spiegelstrich — "beim Wechsel vom Kleinfeld auf das
# Großfeld (ab C-Junioren/innen)". Betrifft den Jugendbereich; in einer Herren-
# oder Ü-Staffel kommt dieser Fall nicht vor.
#
# § 67 (2) — "muss einen erkennbaren Vereinsbezug des antragstellenden Vereins
# aufweisen". Das ist eine Aussage über das Bild selbst, nicht über ein Datum.
