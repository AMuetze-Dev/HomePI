import { describe, expect, it } from "vitest";

import { pfad, verbindungen } from "./rasterlinien";
import { spiel } from "./testdaten";

describe("Welche Spiele eine Linie verbindet", () => {
  it("fuehrt von beiden Halbfinals in die beiden Plaetze des Endspiels", () => {
    const spiele = [
      spiel({ nummer: 1, phase: "ko", runde: 1 }),
      spiel({ nummer: 2, phase: "ko", runde: 1 }),
      spiel({ nummer: 3, phase: "ko", runde: 2, heim_aus_spiel: 1, gast_aus_spiel: 2 }),
    ];

    expect(verbindungen(spiele)).toEqual([
      { von: 1, nach: 3, platz: "heim" },
      { von: 2, nach: 3, platz: "gast" },
    ]);
  });

  it("zieht keine Linie zu einem Spiel, das in einer anderen Karte steht", () => {
    // "Verlierer aus Spiel 25" kommt aus dem Hauptraster. Eine Linie
    // dorthin muesste quer ueber die Karte laufen - dafuer gibt es die
    // Hervorhebung beim Zeigen.
    const verliererzweig = [
      spiel({ nummer: 30, phase: "ko_verlierer", runde: 1 }),
      spiel({
        nummer: 32,
        phase: "ko_verlierer",
        runde: 2,
        heim_aus_spiel: 30,
        gast_aus_spiel: 25,
      }),
    ];

    expect(verbindungen(verliererzweig)).toEqual([{ von: 30, nach: 32, platz: "heim" }]);
  });

  it("zieht keine Linie aus der ersten Runde heraus, wenn nichts nachfolgt", () => {
    expect(verbindungen([spiel({ nummer: 1 }), spiel({ nummer: 2 })])).toEqual([]);
  });
});

describe("Der Weg einer Linie", () => {
  it("laeuft gerade, wenn beide Enden auf einer Hoehe liegen", () => {
    expect(pfad({ x: 0, y: 10 }, { x: 40, y: 10 }, 20)).toBe("M 0 10 H 40");
  });

  it("knickt in der Luecke vor dem Ziel ab, mit gerundeten Ecken", () => {
    // Hinaus bis zum Knick, hinab zur Hoehe des Platzes, hinein.
    expect(pfad({ x: 0, y: 0 }, { x: 40, y: 50 }, 20, 6)).toBe(
      "M 0 0 H 14 Q 20 0 20 6 V 44 Q 20 50 26 50 H 40",
    );
  });

  it("macht die Ecke kleiner, wenn der Hoehenunterschied klein ist", () => {
    expect(pfad({ x: 0, y: 4 }, { x: 40, y: 0 }, 20, 6)).toBe(
      "M 0 4 H 18 Q 20 4 20 2 V 2 Q 20 0 22 0 H 40",
    );
  });
});
