import { schnittstelle } from "../../api/schnittstelle";

/**
 * Zugriff auf das eigene Backend.
 *
 * Sitzungscookie, JSON und Fehlermeldungen aus problem+json erledigt
 * `schnittstelle`. Hier stehen nur Pfade und Typen - gespiegelt aus
 * `modules/kinderzimmer/src/homepi_kinderzimmer/schemas.py`.
 */
const { anfrage, sende, adresse } = schnittstelle("/kinderzimmer");

export type Art =
  | "familie"
  | "tier"
  | "farbe"
  | "form"
  | "menge"
  | "ritual"
  | "gefuehl"
  | "geschichte"
  | "sonstiges";
export type Farbwort =
  | "rot"
  | "blau"
  | "gelb"
  | "gruen"
  | "orange"
  | "lila"
  | "rosa"
  | "weiss"
  | "schwarz"
  | "braun";
export type Formwort = "kreis" | "quadrat" | "dreieck" | "rechteck" | "stern" | "herz";
export type AufnahmeArt = "stimme" | "klang";

export interface Phase {
  nummer: number;
  titel: string;
  alter: string;
}

export interface Spiel {
  id: string;
  nummer: number;
  phase: number;
  titel: string;
  alter: string;
  ablauf: string;
  foerdert: string;
  warum: string;
  bereit: boolean;
  aktiv: boolean;
}

export interface Uebersicht {
  phasen: Phase[];
  spiele: Spiel[];
  stand: string;
  zahlen: { figuren: number; aufnahmen: number; geraete: number };
}

export interface Knopf {
  nummer: number;
  farbe: string;
  klang: string | null;
}

export interface Einstellungen {
  lautstaerke_max: number;
  helligkeit_max: number;
  ruhe_nach_min: number;
  startspiel: string;
  spiele_aktiv: string[];
  knoepfe: Knopf[];
}

export interface Aufnahme {
  id: string;
  titel: string;
  art: AufnahmeArt;
  dauer_ms: number;
  bytes: number;
  sha256: string;
  angelegt: string;
}

export interface FigurEingabe {
  uid: string;
  name: string;
  art: Art;
  farbe: Farbwort | null;
  form: Formwort | null;
  menge: number | null;
  stimme: string | null;
  klang: string | null;
}

export interface Figur extends FigurEingabe {
  id: string;
}

export interface UnbekannteFigur {
  uid: string;
  zuletzt: string | null;
}

export interface Geraet {
  id: string;
  name: string;
  zuletzt_gesehen: string | null;
  firmware: string | null;
  stand_aktuell: boolean | null;
  angelegt: string;
}

export interface GeraetMitToken extends Geraet {
  token: string;
}

export interface Ereignis {
  id: number;
  geraet: string;
  art: string;
  text: string;
  zeitpunkt: string | null;
  empfangen: string;
}

export interface Tagebucheintrag {
  id: string;
  datum: string;
  text: string;
}

export function ladeUebersicht(signal?: AbortSignal): Promise<Uebersicht> {
  return anfrage<Uebersicht>("/", {}, signal);
}

export function ladeEinstellungen(signal?: AbortSignal): Promise<Einstellungen> {
  return anfrage<Einstellungen>("/einstellungen", {}, signal);
}

export function speichereEinstellungen(werte: Einstellungen): Promise<Einstellungen> {
  return sende<Einstellungen>("PUT", "/einstellungen", werte);
}

export function ladeAufnahmen(signal?: AbortSignal): Promise<Aufnahme[]> {
  return anfrage<Aufnahme[]>("/aufnahmen", {}, signal);
}

/** Die WAV-Datei geht roh hinaus, Titel und Art stehen in der Adresse. */
export function ladeAufnahmeHoch(
  titel: string,
  art: AufnahmeArt,
  wav: Blob,
): Promise<Aufnahme> {
  const suche = new URLSearchParams({ titel, art });
  return anfrage<Aufnahme>(`/aufnahmen?${suche.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: wav,
  });
}

export function aendereAufnahme(
  id: string,
  werte: { titel: string; art: AufnahmeArt },
): Promise<Aufnahme> {
  return sende<Aufnahme>("PUT", `/aufnahmen/${encodeURIComponent(id)}`, werte);
}

export function entferneAufnahme(id: string): Promise<void> {
  return sende<void>("DELETE", `/aufnahmen/${encodeURIComponent(id)}`);
}

/** Für `<audio src>` - der Browser lädt selbst und schickt das Cookie mit. */
export function aufnahmeAdresse(id: string): string {
  return adresse(`/aufnahmen/${encodeURIComponent(id)}/datei`);
}

export function ladeFiguren(signal?: AbortSignal): Promise<Figur[]> {
  return anfrage<Figur[]>("/figuren", {}, signal);
}

export function ladeUnbekannte(signal?: AbortSignal): Promise<UnbekannteFigur[]> {
  return anfrage<UnbekannteFigur[]>("/figuren/unbekannt", {}, signal);
}

export function legeFigurAn(werte: FigurEingabe): Promise<Figur> {
  return sende<Figur>("POST", "/figuren", werte);
}

export function aendereFigur(id: string, werte: FigurEingabe): Promise<Figur> {
  return sende<Figur>("PUT", `/figuren/${encodeURIComponent(id)}`, werte);
}

export function entferneFigur(id: string): Promise<void> {
  return sende<void>("DELETE", `/figuren/${encodeURIComponent(id)}`);
}

export function ladeGeraete(signal?: AbortSignal): Promise<Geraet[]> {
  return anfrage<Geraet[]>("/geraete", {}, signal);
}

export function legeGeraetAn(name: string): Promise<GeraetMitToken> {
  return sende<GeraetMitToken>("POST", "/geraete", { name });
}

export function stelleTokenAus(id: string): Promise<GeraetMitToken> {
  return sende<GeraetMitToken>("POST", `/geraete/${encodeURIComponent(id)}/token`);
}

export function entferneGeraet(id: string): Promise<void> {
  return sende<void>("DELETE", `/geraete/${encodeURIComponent(id)}`);
}

/** Wohin das Gerät seine Anfragen schickt. */
export function geraeteAdresse(): string {
  return new URL(adresse(""), window.location.href).toString();
}

export function ladeProtokoll(signal?: AbortSignal): Promise<Ereignis[]> {
  return anfrage<Ereignis[]>("/protokoll", {}, signal);
}

export function ladeTagebuch(signal?: AbortSignal): Promise<Tagebucheintrag[]> {
  return anfrage<Tagebucheintrag[]>("/tagebuch", {}, signal);
}

export function schreibeTagebuch(werte: {
  datum: string;
  text: string;
}): Promise<Tagebucheintrag> {
  return sende<Tagebucheintrag>("POST", "/tagebuch", werte);
}

export function entferneTagebuch(id: string): Promise<void> {
  return sende<void>("DELETE", `/tagebuch/${encodeURIComponent(id)}`);
}
