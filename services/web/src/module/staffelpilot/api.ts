import { ApiError } from "../../api/client";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export type Schwere = "kritisch" | "warnung" | "hinweis";
export type Entscheidung = "offen" | "kenntnis" | "verworfen";
/** Wohin ein Befund fuehrt, wenn er stehen bleibt. Sagt der Prueflauf. */
export type Weg = "kein" | "mahnung" | "sportgericht";
export type VorgangArt = "mahnung" | "sportgericht";
export type VorgangZustand = "entwurf" | "versandt" | "erledigt";
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
  weg: Weg;
  /** Gesetzt, sobald ein Entwurf dazu besteht. */
  vorgang_id: string | null;
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
  vorgaenge_entwurf: number;
}

export interface Einstellungen {
  staffelleiter: string;
  verband: string;
  absender: string;
  pruefzeitraum_tage: number;
  frist_tage: number;
}

export interface Mannschaft {
  id: string;
  name: string;
  verein: string;
  nummer: number;
  ist_sg: boolean;
  hoehere: string[];
  bestaetigt: boolean;
  /** Berechnet: ob der geratene Aufbau einen zweiten Blick wert ist. */
  unsicher: boolean;
}

export interface VorgangZeile {
  id: string;
  befund_id: string;
  art: VorgangArt;
  aktenzeichen: string;
  verein: string;
  betroffener: string;
  betreff: string;
  zustand: VorgangZustand;
}

export interface Vorgang extends VorgangZeile {
  grund: string;
  empfaenger: string;
  text: string;
  versandt_am: string | null;
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

async function anfrage<T>(
  pfad: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
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

export function ladeWarteschlange(
  staffelId?: string,
  signal?: AbortSignal,
): Promise<SpielZeile[]> {
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
  return anfrage<Befund>(
    `/befunde/${befundId}/entscheidung`,
    mitKoerper("POST", { art, grund }),
  );
}

export function hakeAb(spielId: string): Promise<Spiel> {
  return anfrage<Spiel>(`/spiele/${spielId}/haken`, { method: "POST" });
}

export function loeseHaken(spielId: string): Promise<Spiel> {
  return anfrage<Spiel>(`/spiele/${spielId}/haken`, { method: "DELETE" });
}

// ── Einstellungen ────────────────────────────────────────────────────────

export function ladeEinstellungen(signal?: AbortSignal): Promise<Einstellungen> {
  return anfrage<Einstellungen>("/einstellungen", {}, signal);
}

/** Nur die mitgeschickten Felder. Ausgelassene bleiben, wie sie waren. */
export function speichereEinstellungen(
  daten: Partial<Einstellungen>,
): Promise<Einstellungen> {
  return anfrage<Einstellungen>("/einstellungen", mitKoerper("PUT", daten));
}

// ── Mannschaften ─────────────────────────────────────────────────────────

export function ladeMannschaften(
  staffelId: string,
  signal?: AbortSignal,
): Promise<Mannschaft[]> {
  return anfrage<Mannschaft[]>(`/staffeln/${staffelId}/mannschaften`, {}, signal);
}

/**
 * Die Meldung als Ganzes. Wer `hoehere` mitschickt, bestaetigt sie damit -
 * ein spaeteres Einspielen aus DFBnet ueberschreibt sie dann nicht mehr.
 */
export function speichereMannschaften(
  staffelId: string,
  mannschaften: { name: string; ist_sg?: boolean; hoehere?: string[] }[],
): Promise<Mannschaft[]> {
  return anfrage<Mannschaft[]>(
    `/staffeln/${staffelId}/mannschaften`,
    mitKoerper("PUT", { mannschaften }),
  );
}

// ── Vorgaenge ────────────────────────────────────────────────────────────

export function ladeVorgaenge(
  zustand?: VorgangZustand,
  signal?: AbortSignal,
): Promise<VorgangZeile[]> {
  const frage = zustand ? `?zustand=${zustand}` : "";
  return anfrage<VorgangZeile[]>(`/vorgaenge${frage}`, {}, signal);
}

export function ladeVorgang(id: string, signal?: AbortSignal): Promise<Vorgang> {
  return anfrage<Vorgang>(`/vorgaenge/${id}`, {}, signal);
}

/** Erzeugt den Entwurf aus der Vorlage - und verschickt ihn nicht. */
export function legeVorgangAn(
  befundId: string,
  daten: { verein?: string; betroffener?: string; grund?: string } = {},
): Promise<Vorgang> {
  return anfrage<Vorgang>(`/befunde/${befundId}/vorgang`, mitKoerper("POST", daten));
}

export function aendereVorgang(
  id: string,
  daten: { empfaenger?: string; betreff?: string; text?: string },
): Promise<Vorgang> {
  return anfrage<Vorgang>(`/vorgaenge/${id}`, mitKoerper("PATCH", daten));
}

/**
 * "versandt" heisst: ein Mensch hat es abgeschickt. Dieses Programm
 * verschickt nichts und hat auch keinen Weg dorthin.
 */
export function setzeVorgangZustand(
  id: string,
  zustand: VorgangZustand,
): Promise<Vorgang> {
  return anfrage<Vorgang>(`/vorgaenge/${id}/zustand`, mitKoerper("POST", { zustand }));
}

export function verwerfeVorgang(id: string): Promise<void> {
  return anfrage<void>(`/vorgaenge/${id}`, { method: "DELETE" });
}
