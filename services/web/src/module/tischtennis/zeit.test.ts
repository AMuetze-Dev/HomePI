import { describe, expect, it } from "vitest";

import { dauer, seit, uhrzeit } from "./zeit";

describe("Zeitangaben", () => {
  it("zeigt eine Uhrzeit zweistellig", () => {
    expect(uhrzeit("2026-11-07T17:05:00Z")).toMatch(/^\d{2}:\d{2}$/);
  });

  it("zeigt einen Gedankenstrich, wenn nichts da ist", () => {
    // Ein Spiel ohne Anfangszeit ist der Normalfall - "Invalid Date" waere
    // eine Fehlermeldung, wo keine hingehoert.
    expect(uhrzeit(null)).toBe("–");
    expect(uhrzeit("keine Zeit")).toBe("–");
  });

  it("nennt Minuten unter einer Stunde als Minuten", () => {
    expect(dauer(48)).toBe("48 min");
    expect(dauer(59)).toBe("59 min");
  });

  it("nennt ganze Stunden ohne Minuten", () => {
    expect(dauer(120)).toBe("2 h");
  });

  it("nennt Stunden und Minuten", () => {
    expect(dauer(130)).toBe("2 h 10 min");
  });

  it("rechnet die Minuten seit dem Anpfiff", () => {
    const jetzt = new Date("2026-11-07T18:07:00Z");

    expect(seit("2026-11-07T18:00:00Z", jetzt)).toBe(7);
  });

  it("rechnet nie in die Vergangenheit", () => {
    // Eine Uhr, die um Sekunden abweicht, soll nicht "-1 min" anzeigen.
    const jetzt = new Date("2026-11-07T18:00:00Z");

    expect(seit("2026-11-07T18:00:30Z", jetzt)).toBe(0);
  });

  it("sagt nichts, wenn es keinen Anpfiff gibt", () => {
    expect(seit(null)).toBeNull();
    expect(seit("quatsch")).toBeNull();
  });
});
