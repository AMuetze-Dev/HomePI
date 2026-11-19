import { describe, expect, it } from "vitest";

import { naechstesSpiel } from "./meinSpiel";
import { spiel } from "./testdaten";

/* Die Frage, mit der ein Spieler die Anzeigetafel aufmacht: Wann und wo
   spiele ICH? Vorher stand die Antwort verteilt auf alle Tische und
   Warteschlangen, und man musste den eigenen Namen darin suchen. */

describe("Das nächste Spiel einer Person", () => {
  it("nennt das laufende Spiel zuerst", () => {
    const laeuft = spiel({ id: "a", zustand: "laeuft", tisch: 2 });
    const spaeter = spiel({ id: "b", erwartet_ab: "2026-11-09T18:30:00Z" });

    expect(naechstesSpiel([spaeter, laeuft], "p1")).toEqual({
      art: "laeuft",
      spiel: laeuft,
      gegner: "Bernd",
    });
  });

  it("nimmt sonst das früheste angesetzte", () => {
    const spaet = spiel({ id: "a", erwartet_ab: "2026-11-09T19:00:00Z" });
    const frueh = spiel({ id: "b", erwartet_ab: "2026-11-09T18:15:00Z" });

    expect(naechstesSpiel([spaet, frueh], "p2")).toMatchObject({
      art: "wartet",
      spiel: frueh,
      gegner: "Anna",
    });
  });

  it("nennt einen Gegner, der noch nicht feststeht, mit seiner Herkunft", () => {
    const ko = spiel({ gast_id: null, gast: null, gast_herkunft: "Sieger aus Spiel 7" });

    expect(naechstesSpiel([ko], "p1")).toMatchObject({ gegner: "Sieger aus Spiel 7" });
  });

  it("zählt beendete Spiele und Freilose nicht", () => {
    const beendet = spiel({ zustand: "beendet", sieger_id: "p1" });
    const freilos = spiel({ id: "f", freilos: true, gast_id: null, gast: null });

    expect(naechstesSpiel([beendet, freilos], "p1")).toEqual({ art: "nichts" });
  });

  it("sagt, wenn für jemanden gerade nichts ansteht", () => {
    expect(naechstesSpiel([spiel()], "p9")).toEqual({ art: "nichts" });
  });
});
