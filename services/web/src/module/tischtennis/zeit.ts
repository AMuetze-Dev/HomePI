/**
 * Zeitangaben für die Anzeige.
 *
 * Eigene Datei, weil die Dashboard-Ansicht, der Spielplan und die Vorschau
 * dasselbe Format brauchen - eine Uhrzeit, die an drei Stellen anders
 * aussieht, liest sich wie drei verschiedene Angaben.
 */

/** „18:42" - oder ein Gedankenstrich, wenn nichts da ist. */
export function uhrzeit(iso: string | null): string {
  if (!iso) return "–";
  const zeitpunkt = new Date(iso);
  if (Number.isNaN(zeitpunkt.getTime())) return "–";
  return zeitpunkt.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

/** „2 h 10 min" - für die Schätzung, nach der der Modus gewählt wird. */
export function dauer(minuten: number): string {
  if (minuten < 60) return `${minuten} min`;
  const stunden = Math.floor(minuten / 60);
  const rest = minuten % 60;
  return rest === 0 ? `${stunden} h` : `${stunden} h ${rest} min`;
}

/**
 * Wie lange ein Spiel schon läuft, in Minuten.
 *
 * Für die Anzeige am Tisch: „läuft seit 7 min" sagt mehr darüber, ob der
 * nächste gleich dran ist, als eine Anfangszeit.
 */
export function seit(iso: string | null, jetzt: Date = new Date()): number | null {
  if (!iso) return null;
  const beginn = new Date(iso);
  if (Number.isNaN(beginn.getTime())) return null;
  return Math.max(0, Math.round((jetzt.getTime() - beginn.getTime()) / 60000));
}
