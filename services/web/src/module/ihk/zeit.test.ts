import { describe, expect, it } from "vitest";

import { dauer, note, uhr, zeitstand } from "./zeit";

const T0 = Date.parse("2026-06-18T09:00:00Z");
const iso = (minuten: number) => new Date(T0 + minuten * 60_000).toISOString();
const GRENZEN = { praesiMin: 15, gesamtMin: 30 };

describe("uhr", () => {
  it("zeigt Minuten und Sekunden", () => {
    expect(uhr(0)).toBe("00:00");
    expect(uhr(61_500)).toBe("01:01");
    expect(uhr(-5000)).toBe("00:00");
  });
});

describe("dauer", () => {
  it("ist null ohne Start", () => {
    expect(dauer(null, null, T0)).toBe(0);
  });

  it("läuft bis jetzt, solange kein Ende gesetzt ist", () => {
    expect(dauer(iso(0), null, T0 + 90_000)).toBe(90_000);
  });

  it("steht nach dem Ende", () => {
    expect(dauer(iso(0), iso(2), T0 + 999_999)).toBe(120_000);
  });
});

describe("zeitstand", () => {
  const leer = { praesi_start: null, praesi_ende: null, fg_start: null, fg_ende: null };

  it("bietet zuerst den Start der Präsentation an", () => {
    const s = zeitstand(leer, T0, GRENZEN);
    expect(s.naechste).toBe("praesentation_starten");
    expect(s.laeuft).toBe(false);
  });

  it("warnt nach 15 Minuten Präsentation", () => {
    const s = zeitstand({ ...leer, praesi_start: iso(0) }, T0 + 16 * 60_000, GRENZEN);
    expect(s.naechste).toBe("fachgespraech_starten");
    expect(s.praesiUeber).toBe(true);
    expect(s.gesamtUeber).toBe(false);
    expect(s.laeuft).toBe(true);
  });

  it("schlägt Alarm nach 30 Minuten insgesamt", () => {
    const z = { ...leer, praesi_start: iso(0), praesi_ende: iso(14), fg_start: iso(14) };
    const s = zeitstand(z, T0 + 31 * 60_000, GRENZEN);
    expect(s.naechste).toBe("beenden");
    expect(s.gesamtMs).toBe(31 * 60_000);
    expect(s.restMs).toBe(-60_000);
    expect(s.gesamtUeber).toBe(true);
  });

  it("ist nach dem Ende abgeschlossen", () => {
    const z = {
      praesi_start: iso(0),
      praesi_ende: iso(14),
      fg_start: iso(14),
      fg_ende: iso(29),
    };
    const s = zeitstand(z, T0 + 99 * 60_000, GRENZEN);
    expect(s.naechste).toBeNull();
    expect(s.laeuft).toBe(false);
    expect(s.gesamtMs).toBe(29 * 60_000);
  });
});

describe("note", () => {
  it("schreibt Noten mit Komma", () => {
    expect(note(2.5)).toBe("2,5");
    expect(note(1)).toBe("1,0");
    expect(note(null)).toBe("–");
  });
});
