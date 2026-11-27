import type { Frage, Zeitaktion, Zeiten } from "./api";

/**
 * Anzeige der Zeitmessung. Entschieden wird im Backend - welcher Schritt
 * zulässig ist, prüft `dienst.zeit_schritt`. Hier wird nur abgelesen, was die
 * Zeitstempel ergeben, und welcher Knopf deshalb gerade passt.
 *
 * Gezählt wird nie hoch: Browser drosseln Timer im Hintergrund. Jede Dauer
 * ist Ende minus Start, und solange kein Ende steht, ist das Ende „jetzt“.
 */

export function dauer(start: string | null, ende: string | null, jetzt: number): number {
  if (!start) return 0;
  return (ende ? Date.parse(ende) : jetzt) - Date.parse(start);
}

export function uhr(ms: number): string {
  const sekunden = Math.max(0, Math.floor(ms / 1000));
  const mm = String(Math.floor(sekunden / 60)).padStart(2, "0");
  const ss = String(sekunden % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export interface Zeitstand {
  praesiMs: number;
  fgMs: number;
  gesamtMs: number;
  /** Bis zur Gesamtgrenze, negativ nach Überschreiten. */
  restMs: number;
  praesiUeber: boolean;
  gesamtUeber: boolean;
  laeuft: boolean;
  naechste: Exclude<Zeitaktion, "zuruecksetzen"> | null;
}

export function zeitstand(
  z: Zeiten,
  jetzt: number,
  grenzen: { praesiMin: number; gesamtMin: number },
): Zeitstand {
  const praesiMs = dauer(z.praesi_start, z.praesi_ende, jetzt);
  const fgMs = dauer(z.fg_start, z.fg_ende, jetzt);
  const gesamtMs = praesiMs + fgMs;
  const praesiLaeuft = Boolean(z.praesi_start) && !z.praesi_ende;
  const fgLaeuft = Boolean(z.fg_start) && !z.fg_ende;

  let naechste: Zeitstand["naechste"] = null;
  if (!z.praesi_start) naechste = "praesentation_starten";
  else if (praesiLaeuft) naechste = "fachgespraech_starten";
  else if (fgLaeuft) naechste = "beenden";

  return {
    praesiMs,
    fgMs,
    gesamtMs,
    restMs: grenzen.gesamtMin * 60_000 - gesamtMs,
    praesiUeber: praesiMs > grenzen.praesiMin * 60_000,
    gesamtUeber: gesamtMs > grenzen.gesamtMin * 60_000,
    laeuft: praesiLaeuft || fgLaeuft,
    naechste,
  };
}

/** Noten wie auf dem Bogen: eine Nachkommastelle, Komma. */
export function note(wert: number | null): string {
  return wert === null ? "–" : wert.toFixed(1).replace(".", ",");
}

export function punkte(wert: number | null): string {
  return wert === null ? "–" : String(wert);
}

/** Die Meldung des Backends, wörtlich. */
export function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

/** ISO-Datum als TT.MM.JJJJ - ohne Zeitzone, die das Datum verschieben könnte. */
export function datum(iso: string): string {
  const [jahr, monat, tag] = iso.split("-");
  return `${tag}.${monat}.${jahr}`;
}

/** Was es im Thema überhaupt gibt - leere Themen zählen nicht als Thema. */
export function themenAus(fragen: Frage[]): string[] {
  return [...new Set(fragen.map((f) => f.thema).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "de"),
  );
}
