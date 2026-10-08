// @vitest-environment node
/**
 * Prüfungen über das ganze Frontend, nicht über eine Komponente.
 *
 * Sie lesen die Quelldateien selbst und stehen deshalb außerhalb von src/:
 * Dort gibt es mit Absicht keine Node-Typen - die Oberfläche läuft im
 * Browser, und ein versehentliches `import "node:fs"` soll beim Bauen
 * auffallen, nicht erst im Browser.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..", "src");

function dateien(verzeichnis: string): string[] {
  return readdirSync(verzeichnis, { withFileTypes: true }).flatMap((eintrag) => {
    const pfad = join(verzeichnis, eintrag.name);
    return eintrag.isDirectory() ? dateien(pfad) : [pfad];
  });
}

const QUELLEN = dateien(SRC)
  .filter((p) => /\.(css|tsx?)$/.test(p) && !/\.test\.tsx?$/.test(p))
  .map((p) => ({
    pfad: relative(SRC, p).replaceAll("\\", "/"),
    text: readFileSync(p, "utf-8"),
  }));

const CSS = QUELLEN.filter((q) => q.pfad.endsWith(".css"));

describe("Gestaltungsgrößen", () => {
  /*
   * Eine undefinierte CSS-Variable meldet kein Werkzeug: Der Browser setzt
   * still den Ausgangswert ein. So hatten die Kästchen im StaffelPilot nie
   * die Akzentfarbe und der Verweis auf das PDF weder Rundung noch
   * Hintergrund - vier Namen, die es in tokens.css nie gab.
   *
   * Jedes Artefakt bringt eigenes CSS mit. Diese Prüfung gilt auch für das
   * nächste, ohne dass jemand daran denken muss.
   */
  it("kennt jede benutzte Variable", () => {
    const bekannt = new Set(
      CSS.flatMap((q) => [...q.text.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((t) => t[1])),
    );

    const unbekannt = QUELLEN.flatMap((q) =>
      [...q.text.matchAll(/var\(\s*(--[a-z0-9-]+)/g)]
        .map((t) => t[1])
        .filter((name) => !bekannt.has(name))
        .map((name) => `${q.pfad}: ${name}`),
    );

    expect([...new Set(unbekannt)]).toEqual([]);
  });

  /*
   * Ein fester Farbwert ist genau die Stelle, an der das Erscheinungsbild
   * auseinanderläuft: Er folgt weder dem dunklen Thema noch der nächsten
   * Änderung der Palette.
   */
  it("hat feste Farbwerte nur in tokens.css", () => {
    const funde = CSS.filter((q) => q.pfad !== "styles/tokens.css").flatMap((q) =>
      [...q.text.matchAll(/#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(/g)].map(
        (t) => `${q.pfad}: ${t[0]}`,
      ),
    );

    expect(funde).toEqual([]);
  });
});
