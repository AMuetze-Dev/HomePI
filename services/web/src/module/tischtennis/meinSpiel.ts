import type { Spiel } from "./api";

/**
 * Was für eine Person als Nächstes ansteht.
 *
 * Die Frage, mit der ein Spieler die Anzeigetafel aufmacht. Vorher stand die
 * Antwort verteilt auf alle Tische und Warteschlangen, und man musste den
 * eigenen Namen darin suchen - auf einem Telefon, in einer lauten Halle.
 */
export type MeinSpiel =
  | { art: "laeuft"; spiel: Spiel; gegner: string }
  | { art: "wartet"; spiel: Spiel; gegner: string }
  | { art: "nichts" };

function gegnerVon(spiel: Spiel, wer: string): string {
  return spiel.heim_id === wer
    ? (spiel.gast ?? spiel.gast_herkunft ?? "offen")
    : (spiel.heim ?? spiel.heim_herkunft ?? "offen");
}

/**
 * Das laufende Spiel dieser Person, sonst das früheste angesetzte.
 *
 * „Früheste" nach der erwarteten Uhrzeit und nicht nach der Nummer: Die
 * Turnierleitung schiebt Spiele in der Warteschlange, und dann steht
 * Spiel 12 vor Spiel 9. Die Uhrzeit rechnet der Zeitplan aus genau dieser
 * Reihenfolge. Freilose sind kein Spiel - dafür steht niemand am Tisch.
 */
export function naechstesSpiel(spiele: readonly Spiel[], wer: string): MeinSpiel {
  const meine = spiele.filter(
    (spiel) => !spiel.freilos && (spiel.heim_id === wer || spiel.gast_id === wer),
  );

  const laeuft = meine.find((spiel) => spiel.zustand === "laeuft");
  if (laeuft) return { art: "laeuft", spiel: laeuft, gegner: gegnerVon(laeuft, wer) };

  const geplant = meine
    .filter((spiel) => spiel.zustand === "geplant")
    .sort((a, b) => {
      // Ohne Uhrzeit nach hinten: Das ist ein Spiel, dessen Platz im
      // Zeitplan noch nicht feststeht.
      if (a.erwartet_ab === b.erwartet_ab) return a.nummer - b.nummer;
      if (a.erwartet_ab === null) return 1;
      if (b.erwartet_ab === null) return -1;
      return a.erwartet_ab.localeCompare(b.erwartet_ab);
    });
  const naechstes = geplant[0];
  if (naechstes) {
    return { art: "wartet", spiel: naechstes, gegner: gegnerVon(naechstes, wer) };
  }

  return { art: "nichts" };
}
