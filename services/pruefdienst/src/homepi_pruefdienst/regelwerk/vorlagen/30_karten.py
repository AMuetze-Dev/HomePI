# ═══════════════════════════════════════════════════════════════════════════
#  § 58 SpO SFV — Verwarnungen und Spielsperren
#
#  DIESE DATEI DARF GEÄNDERT WERDEN. Sie gehört Ihnen, nicht dem Programm.
#
#  Die vier Stellen, an denen man sich hier verrechnet:
#
#  1. Die gelbe Karte DESSELBEN Spiels ist verbraucht, wenn es zusätzlich
#     Gelb-Rot (§ 58 (1) c) oder Rot (§ 58 (2) d) gab. Sie zählt nicht mit.
#  2. Pokal und übrige Pflichtspiele werden GETRENNT gezählt (§ 58 (2)).
#  3. Nach jeder verwirkten Sperre beginnt der Zähler bei null. Es sind immer
#     „5 weitere", nicht die absoluten Schwellen 5/10/15 (§ 58 (2) b).
#  4. Im Pokal ist es die ZWEITE Verwarnung, nicht die fünfte (§ 58 (2) c).
#
#  Zahlen zum Anpassen stehen unten als Konstanten.
# ═══════════════════════════════════════════════════════════════════════════

# § 58 (2) a): die 5. Verwarnung in Meisterschafts-, Aufstiegs- oder
# Entscheidungsspielen.
VERWARNUNGEN_MEISTERSCHAFT = 5

# § 58 (2) c): die 2. Verwarnung in Pokalspielen und Meisterschaftsturnieren.
VERWARNUNGEN_POKAL = 2

# § 58 (1) b): Sperre in anderen Mannschaften des Vereins „längstens bis zum
# Ablauf von 10 Tagen".
SPERRE_ANDERE_MANNSCHAFTEN_TAGE = 10


def _verwarnt_heute(person):
    """Hat diese Person in diesem Spiel eine Verwarnung erhalten, die zählt?

    § 58 (1) c) und (2) d): bei Gelb-Rot oder Rot im selben Spiel gilt die
    gelbe Karte als verbraucht und wird nicht registriert. Dann löst sie auch
    keine Sperre aus, und der Zähler steht danach so wie vorher.
    """
    if IRGENDEINER(k.ist_gelb_rot or k.ist_rot for k in person.karten):  # noqa: F821
        return False
    return IRGENDEINER(k.ist_gelb for k in person.karten)  # noqa: F821


@regel(  # noqa: F821
    id="verwarnung_fuenf",
    name="Fünfte Verwarnung — Sperre",
    schwere="warnung",
    weg="hinweis",
    paragraf="§ 58 (2) a) SpO SFV",
    beschreibung="Die 5. Verwarnung sperrt für das nächste Meisterschaftsspiel.",
)
def fuenfte_verwarnung(spiel, melde):
    # Gemeldet wird nur, wenn die Verwarnung HEUTE fiel. Der Zähler steht auch
    # nächste Woche noch auf fünf — die Sperre dort erneut zu melden hieße, sie
    # bis zum Saisonende jede Woche zu melden.
    if spiel.wettbewerbskategorie != "Meisterschaft":
        return
    for elf in spiel.mannschaften:
        for person in elf.alle_personen:
            if not _verwarnt_heute(person):
                continue
            anzahl = person.verwarnungen_seit_sperre()
            if anzahl is None or anzahl < VERWARNUNGEN_MEISTERSCHAFT:
                continue
            melde(
                f"{person.name} hat die {anzahl}. Verwarnung erhalten und ist "
                "für das nächste Meisterschafts-, Aufstiegs- oder "
                "Entscheidungsspiel dieser Mannschaft gesperrt.",
                person=person.name,
                mannschaft=elf.name,
                pass_nr=person.pass_nr,
                verwarnungen=anzahl,
            )


