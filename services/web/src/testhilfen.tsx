/**
 * Hilfen für Tests, die eine angemeldete Sitzung brauchen.
 *
 * Seit Artefakte je Benutzer sichtbar sind, hängt fast jede Ansicht am
 * Anmeldekontext. Ohne Hülle würde `useAnmeldung` werfen - und der Test
 * scheiterte an etwas, das mit seiner Frage nichts zu tun hat.
 */

import type { ReactNode } from "react";
import { vi } from "vitest";

import * as anmeldungApi from "./api/anmeldung";
import type { Benutzer } from "./api/anmeldung";
import * as einrichtungApi from "./api/einrichtung";
import { AnmeldungProvider } from "./anmeldung/AnmeldungProvider";

export const TESTBENUTZER: Benutzer = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "pruefer",
  anzeigename: "Prüfer",
  rechte: { geraete: "verwalter", messwerte: "verwalter" },
  passwort_wechseln: false,
};

/**
 * Diese Installation ist bereits eingerichtet.
 *
 * Der Normalfall für jeden Test, der nicht gerade die Ersteinrichtung prüft -
 * ohne diese Vorgabe ginge jeder davon durch das Einrichtungstor.
 */
export function eingerichtet(noetig = false) {
  return vi.spyOn(einrichtungApi, "holeStand").mockResolvedValue({ noetig });
}

/**
 * Umhüllt eine Ansicht mit einer Anmeldung.
 *
 * `null` bedeutet: niemand angemeldet - genau der Fall, in dem das Manifest
 * berechtigterweise leer ist.
 */
export function mitAnmeldung(kind: ReactNode, benutzer: Benutzer | null = TESTBENUTZER) {
  vi.spyOn(anmeldungApi, "holeIch").mockResolvedValue(benutzer);
  eingerichtet();
  return <AnmeldungProvider>{kind}</AnmeldungProvider>;
}
