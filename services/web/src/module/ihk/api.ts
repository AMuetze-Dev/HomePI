import { ApiError } from "../../api/client";
import { schnittstelle } from "../../api/schnittstelle";

/**
 * Zugriff auf das eigene Backend.
 *
 * Gerechnet wird nur dort: Jede Änderung an einer Bewertung kommt mit der
 * neuen Auswertung zurück. Die Oberfläche zeigt Punkte, Noten und
 * Grenzfälle an, sie bestimmt sie nicht - sonst gäbe es den Rechenkern zweimal,
 * und zwei Rechenkerne laufen auseinander.
 */
const { anfrage, sende, adresse } = schnittstelle("/ihk");

// ── Katalog ──────────────────────────────────────────────────────────────────

export type KnotenArt = "points" | "malus" | "group" | "scale";

export interface Knoten {
  id: string;
  label: string;
  art: KnotenArt;
  max: number | null;
  hinweis: string;
  kinder: Knoten[];
}

export interface Block {
  id: string;
  knoten: string[];
}

export interface Sektion {
  id: string;
  nr: string;
  label: string;
  max: number;
  kinder: Knoten[];
  bloecke: Block[];
}

export type MepBereich = "planen_softwareprodukt" | "algorithmen" | "wiso";
export type Korrekturart = "Erstkorrektur" | "Zweitkorrektur" | "Information";

export interface Katalog {
  doku: Sektion[];
  praesentation: Sektion[];
  skala: number[];
  korrekturarten: Korrekturart[];
  notenbaender: { von: number; bis: number; note: number }[];
  teil1_label: string;
  bereiche: { id: MepBereich; label: string }[];
  projekt_label: string;
  praesi_grenze_min: number;
  gesamt_grenze_min: number;
}

// ── Prüfungstage ─────────────────────────────────────────────────────────────

export interface Tag {
  id: string;
  datum: string;
  ort: string;
  korrektor: string;
  anzahl_prueflinge: number;
}

export interface NeuerTag {
  datum: string;
  ort: string;
  korrektor: string;
}

export interface Status {
  runtergeladen: boolean;
  kontrolliert: boolean;
  abgestimmt: boolean;
  hochgeladen: boolean;
}

export interface PrueflingKurz {
  id: string;
  reihenfolge: number;
  name: string;
  ident: string;
  korrekturart: Korrekturart;
  status: Status;
  doku_punkte: number | null;
  doku_note: number | null;
  praesi_punkte: number | null;
  praesi_note: number | null;
  /** Zahl der hinterlegten PDFs - daran erkennt man, ob die Doku da ist. */
  dokumente: number;
}

export interface TagDetail {
  tag: Tag;
  prueflinge: PrueflingKurz[];
}

// ── Prüfling ─────────────────────────────────────────────────────────────────

export interface Bewertung {
  doku: Record<string, number>;
  doku_bemerkungen: Record<string, string>;
  praesi_skala: Record<string, number>;
  praesi_punkte: Record<string, number>;
  praesi_bemerkungen: Record<string, string>;
  notizen: string;
  fragen: string;
}

export interface BewertungAenderung {
  doku?: Record<string, number | null>;
  doku_bemerkungen?: Record<string, string | null>;
  praesi_skala?: Record<string, number | null>;
  praesi_punkte?: Record<string, number | null>;
  praesi_bemerkungen?: Record<string, string | null>;
  notizen?: string;
  fragen?: string;
}

export interface Teilnoten {
  teil1: number | null;
  planen_softwareprodukt: number | null;
  algorithmen: number | null;
  wiso: number | null;
  mep: { bereich: MepBereich; punkte: number } | null;
}

export interface Zeiten {
  praesi_start: string | null;
  praesi_ende: string | null;
  fg_start: string | null;
  fg_ende: string | null;
}

export type Zeitaktion =
  "praesentation_starten" | "fachgespraech_starten" | "beenden" | "zuruecksetzen";

export type DokumentArt = "projekt" | "kunde";

export interface Dokument {
  id: string;
  art: DokumentArt;
  dateiname: string;
  groesse: number;
  angelegt: string;
}

export interface SektionErgebnis {
  id: string;
  nr: string;
  label: string;
  max: number;
  wert: number | null;
  vollstaendig: boolean;
  vorschlag: number | null;
}

export interface TeilErgebnis {
  sektionen: SektionErgebnis[];
  gesamt: number | null;
  note: number | null;
  grenzfall: boolean;
  fehlend: string[];
}

export interface BereichErgebnis {
  id: MepBereich;
  label: string;
  gewicht: number;
  schriftlich: number | null;
  muendlich: number | null;
  wert: number | null;
}

export interface GesamtErgebnis {
  projekt: number | null;
  bereiche: BereichErgebnis[];
  teil1: number | null;
  teil2: number | null;
  gesamt: number | null;
  note: number | null;
  grenzfall: boolean;
  fehlend: string[];
}

