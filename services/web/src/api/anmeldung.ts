/**
 * Anmeldung gegen `/auth`.
 *
 * Das Token liegt in einem httponly-Cookie. Es ist damit für JavaScript
 * unlesbar - ein XSS-Fund in dieser Anwendung liefert einem Angreifer also
 * keine Sitzung. Der Preis: der Browser muss das Cookie mitschicken, deshalb
 * `credentials: "include"` bei jeder Anfrage.
 */

import { ApiError } from "./client";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export type Rolle = "leser" | "nutzer" | "verwalter";

export interface Benutzer {
  id: string;
  name: string;
  anzeigename: string;
  /** Artefakt → Rolle. Nur zum Ausblenden von Bedienelementen - geprüft wird im Backend. */
  rechte: Record<string, Rolle>;
  /**
   * True, solange das Passwort von jemand anderem gesetzt wurde.
   *
   * Bis zum Wechsel weist das Backend dieses Konto an jedem Artefakt ab. Die
   * Maske im Frontend ist die Führung dorthin, nicht die Sicherung.
   */
  passwort_wechseln: boolean;
}

/** Fehlerformat des Backends (RFC 9457). */
interface Problem {
  title?: string;
  detail?: string;
}

async function anfrage<T>(pfad: string, init: RequestInit = {}): Promise<T> {
  const antwort = await fetch(`${BASE_URL}/auth${pfad}`, {
    ...init,
    credentials: "include",
    headers: { Accept: "application/json", ...init.headers },
  });

  if (!antwort.ok) {
    // Die Meldung aus problem+json ist für den Benutzer brauchbar,
    // "HTTP 401" wäre es nicht.
    let meldung = `Fehler ${antwort.status}`;
    try {
      const problem = (await antwort.json()) as Problem;
      meldung = problem.detail ?? problem.title ?? meldung;
    } catch {
      /* Antwort ohne JSON-Körper - dann bleibt es beim Statuscode */
    }
    throw new ApiError(meldung, antwort.status);
  }

  if (antwort.status === 204) return undefined as T;
  return (await antwort.json()) as T;
}

export function anmelden(name: string, passwort: string): Promise<Benutzer> {
  return anfrage<Benutzer>("/anmelden", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, passwort }),
  });
}

export function abmelden(): Promise<void> {
  return anfrage<void>("/abmelden", { method: "POST" });
}

/**
 * Das eigene Passwort ändern.
 *
 * Die laufende Sitzung bleibt bestehen, alle anderen Geräte fliegen raus. Wer
 * sein Passwort ändert, tut das häufig genau deshalb.
 */
export function aenderePasswort(altes: string, neues: string): Promise<void> {
  return anfrage<void>("/passwort", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ altes_passwort: altes, neues_passwort: neues }),
  });
}

/**
 * Wer ist angemeldet? `null`, wenn niemand.
 *
 * 401 ist hier kein Fehler, sondern die Antwort auf die Frage - deshalb wird
 * er nicht geworfen. Jeder andere Fehler schon: ein abgestürztes Gateway soll
 * nicht wie "nicht angemeldet" aussehen.
 */
export async function holeIch(signal?: AbortSignal): Promise<Benutzer | null> {
  const antwort = await fetch(`${BASE_URL}/auth/ich`, {
    signal: signal ?? null,
    credentials: "include",
    headers: { Accept: "application/json" },
  });

  if (antwort.status === 401) return null;
  if (!antwort.ok) {
    throw new ApiError(`Unerwartete Antwort ${antwort.status}`, antwort.status);
  }
  return (await antwort.json()) as Benutzer;
}
