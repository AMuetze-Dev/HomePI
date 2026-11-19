import type { Flussbild, Kategorie, Konto, Person, Posten, Uebersicht } from "./api";

/**
 * Was die Hülle geladen hat und an ihre Tafeln weiterreicht.
 *
 * Alles auf einmal, weil ein Haushalt in Dutzenden Zeilen zählt und nicht in
 * Tausenden: sechs Abrufe beim Betreten, danach wechselt man zwischen den
 * Bereichen ohne einen einzigen weiteren. Das ist der Grund, warum die
 * Unterseiten hier keine eigenen Ladezustände haben.
 *
 * Eigene Datei und nicht neben der Komponente: sonst exportiert die Datei der
 * Hülle neben ihrem Bauteil auch noch Funktionen, und das Nachladen im
 * laufenden Entwicklungsserver fällt auf einen ganzen Neuaufbau zurück.
 */
export interface Daten {
  uebersicht: Uebersicht;
  flussbild: Flussbild;
  personen: Person[];
  konten: Konto[];
  kategorien: Kategorie[];
  posten: Posten[];
}

/**
 * Die Titel der vier Bereiche - dieselben Wörter wie im Register.
 *
 * Hier und nicht aus dem Register gelesen: Das Register importiert diese
 * Oberfläche, der Weg zurück wäre ein Zyklus. Dass es damit an zwei Stellen
 * steht, hält ein Test im Register fest.
 */
export const BEREICHSTITEL = {
  uebersicht: "Monatsplan",
  fluss: "Geldfluss",
  posten: "Posten",
  stammdaten: "Konten & Personen",
} as const;

/**
 * Der Titel zu einer Bereichskennung, mit dem Monatsplan als Rückfall.
 *
 * Ohne Bereich steht man auf der Startfläche - und ein erfundener Bereich
 * landet dort ebenfalls, weil die Modulseite ihn dorthin umleitet.
 */
export function bereichstitel(unterseite: string | undefined): string {
  if (unterseite !== undefined && unterseite in BEREICHSTITEL) {
    return BEREICHSTITEL[unterseite as keyof typeof BEREICHSTITEL];
  }
  return BEREICHSTITEL.uebersicht;
}

export interface Zeitraum {
  jahr: number;
  monat: number;
}

export function dieserMonat(): Zeitraum {
  const heute = new Date();
  return { jahr: heute.getFullYear(), monat: heute.getMonth() + 1 };
}

/**
 * Ein Monat weiter oder zurück - über die Monatszahl, nicht über ein Datum.
 *
 * `new Date(jahr, monat, 31)` landet je nach Monat im übernächsten. Der
 * Haushalt rechnet ohnehin nur in ganzen Monaten; dann soll er das auch hier.
 */
export function verschiebe(zeitraum: Zeitraum, schritte: number): Zeitraum {
  const laufend = zeitraum.jahr * 12 + (zeitraum.monat - 1) + schritte;
  return { jahr: Math.floor(laufend / 12), monat: (laufend % 12) + 1 };
}
