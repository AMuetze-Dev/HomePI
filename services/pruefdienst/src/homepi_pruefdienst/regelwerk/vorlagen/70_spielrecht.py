# ═══════════════════════════════════════════════════════════════════════════
#  Spielrecht — wer an diesem Tag für diese Mannschaft spielen durfte
#  Grundlage: §§ 56, 59 (8), 67 Spielordnung SFV
#
#  DIESE DATEI DARF GEÄNDERT WERDEN. Sie gehört Ihnen, nicht dem Programm.
#  Ein Update von StaffelPilot fasst sie nicht an.
#
#  Woher die Angaben kommen: DFBnet führt das Spielrecht in der Aufstellung
#  als eigene Felder — nicht als Text am Namen. Das Programm deutet nichts um,
#  es reicht sie durch. Was sie bedeuten, steht hier.
#
#  Überall gilt: „nicht bekannt" ist kein Verstoß. Ältere gespeicherte
#  Berichte kennen diese Felder nicht; für sie schweigen alle Regeln dieser
#  Datei, statt einen ganzen Kader für spielunberechtigt zu erklären.
#
#  Vokabeln: docs/regelwerk-vokabeln.md
# ═══════════════════════════════════════════════════════════════════════════


def aufstellung(spieler):
    """Startelf oder Ersatzbank, für den Befundtext.

    Ein Sportgerichtsantrag soll nicht behaupten, jemand sei eingesetzt
    worden, der auf der Bank saß. Wer dort saß, gehört trotzdem gemeldet: er
    stand im Spielbericht und hätte jederzeit kommen können.
    """
    return {
        "startelf": "Startelf",
        "bank": "Ersatzbank",
        "nicht_im_kader": "nicht im Kader",
        "betreuer": "Betreuer",
    }.get(spieler.aufstellung, spieler.aufstellung or "Aufstellung")


@regel(  # noqa: F821 - vom Lader gestellt
    id="spielrecht_fehlt",
    name="Kein Spielrecht für diese Mannschaft",
    schwere="kritisch",
    weg="sportgericht",
    grund="Einsatz ohne Spielberechtigung",
    paragraf="§ 56 (1) und (3) SpO SFV",
    beschreibung=(
        "DFBnet führt für diesen Spieler kein Spielrecht für diese Mannschaft "
        "oder diesen Verein."
    ),
)
def spielrecht(spiel, melde):
    # § 56 (1): "Zur Teilnahme an Spielen jeder Art sind nur Vereinsmitglieder
    # berechtigt, die im Besitz einer ordnungsgemäß erlangten Spielerlaubnis
    # sind." § 56 (3): "Eine Spielerin/ein Spieler darf nur für den Verein
    # spielen, auf den die Spielerlaubnis in der zentralen Passdatenbank
    # lautet."
    #
    # Ausdrücklich `is False` und nicht `not ...`: `None` heißt hier nicht
    # bekannt, und Unwissen darf keinen Sportgerichtsfall auslösen.
    for elf in spiel.mannschaften:
        for spieler in elf.spieler:
            fehlt = []
            if spieler.spielrecht_mannschaft is False:
                fehlt.append("für diese Mannschaft")
            if spieler.spielrecht_verein is False:
                fehlt.append("für diesen Verein")
            if not fehlt:
                continue
            melde(
                f"{spieler.name} ({spieler.pass_nr}, {aufstellung(spieler)}) "
                f"hat nach DFBnet kein Spielrecht {' und '.join(fehlt)}.",
                person=spieler.name,
                mannschaft=elf.name,
                pass_nr=spieler.pass_nr,
                aufstellung=aufstellung(spieler),
            )


