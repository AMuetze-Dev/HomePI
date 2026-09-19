# ═══════════════════════════════════════════════════════════════════════════
#  Altersklassen — wer in einer Ü-Staffel spielen darf
#  Grundlage: § 42 (2) Spielordnung SFV
#
#  DIESE DATEI DARF GEÄNDERT WERDEN. Sie gehört Ihnen, nicht dem Programm.
#  Ein Update von StaffelPilot fasst sie nicht an.
#
#  Aufbau einer Regel:
#
#      @regel(
#          id="kurz_und_technisch",        # Schlüssel, ändert sich nie
#          name="Was der Nutzer liest",    # frei, Leerzeichen erlaubt
#          schwere="warnung",              # hinweis | warnung | kritisch
#          weg="mahnung",                  # hinweis | mahnung | sportgericht | beides
#          bagatelle="Ordnungsdienst",     # nur bei weg="mahnung"
#          paragraf="§ 42 (2) SpO SFV",
#      )
#      def lesbarer_funktionsname(spiel, melde):
#          if <etwas stimmt nicht>:
#              melde("Text für den Staffelleiter", person="…", mannschaft="…")
#
#  `id=` darf weggelassen werden — dann wird eine aus dem Namen gebildet.
#  Für eigene Regeln bequem; hier steht sie ausdrücklich, damit ein neuer Name
#  keine bereits gespeicherten Befunde entwertet.
#
#  Es muss nichts importiert werden. `regel`, `melde`, `ANZAHL`, `SUMME`,
#  `SORTIERT` und `date` sind da.
#
#  Stolpert eine Regel, wird nur sie ausgesetzt — mit einem sichtbaren Befund
#  am Spiel. Alle anderen laufen weiter.
#
#  Vokabeln: docs/regelwerk-vokabeln.md
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────
#  DIE ZAHLEN IHRES KREISVERBANDES
#
#  Bis zum 06.09.2026 standen sie in der Staffelverwaltung. Das war der
#  falsche Ort: es sind keine Angaben zur Staffel wie die Sportrichter-Mail,
#  sondern die Regel selbst. Hier stehen sie neben dem Satz, den sie umsetzen.
#
#  § 42 (2) SpO: "A-Senioren (Ü 35) sind Spieler, die das 35. Lebensjahr
#  vollendet haben oder älter. Die Kreisverbände können bzgl. der
#  Altersuntergrenze andere Regelungen treffen, wobei das Mindestalter
#  32 Jahre betragen muss." Für Ü40 sind es 38, Ü50 → 48, Ü60 → 58, Ü70 → 68.
#
#  Die Tabelle sagt: ab welchem Alter darf in dieser Altersklasse überhaupt
#  gespielt werden. Nutzt Ihr Kreis die Ausnahme nicht, tragen Sie die
#  Altersklasse selbst ein (Ü35: 35) oder nehmen die Zeile heraus.
# ─────────────────────────────────────────────────────────────────────────

UNTERGRENZEN = {
    35: 32,     # Ü35 — Kreis Dresden nutzt die Ausnahme, Mindestalter 32
    40: 38,
    50: 48,
    60: 58,
    70: 68,
}

#: Wie viele Spieler unter dem Altersband je Mannschaft zugelassen sind.
#: 0 heißt: gar keine, dann ist jeder darunter ein Fall für `altersklasse_zu_jung`.
#:
#: ACHTUNG, diese Zahl steht in KEINER Vorschrift. § 42 (2) SpO SFV erlaubt dem
#: Kreisverband, die Altersuntergrenze zu senken — wie viele Spieler er darunter
#: zulässt, sagt die Spielordnung nicht. Im ganzen Text kommt „maximal zwei"
#: genau einmal vor, und zwar in § 68 (2) b) bei den Stammspielern: eine andere
#: Regelung, ein anderer Sachverhalt.
#:
#: Fragen Sie also bei Ihrem Kreisverband nach und tragen Sie hier ein, was er
#: sagt. Für den Kreis Dresden hat der Vorsitzende des Stadtverbands
#: am 06.09.2026 mündlich bestätigt: drei. Eine schriftliche Fundstelle
#: dafür gibt es nicht.
HOECHSTENS_UNTER_DEM_BAND = 3


def untergrenze_fuer(band):
    """Ab welchem Alter in dieser Altersklasse gespielt werden darf.

    Ohne Eintrag gilt die Altersklasse selbst — eine unbekannte Klasse soll
    nicht auf 0 fallen und jeden zulassen.
    """
    return UNTERGRENZEN.get(band, band)


