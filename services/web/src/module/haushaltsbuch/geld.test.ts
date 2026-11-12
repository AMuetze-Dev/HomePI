import { describe, expect, it } from "vitest";

import {
  abbuchungstext,
  alsEuro,
  alsProzent,
  alsZahl,
  monatswort,
  rhythmus,
} from "./geld";

describe("Beträge", () => {
  it("zeigt Geld auf deutsche Art", () => {
    // Nicht-trennbares Leerzeichen vor dem Euro - deshalb kein Vergleich auf
    // die ganze Zeichenkette mit einem normalen Leerzeichen.
    expect(alsEuro("1133.47")).toMatch(/^1\.133,47\s€$/);
  });

  it("macht aus Unsinn eine Null statt NaN", () => {
    // Ein NaN im Flussbild wäre eine unsichtbare Fläche und kein Fehler.
    expect(alsZahl("keine Zahl")).toBe(0);
    expect(alsEuro("")).toMatch(/0,00/);
  });

  it("schreibt Prozent mit einer Nachkommastelle", () => {
    expect(alsProzent("16.7")).toBe("16,7 %");
  });
});

describe("Rhythmus", () => {
  it("nennt monatlich einfach monatlich", () => {
    expect(rhythmus(1, [1, 2, 3])).toBe("monatlich");
  });

  it("schreibt die Abbuchungsmonate aus", () => {
    // "alle 3 Monate ab Monat 2" steht auf keinem Kontoauszug.
    expect(rhythmus(3, [2, 5, 8, 11])).toBe("vierteljährlich (Feb, Mai, Aug, Nov)");
  });

  it("kommt auch mit einem Intervall zurecht, das kein Name hat", () => {
    expect(rhythmus(4, [1, 5, 9])).toBe("alle 4 Monate (Jan, Mai, Sep)");
  });

  it("nennt den Abbuchungstag nur, wenn es einen gibt", () => {
    expect(abbuchungstext(1)).toBe("zum 1.");
    expect(abbuchungstext(null)).toBe("");
  });
});

describe("Monate", () => {
  it("übersetzt die Zahl in ein Wort", () => {
    expect(monatswort(3)).toBe("März");
  });

  it("zeigt bei einer unmöglichen Zahl einen Strich statt undefined", () => {
    expect(monatswort(0)).toBe("—");
    expect(monatswort(13)).toBe("—");
  });
});
