import type { Spiel } from "./api";

/** Eine Linie im Raster: von einem Spiel in einen Platz eines späteren. */
export interface Verbindung {
  von: number;
  nach: number;
  platz: "heim" | "gast";
}

/**
 * Welche Spiele eines Rasters eine Linie verbindet.
 *
 * Nur innerhalb derselben Karte. Dort heißt ein Verweis immer „der Sieger
 * kommt hierher“: Wer im Verliererzweig verliert, ist raus, und was aus
 * einer anderen Karte kommt - „Verlierer aus Spiel 25“ -, fällt weg, weil
 * die Quelle hier gar nicht steht. Eine Linie quer über die Seite wäre
 * ohnehin kein Weg mehr, sondern ein Gewirr; dafür gibt es die
 * Hervorhebung beim Zeigen.
 */
export function verbindungen(spiele: Spiel[]): Verbindung[] {
  const hier = new Set(spiele.map((spiel) => spiel.nummer));
  const ergebnis: Verbindung[] = [];
  for (const spiel of spiele) {
    for (const platz of ["heim", "gast"] as const) {
      const von = platz === "heim" ? spiel.heim_aus_spiel : spiel.gast_aus_spiel;
      if (von !== null && von !== undefined && hier.has(von)) {
        ergebnis.push({ von, nach: spiel.nummer, platz });
      }
    }
  }
  return ergebnis;
}

interface Punkt {
  x: number;
  y: number;
}

const zahl = (wert: number) => String(Math.round(wert * 10) / 10);

/**
 * Der Weg einer Linie als SVG-Pfad: waagerecht hinaus bis `knick`, dort
 * senkrecht auf die Höhe des Platzes, dann waagerecht hinein. Die Ecken
 * sind gerundet wie die Karten, nur nie stärker als der halbe
 * Höhenunterschied - sonst schlüge die Kurve über das Ziel hinaus.
 */
export function pfad(von: Punkt, nach: Punkt, knick: number, radius = 6): string {
  const anfang = `M ${zahl(von.x)} ${zahl(von.y)}`;
  const hoehe = nach.y - von.y;
  if (Math.abs(hoehe) < 0.5) return `${anfang} H ${zahl(nach.x)}`;

  const r = Math.min(radius, Math.abs(hoehe) / 2);
  const s = Math.sign(hoehe);
  return [
    anfang,
    `H ${zahl(knick - r)}`,
    `Q ${zahl(knick)} ${zahl(von.y)} ${zahl(knick)} ${zahl(von.y + s * r)}`,
    `V ${zahl(nach.y - s * r)}`,
    `Q ${zahl(knick)} ${zahl(nach.y)} ${zahl(knick + r)} ${zahl(nach.y)}`,
    `H ${zahl(nach.x)}`,
  ].join(" ");
}
