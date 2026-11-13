/**
 * Thema und Bewegung aus dem Speicher auf das Dokument bringen.
 *
 * Läuft VOR dem ersten Rendern (siehe main.tsx) und nicht in einer
 * Komponente. Der Grund ist sichtbar: Würde React das Attribut erst in
 * einem Effekt setzen, zeigte die Seite für einen Wimpernschlag den
 * Dunkelmodus des Systems, bevor sie auf die Wahl des Benutzers umspringt -
 * ein Aufblitzen, das man einmal sieht und nicht mehr vergisst.
 *
 * Die Funktion ist absichtlich nur hier zu Hause. Wer das Thema ÄNDERN
 * will, nimmt useThema bzw. useBewegung; die schreiben in denselben
 * Speicher und setzen dieselben Attribute.
 */

export const THEMA_SCHLUESSEL = "homepi.thema";
export const BEWEGUNG_SCHLUESSEL = "homepi.bewegung";

export function wendeDarstellungAn(): void {
  const wurzel = document.documentElement;

  try {
    const thema = localStorage.getItem(THEMA_SCHLUESSEL);
    if (thema === "hell" || thema === "dunkel") {
      wurzel.setAttribute("data-thema", thema);
    }

    if (localStorage.getItem(BEWEGUNG_SCHLUESSEL) === "reduziert") {
      wurzel.setAttribute("data-bewegung", "reduziert");
    }
  } catch {
    // Privates Fenster oder blockierte Speicherung: dann gilt das System.
    // Kein Grund, die Anwendung nicht zu starten.
  }
}
