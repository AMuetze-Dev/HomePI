import { describe, expect, it } from "vitest";

import { anfangDerBewegung, zieltAuf } from "./zielen";

describe("Woher die letzte Bewegung kam", () => {
  it("nimmt den ältesten Punkt der letzten 150 ms", () => {
    const spur = [
      { x: 0, y: 0, t: 0 },
      { x: 10, y: 0, t: 900 },
      { x: 20, y: 0, t: 950 },
      { x: 30, y: 0, t: 1000 },
    ];
    expect(anfangDerBewegung(spur)).toEqual({ x: 10, y: 0, t: 900 });
  });

  it("nimmt den vorigen Punkt, wenn der Zeiger lange stand", () => {
    // Ein Punkt von vor einer Sekunde sagt nichts mehr über die Richtung -
    // aber der unmittelbar vorige sagt, woher er gerade kam.
    const spur = [
      { x: 300, y: 0, t: 0 },
      { x: 10, y: 0, t: 2000 },
      { x: 20, y: 0, t: 3000 },
    ];
    expect(anfangDerBewegung(spur)).toEqual({ x: 10, y: 0, t: 2000 });
  });

  it("hat keinen Anfang bei einem einzigen Punkt", () => {
    expect(anfangDerBewegung([{ x: 1, y: 1, t: 0 }])).toBeUndefined();
  });
});

/* Die rechte Spalte beginnt bei x = 400 und reicht von y = 100 bis 500. */
const spalte = { links: 400, oben: 100, unten: 500 };

describe("Zielt der Zeiger auf die Bereiche?", () => {
  it("ja, wenn er schräg nach rechts unten auf die Spalte zuläuft", () => {
    // Von "StaffelPilot" hinunter zu einem Bereich weiter unten: Unterwegs
    // streift er "Haushaltsbuch" - das darf die Spalte nicht umschlagen.
    expect(zieltAuf({ x: 100, y: 200 }, { x: 140, y: 215 }, spalte)).toBe(true);
  });

  it("ja, auch schräg nach rechts oben", () => {
    expect(zieltAuf({ x: 100, y: 400 }, { x: 140, y: 380 }, spalte)).toBe(true);
  });

  it("nein, wenn er in der Liste senkrecht nach unten läuft", () => {
    // Wer von Eintrag zu Eintrag geht, will das nächste Artefakt sehen.
    expect(zieltAuf({ x: 100, y: 200 }, { x: 101, y: 240 }, spalte)).toBe(false);
  });

  it("nein, wenn er nach links zurückgeht", () => {
    expect(zieltAuf({ x: 140, y: 200 }, { x: 100, y: 210 }, spalte)).toBe(false);
  });

  it("nein, wenn er an der Spalte vorbei nach unten zielt", () => {
    // Steil nach unten, flacher als die untere Kante: das Ziel liegt
    // unterhalb der Spalte.
    expect(zieltAuf({ x: 100, y: 200 }, { x: 110, y: 300 }, spalte)).toBe(false);
  });

  it("nein, wenn er sich nicht bewegt hat", () => {
    expect(zieltAuf({ x: 100, y: 200 }, { x: 100, y: 200 }, spalte)).toBe(false);
  });
});
