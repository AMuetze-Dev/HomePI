/**
 * Die Ersteinrichtung.
 *
 * Dass diese Oberfläche die Maske zeigt oder nicht, ist **keine** Sicherung.
 * Wer `/einrichtung` von Hand aufruft oder direkt gegen die API spricht,
 * landet trotzdem beim Backend - und dort wird bei jedem Aufruf geprüft, ob es
 * wirklich noch keinen Verwalter gibt und ob das Einrichtungstoken stimmt.
 */

import type { Benutzer } from "./anmeldung";
import { schnittstelle } from "./schnittstelle";

const AUTH = schnittstelle("/auth");

export interface Einrichtungsstand {
  noetig: boolean;
}

function anfrage<T>(init: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  return AUTH.anfrage<T>("/einrichtung", init, signal);
}

/**
 * Ist die Ersteinrichtung noch offen?
 *
 * Braucht keine Anmeldung - es gibt ja noch niemanden, der sich anmelden
 * könnte. Die Antwort besteht aus genau einem Ja oder Nein.
 */
export function holeStand(signal?: AbortSignal): Promise<Einrichtungsstand> {
  return anfrage<Einrichtungsstand>({}, signal);
}

export function einrichten(daten: {
  token: string;
  name: string;
  passwort: string;
  anzeigename?: string;
}): Promise<Benutzer> {
  return anfrage<Benutzer>({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(daten),
  });
}
