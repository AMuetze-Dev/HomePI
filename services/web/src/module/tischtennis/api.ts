import { schnittstelle } from "../../api/schnittstelle";

/**
 * Zugriff auf das eigene Backend.
 *
 * Sitzungscookie, JSON und Fehlermeldungen aus problem+json erledigt
 * `schnittstelle` - für jedes Artefakt gleich. Hier stehen nur Pfade und
 * Typen. Eine eigene fetch-Hülle zu schreiben ist die falsche Datei.
 *
 * Alle `lade…`-Funktionen sprechen Endpunkte an, die ohne Anmeldung
 * antworten; alles Schreibende braucht ein Recht auf diesem Artefakt. Das
 * ist der Grund, warum die Dashboard-Ansicht für jeden Kollegen mit dem Link
 * funktioniert, der Würfelknopf aber nicht.
 */
const { anfrage, sende } = schnittstelle("/tischtennis");

export type Modus = "gruppen_ko" | "ko" | "schweizer";
export type TurnierZustand = "planung" | "laufend" | "beendet";
export type SpielZustand = "geplant" | "laeuft" | "beendet";
export type Phase =
  | "gruppe"
  | "ko"
  | "ko_verlierer"
  | "ko_finale"
  | "runde"
  | "entscheidung";

/** Einen Platz nach vorn oder nach hinten in der Warteschlange. */
export type Richtung = "hoch" | "runter";

export interface Einstellungen {
  modus: Modus;
  tische: number;
  /** Sagt nur, wie lange gespielt wird - in keinem Ergebnis steht sie. */
  best_of: number;
  minuten_pro_spiel: number;
  anzahl_gruppen: number;
  weiter_pro_gruppe: number;
  runden: number;
  /** Zweite Chance im KO: wer einmal verliert, spielt im Verliererzweig. */
  doppel_ko: boolean;
}

export interface Turnier extends Einstellungen {
  id: string;
  name: string;
  zustand: TurnierZustand;
  saat: number | null;
  runde_angesetzt: number;
  ko_steht: boolean;
  anzahl_teilnehmer: number;
  anzahl_spiele: number;
  offene_spiele: number;
}

export interface Teilnehmer {
  id: string;
  name: string;
  notiz: string;
  gruppe: string | null;
  freilose: number;
}

export interface Spiel {
  id: string;
  nummer: number;
  phase: Phase;
  runde: number;
  bezeichnung: string;
  gruppe: string | null;
  heim_id: string | null;
  gast_id: string | null;
  heim: string | null;
  gast: string | null;
  heim_herkunft: string | null;
  gast_herkunft: string | null;
  zustand: SpielZustand;
  tisch: number | null;
  sieger_id: string | null;
  freilos: boolean;
  begonnen_am: string | null;
  beendet_am: string | null;
  erwartet_ab: string | null;
  /** Der Vorgänger am selben Tisch läuft gerade - daran hängt die Glocke. */
  gleich_dran: boolean;
}

export interface Tabellenzeile {
  platz: number;
  teilnehmer_id: string | null;
  teilnehmer: string;
  spiele: number;
  siege: number;
  niederlagen: number;
  punkte: number;
}

export interface Tabelle {
  titel: string;
  zeilen: Tabellenzeile[];
  /** Punktgleiche an der Grenze, die noch gegeneinander spielen. */
  entscheidung_offen: string[];
}

export interface GruppeVorschau {
  name: string;
  teilnehmer: string[];
}

export interface PaarungVorschau {
  bezeichnung: string;
  heim: string;
  gast: string;
}

export interface Auslosung {
  saat: number;
  modus: Modus;
  gruppen: GruppeVorschau[];
  paarungen: PaarungVorschau[];
  anzahl_spiele: number;
  dauer_minuten: number;
  hinweis: string;
}

export interface Tisch {
  tisch: number;
  laeuft: Spiel | null;
  danach: Spiel[];
}

export interface Dashboard {
  turnier: Turnier | null;
  stand: string;
  tische: Tisch[];
  /** Alle Spiele - die Grundlage für Gruppenkarten und KO-Raster. */
  spiele: Spiel[];
  naechste: Spiel[];
  letzte: Spiel[];
  tabellen: Tabelle[];
  teilnehmer: Teilnehmer[];
  fertig: boolean;
}

export interface NeuesTurnier extends Partial<Einstellungen> {
  name: string;
}

export interface NeuerTeilnehmer {
  name: string;
  notiz?: string;
}

const kennung = (id: string) => encodeURIComponent(id);

