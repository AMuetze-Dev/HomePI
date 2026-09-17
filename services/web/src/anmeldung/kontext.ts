import { createContext, useContext } from "react";

import type { Benutzer, Rolle } from "../api/anmeldung";

/**
 * Wer ist angemeldet - eine Antwort fuer die ganze Anwendung.
 *
 * `laedt` ist ein eigener Zustand und kein `null`: beim ersten Rendern ist
 * noch unbekannt, ob eine Sitzung besteht. Ohne diese Unterscheidung blitzt
 * das Anmeldeformular bei jedem Seitenaufruf kurz auf, obwohl der Benutzer
 * angemeldet ist.
 */
export interface Anmeldung {
  zustand: "laedt" | "angemeldet" | "abgemeldet";
  /** Angemeldet, aber noch mit dem vergebenen Startpasswort. */
  mussPasswortWechseln: boolean;
  benutzer: Benutzer | null;
  anmelden: (name: string, passwort: string) => Promise<void>;
  abmelden: () => Promise<void>;
  /** Uebernimmt einen Benutzer, der anderswo entstanden ist - die
   *  Ersteinrichtung meldet den ersten Verwalter gleich mit an. */
  uebernimm: (benutzer: Benutzer) => void;
  /** Hat der Benutzer fuer dieses Artefakt mindestens diese Rolle? */
  darf: (artefakt: string, benoetigt?: Rolle) => boolean;
}

/** Rangfolge wie im Backend. Aendert sich eine Seite, muss die andere mit. */
export const RANG: Record<Rolle, number> = { leser: 1, nutzer: 2, verwalter: 3 };

export const AnmeldungKontext = createContext<Anmeldung | null>(null);

export function useAnmeldung(): Anmeldung {
  const wert = useContext(AnmeldungKontext);
  if (wert === null) {
    throw new Error("useAnmeldung braucht einen AnmeldungProvider darueber");
  }
  return wert;
}
