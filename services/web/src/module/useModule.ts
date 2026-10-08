import { useEffect, useState } from "react";

import { fetchModule, type ModulEintrag } from "../api/client";
import { useAnmeldung } from "../anmeldung/kontext";

/**
 * Das Manifest, einmal geholt und geteilt.
 *
 * Vorher holte es jede Ansicht selbst. Mit der Navigationsleiste wären es
 * drei gleichzeitige Abrufe derselben Liste geworden - beim Öffnen eines
 * Moduls einer für die Leiste, einer für die Seite, und beim Zurückgehen
 * gleich wieder.
 *
 * Der Zwischenspeicher hängt an der Anmeldung und nicht nur an der Zeit: Das
 * Manifest ist je Konto verschieden, weil darin nur steht, wofür jemand
 * berechtigt ist. Ein Wechsel des Kontos muss ihn also verwerfen - sonst
 * sieht der Nächste die Artefakte des Vorigen.
 */

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; module: ModulEintrag[] }
  | { phase: "fehler"; nachricht: string };

type Horcher = (z: Zustand) => void;

let schluessel: string | null = null;
let stand: Zustand = { phase: "laedt" };
/**
 * Zählt die Abrufe durch.
 *
 * Ein Abruf, der verworfen wurde und trotzdem noch ankommt, darf den
 * neueren Stand nicht überschreiben. Das ist kein erdachter Fall: Beim
 * Abmelden während eines laufenden Abrufs träfe die Antwort des alten
 * Kontos auf die Ansicht des neuen.
 */
let lauf = 0;
const horcher = new Set<Horcher>();

function verteile(z: Zustand) {
  stand = z;
  for (const h of horcher) h(z);
}

function hole(fuer: string) {
  schluessel = fuer;
  const meiner = ++lauf;
  void fetchModule()
    .then((module) => {
      if (meiner === lauf) verteile({ phase: "fertig", module });
    })
    .catch((fehler: unknown) => {
      if (meiner !== lauf) return;
      const nachricht = fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
      verteile({ phase: "fehler", nachricht });
    });
}

/**
 * Nach einer Änderung, die das Manifest betrifft - etwa neuen Rechten.
 *
 * Auch die Tests rufen das zwischen zwei Fällen auf: Ein Zwischenspeicher,
 * der den Test überlebt, zeigt dem nächsten die Daten des vorigen.
 */
export function manifestVerwerfen() {
  schluessel = null;
  lauf += 1;
  verteile({ phase: "laedt" });
}

/**
 * Alles, wovon das Manifest abhängt - und nichts darüber hinaus.
 *
 * Nur die Kennung reichte nicht: Bis zum Passwortwechsel behandelt das
 * Backend ein Konto beim Manifest wie einen Besucher und liefert es leer.
 * Nach dem Wechsel ist es dieselbe Kennung - und die Übersicht blieb mit dem
 * alten, leeren Stand stehen. Dasselbe gilt, wenn ein Verwalter Rechte
 * vergibt.
 *
 * Das ganze Benutzerobjekt wäre umgekehrt zu viel: Es ist bei jedem Abruf
 * neu, und jeder Seitenwechsel holte das Manifest dann ein zweites Mal.
 * Deshalb ein Schlüssel aus dem INHALT, mit sortierten Rechten, damit die
 * Reihenfolge im JSON keine Rolle spielt.
 */
function schluesselFuer(
  anmeldung: string,
  benutzer: {
    id: string;
    passwort_wechseln?: boolean;
    rechte: Record<string, string>;
  } | null,
): string {
  if (!benutzer) return `${anmeldung}:-`;
  const rechte = Object.entries(benutzer.rechte)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([artefakt, rolle]) => `${artefakt}=${rolle}`)
    .join(",");
  return `${anmeldung}:${benutzer.id}:${benutzer.passwort_wechseln ? "wechsel" : "frei"}:${rechte}`;
}

export function useModule(): Zustand {
  const { zustand: anmeldung, benutzer } = useAnmeldung();
  const fuer = schluesselFuer(anmeldung, benutzer);
  const [zustand, setZustand] = useState<Zustand>(stand);

  useEffect(() => {
    // Erst fragen, wenn feststeht, wer fragt. Sonst holt die Anwendung das
    // Manifest zweimal - einmal anonym, einmal angemeldet.
    if (anmeldung === "laedt") return undefined;

    horcher.add(setZustand);

    if (schluessel !== fuer) {
      stand = { phase: "laedt" };
      setZustand(stand);
      hole(fuer);
    } else {
      // Ein Abruf, der noch laeuft, wird nicht verdoppelt - dieser Horcher
      // bekommt sein Ergebnis, sobald es eintrifft.
      setZustand(stand);
    }

    return () => {
      horcher.delete(setZustand);
    };
  }, [anmeldung, fuer]);

  return anmeldung === "laedt" ? { phase: "laedt" } : zustand;
}
