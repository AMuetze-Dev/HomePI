import { describe, expect, it } from "vitest";

import { einrueckung, zeilen, zerlege } from "./quelltext";

/**
 * Der Einfärber für Regeldateien.
 *
 * Er versteht Python **nicht**, er erkennt es nur — das reicht zum Einfärben
 * und ist ausdrücklich keine Prüfung. Ob eine Datei lädt, sagt der Prüfdienst.
 *
 * Geprüft wird an dem, was wirklich in Regeldateien steht.
 */

/** Wie eine echte Regel anfängt. */
const ECHTE_REGEL = `@regel("spielerfoto_fehlt", "Spielerfoto fehlt")
def pruefe(spiel, melde):
    # Ohne Lichtbild ist die Spielberechtigung nicht überprüfbar.
    for person in spiel.alle_spieler:
        if not person.hat_foto:
            melde("Kein Foto hinterlegt.", person=person.name)
`;

function texte(quelltext: string, art: string): string[] {
  return zerlege(quelltext)
    .filter((s) => s.art === art)
    .map((s) => s.text);
}

describe("Quelltext zerlegen", () => {
  it("setzt die Stücke lückenlos wieder zusammen", () => {
    // Die eine Zusicherung, die alles trägt: der Editor zeigt die Stücke
    // nebeneinander. Fehlt eines oder steht eines doppelt, weicht die Farbe
    // vom Text darunter ab — und die Schreibmarke steht woanders als der
    // Buchstabe.
    expect(
      zerlege(ECHTE_REGEL)
        .map((s) => s.text)
        .join(""),
    ).toBe(ECHTE_REGEL);
  });

  it("erkennt den Dekorator über jeder Prüfung", () => {
    expect(texte(ECHTE_REGEL, "dekorator")).toEqual(["@regel"]);
  });

  it("erkennt Schlüsselwörter", () => {
    expect(texte(ECHTE_REGEL, "schluessel")).toEqual(["def", "for", "in", "if", "not"]);
  });

  it("erkennt die gestellten Namen", () => {
    // `regel`, `melde`, `spiel` stehen in keinem import -- der Lader stellt
    // sie. Genau deshalb lohnt es sich, sie zu zeigen.
    expect(texte(ECHTE_REGEL, "eingebaut")).toContain("spiel");
    expect(texte(ECHTE_REGEL, "eingebaut")).toContain("melde");
  });

  it("nimmt den Kommentar bis zum Zeilenende, nicht weiter", () => {
    const stuecke = zerlege("a = 1  # hallo\nb = 2\n");

    expect(texte("a = 1  # hallo\nb = 2\n", "kommentar")).toEqual(["# hallo"]);
    expect(stuecke.map((s) => s.text).join("")).toBe("a = 1  # hallo\nb = 2\n");
  });

  it("hält ein Doppelkreuz in einer Zeichenkette für Text", () => {
    expect(texte('melde("# kein Kommentar")', "kommentar")).toEqual([]);
  });

  it("erkennt dreifache Anführungszeichen über mehrere Zeilen", () => {
    // Sonst endet """ sofort nach dem ersten Anführungszeichen, und der Rest
    // der Datei wäre Text.
    const quelle = 'def f():\n    """Erklärt,\n    was sie tut.\n    """\n    pass\n';

    expect(texte(quelle, "zeichenkette")).toEqual(['"""Erklärt,\n    was sie tut.\n    """']);
  });

  it("lässt eine einfache Zeichenkette am Zeilenende enden", () => {
    // Ein vergessenes Anführungszeichen färbt sonst die halbe Datei.
    const quelle = 'melde("offen\nspiel = 1\n';

    expect(texte(quelle, "zeichenkette")).toEqual(['"offen']);
    expect(texte(quelle, "eingebaut")).toContain("spiel");
  });

  it("macht aus regel2 keine 2", () => {
    // Wörter vor Zahlen: sonst zerfällt jeder Name mit Ziffer.
    expect(texte("regel2 = 1", "zahl")).toEqual(["1"]);
  });

  it("erkennt Zahlen mit Punkt", () => {
    expect(texte("quote = 0.5", "zahl")).toEqual(["0.5"]);
  });

  it("kommt mit leerem Text zurecht", () => {
    expect(zerlege("")).toEqual([]);
  });

  it("lässt einen maskierten Anführungsstrich die Zeichenkette nicht beenden", () => {
    expect(texte('melde("sagte \\"nein\\" dazu")', "zeichenkette")).toEqual([
      '"sagte \\"nein\\" dazu"',
    ]);
  });
});

describe("Zeilen zählen", () => {
  it("eine leere Datei hat eine Zeile", () => {
    expect(zeilen("")).toBe(1);
  });

  it("drei Zeilen sind drei", () => {
    expect(zeilen("a\nb\nc")).toBe(3);
  });

  it("ein Zeilenumbruch am Ende zählt die leere Zeile mit", () => {
    // Der Editor zeigt sie, also muss die Leiste eine Nummer dafür haben.
    expect(zeilen("a\n")).toBe(2);
  });
});

describe("Einrückung", () => {
  it("hält die Tiefe der laufenden Zeile", () => {
    const quelle = "def f():\n    melde(1)";

    expect(einrueckung(quelle, quelle.length)).toBe("    ");
  });

  it("geht nach einem Doppelpunkt eine Stufe tiefer", () => {
    // In Python ist das keine Bequemlichkeit, sondern die Bedeutung: ein
    // Editor, der nach `if ...:` in Spalte 1 weitermacht, ist unbenutzbar.
    const quelle = "def f():";

    expect(einrueckung(quelle, quelle.length)).toBe("    ");
  });

  it("geht aus vier Leerzeichen und Doppelpunkt auf acht", () => {
    const quelle = "def f():\n    if wahr:";

    expect(einrueckung(quelle, quelle.length)).toBe("        ");
  });

  it("bleibt am Anfang bei nichts", () => {
    expect(einrueckung("melde(1)", 8)).toBe("");
  });
});
