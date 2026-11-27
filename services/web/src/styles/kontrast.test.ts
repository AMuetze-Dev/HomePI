import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Die Schriftfarben gegen jeden Grund, nachgerechnet aus tokens.css.
 *
 * WCAG AA verlangt 4,5:1 für normale Schrift. „Leise" steht ausgerechnet
 * an der kleinsten Schrift - Nummern, Fußzeilen, Nebensachen -, also gilt
 * dort keine Ausnahme für große Schrift. Gerechnet wird gegen jede Fläche,
 * auf der Text liegen kann, in Hell und Dunkel und für jede Grundfarbe.
 */

const css = readFileSync(resolve(__dirname, "tokens.css"), "utf-8");

/** Die Hexwerte eines Blocks - `:root` oder `[data-grund="…"]`. */
function block(waehler: string): Record<string, string> {
  const anfang = css.indexOf(`${waehler} {`);
  if (anfang < 0) throw new Error(`${waehler} fehlt in tokens.css`);
  const inhalt = css.slice(anfang, css.indexOf("\n}", anfang));
  const werte: Record<string, string> = {};
  for (const [, name, wert] of inhalt.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    if (name && wert) werte[name] = wert;
  }
  return werte;
}

/** `light-dark(a, b)` einer Rolle, mit Variablen aufgelöst. */
function rolle(name: string, werte: Record<string, string>): [string, string] {
  const treffer = new RegExp(
    `--${name}:\\s*light-dark\\(([^,]+),\\s*([^)]+\\)?)\\)`,
  ).exec(css);
  if (!treffer?.[1] || !treffer[2]) throw new Error(`--${name} ist kein light-dark()`);
  const loese = (teil: string) => {
    const roh = teil.trim();
    if (roh.startsWith("#")) return roh;
    const variable = /var\(--([\w-]+)\)/.exec(roh)?.[1];
    const wert = variable ? werte[variable] : undefined;
    if (!wert) throw new Error(`${roh} in --${name} nicht auflösbar`);
    return wert;
  };
  return [loese(treffer[1]), loese(treffer[2])];
}

function leuchtdichte(hex: string): number {
  const kanaele = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r = 0, g = 0, b = 0] = kanaele.map((c) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function kontrast(a: string, b: string): number {
  const [hell, dunkel] = [leuchtdichte(a), leuchtdichte(b)].sort((x, y) => y - x);
  return ((hell ?? 0) + 0.05) / ((dunkel ?? 0) + 0.05);
}

const GRUNDLAGE = block(":root");
const GRUENDE = ["nocturne", "schiefer", "glut", "moos", "bernstein"];

function werteFuer(grund: string): Record<string, string> {
  return grund === "nocturne"
    ? GRUNDLAGE
    : { ...GRUNDLAGE, ...block(`[data-grund="${grund}"]`) };
}

describe.each(GRUENDE)("Schrift auf dem Grund „%s“", (grund) => {
  const werte = werteFuer(grund);
  const flaechen = {
    hell: [werte["ton-100"], werte["ton-50"], werte["ton-200"]],
    dunkel: [
      werte["ton-950"],
      werte["dunkel-flaeche"],
      werte["dunkel-flaeche-erhoben"],
      werte["dunkel-flaeche-gedaempft"],
    ],
  };

  it.each(["farbe-text", "farbe-text-gedaempft", "farbe-text-leise"])(
    "%s erreicht auf jeder Fläche 4,5:1",
    (name) => {
      const [hell, dunkel] = rolle(name, werte);
      for (const flaeche of flaechen.hell) {
        expect(kontrast(hell, flaeche ?? "")).toBeGreaterThanOrEqual(4.5);
      }
      for (const flaeche of flaechen.dunkel) {
        expect(kontrast(dunkel, flaeche ?? "")).toBeGreaterThanOrEqual(4.5);
      }
    },
  );
});