@regel(  # noqa: F821 - vom Lader gestellt
    id="geburtsdatum_unplausibel",
    name="Geburtsdatum liegt in der Zukunft",
    schwere="warnung",
    weg="hinweis",
    paragraf="—",
    beschreibung="Vermutlich ein Tippfehler in DFBnet, kein Regelverstoß.",
)
def geburtsdatum_pruefen(spiel, melde):
    # Vor allen Altersregeln: ein Datum in der Zukunft würde sonst als
    # "-4 Jahre alt, mindestens 35 nötig" gemeldet. Das schickt den
    # Staffelleiter zum Spieler statt zum Datum.
    for elf in spiel.mannschaften:
        for spieler in elf.spieler:
            if not spieler.geburtsdatum_plausibel:
                melde(
                    f"{spieler.name} hat als Geburtsdatum {spieler.geburtsdatum} — "
                    "das liegt in der Zukunft.",
                    person=spieler.name,
                    mannschaft=elf.name,
                    pass_nr=spieler.pass_nr,
                )


@regel(  # noqa: F821
    id="altersklasse_zu_jung",
    name="Spieler unterschreitet das Mindestalter",
    schwere="kritisch",
    weg="sportgericht",
    grund="Einsatz unterhalb der Altersklasse",
    paragraf="§ 42 (2) SpO SFV",
    beschreibung="Unter der Altersuntergrenze der Ü-Staffel eingesetzt.",
)
def mindestalter(spiel, melde):
    # Die Untergrenze steht oben in dieser Datei, nicht in der
    # Staffelverwaltung: § 42 (2) überlässt sie dem Kreisverband, und damit
    # ist sie Teil der Regel und keine Angabe zur Staffel.
    grenze = spiel.staffel.mindestalter
    if grenze is None:
        return  # Herren oder Frauen: keine untere Altersgrenze

    untergrenze = untergrenze_fuer(grenze)

    for elf in spiel.mannschaften:
        for spieler in elf.spieler:
            if spieler.alter is None or not spieler.geburtsdatum_plausibel:
                continue
            if spieler.alter < untergrenze:
                melde(
                    f"{spieler.name} ({spieler.pass_nr}) ist {spieler.alter} Jahre alt — "
                    f"für Ü{grenze} sind mindestens {untergrenze} Jahre erforderlich.",
                    person=spieler.name,
                    mannschaft=elf.name,
                    pass_nr=spieler.pass_nr,
                    alter=spieler.alter,
                    mindestalter=grenze,
                    untergrenze=untergrenze,
                )


@regel(  # noqa: F821
    id="ue32_limit",
    name="Zu viele Spieler unter dem Altersband",
    schwere="warnung",
    weg="sportgericht",
    grund="Ü32-Obergrenze überschritten",
    # § 42 (2) trägt das Ausnahmeband, nicht die Höchstzahl — die steht in
    # keiner Vorschrift und kommt vom Kreisverband. Der Zusatz sagt das, damit
    # ein Sportgerichtsantrag nichts behauptet, was im Paragrafen nicht steht.
    paragraf="§ 42 (2) SpO SFV i. V. m. der Regelung des Kreisverbandes",
    beschreibung=(
        "Mehr Spieler im Ausnahmeband als der Kreisverband zulässt. Die "
        "Höchstzahl steht oben in dieser Datei; die Spielordnung nennt keine."
    ),
)
def ausnahmeband_obergrenze(spiel, melde):
    # Gezählt wird, wer unter dem Band der Staffel liegt, aber die
    # Untergrenze erreicht. Wer noch jünger ist, ist gar nicht spielberechtigt
    # und steht bereits oben — hier doppelt zu melden wäre derselbe Vorwurf
    # zweimal.
    grenze = spiel.staffel.mindestalter
    if grenze is None:
        return

    untergrenze = untergrenze_fuer(grenze)
    erlaubt = HOECHSTENS_UNTER_DEM_BAND

    # Kein Ausnahmeband: dann gibt es hier nichts zu zählen — wer darunter
    # liegt, steht bereits bei `altersklasse_zu_jung`.
    if untergrenze >= grenze:
        return

    for elf in spiel.mannschaften:
        ausnahmen = [
            f"{s.name} ({s.alter})"
            for s in elf.spieler
            if s.alter is not None and untergrenze <= s.alter < grenze
        ]
        if ANZAHL(ausnahmen) > erlaubt:  # noqa: F821
            melde(
                f"{ANZAHL(ausnahmen)} Spieler unter Ü{grenze} im Kader, "  # noqa: F821
                f"erlaubt sind {erlaubt} — {', '.join(SORTIERT(ausnahmen))}.",  # noqa: F821
                mannschaft=elf.name,
                anzahl=ANZAHL(ausnahmen),  # noqa: F821
                limit=erlaubt,
                spieler=SORTIERT(ausnahmen),  # noqa: F821
                mindestalter=grenze,
            )


# § 42 (2), letzter Satz: "Die Teilnahme am Spielbetrieb der jüngeren
# Altersklassen ist möglich."
#
# Ein Ü50-Spieler in einer Ü35-Staffel ist also ausdrücklich zulässig. Es gibt
# hier bewusst KEINE Obergrenze — wer eine einbaut, meldet in jeder
# Ü35-Mannschaft die Hälfte der Elf.