@regel(  # noqa: F821
    id="pflichtspielrecht_spaeter",
    name="Pflichtspielrecht beginnt erst nach dem Spiel",
    schwere="kritisch",
    weg="sportgericht",
    grund="Einsatz vor Beginn des Pflichtspielrechts",
    paragraf="§ 56 (1) SpO SFV",
    beschreibung=(
        "Der Spieler war am Spieltag noch nicht für Pflichtspiele "
        "spielberechtigt — der übliche Fall nach einem Vereinswechsel."
    ),
)
def pflichtspielrecht(spiel, melde):
    # DFBnet nennt zu jedem Spieler den Tag, ab dem er Pflichtspiele bestreiten
    # darf. Läuft nach einem Vereinswechsel noch eine Wartefrist, liegt dieses
    # Datum in der Zukunft. Das ist der zuverlässigste Weg zu einem Verstoß,
    # der sonst erst beim Einspruch des Gegners auffällt.
    if spiel.datum is None:
        return
    if spiel.ist_freundschaftsspiel:
        return

    for elf in spiel.mannschaften:
        for spieler in elf.spieler:
            beginn = spieler.pflichtspielrecht_ab
            if beginn is None or beginn <= spiel.datum:
                continue
            melde(
                f"{spieler.name} ({spieler.pass_nr}, {aufstellung(spieler)}) "
                f"ist erst ab dem {beginn.strftime('%d.%m.%Y')} für "
                "Pflichtspiele spielberechtigt.",
                person=spieler.name,
                mannschaft=elf.name,
                pass_nr=spieler.pass_nr,
                spielrecht_ab=beginn.strftime("%d.%m.%Y"),
            )


@regel(  # noqa: F821
    id="meisterschaftsrecht_fehlt",
    name="Kein Meisterschaftsspielrecht",
    schwere="kritisch",
    weg="sportgericht",
    grund="Einsatz ohne Meisterschaftsspielrecht",
    paragraf="§ 56 (1) SpO SFV",
    beschreibung=(
        "Der Spieler hat kein Spielrecht für Meisterschaftsspiele oder es "
        "beginnt erst später."
    ),
)
def meisterschaftsrecht(spiel, melde):
    # Nur im Meisterschaftsspiel. Im Pokal daraus einen Verstoß zu machen
    # hieße, eine Vorschrift auf einen Wettbewerb anzuwenden, für den sie
    # nicht geschrieben ist.
    if spiel.ist_freundschaftsspiel or spiel.wettbewerbskategorie != "Meisterschaft":
        return

    for elf in spiel.mannschaften:
        for spieler in elf.spieler:
            beginn = spieler.meisterschaftsrecht_ab
            spaeter = (
                beginn is not None
                and spiel.datum is not None
                and beginn > spiel.datum
            )
            if not (spieler.ohne_meisterschaftsrecht is True or spaeter):
                continue
            wann = (
                f" — es beginnt am {beginn.strftime('%d.%m.%Y')}"
                if spaeter else ""
            )
            melde(
                f"{spieler.name} ({spieler.pass_nr}, {aufstellung(spieler)}) "
                f"hat nach DFBnet kein Spielrecht für "
                f"Meisterschaftsspiele{wann}.",
                person=spieler.name,
                mannschaft=elf.name,
                pass_nr=spieler.pass_nr,
                aufstellung=aufstellung(spieler),
            )


@regel(  # noqa: F821
    id="sperrvermerk_dfbnet",
    name="DFBnet meldet eine Sperre",
    schwere="kritisch",
    weg="sportgericht",
    grund="Einsatz trotz Sperre",
    paragraf="§ 59 (8) a) SpO SFV",
    beschreibung=(
        "DFBnet hat zur Aufstellung einen Sperrvermerk gesetzt. § 59 (8) a): "
        "während einer Sperrfrist besteht keine Spielberechtigung."
    ),
)
def sperrvermerk(spiel, melde):
    # § 59 (8): "Eine Spielerin/ein Spieler mit einer gültigen
    # Spielberechtigung ist in folgenden Fällen nicht spielberechtigt:
    # a) während einer Sperrfrist, b) während einer Wartefrist, c) nach
    # Feldverweis auf Dauer bis zur Entscheidung durch das Sportgericht."
    #
    # Der Vermerk stammt aus DFBnet selbst. Die eigene Tabelle `sperren` wird
    # nur lückenhaft gefüllt — deshalb gab es diese Prüfung bisher nicht.
    # Dieses Feld ist die Auskunft der Stelle, die die Sperren führt.
    for elf in spiel.mannschaften:
        for spieler in elf.alle_personen:
            if not spieler.sperrvermerk:
                continue
            melde(
                f"DFBnet meldet zu {spieler.name} ({spieler.pass_nr}, "
                f"{aufstellung(spieler)}): {spieler.sperrvermerk}",
                person=spieler.name,
                mannschaft=elf.name,
                pass_nr=spieler.pass_nr,
                vermerk=spieler.sperrvermerk,
            )