export interface Pruefling {
  id: string;
  tag: Tag;
  reihenfolge: number;
  name: string;
  ident: string;
  korrekturart: Korrekturart;
  status: Status;
  bewertung: Bewertung;
  teilnoten: Teilnoten;
  zeiten: Zeiten;
  dokumente: Dokument[];
  auswertung: {
    doku: TeilErgebnis;
    praesentation: TeilErgebnis;
    gesamt_ohne_mep: GesamtErgebnis;
    gesamt_mit_mep: GesamtErgebnis | null;
  };
  /** Uhr des Servers - laufende Zeiten werden gegen sie gerechnet. */
  jetzt: string;
}

export interface Stammdaten {
  name?: string;
  ident?: string;
  korrekturart?: Korrekturart;
  status?: Partial<Status>;
}

const id = encodeURIComponent;

export function ladeKatalog(signal?: AbortSignal): Promise<Katalog> {
  return anfrage<Katalog>("/katalog", {}, signal);
}

/** Alle Tage samt ihren Prüflingen - die Übersicht klappt sie auf, ohne nachzuladen. */
export function ladeTage(signal?: AbortSignal): Promise<TagDetail[]> {
  return anfrage<TagDetail[]>("/", {}, signal);
}

export function legeTagAn(daten: NeuerTag): Promise<Tag> {
  return sende<Tag>("POST", "/tage", daten);
}

export function ladeTag(tagId: string, signal?: AbortSignal): Promise<TagDetail> {
  return anfrage<TagDetail>(`/tage/${id(tagId)}`, {}, signal);
}

export function aendereTag(tagId: string, daten: Partial<NeuerTag>): Promise<Tag> {
  return sende<Tag>("PATCH", `/tage/${id(tagId)}`, daten);
}

export function entferneTag(tagId: string): Promise<void> {
  return sende<void>("DELETE", `/tage/${id(tagId)}`);
}

export function legePrueflingAn(tagId: string, name: string): Promise<Pruefling> {
  return sende<Pruefling>("POST", `/tage/${id(tagId)}/prueflinge`, { name });
}

export function ladePruefling(
  prueflingId: string,
  signal?: AbortSignal,
): Promise<Pruefling> {
  return anfrage<Pruefling>(`/prueflinge/${id(prueflingId)}`, {}, signal);
}

export function aenderePruefling(
  prueflingId: string,
  daten: Stammdaten,
): Promise<Pruefling> {
  return sende<Pruefling>("PATCH", `/prueflinge/${id(prueflingId)}`, daten);
}

export function entfernePruefling(prueflingId: string): Promise<void> {
  return sende<void>("DELETE", `/prueflinge/${id(prueflingId)}`);
}

export function aendereBewertung(
  prueflingId: string,
  daten: BewertungAenderung,
): Promise<Pruefling> {
  return sende<Pruefling>("PATCH", `/prueflinge/${id(prueflingId)}/bewertung`, daten);
}

export function setzeTeilnoten(
  prueflingId: string,
  daten: Teilnoten,
): Promise<Pruefling> {
  return sende<Pruefling>("PUT", `/prueflinge/${id(prueflingId)}/teilnoten`, daten);
}

export function schalteZeit(prueflingId: string, aktion: Zeitaktion): Promise<Pruefling> {
  return sende<Pruefling>("POST", `/prueflinge/${id(prueflingId)}/zeit`, { aktion });
}

/**
 * Lädt eine Datei als rohen Körper hoch. Kein multipart: Das Backend liest
 * die Bytes direkt, Art und Name stehen in der Adresse.
 */
export async function ladeDokumentHoch(
  prueflingId: string,
  art: DokumentArt,
  datei: File,
): Promise<Dokument> {
  const suche = new URLSearchParams({ art, dateiname: datei.name });
  return anfrage<Dokument>(
    `/prueflinge/${id(prueflingId)}/dokumente?${suche.toString()}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/pdf" },
      body: datei,
    },
  );
}

export function entferneDokument(prueflingId: string, dokumentId: string): Promise<void> {
  return sende<void>(
    "DELETE",
    `/prueflinge/${id(prueflingId)}/dokumente/${id(dokumentId)}`,
  );
}

export function dokumentAdresse(prueflingId: string, dokumentId: string): string {
  return adresse(`/prueflinge/${id(prueflingId)}/dokumente/${id(dokumentId)}`);
}

export function korrekturbogenAdresse(prueflingId: string): string {
  return adresse(`/prueflinge/${id(prueflingId)}/korrekturbogen`);
}

/** Holt ein Dokument als Bytes - für die PDF-Ansicht, die selbst zeichnet. */
export async function ladeDokumentDaten(
  prueflingId: string,
  dokumentId: string,
  signal?: AbortSignal,
): Promise<ArrayBuffer> {
  const antwort = await fetch(dokumentAdresse(prueflingId, dokumentId), {
    credentials: "include",
    signal: signal ?? null,
  });
  if (!antwort.ok)
    throw new ApiError("Das Dokument ließ sich nicht laden", antwort.status);
  return antwort.arrayBuffer();
}
