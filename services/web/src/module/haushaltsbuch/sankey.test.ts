import { describe, expect, it } from "vitest";

import type { Flussbild, Knoten, Knotenart } from "./api";
import { baueFlussbild, KNOTEN_BREITE } from "./sankey";

function knoten(
  id: string,
  ebene: number,
  betrag: string,
  art: Knotenart = "konto",
): Knoten {
  return { id, beschriftung: id, art, ebene, betrag };
}

/** Gehalt → Konto → zwei Kategorien. */
const BILD: Flussbild = {
  ebenen: 3,
  knoten: [
    knoten("sold", 0, "1000.00", "einnahme"),
    knoten("konto", 1, "1000.00"),
    knoten("wohnen", 2, "750.00", "kategorie"),
    knoten("konsum", 2, "250.00", "kategorie"),
  ],
  fluesse: [
    { von: "sold", nach: "konto", betrag: "1000.00" },
    { von: "konto", nach: "wohnen", betrag: "750.00" },
    { von: "konto", nach: "konsum", betrag: "250.00" },
  ],
};

describe("Flussbild", () => {
  it("gibt für einen leeren Haushalt nichts zurück statt zu rechnen", () => {
    const leer = baueFlussbild({ knoten: [], fluesse: [], ebenen: 0 });

    expect(leer.plaetze).toEqual([]);
    expect(leer.hoehe).toBe(0);
  });

  it("setzt jede Ebene in eine eigene Spalte", () => {
    const aufbau = baueFlussbild(BILD);
    const x = new Map(aufbau.plaetze.map((p) => [p.id, p.x]));

    expect(x.get("sold")).toBeLessThan(x.get("konto") ?? 0);
    expect(x.get("konto")).toBeLessThan(x.get("wohnen") ?? 0);
    expect(x.get("wohnen")).toBe(x.get("konsum"));
  });

  it("macht den größeren Betrag zum höheren Balken", () => {
    const aufbau = baueFlussbild(BILD);
    const hoehe = new Map(aufbau.plaetze.map((p) => [p.id, p.hoehe]));

    // 750 zu 250 - das Verhältnis ist die ganze Aussage eines Sankey.
    expect((hoehe.get("wohnen") ?? 0) / (hoehe.get("konsum") ?? 1)).toBeCloseTo(3, 1);
  });

  it("stapelt eine Spalte ohne Überlappung", () => {
    const aufbau = baueFlussbild(BILD);
    const wohnen = aufbau.plaetze.find((p) => p.id === "wohnen");
    const konsum = aufbau.plaetze.find((p) => p.id === "konsum");

    expect(wohnen).toBeDefined();
    expect(konsum).toBeDefined();
    const [oben, unten] = [wohnen!, konsum!].sort((a, b) => a.y - b.y);
    expect(oben!.y + oben!.hoehe).toBeLessThanOrEqual(unten!.y);
  });

  it("zieht für jeden Fluss ein Band von links nach rechts", () => {
    const aufbau = baueFlussbild(BILD);

    expect(aufbau.baender).toHaveLength(3);
    for (const band of aufbau.baender) {
      const von = aufbau.plaetze.find((p) => p.id === band.von.id);
      expect(band.pfad.startsWith(`M${(von?.x ?? 0) + KNOTEN_BREITE},`)).toBe(true);
    }
  });

  it("überspringt einen Fluss, dessen Knoten es nicht gibt", () => {
    // Das Backend liefert so etwas nicht - aber ein halb geladenes Bild darf
    // die Seite nicht mit einem Fehler abräumen.
    const kaputt: Flussbild = {
      ...BILD,
      fluesse: [...BILD.fluesse, { von: "sold", nach: "gibtsnicht", betrag: "5.00" }],
    };

    expect(baueFlussbild(kaputt).baender).toHaveLength(3);
  });

  it("gibt auch einem Zwergbetrag eine sichtbare Höhe", () => {
    const winzig: Flussbild = {
      ebenen: 2,
      knoten: [knoten("gross", 0, "10000.00"), knoten("klein", 1, "1.00")],
      fluesse: [{ von: "gross", nach: "klein", betrag: "1.00" }],
    };

    const klein = baueFlussbild(winzig).plaetze.find((p) => p.id === "klein");

    expect(klein?.hoehe).toBeGreaterThan(1);
  });

  it("kommt mit einer einzigen Ebene zurecht", () => {
    const eine: Flussbild = {
      ebenen: 1,
      knoten: [knoten("allein", 0, "10.00")],
      fluesse: [],
    };

    expect(baueFlussbild(eine).plaetze).toHaveLength(1);
  });
});
