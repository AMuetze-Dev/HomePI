import type { Flussbild, Knoten } from "./api";
import { alsZahl } from "./geld";

/**
 * Aus einem gerichteten Graphen werden Bänder.
 *
 * Die Fachlichkeit steckt nicht hier: *welcher* Knoten in welcher Spalte
 * steht, hat das Backend entschieden (dienst.flussbild). Dieses Modul macht
 * daraus Pixel — und sonst nichts. Deshalb ist es eine reine Funktion und
 * lässt sich ohne DOM prüfen.
 *
 * Keine Bibliothek: d3-sankey wären 40 kB für eine Rechnung, die in hundert
 * Zeilen passt, solange die Ebenen schon feststehen. Auf einem Pi, der sein
 * Frontend selbst ausliefert, ist das ein Argument.
 */

export const KNOTEN_BREITE = 13;
/**
 * Der Abstand zwischen zwei Knoten einer Spalte.
 *
 * Nicht nach Geschmack gewählt: die Beschriftung steht mittig neben ihrem
 * Knoten, also ist der Abstand zweier Beschriftungen die Knotenhöhe plus
 * diese Lücke. Bei 9 px überlappten in der Spalte der Einzelposten die Namen
 * der kleinen Beträge — vier Zeilen übereinander, keine lesbar. 14 px ist
 * eine Zeile bei 11 px Schrift, und damit kann das nicht mehr passieren.
 */
const LUECKE = 14;
/** Damit ein Betrag von 2 € nicht zu einer unsichtbaren Linie wird. */
const MINDESTHOEHE = 3;
/**
 * Platz für die Beschriftung links und rechts der äußersten Spalten.
 *
 * Links ist er genauso nötig wie rechts: die erste Spalte sind die Einnahmen,
 * und ohne diesen Rand stand "Kindergeld 8,80 €" außerhalb des Bildes.
 */
const BESCHRIFTUNG = 150;

export interface Platz {
  id: string;
  knoten: Knoten;
  x: number;
  y: number;
  hoehe: number;
  wert: number;
}

export interface Band {
  id: string;
  pfad: string;
  wert: number;
  von: Knoten;
  nach: Knoten;
}

export interface Aufbau {
  plaetze: Platz[];
  baender: Band[];
  breite: number;
  hoehe: number;
}

const LEER: Aufbau = { plaetze: [], baender: [], breite: 0, hoehe: 0 };

export function baueFlussbild(
  bild: Flussbild,
  zielhoehe = 520,
  zielbreite = 1040,
): Aufbau {
  if (bild.knoten.length === 0 || bild.ebenen === 0) return LEER;

  const werte = new Map(bild.knoten.map((k) => [k.id, alsZahl(k.betrag)]));
  const spalten: Knoten[][] = Array.from({ length: bild.ebenen }, () => []);
  for (const knoten of bild.knoten) spalten[knoten.ebene]?.push(knoten);

  ordneNachZufluss(spalten, bild);

  // Ein gemeinsamer Maßstab für alle Spalten: unterschiedliche wären bequemer
  // zu stapeln, würden aber aus gleich hohen Bändern verschiedene Beträge
  // machen - und damit genau die Aussage zerstören, für die man ein Sankey
  // überhaupt zeichnet.
  const hoehe = Math.max(
    zielhoehe,
    ...spalten.map((s) => s.length * (MINDESTHOEHE + LUECKE)),
  );
  const massstab = Math.min(
    ...spalten
      .map((spalte) => ({
        summe: spalte.reduce((s, k) => s + (werte.get(k.id) ?? 0), 0),
        platz: hoehe - Math.max(0, spalte.length - 1) * LUECKE,
      }))
      .filter((s) => s.summe > 0)
      .map((s) => s.platz / s.summe),
  );

  const spaltenbreite =
    bild.ebenen > 1
      ? (zielbreite - KNOTEN_BREITE - 2 * BESCHRIFTUNG) / (bild.ebenen - 1)
      : 0;

  const plaetze: Platz[] = [];
  const nachId = new Map<string, Platz>();
  let hoechste = 0;

  spalten.forEach((spalte, ebene) => {
    let y = 0;
    for (const knoten of spalte) {
      const wert = werte.get(knoten.id) ?? 0;
      const platz: Platz = {
        id: knoten.id,
        knoten,
        x: BESCHRIFTUNG + ebene * spaltenbreite,
        y,
        hoehe: Math.max(MINDESTHOEHE, wert * massstab),
        wert,
      };
      plaetze.push(platz);
      nachId.set(knoten.id, platz);
      y += platz.hoehe + LUECKE;
    }
    hoechste = Math.max(hoechste, y - LUECKE);
  });

  return {
    plaetze,
    baender: baueBaender(bild, nachId),
    breite: zielbreite,
    hoehe: Math.max(hoechste, 1),
  };
}

