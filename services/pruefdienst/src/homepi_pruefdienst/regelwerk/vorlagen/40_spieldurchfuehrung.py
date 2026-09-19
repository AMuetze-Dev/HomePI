# ═══════════════════════════════════════════════════════════════════════════
#  § 59 SpO SFV — Spieldurchführung
#
#  DIESE DATEI DARF GEÄNDERT WERDEN. Sie gehört Ihnen, nicht dem Programm.
#
#  § 59 (18): „In allen Alters- und Spielklassen sind Rückennummern zu tragen.
#  Dabei darf ein Feldspieler nur unter einer Nummer im Spiel eingesetzt
#  werden. Lediglich die Torhüter dürfen mit zwei Rückennummern auf dem
#  Spielbericht vermerkt werden."
#
#  § 59 (10): „Als angetreten gilt eine Mannschaft, wenn … im Frauen- und
#  Herrenbereich (Großfeld) mindestens 7 Spielerinnen/Spieler in Spielkleidung
#  zum festgesetzten Spielbeginn auf dem Spielfeld erschienen sind."
# ═══════════════════════════════════════════════════════════════════════════

# § 59 (10) — Großfeld, Frauen- und Herrenbereich.
MINDESTSTAERKE = 7


@regel(  # noqa: F821
    id="rueckennummer_doppelt",
    name="Rückennummer doppelt vergeben",
    schwere="warnung",
    weg="hinweis",
    paragraf="§ 59 (18) SpO SFV",
    beschreibung="Zwei Feldspieler derselben Mannschaft mit derselben Nummer.",
)
def rueckennummer_doppelt(spiel, melde):
    # Die Ausnahme des Paragrafen — „Lediglich die Torhüter dürfen mit zwei
    # Rückennummern auf dem Spielbericht vermerkt werden" — meint EINEN
    # Torhüter mit ZWEI Nummern. Das lässt sich hier gar nicht darstellen:
    # DFBnet führt je Person ein einziges Trikotfeld. Zwei Personen mit
    # derselben Nummer sind deshalb immer ein Verstoß, auch wenn eine davon
    # der Torhüter ist.
    for elf in spiel.mannschaften:
        gesehen = {}
        for spieler in elf.spieler:
            nummer = (spieler.trikot or "").strip()
            if not nummer:
                continue  # das meldet die nächste Regel
            gesehen.setdefault(nummer, []).append(spieler)

        for nummer, personen in SORTIERT(gesehen.items()):  # noqa: F821
            if ANZAHL(personen) < 2:  # noqa: F821
                continue
            namen = SORTIERT(p.name for p in personen)  # noqa: F821
            melde(
                f"Rückennummer {nummer} ist doppelt vergeben: "
                f"{', '.join(namen)}. Ein Feldspieler darf nur unter einer "
                "Nummer eingesetzt werden.",
                mannschaft=elf.name,
                nummer=nummer,
                spieler=namen,
            )


@regel(  # noqa: F821
    id="rueckennummer_fehlt",
    name="Rückennummer fehlt",
    schwere="hinweis",
    weg="hinweis",
    paragraf="§ 59 (18) SpO SFV",
    beschreibung="Ein eingesetzter Spieler ohne Rückennummer im Bericht.",
)
def rueckennummer_fehlt(spiel, melde):
    for elf in spiel.mannschaften:
        ohne = SORTIERT(  # noqa: F821
            s.name for s in elf.spieler if not (s.trikot or "").strip()
        )
        if not ohne:
            continue
        melde(
            f"Ohne Rückennummer im Spielbericht: {', '.join(ohne)}.",
            mannschaft=elf.name,
            spieler=ohne,
        )


@regel(  # noqa: F821
    id="mannschaftsstaerke",
    name="Mannschaft zu schwach besetzt",
    schwere="warnung",
    weg="hinweis",
    paragraf="§ 59 (10) SpO SFV",
    beschreibung="Weniger als sieben Spieler auf dem Spielbericht.",
)
def mannschaftsstaerke(spiel, melde):
    # Ein leerer Kader heißt „noch nicht erfasst", nicht „null angetreten".
    # Ohne diese Unterscheidung meldet jede geplante Begegnung einen Verstoß.
    for elf in spiel.mannschaften:
        anzahl = ANZAHL(elf.spieler)  # noqa: F821
        if anzahl == 0 or anzahl >= MINDESTSTAERKE:
            continue
        melde(
            f"Nur {anzahl} Spieler im Spielbericht — als angetreten gilt eine "
            f"Mannschaft ab {MINDESTSTAERKE} Spielern.",
            mannschaft=elf.name,
            anzahl=anzahl,
            mindestens=MINDESTSTAERKE,
        )
