# ═══════════════════════════════════════════════════════════════════════════
#  § 60 und § 61 SpO SFV — Nichtantreten und Spielabbruch
#
#  DIESE DATEI DARF GEÄNDERT WERDEN. Sie gehört Ihnen, nicht dem Programm.
#
#  § 61 (3): Ein Spiel kann abgebrochen werden bei
#      a) starker Dunkelheit
#      b) Unbespielbarkeit des Platzes
#      c) Witterungsbedingungen
#      d) Tätlichkeiten gegen Schiedsrichter oder Assistenten
#      e) Widersetzlichkeiten der Spieler
#      f) bedrohlicher Haltung der Zuschauer, mangelhaftem Ordnungsdienst
#      g) tätlichem Angriff durch Zuschauer gegen Schiedsrichter
#      h) besonders schweren Verletzungen
#
#      „Bei Spielabbrüchen nach a), b) und c) erfolgt Neuansetzung durch den
#       Staffelleiter. In allen anderen Fällen ist durch das zuständige
#       Sportgericht ein Verfahren durchzuführen."
#
#  Der Unterschied entscheidet, was Sie tun müssen — deshalb sind es zwei
#  getrennte Regeln und nicht eine mit einem Fragezeichen.
#
#  § 59 (12): Kam ein Spiel wegen Nichtantretens nicht zur Austragung, sind die
#  Umstände „innerhalb von drei (3) Tagen dem zuständigen Staffelleiter
#  nachzuweisen".
# ═══════════════════════════════════════════════════════════════════════════

# § 61 (3) a) bis c): Neuansetzung durch den Staffelleiter, kein Verfahren.
NEUANSETZUNG = ("dunkelheit", "unbespielbar", "witterung", "platz")

# § 59 (12): Frist für den Nachweis beim Staffelleiter.
NACHWEIS_TAGE = 3


@regel(  # noqa: F821
    id="spielabbruch",
    name="Spielabbruch — Verfahren erforderlich",
    schwere="kritisch",
    weg="sportgericht",
    grund="Spielabbruch",
    paragraf="§ 61 (3) SpO SFV",
    beschreibung="Abbruch aus einem Grund, der ein Sportgerichtsverfahren nach sich zieht.",
)
def spielabbruch_mit_verfahren(spiel, melde):
    # „In allen anderen Fällen ist durch das zuständige Sportgericht ein
    # Verfahren durchzuführen." Kein Ermessen, keine Bagatelle.
    treffer = spiel.vorkommnis_genannt("abbruch")
    if not treffer:
        return
    if IRGENDEINER(  # noqa: F821
        wort in t.lower() for t in treffer for wort in NEUANSETZUNG
    ):
        return  # das meldet die nächste Regel
    melde(
        "Spielabbruch: " + "; ".join(treffer)
        + ". Nach § 61 (3) ist hierzu ein Verfahren beim zuständigen "
        "Sportgericht durchzuführen.",
        vorkommnisse=list(treffer),
    )


@regel(  # noqa: F821
    id="spielabbruch_neuansetzung",
    name="Spielabbruch — Neuansetzung durch Sie",
    schwere="warnung",
    weg="hinweis",
    paragraf="§ 61 (3) SpO SFV",
    beschreibung="Abbruch wegen Dunkelheit, Platz oder Witterung.",
)
def spielabbruch_ohne_verfahren(spiel, melde):
    treffer = spiel.vorkommnis_genannt("abbruch")
    if not treffer:
        return
    harmlos = [
        t for t in treffer
        if IRGENDEINER(wort in t.lower() for wort in NEUANSETZUNG)  # noqa: F821
    ]
    if not harmlos:
        return
    melde(
        "Spielabbruch: " + "; ".join(harmlos)
        + ". Nach § 61 (3) a) bis c) erfolgt die Neuansetzung durch den "
        "Staffelleiter — ein Verfahren ist nicht erforderlich.",
        vorkommnisse=list(harmlos),
    )


@regel(  # noqa: F821
    id="nichtantreten",
    name="Mannschaft nicht angetreten",
    schwere="kritisch",
    weg="sportgericht",
    grund="Nichtantreten",
    paragraf="§ 60 (1) SpO SFV",
    beschreibung="Spielwertung 0:2 und gegebenenfalls ein Verfahren.",
)
def nichtantreten(spiel, melde):
    # § 59 (12): der Verein muss den Grund innerhalb von drei Tagen
    # nachweisen. Bei begründetem Nachweis setzt der Staffelleiter neu an, in
    # allen anderen Fällen führt das Sportgericht ein Verfahren. Beides ist
    # eine Entscheidung des Staffelleiters — die Regel stellt sie ihm, sie
    # trifft sie nicht.
    treffer = spiel.vorkommnis_genannt("nicht angetreten", "nichtantreten")
    if not treffer:
        return
    melde(
        "Nicht angetreten: " + "; ".join(treffer)
        + f". Die Umstände sind innerhalb von {NACHWEIS_TAGE} Tagen "
        "nachzuweisen (§ 59 (12)); ohne begründeten Nachweis führt das "
        "Sportgericht ein Verfahren.",
        vorkommnisse=list(treffer),
        nachweis_tage=NACHWEIS_TAGE,
    )
