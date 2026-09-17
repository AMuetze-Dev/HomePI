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
import { AnmeldungProvider } from "./anmeldung/AnmeldungProvider";

export const TESTBENUTZER: Benutzer = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "pruefer",
  anzeigename: "Prüfer",
  rechte: { geraete: "verwalter", messwerte: "verwalter" },
};

/**
 * Umhüllt eine Ansicht mit einer Anmeldung.
 *
 * `null` bedeutet: niemand angemeldet - genau der Fall, in dem das Manifest
 * berechtigterweise leer ist.
 */
export function mitAnmeldung(kind: ReactNode, benutzer: Benutzer | null = TESTBENUTZER) {
  vi.spyOn(anmeldungApi, "holeIch").mockResolvedValue(benutzer);
  return <AnmeldungProvider>{kind}</AnmeldungProvider>;
}
