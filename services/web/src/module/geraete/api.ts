import { ApiError } from "../../api/client";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export type GeraetZustand = "bereit" | "wartung";

export interface Geraet {
  id: string;
  name: string;
  raum: string;
  zustand: GeraetZustand;
  eingeschaltet: boolean;
}

export interface Zusammenfassung {
  anzahl: number;
  eingeschaltet: number;
  in_wartung: number;
  raeume: Record<string, number>;
}

export interface NeuesGeraet {
  name: string;
  raum: string;
  zustand?: GeraetZustand;
}

/** Fehlerformat des Backends (RFC 9457). */
interface Problem {
  title?: string;
  detail?: string;
}

async function anfrage<T>(
  pfad: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  const antwort = await fetch(`${BASE_URL}/geraete${pfad}`, {
    ...init,
    signal: signal ?? null,
    headers: { Accept: "application/json", ...init.headers },
  });

  if (!antwort.ok) {
    // Das Backend schickt bei jedem Fehler problem+json. Die Meldung daraus
    // ist fuer den Benutzer brauchbar - "HTTP 409" waere es nicht.
    let meldung = `Fehler ${antwort.status}`;
    try {
      const problem = (await antwort.json()) as Problem;
      meldung = problem.detail ?? problem.title ?? meldung;
    } catch {
      /* Antwort ohne JSON-Koerper - dann bleibt es beim Statuscode */
    }
    throw new ApiError(meldung, antwort.status);
  }

  if (antwort.status === 204) return undefined as T;
  return (await antwort.json()) as T;
}

export function ladeGeraete(signal?: AbortSignal): Promise<Geraet[]> {
  return anfrage<Geraet[]>("/", {}, signal);
}

export function ladeZusammenfassung(signal?: AbortSignal): Promise<Zusammenfassung> {
  return anfrage<Zusammenfassung>("/zusammenfassung", {}, signal);
}

export function legeGeraetAn(daten: NeuesGeraet): Promise<Geraet> {
  return anfrage<Geraet>("/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(daten),
  });
}

export function schalteGeraet(id: string, eingeschaltet: boolean): Promise<Geraet> {
  return anfrage<Geraet>(`/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ eingeschaltet }),
  });
}

export function entferneGeraet(id: string): Promise<void> {
  return anfrage<void>(`/${id}`, { method: "DELETE" });
}
