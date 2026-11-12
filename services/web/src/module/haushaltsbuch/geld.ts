import type { Betrag } from "./api";

/**
 * Beträge zum Anzeigen und zum Rechnen.
 *
 * Das Backend schickt Geld als Zeichenkette (siehe api.ts). Hier wird daraus
 * entweder ein deutscher Betrag für den Bildschirm oder eine Zahl für die
 * Geometrie des Flussbilds — und nur dafür. Gerechnet wird im Backend.
 */

const EURO = new Intl.NumberFormat("de-DE", {
  style: "currency",
  currency: "EUR",
});

export function alsZahl(betrag: Betrag): number {
  const zahl = Number(betrag);
  return Number.isFinite(zahl) ? zahl : 0;
}

export function alsEuro(betrag: Betrag): string {
  return EURO.format(alsZahl(betrag));
}

export function alsProzent(wert: Betrag): string {
  return `${alsZahl(wert).toLocaleString("de-DE", { minimumFractionDigits: 1 })} %`;
}

export const MONATE = [
  "Januar",
  "Februar",
  "März",
  "April",
  "Mai",
  "Juni",
  "Juli",
  "August",
  "September",
  "Oktober",
  "November",
  "Dezember",
] as const;

export const KURZE_MONATE = [
  "Jan",
  "Feb",
  "Mär",
  "Apr",
  "Mai",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Okt",
  "Nov",
  "Dez",
] as const;

/** 1 → "Januar". Außerhalb von 1..12 lieber ein Strich als "undefined". */
export function monatswort(monat: number): string {
  return MONATE[monat - 1] ?? "—";
}

/**
 * Wie ein Posten wiederkehrt — in Worten, nicht in Zahlen.
 *
 * "alle 3 Monate ab Monat 2" steht nirgends auf einem Kontoauszug.
 */
export function rhythmus(intervallMonate: number, faelligeMonate: number[]): string {
  if (intervallMonate <= 1) return "monatlich";

  const wann = faelligeMonate.map((m) => KURZE_MONATE[m - 1] ?? "?").join(", ");
  const takt =
    intervallMonate === 3
      ? "vierteljährlich"
      : intervallMonate === 6
        ? "halbjährlich"
        : intervallMonate === 12
          ? "jährlich"
          : `alle ${intervallMonate} Monate`;

  return `${takt} (${wann})`;
}

/** "zum 1." — oder nichts, wenn der Tag nicht bekannt ist. */
export function abbuchungstext(tag: number | null): string {
  return tag === null ? "" : `zum ${tag}.`;
}
