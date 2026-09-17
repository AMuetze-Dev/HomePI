import type { Rolle } from "../../api/anmeldung";
import { ApiError } from "../../api/client";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export type { Rolle };

export interface Konto {
  id: string;
  name: string;
  anzeigename: string;
  aktiv: boolean;
  /** Artefakt → Rolle. */
  rechte: Record<string, Rolle>;
  angelegt: string | null;
  /** Darf dieses Konto die Verwaltung? Blendet Knöpfe aus - geprüft wird im Backend. */
  verwalter: boolean;
}

export interface Artefakt {
  id: string;
  titel: string;
  zugang: string;
}

export interface NeuesKonto {
  name: string;
  passwort: string;
  anzeigename?: string;
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
  const antwort = await fetch(`${BASE_URL}/verwaltung${pfad}`, {
    ...init,
    signal: signal ?? null,
    // Das Artefakt ist geschützt. Ohne das Sitzungscookie antwortet das
    // Gateway mit 401, egal was hier steht.
    credentials: "include",
    headers: { Accept: "application/json", ...init.headers },
  });

  if (!antwort.ok) {
    // Die Meldung aus problem+json ist für den Benutzer brauchbar - gerade
    // hier: "Das geht nicht am eigenen Konto" sagt mehr als "HTTP 409".
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

export function ladeKonten(signal?: AbortSignal): Promise<Konto[]> {
  return anfrage<Konto[]>("/benutzer", {}, signal);
}

export function ladeArtefakte(signal?: AbortSignal): Promise<Artefakt[]> {
  return anfrage<Artefakt[]>("/artefakte", {}, signal);
}

export function legeKontoAn(daten: NeuesKonto): Promise<Konto> {
  return anfrage<Konto>("/benutzer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(daten),
  });
}

export function setzeAktiv(id: string, aktiv: boolean): Promise<Konto> {
  return anfrage<Konto>(`/benutzer/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aktiv }),
  });
}

export function setzeAnzeigename(id: string, anzeigename: string): Promise<Konto> {
  return anfrage<Konto>(`/benutzer/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ anzeigename }),
  });
}

export function setzePasswort(id: string, passwort: string): Promise<void> {
  return anfrage<void>(`/benutzer/${id}/passwort`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ passwort }),
  });
}

export function loescheKonto(id: string): Promise<void> {
  return anfrage<void>(`/benutzer/${id}`, { method: "DELETE" });
}

export function setzeRecht(id: string, artefakt: string, rolle: Rolle): Promise<Konto> {
  return anfrage<Konto>(`/benutzer/${id}/rechte/${artefakt}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rolle }),
  });
}

export function entzieheRecht(id: string, artefakt: string): Promise<Konto> {
  return anfrage<Konto>(`/benutzer/${id}/rechte/${artefakt}`, { method: "DELETE" });
}