@regel(  # noqa: F821
    id="verwarnung_pokal_zwei",
    name="Zweite Verwarnung im Pokal — Sperre",
    schwere="warnung",
    weg="hinweis",
    paragraf="§ 58 (2) c) SpO SFV",
    beschreibung="Im Pokal sperrt bereits die 2. Verwarnung.",
)
def zweite_verwarnung_pokal(spiel, melde):
    if spiel.wettbewerbskategorie not in ("Pokal", "Turnier"):
        return
    for elf in spiel.mannschaften:
        for person in elf.alle_personen:
            if not _verwarnt_heute(person):
                continue
            anzahl = person.verwarnungen_seit_sperre()
            if anzahl is None or anzahl < VERWARNUNGEN_POKAL:
                continue
            melde(
                f"{person.name} hat die {anzahl}. Verwarnung in diesem "
                "Wettbewerb erhalten und ist für das nächste Spiel des Pokals "
                "bzw. des Turniers gesperrt.",
                person=person.name,
                mannschaft=elf.name,
                pass_nr=person.pass_nr,
                verwarnungen=anzahl,
            )


@regel(  # noqa: F821
    id="verwarnungszaehler_fehlt",
    name="Verwarnungszähler nicht verfügbar",
    schwere="warnung",
    weg="hinweis",
    paragraf="§ 58 (2) SpO SFV",
    beschreibung="Ohne Zähler lässt sich die 5. Verwarnung nicht feststellen.",
)
def zaehler_fehlt(spiel, melde):
    # Der wichtigste Befund dieser Datei: er sagt, dass NICHT geprüft wurde.
    # Ohne ihn sähe ein Spiel mit einer Verwarnung ohne Zählerstand genauso aus
    # wie eines, in dem alles in Ordnung ist.
    #
    # Betreuer haben in DFBnet keine Passnummer, und der Zähler hängt daran.
    # Auch das gehört gesagt: § 58 nennt sie gleichrangig mit Spielern.
    for elf in spiel.mannschaften:
        for person in elf.alle_personen:
            if not _verwarnt_heute(person):
                continue
            if person.verwarnungen_seit_sperre() is not None:
                continue
            grund = (
                "keine Passnummer im Spielbericht"
                if not person.pass_nr
                else "der Verwarnungszähler ist nicht verfügbar"
            )
            melde(
                f"{person.name} wurde verwarnt, aber {grund} — ob damit eine "
                "Sperre ausgelöst wurde, konnte nicht geprüft werden.",
                person=person.name,
                mannschaft=elf.name,
                pass_nr=person.pass_nr,
            )


@regel(  # noqa: F821
    id="red_card",
    name="Feldverweis auf Dauer",
    schwere="kritisch",
    weg="sportgericht",
    grund="Feldverweis auf Dauer",
    paragraf="§ 58 (5) SpO SFV",
    beschreibung="Rote Karte — dafür ist stets das Sportgericht zuständig.",
)
def rote_karte(spiel, melde):
    for elf in spiel.mannschaften:
        for person in elf.alle_personen:
            for karte in person.karten:
                if not karte.ist_rot:
                    continue
                minute = f" in Minute {karte.minute}" if karte.minute else ""
                grund = f" — {karte.grund}" if karte.grund else ""
                melde(
                    f"Feldverweis auf Dauer gegen {person.name}{minute}{grund}. "
                    "Für die Sperrstrafe ist das Sportgericht zuständig.",
                    person=person.name,
                    mannschaft=elf.name,
                    minute=karte.minute,
                    kartengrund=karte.grund,
                )


@regel(  # noqa: F821
    id="yellow_red_card",
    name="Gelb-Rote Karte",
    schwere="warnung",
    weg="hinweis",
    paragraf="§ 58 (1) b) SpO SFV",
    beschreibung="Sperre für das nächste Pflichtspiel derselben Kategorie.",
)
def gelb_rote_karte(spiel, melde):
    # Kein Verstoß des Vereins, sondern eine Folge, die der Staffelleiter im
    # Blick behalten muss — und zwar in zwei Richtungen: die Mannschaft selbst
    # und jede andere Mannschaft desselben Vereins.
    for elf in spiel.mannschaften:
        for person in elf.alle_personen:
            for karte in person.karten:
                if not karte.ist_gelb_rot:
                    continue
                minute = f" in Minute {karte.minute}" if karte.minute else ""
                melde(
                    f"Gelb-Rote Karte gegen {person.name}{minute} — gesperrt "
                    "für das nächste Pflichtspiel dieser Wettbewerbskategorie "
                    "und für das nächstfolgende Spiel jeder anderen Mannschaft "
                    f"des Vereins, dort längstens {SPERRE_ANDERE_MANNSCHAFTEN_TAGE} Tage.",
                    person=person.name,
                    mannschaft=elf.name,
                    minute=karte.minute,
                    sperre_tage=SPERRE_ANDERE_MANNSCHAFTEN_TAGE,
                )
