export interface Punkt {
  x: number;
  y: number;
}

/** Ein Punkt der Mausspur, mit dem Zeitpunkt des Ereignisses in ms. */
export interface Spurpunkt extends Punkt {
  t: number;
}

/** Über diese Zeit gemittelt ist eine Bewegung eine Richtung, kein Zittern. */
const RICHTUNGSFENSTER_MS = 150;

/**
 * Wo die letzte Bewegung anfing.
 *
 * Nach Zeit und nicht nach Anzahl: Eine Maus meldet sich in 150 ms
 * zwanzigmal, ein Touchpad viermal. Vier Ereignisse zurück reichten beim
 * einen in die vorige Bewegung, beim anderen nicht einmal über ein Pixel.
 * Stand der Zeiger länger still, gilt der unmittelbar vorige Punkt.
 */
export function anfangDerBewegung(spur: Spurpunkt[]): Spurpunkt | undefined {
  const jetzt = spur.at(-1);
  if (!jetzt || spur.length < 2) return undefined;
  const frisch = spur.filter((punkt) => jetzt.t - punkt.t <= RICHTUNGSFENSTER_MS);
  return frisch.length > 1 ? frisch[0] : spur.at(-2);
}

/** Die linke Kante einer Spalte, auf die der Zeiger zulaufen kann. */
export interface Kante {
  links: number;
  oben: number;
  unten: number;
}

/**
 * Läuft der Zeiger gerade auf die Spalte rechts zu?
 *
 * Wer von „StaffelPilot" zu einem Bereich weiter unten will, zieht die
 * Maus schräg nach rechts unten - und streift dabei „Haushaltsbuch". Die
 * rechte Spalte darf dann nicht umschlagen. Die Frage dafür: Liegt die
 * Richtung der letzten Bewegung zwischen den beiden Strahlen zur oberen
 * und zur unteren Ecke der Spalte? Dann zielt er auf sie, und was er
 * unterwegs streift, ist nur Weg.
 *
 * Ein reines Stück Geometrie, damit es sich ohne Maus prüfen lässt.
 */
export function zieltAuf(vorher: Punkt, jetzt: Punkt, kante: Kante): boolean {
  const dx = jetzt.x - vorher.x;
  if (dx <= 0 || vorher.x >= kante.links) return false;

  const weite = kante.links - vorher.x;
  const richtung = (jetzt.y - vorher.y) / dx;
  const zurOberenEcke = (kante.oben - vorher.y) / weite;
  const zurUnterenEcke = (kante.unten - vorher.y) / weite;
  return richtung > zurOberenEcke && richtung < zurUnterenEcke;
}
