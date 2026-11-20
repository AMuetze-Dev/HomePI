import { describe, expect, it } from "vitest";

import { qrMuster } from "./qrcode";

describe("Das Muster eines QR-Codes", () => {
  it("ist quadratisch und traegt oben links das Suchmuster", () => {
    const muster = qrMuster("https://homelab.example.ts.net");

    expect(muster.length).toBeGreaterThanOrEqual(21);
    expect(muster.every((zeile) => zeile.length === muster.length)).toBe(true);
    // Das Suchmuster: ein dunkler Rahmen aus sieben Feldern, darin ein
    // heller Ring und ein dunkler Kern. Daran erkennt jede Kamera den Code.
    expect(muster[0]?.slice(0, 7)).toEqual(Array(7).fill(true));
    expect(muster[1]?.slice(0, 7)).toEqual([
      true,
      false,
      false,
      false,
      false,
      false,
      true,
    ]);
    expect(muster[3]?.[3]).toBe(true);
  });

  it("waechst mit der Laenge der Adresse", () => {
    const kurz = qrMuster("https://a.de");
    const lang = qrMuster(`https://${"x".repeat(120)}.example.ts.net`);

    expect(lang.length).toBeGreaterThan(kurz.length);
  });
});
