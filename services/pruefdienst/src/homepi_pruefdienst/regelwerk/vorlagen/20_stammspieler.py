# ═══════════════════════════════════════════════════════════════════════════
#  § 68 SpO SFV — Stammspieler, Wartefrist und die U23-Ausnahme
#
#  Die drei Absätze im Klartext:
#
#  (2) a)  Wartefrist 5 Tage nach einem Einsatz in einer höherklassigen
#          Mannschaft. "Der dem Spieltag folgende Tag ist der erste Tag der
#          Wartefrist" — der Einsatztag selbst zählt also nicht mit.
#
#  (2) b)  Höchstens zwei Stammspieler einer höherklassigen Mannschaft
#          derselben Altersklasse. Stammspieler ist, wer nach dem fünften
#          Pflichtspiel jener Mannschaft in mindestens 50 % ihrer Spiele
#          eingesetzt war. Vorher gibt es keine Stammspieler.
#
#  (2) c)  Beides gilt nicht für Spieler, die am 1. Juli das 23. Lebensjahr
#          noch nicht vollendet hatten — AUSSER an den letzten vier Spieltagen
#          der unterklassigen Mannschaft, also dieser Staffel.
#
#  Anpassbar ohne Programmänderung: die Zahlen 5 (Tage), 2 (Stammspieler),
#  4 (Spieltage), 23 (Alter) stehen unten als Konstanten.
# ═══════════════════════════════════════════════════════════════════════════

# § 68 (2) a) aa) — für Kreis und Land einheitlich.
#: § 68 (2) b): "Es dürfen höchstens zwei Stammspieler einer höherklassigen
#: Mannschaft eingesetzt werden." Stand bis zum 06.09.2026 in der
#: Staffelverwaltung — eine Zahl, die die Spielordnung vorgibt, gehört nicht
#: in die Einstellungen einer einzelnen Staffel.
HOECHSTENS = 2

WARTEFRIST_TAGE = 5

# § 68 (2) c) — die letzten vier Spieltage der unterklassigen Mannschaft.
LETZTE_SPIELTAGE = 4

# § 68 (2) c) — "das 23. Lebensjahr am 1. Juli noch nicht vollendet".
U23_ALTER = 23


def _u23_ausnahme_gilt(spiel, spieler):
    """Ob dieser Spieler von Wartefrist und Obergrenze befreit ist.

    Zwei Bedingungen, und beide sind leicht falsch zu treffen:

    * Das Alter zählt am 1. Juli, nicht am Spieltag. Wer im Oktober 23 wird,
      ist die ganze Saison über U23.
    * An den letzten vier Spieltagen entfällt die Ausnahme. Ist die Zahl der
      Spieltage nicht bekannt, lässt sich das nicht feststellen — dann gilt
      die Ausnahme weiter, und die Regel `spieltage_unbekannt` sagt, dass hier
      etwas ungeprüft blieb. Stillschweigend aufzuheben wäre die schlechtere
      Hälfte: es sähe aus wie eine Prüfung.
    """
    if spieler.alter_am_1_juli is None or spieler.alter_am_1_juli >= U23_ALTER:
        return False
    rest = spiel.spieltage_bis_ende
    if rest is not None and rest <= LETZTE_SPIELTAGE:
        return False
    return True


@regel(  # noqa: F821
    id="spieltage_unbekannt",
    name="Anzahl der Spieltage fehlt",
    schwere="warnung",
    weg="hinweis",
    paragraf="§ 68 (2) c) SpO SFV",
    beschreibung="Ohne Saisonlänge lässt sich die U23-Ausnahme nicht aufheben.",
)
def spieltage_fehlen(spiel, melde):
    # In einer Ü-Staffel ist der jüngste zulässige Spieler 32 — die
    # U23-Ausnahme kann dort nie greifen, und die Saisonlänge wird nicht
    # gebraucht. Dort danach zu fragen war Rauschen in jedem einzelnen Spiel.
    if spiel.staffel.ist_ue or not spiel.spieltag:
        return
    if not spiel.staffel.spieltage:
        melde(
            "Anzahl der Spieltage ist für diese Staffel nicht hinterlegt. Die "
            "U23-Ausnahme kann an den letzten vier Spieltagen nicht aufgehoben "
            "werden — in der Staffelverwaltung „Initialisieren“ holt die Zahl.",
            spieltag=spiel.spieltag,
        )


