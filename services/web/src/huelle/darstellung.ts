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
export const GRUND_SCHLUESSEL = "homepi.grund";

/**
 * Die wählbaren Grundfarben.
 *
 * Die Werte dazu stehen in `styles/tokens.css` unter `[data-grund="…"]`;
 * hier stehen nur Kennung und Wort. Eine zweite Liste von Hexwerten für die
 * Vorschau wäre die erste, die veraltet — der Farbtupfen in den
 * Einstellungen trägt deshalb dasselbe Attribut und zeigt damit genau die
 * Farbe, die die Oberfläche annehmen wird.
 *
 * „nocturne" ist die Voreinstellung und setzt kein Attribut: Es ist der
 * Entwurf, wie er gezeichnet wurde.
 */
export const GRUENDE = [
  { wert: "nocturne", wort: "Nocturne" },
  { wert: "schiefer", wort: "Schiefer" },
  { wert: "glut", wort: "Glut" },
  { wert: "moos", wort: "Moos" },
  { wert: "bernstein", wort: "Bernstein" },
] as const;

export type Grund = (typeof GRUENDE)[number]["wert"];

export function istGrund(wert: string | null): wert is Grund {
  return GRUENDE.some((g) => g.wert === wert);
}

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

    const grund = localStorage.getItem(GRUND_SCHLUESSEL);
    if (istGrund(grund) && grund !== "nocturne") {
      wurzel.setAttribute("data-grund", grund);
    }
  } catch {
    // Privates Fenster oder blockierte Speicherung: dann gilt das System.
    // Kein Grund, die Anwendung nicht zu starten.
  }
}