export function ladeTurniere(signal?: AbortSignal): Promise<Turnier[]> {
  return anfrage<Turnier[]>("/", {}, signal);
}

export function ladeTurnier(id: string, signal?: AbortSignal): Promise<Turnier> {
  return anfrage<Turnier>(`/turnier/${kennung(id)}`, {}, signal);
}

/** Ohne Kennung: das laufende Turnier - das, was ein Besucher sehen will. */
export function ladeDashboard(id?: string, signal?: AbortSignal): Promise<Dashboard> {
  const pfad = id ? `/turnier/${kennung(id)}/dashboard` : "/dashboard";
  return anfrage<Dashboard>(pfad, {}, signal);
}

export function ladeTeilnehmer(id: string, signal?: AbortSignal): Promise<Teilnehmer[]> {
  return anfrage<Teilnehmer[]>(`/turnier/${kennung(id)}/teilnehmer`, {}, signal);
}

export function ladeSpiele(id: string, signal?: AbortSignal): Promise<Spiel[]> {
  return anfrage<Spiel[]>(`/turnier/${kennung(id)}/spiele`, {}, signal);
}

export function ladeTabellen(id: string, signal?: AbortSignal): Promise<Tabelle[]> {
  return anfrage<Tabelle[]>(`/turnier/${kennung(id)}/tabellen`, {}, signal);
}

export function legeTurnierAn(daten: NeuesTurnier): Promise<Turnier> {
  return sende<Turnier>("POST", "/turnier", daten);
}

export function aendereTurnier(id: string, daten: Einstellungen): Promise<Turnier> {
  return sende<Turnier>("PUT", `/turnier/${kennung(id)}`, daten);
}

export function loescheTurnier(id: string): Promise<void> {
  return sende<void>("DELETE", `/turnier/${kennung(id)}`);
}

export function legeTeilnehmerAn(
  id: string,
  daten: NeuerTeilnehmer,
): Promise<Teilnehmer> {
  return sende<Teilnehmer>("POST", `/turnier/${kennung(id)}/teilnehmer`, daten);
}

export function aendereTeilnehmer(
  id: string,
  daten: NeuerTeilnehmer,
): Promise<Teilnehmer> {
  return sende<Teilnehmer>("PUT", `/teilnehmer/${kennung(id)}`, daten);
}

export function entferneTeilnehmer(id: string): Promise<void> {
  return sende<void>("DELETE", `/teilnehmer/${kennung(id)}`);
}

/** Der Würfel: zeigt ein Los, ohne es zu speichern. */
export function loseAus(id: string, saat?: number): Promise<Auslosung> {
  return sende<Auslosung>("POST", `/turnier/${kennung(id)}/auslosung`, {
    saat: saat ?? null,
  });
}

export function wuerfleAus(id: string, saat: number): Promise<Turnier> {
  return sende<Turnier>("POST", `/turnier/${kennung(id)}/auswuerfeln`, { saat });
}

export function naechsteRunde(id: string): Promise<Turnier> {
  return sende<Turnier>("POST", `/turnier/${kennung(id)}/naechste-runde`);
}

export function setzeZurueck(id: string): Promise<Turnier> {
  return sende<Turnier>("POST", `/turnier/${kennung(id)}/zuruecksetzen`);
}

export function beendeTurnier(id: string): Promise<Turnier> {
  return sende<Turnier>("POST", `/turnier/${kennung(id)}/beenden`);
}

export function beginneSpiel(id: string, tisch?: number): Promise<Spiel> {
  return sende<Spiel>("POST", `/spiel/${kennung(id)}/beginnen`, { tisch: tisch ?? null });
}

/** Das ganze Ergebnis: wer gewonnen hat. */
export function trageErgebnisEin(id: string, siegerId: string): Promise<Spiel> {
  return sende<Spiel>("PUT", `/spiel/${kennung(id)}/ergebnis`, { sieger_id: siegerId });
}

export function nimmErgebnisZurueck(id: string): Promise<Spiel> {
  return sende<Spiel>("DELETE", `/spiel/${kennung(id)}/ergebnis`);
}

/**
 * Ein Spiel einen Platz nach vorn oder nach hinten.
 *
 * Nur um einen Platz: wer jemanden deutlich später spielen lassen will,
 * drückt mehrmals - und sieht dazwischen, was es mit dem Plan macht.
 */
export function verschiebeSpiel(id: string, richtung: Richtung): Promise<Spiel> {
  return sende<Spiel>("POST", `/spiel/${kennung(id)}/verschieben`, { richtung });
}
