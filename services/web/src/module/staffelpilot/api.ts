import { ApiError } from "../../api/client";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export type Schwere = "kritisch" | "warnung" | "hinweis";
export type Entscheidung = "offen" | "kenntnis" | "verworfen";
export type Altersklasse = "maenner" | "frauen" | "ue32" | "ue35" | "ue40" | "ue50";

export interface Staffel {
  id: string;
  name: string;
  altersklasse: Altersklasse;
  spielklasse: string;
  saison: string;
  aktiv: boolean;
}

export interface Befund {
  id: string;
  regel: string;
  schwere: Schwere;
  titel: string;
  text: string;
  person: string;
  mannschaft: string;
  entscheidung: Entscheidung;
  grund: string;
}

/** Eine Zeile der Warteschlange - ohne die Befunde selbst. */
export interface SpielZeile {
  id: string;
  dfbnet_id: string;
  datum: string;
  heim: string;
  gast: string;
  ergebnis: string;
  abgehakt: boolean;
  offene_befunde: number;
  kritische_befunde: number;
}

export interface Spiel extends Omit<SpielZeile, "offene_befunde" | "kritische_befunde"> {
  staffel_id: string;
  abgehakt_am: string | null;
  befunde: Befund[];
}

export interface Zusammenfassung {
  spiele: number;
  offen: number;
  abgehakt: number;
  befunde_offen: number;
  befunde_kritisch: number;
  staffeln_aktiv: number;
}

export interface NeueStaffel {
  name: string;
  altersklasse: Altersklasse;
  spielklasse: string;
  saison?: string;
}

/** Fehlerformat des Backends (RFC 9457). */
interface Problem {
  title?: string;
  detail?: string;
}

async function anfrage<T>(pfad: string, init: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  const antwort = await fetch(`${BASE_URL}/staffelpilot${pfad}`, {
    ...init,
    signal: signal ?? null,
    // Das Artefakt ist geschuetzt. Ohne das Sitzungscookie antwortet das
    // Gateway mit 401, egal was hier steht.
    credentials: "include",
    headers: { Accept: "application/json", ...init.headers },
  });

  if (!antwort.ok) {
    // Das Backend schickt bei jedem Fehler problem+json. Die Meldung daraus
    // ist fuer den Staffelleiter brauchbar - "HTTP 409" waere es nicht.
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

function mitKoerper(methode: string, daten: unknown): RequestInit {
  return {
    method: methode,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(daten),
  };
}

export function ladeStaffeln(signal?: AbortSignal): Promise<Staffel[]> {
  return anfrage<Staffel[]>("/staffeln", {}, signal);
}

export function legeStaffelAn(daten: NeueStaffel): Promise<Staffel> {
  return anfrage<Staffel>("/staffeln", mitKoerper("POST", daten));
}

export function ladeWarteschlange(staffelId?: string, signal?: AbortSignal): Promise<SpielZeile[]> {
  const frage = staffelId ? `?staffel_id=${encodeURIComponent(staffelId)}` : "";
  return anfrage<SpielZeile[]>(`/${frage}`, {}, signal);
}

export function ladeZusammenfassung(signal?: AbortSignal): Promise<Zusammenfassung> {
  return anfrage<Zusammenfassung>("/zusammenfassung", {}, signal);
}

export function ladeSpiel(id: string, signal?: AbortSignal): Promise<Spiel> {
  return anfrage<Spiel>(`/spiele/${id}`, {}, signal);
}

export function entscheide(
  befundId: string,
  art: "kenntnis" | "verworfen",
  grund = "",
): Promise<Befund> {
  return anfrage<Befund>(`/befunde/${befundId}/entscheidung`, mitKoerper("POST", { art, grund }));
}

export function hakeAb(spielId: string): Promise<Spiel> {
  return anfrage<Spiel>(`/spiele/${spielId}/haken`, { method: "POST" });
}

export function loeseHaken(spielId: string): Promise<Spiel> {
  return anfrage<Spiel>(`/spiele/${spielId}/haken`, { method: "DELETE" });
}
