/** Aus "2026-09-13" wird "13.09.2026" - so steht es auf jedem Spielbericht.
 *
 * Eigene Datei und nicht neben der Komponente: eine Datei, die ausser
 * Komponenten noch etwas anderes ausfuehrt, bricht Fast Refresh.
 */
export function alsDatum(iso: string): string {
  const treffer = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return treffer ? `${treffer[3]}.${treffer[2]}.${treffer[1]}` : iso;
}
