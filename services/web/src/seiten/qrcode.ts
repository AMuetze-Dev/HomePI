import qrcode from "qrcode-generator";

/**
 * Das Muster eines QR-Codes: Zeile für Zeile, `true` heißt dunkel.
 *
 * Die Bibliothek rechnet nur, gezeichnet wird in der Seite selbst - so
 * kommen die Farben aus den Tokens, und kein Dienst im Internet erfährt,
 * welche Adresse hier gerade an der Wand hängt.
 *
 * Fehlerkorrektur M: Rund 15 % des Codes dürfen fehlen. Das reicht für
 * einen Beamer mit Spiegelung oder ein Handy, das schräg gehalten wird,
 * und hält den Code klein genug, um aus drei Metern noch zu lesen.
 */
export function qrMuster(text: string): boolean[][] {
  const code = qrcode(0, "M");
  code.addData(text);
  code.make();
  const groesse = code.getModuleCount();
  return Array.from({ length: groesse }, (_, zeile) =>
    Array.from({ length: groesse }, (_, spalte) => code.isDark(zeile, spalte)),
  );
}

/** Die dunklen Felder als ein einziger SVG-Pfad, ein Quadrat je Feld. */
export function qrPfad(muster: boolean[][], rand: number): string {
  const teile: string[] = [];
  muster.forEach((zeile, y) =>
    zeile.forEach((dunkel, x) => {
      if (dunkel) teile.push(`M${x + rand} ${y + rand}h1v1h-1z`);
    }),
  );
  return teile.join("");
}