/**
 * Knoten einer Spalte nach der Lage ihrer Quellen sortieren.
 *
 * Ein Durchgang von links nach rechts, mehr nicht. Das löst nicht jede
 * Kreuzung auf, nimmt aber die auffälligen weg - und bleibt dabei
 * nachvollziehbar, was für ein Bild, das etwas erklären soll, mehr wert ist
 * als das letzte Prozent Ordnung.
 */
function ordneNachZufluss(spalten: Knoten[][], bild: Flussbild): void {
  const rang = new Map<string, number>();
  spalten[0]?.forEach((k, i) => rang.set(k.id, i));

  for (let ebene = 1; ebene < spalten.length; ebene++) {
    const spalte = spalten[ebene];
    if (!spalte) continue;

    const schwerpunkt = new Map<string, number>();
    for (const knoten of spalte) {
      const quellen = bild.fluesse
        .filter((f) => f.nach === knoten.id)
        .map((f) => rang.get(f.von))
        .filter((r): r is number => r !== undefined);
      // Ohne Quelle: ans Ende, statt die anderen durcheinanderzubringen.
      schwerpunkt.set(
        knoten.id,
        quellen.length > 0
          ? quellen.reduce((a, b) => a + b, 0) / quellen.length
          : Infinity,
      );
    }

    spalte.sort((a, b) => (schwerpunkt.get(a.id) ?? 0) - (schwerpunkt.get(b.id) ?? 0));
    spalte.forEach((k, i) => rang.set(k.id, i));
  }
}

function baueBaender(bild: Flussbild, nachId: Map<string, Platz>): Band[] {
  // Je Knoten wandert ein Zeiger von oben nach unten durch seine Kante -
  // einmal für das, was hineinfließt, einmal für das, was herausgeht.
  const abgang = new Map<string, number>();
  const zugang = new Map<string, number>();
  const lage = (id: string) => nachId.get(id)?.y ?? 0;

  const sortiert = [...bild.fluesse].sort(
    (a, b) => lage(a.von) - lage(b.von) || lage(a.nach) - lage(b.nach),
  );

  const baender: Band[] = [];
  for (const fluss of sortiert) {
    const von = nachId.get(fluss.von);
    const nach = nachId.get(fluss.nach);
    if (!von || !nach) continue;

    const wert = alsZahl(fluss.betrag);
    const dicke = Math.max(MINDESTHOEHE, (wert / (von.wert || wert)) * von.hoehe);
    const dickeZiel = Math.max(MINDESTHOEHE, (wert / (nach.wert || wert)) * nach.hoehe);

    const a0 = von.y + (abgang.get(von.id) ?? 0);
    const b0 = nach.y + (zugang.get(nach.id) ?? 0);
    abgang.set(von.id, (abgang.get(von.id) ?? 0) + dicke);
    zugang.set(nach.id, (zugang.get(nach.id) ?? 0) + dickeZiel);

    baender.push({
      id: `${fluss.von}->${fluss.nach}`,
      pfad: bandpfad(von.x + KNOTEN_BREITE, a0, a0 + dicke, nach.x, b0, b0 + dickeZiel),
      wert,
      von: von.knoten,
      nach: nach.knoten,
    });
  }

  return baender;
}

function bandpfad(
  x0: number,
  oben0: number,
  unten0: number,
  x1: number,
  oben1: number,
  unten1: number,
): string {
  // Die Kontrollpunkte liegen auf halber Strecke: so verlässt das Band seinen
  // Knoten waagerecht und trifft den nächsten ebenso - der Knick, an dem das
  // Auge hängen bleibt, entsteht gar nicht erst.
  const mitte = (x0 + x1) / 2;
  return [
    `M${x0},${oben0}`,
    `C${mitte},${oben0} ${mitte},${oben1} ${x1},${oben1}`,
    `L${x1},${unten1}`,
    `C${mitte},${unten1} ${mitte},${unten0} ${x0},${unten0}`,
    "Z",
  ].join(" ");
}