@regel(  # noqa: F821
    id="stammspieler_wartefrist",
    name="Einsatz vor Ablauf der Wartefrist",
    schwere="kritisch",
    weg="sportgericht",
    grund="Einsatz trotz Wartefrist",
    paragraf="§ 68 (2) a) SpO SFV",
    beschreibung="Einsatz vor Ablauf der Wartefrist nach einem Spiel oben.",
)
def wartefrist(spiel, melde):
    for elf in spiel.mannschaften:
        if not elf.hoehere:
            continue  # ohne bekannte höhere Mannschaften nichts zu vergleichen
        for spieler in elf.spieler:
            # § 68 (2) a) spricht vom „Einsatz". Wer auf der Bank sitzt und
            # nicht kommt, ist nicht eingesetzt — die Regel greift erst mit
            # der Einwechslung. (Gemeldet am 06.09.2026 zu SG Weixdorf 3 –
            # Dresdner SC 1898 3.)
            if not spieler.wurde_eingesetzt:
                continue
            tage = spieler.tage_seit_einsatz_bei(elf.hoehere)
            if tage is None or tage > WARTEFRIST_TAGE:
                continue
            if _u23_ausnahme_gilt(spiel, spieler):
                continue
            letzter = spieler.letzter_einsatz_bei(elf.hoehere)
            melde(
                f"{spieler.name} spielte am {letzter:%d.%m.%Y} in einer höheren "
                f"Mannschaft — das sind {tage} Tage, die Wartefrist beträgt "
                f"{WARTEFRIST_TAGE} Tage.",
                person=spieler.name,
                mannschaft=elf.name,
                pass_nr=spieler.pass_nr,
                tage=tage,
                wartefrist=WARTEFRIST_TAGE,
                letzter_einsatz=str(letzter),
            )


@regel(  # noqa: F821
    id="stammspieler_limit",
    name="Zu viele Stammspieler eingesetzt",
    schwere="kritisch",
    weg="sportgericht",
    grund="Mehr als zwei Stammspieler eingesetzt",
    paragraf="§ 68 (2) b) SpO SFV",
    beschreibung="Obergrenze für Stammspieler höherklassiger Mannschaften.",
)
def stammspieler_obergrenze(spiel, melde):
    # Wichtig: das Kennzeichen "Stammspieler" an einer Person ist KEIN Verstoß.
    # Es sagt nur, dass für sie eine Obergrenze gilt. Ein Befund entsteht erst,
    # wenn mehr als `HOECHSTENS` von ihnen aufgestellt wurden — jede einzelne
    # zu melden war der größte Posten an Falschbefunden.
    grenze = HOECHSTENS
    for elf in spiel.mannschaften:
        if not elf.hoehere:
            continue
        # Gerechnet nach § 68 (2) b), nicht am DFBnet-Kennzeichen abgelesen:
        # das Kennzeichen sagt nicht, für welche Mannschaft es gilt, und die
        # Obergrenze gilt je höherklassiger Mannschaft.
        betroffen = [
            s for s in elf.spieler
            # § 68 (2) b): „dürfen maximal zwei Stammspieler … eingesetzt
            # werden". Wer nicht gespielt hat, zählt nicht mit.
            if s.wurde_eingesetzt
            and s.ist_stammspieler_bei(elf.hoehere)
            and not _u23_ausnahme_gilt(spiel, s)
        ]
        if ANZAHL(betroffen) <= grenze:  # noqa: F821
            continue
        namen = SORTIERT(s.name for s in betroffen)  # noqa: F821
        melde(
            f"{ANZAHL(betroffen)} Stammspieler höherklassiger Mannschaften "  # noqa: F821
            f"eingesetzt, erlaubt sind {grenze} — {', '.join(namen)}.",
            mannschaft=elf.name,
            anzahl=ANZAHL(betroffen),  # noqa: F821
            limit=grenze,
            spieler=namen,
        )