@regel(  # noqa: F821
    id="gastspielrecht_im_pflichtspiel",
    name="Gastspielgenehmigung im Pflichtspiel",
    schwere="kritisch",
    weg="sportgericht",
    grund="Einsatz mit Gastspielgenehmigung im Pflichtspiel",
    paragraf="§ 67 (1) SpO SFV",
    beschreibung=(
        "Eine Gastspielgenehmigung gilt nur für Freundschaftsspiele, nicht "
        "für Meisterschaft und Pokal."
    ),
)
def gastspielrecht(spiel, melde):
    # § 67 (1): "Eine Gastspielgenehmigung wird im SFV sowie in den KVF nur
    # für Freundschaftsspiele nach den Maßgaben von Ziffer (5) erteilt."
    # § 67 (6) nennt daneben die U 13 Talentspielrunde — kein Wettbewerb, der
    # in einer Herren- oder Ü-Staffel vorkommt.
    if spiel.ist_freundschaftsspiel:
        return

    for elf in spiel.mannschaften:
        for spieler in elf.spieler:
            if spieler.gastspielrecht is not True:
                continue
            melde(
                f"{spieler.name} ({spieler.pass_nr}, {aufstellung(spieler)}) "
                "hat nur eine Gastspielgenehmigung — die gilt nach § 67 (1) "
                "nur für Freundschaftsspiele.",
                person=spieler.name,
                mannschaft=elf.name,
                pass_nr=spieler.pass_nr,
                aufstellung=aufstellung(spieler),
            )


@regel(  # noqa: F821
    id="zwei_spiele_am_tag",
    name="Zu viele Einsätze am selben Kalendertag",
    schwere="warnung",
    weg="sportgericht",
    grund="Einsatz in zwei Spielen am selben Kalendertag",
    paragraf="§ 56 (6) SpO SFV",
    beschreibung=(
        "Ab 18 sind zwei Spiele am Kalendertag erlaubt, darunter nur eines."
    ),
)
def einsaetze_am_tag(spiel, melde):
    # § 56 (6): "Alle Spieler, die das 18. Lebensjahr, und alle Spielerinnen,
    # die das 16. Lebensjahr vollendet haben, dürfen am gleichen Kalendertag
    # in zwei Spielen eingesetzt werden. Alle anderen Spieler/Spielerinnen
    # dürfen am gleichen Tag nur in einem Spiel/einem Turnier eingesetzt
    # werden."
    #
    # Gezählt werden nur Spiele mit Spielminuten. Auf dem Bogen zu stehen ist
    # kein Einsatz — sonst meldete jeder Ersatzspieler eines Parallelspiels.
    for elf in spiel.mannschaften:
        for spieler in elf.spieler:
            andere = spiel.andere_einsaetze(spieler)
            if not andere:
                continue
            # Wer jünger als 18 ist, darf an diesem Tag überhaupt nur einmal
            # spielen — für ihn ist schon das zweite Spiel eines zu viel.
            erlaubt_weitere = 0 if (spieler.alter is not None and spieler.alter < 18) else 1
            if ANZAHL(andere) <= erlaubt_weitere:  # noqa: F821
                continue
            wo = SORTIERT(f"{e.heim} – {e.gast}" for e in andere)  # noqa: F821
            melde(
                f"{spieler.name} ({spieler.pass_nr}) war am selben Tag in "
                f"{ANZAHL(andere) + 1} Spielen im Einsatz: dieses Spiel und "  # noqa: F821
                f"{', '.join(wo)}.",
                person=spieler.name,
                mannschaft=elf.name,
                pass_nr=spieler.pass_nr,
                anzahl=ANZAHL(andere) + 1,  # noqa: F821
                weitere_spiele=", ".join(wo),
            )


# Nicht geprüft, obwohl das Feld da ist:
#
# `secondEligibility` — das Zweitspielrecht nach §§ 67a bis 67c. Am 2. Spieltag
# hatten es 10 von 284 Personen, und keine der Einschränkungen lässt sich aus
# einem Spielbericht ablesen: § 67b (2) verlangt zu wissen, ob eine Mannschaft
# des Stammvereins am selben Wettbewerb teilnimmt, § 67c (5) hängt an der
# Mannschaftsmeldung des Stammvereins. Ein Befund „hat Zweitspielrecht" wäre
# in jedem zwanzigsten Spielbericht zu lesen und in keinem einzigen ein
# Verstoß.
