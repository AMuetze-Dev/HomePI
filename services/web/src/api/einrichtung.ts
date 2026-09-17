/**
 * Die Ersteinrichtung.
 *
 * Dass diese Oberfläche die Maske zeigt oder nicht, ist **keine** Sicherung.
 * Wer `/einrichtung` von Hand aufruft oder direkt gegen die API spricht,
 * landet trotzdem beim Backend - und dort wird bei jedem Aufruf geprüft, ob es
 * wirklich noch keinen Verwalter gibt und ob das Einrichtungstoken stimmt.
 */

import type { Benutzer } from "./anmeldung";
import { ApiError } from "./client";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export interface Einrichtungsstand {
  noetig: boolean;
}

/** Fehlerformat des Backends (RFC 9457). */
interface Problem {
  title?: string;
  detail?: string;
}

async function anfrage<T>(init: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  const antwort = await fetch(`${BASE_URL}/auth/einrichtung`, {
    ...init,
    signal: signal ?? null,
    credentials: "include",
    headers: { Accept: "application/json", ...init.headers },
  });

  if (!antwort.ok) {
    let meldung = `Fehler ${antwort.status}`;
    try {
      const problem = (await antwort.json()) as Problem;
      meldung = problem.detail ?? problem.title ?? meldung;
    } catch {
      /* Antwort ohne JSON-Körper - dann bleibt es beim Statuscode */
    }
    throw new ApiError(meldung, antwort.status);
  }

  return (await antwort.json()) as T;
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
