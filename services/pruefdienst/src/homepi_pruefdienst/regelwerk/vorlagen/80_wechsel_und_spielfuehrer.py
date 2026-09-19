# ═══════════════════════════════════════════════════════════════════════════
#  Wechselspieler und Spielführer
#  Grundlage: § 59 (7) und § 55 (1) Spielordnung SFV
#
#  DIESE DATEI DARF GEÄNDERT WERDEN. Sie gehört Ihnen, nicht dem Programm.
#  Ein Update von StaffelPilot fasst sie nicht an.
#
#  Beides steht im Spielbericht und wird von DFBnet nicht geprüft: die Wechsel
#  trägt der Schiedsrichter frei ein, den Spielführer der Verein.
#
#  Vokabeln: docs/regelwerk-vokabeln.md
# ═══════════════════════════════════════════════════════════════════════════

#: § 59 (7): "im Spielbetrieb der Herren und Frauen bis zu fünf Wechselspieler".
WECHSELSPIELER = 5


@regel(  # noqa: F821 - vom Lader gestellt
    id="einwechslungen_zu_viele",
    name="Mehr Wechselspieler eingesetzt als zulässig",
    schwere="warnung",
    weg="sportgericht",
    grund="Mehr Wechselspieler eingesetzt als zulässig",
    paragraf="§ 59 (7) SpO SFV",
    beschreibung=(
        "Im Herren- und Frauenbereich dürfen höchstens fünf Wechselspieler "
        "eingesetzt werden. Im Senioren- und Breitensport sowie in "
        "Freundschaftsspielen gilt keine Grenze."
    ),
)
def wechselspieler(spiel, melde):
    # § 59 (7): "Während eines Spieles können eingesetzt werden: im
    # Spielbetrieb der Herren und Frauen bis zu fünf Wechselspieler […] In
    # Freundschaftsspielen sowie im Senioren- und Breitensport ist die Aus-
    # und Einwechslung ohne Begrenzung möglich."
    #
    # Eine Ü-Staffel ist Seniorenspielbetrieb — dort zu zählen wäre eine
    # erfundene Grenze.
    if spiel.staffel.ist_ue or spiel.ist_freundschaftsspiel:
        return

    for elf in spiel.mannschaften:
        # `wechselspieler` zählt Personen, nicht Vorgänge: unterhalb der
        # Kreisoberligen darf wieder eingewechselt werden, und wer zweimal
        # kommt, ist derselbe Wechselspieler.
        namen = elf.wechselspieler
        if ANZAHL(namen) <= WECHSELSPIELER:  # noqa: F821
            continue
        melde(
            f"{ANZAHL(namen)} Wechselspieler eingesetzt, erlaubt sind "  # noqa: F821
            f"{WECHSELSPIELER} — {', '.join(SORTIERT(namen))}.",  # noqa: F821
            mannschaft=elf.name,
            anzahl=ANZAHL(namen),  # noqa: F821
            limit=WECHSELSPIELER,
            spieler=", ".join(SORTIERT(namen)),  # noqa: F821
        )


@regel(  # noqa: F821
    id="spielfuehrer_fehlt",
    name="Spielführer nicht benannt",
    schwere="hinweis",
    weg="hinweis",
    paragraf="§ 55 (1) SpO SFV",
    beschreibung=(
        "Der Spielführer ist auf dem Spielbericht zu benennen. Ohne ihn ist "
        "nicht dokumentiert, wer die Mannschaft auf dem Feld vertreten hat."
    ),
)
def spielfuehrer(spiel, melde):
    # § 55 (1): "Der Spielführer jeder Mannschaft vertritt ihre Belange auf
    # dem Spielfeld. […] Der Spielführer ist auf dem Spielbericht zu
    # benennen."
    for elf in spiel.mannschaften:
        # Ohne Aufstellung ist das ein anderes Problem, und
        # `mannschaftsstaerke` meldet es bereits. Zweimal dasselbe zu melden
        # macht die Liste länger, nicht klarer.
        if not elf.startelf:
            continue
        if IRGENDEINER(s.ist_spielfuehrer for s in elf.startelf):  # noqa: F821
            continue
        melde(
            f"{elf.name} hat auf dem Spielbericht keinen Spielführer benannt.",
            mannschaft=elf.name,
        )


# Nicht geprüft, obwohl § 59 (7) es nennt:
#
# "Auf dem Spielbericht können vor Spielbeginn bis zu 7 Wechselspieler
# eingetragen werden." Das lässt DFBnet im Formular gar nicht zu — über neun
# Spiele hinweg war die größte Bank genau sieben. Eine Regel, die nie
# anschlagen kann, steht nur in der Übersicht im Weg.
