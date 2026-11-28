import { schnittstelle } from "../../api/schnittstelle";

/**
 * Zugriff auf das eigene Backend.
 *
 * Sitzungscookie, JSON und Fehlermeldungen aus problem+json erledigt
 * `schnittstelle`. Das gilt auch für das Spielertoken: Es ist ein
 * httponly-Cookie, das der Browser bei `credentials: "include"` selbst
 * mitschickt - diese Datei sieht es nie, und ein Skript auf der Seite auch
 * nicht.
 */
const { anfrage, sende, adresse } = schnittstelle("/quiz");

// ------------------------------------------------------------- Fragen

export type Fragetyp =
  | "freitext"
  | "zahl"
  | "schaetzung"
  | "auswahl"
  | "buzzer"
  | "bild"
  | "hotspot"
  | "sortieren"
  | "zuordnen"
  | "bildauswahl";

export interface Option {
  text: string;
  richtig: boolean;
}

export interface Paar {
  links: string;
  rechts: string;
}

export interface BildOption {
  text: string;
  richtig: boolean;
}

export interface Ziel {
  x: number;
  y: number;
  radius: number;
}

export type FrageDaten =
  | { typ: "freitext"; loesungen: string[] }
  | { typ: "zahl"; loesung: number; toleranz: number; einheit: string }
  | {
      typ: "schaetzung";
      minimum: number;
      maximum: number;
      schritt: number;
      loesung: number;
      einheit: string;
    }
  | { typ: "auswahl"; optionen: Option[] }
  | { typ: "buzzer"; loesung: string }
  | { typ: "bild"; loesungen: string[] }
  | { typ: "hotspot"; ziele: Ziel[] }
  | { typ: "sortieren"; elemente: string[] }
  | { typ: "zuordnen"; paare: Paar[] }
  | { typ: "bildauswahl"; optionen: BildOption[] };

export interface FrageEingabe {
  text: string;
  kategorie: string;
  punkte: number;
  zeitlimit: number | null;
  daten: FrageDaten;
}

export interface Frage extends FrageEingabe {
  id: string;
  position: number;
  hat_bild: boolean;
  /** Weitere Medien: "ton" und "option-<n>" (Bildauswahl). */
  medien: string[];
}

export interface Katalog {
  id: string;
  titel: string;
  beschreibung: string;
  anzahl_fragen: number;
  geaendert: string;
}

export interface KatalogDetail extends Katalog {
  fragen: Frage[];
}

// ------------------------------------------------------------- Runden

export type Rundenstatus = "lobby" | "laeuft" | "beendet";
export type Phase = "keine" | "bereit" | "offen" | "gesperrt" | "aufgeloest";
export type Urteil = "wartet" | "richtig" | "falsch";

export interface Runde {
  id: string;
  code: string;
  katalog_id: string;
  katalog_titel: string;
  status: Rundenstatus;
  anzahl_spieler: number;
  angelegt: string;
  beitritt_offen: boolean;
}

export interface TeamPlatz {
  id: string;
  name: string;
  punkte: number;
  rang: number;
  mitglieder: number;
}

export interface AntwortSicht {
  id: string;
  spieler_id: string;
  spieler: string;
  anzeige: string;
  eingeloggt: boolean;
  punkte: number | null;
  richtig: boolean | null;
  wert: Record<string, unknown>;
}

export interface SpielerSicht {
  id: string;
  name: string;
  punkte: number;
  rang: number;
  zuletzt_gesehen: string;
  verbunden: boolean;
  team_id: string | null;
}

export interface BuzzerSicht {
  spieler_id: string;
  spieler: string;
  position: number;
  urteil: Urteil;
}

export interface Steuerung {
  runde: Runde;
  phase: Phase;
  frage: Frage | null;
  fragen: Frage[];
  beantwortet: string[];
  bild_sichtbar: boolean;
  frist: string | null;
  jetzt: string;
  spieler: SpielerSicht[];
  antworten: AntwortSicht[];
  buzzer: BuzzerSicht[];
  teams: TeamPlatz[];
}

export interface AuswertungAntwort {
  spieler: string;
  anzeige: string;
  punkte: number | null;
  richtig: boolean | null;
}

export interface FrageAuswertung {
  frage_id: string;
  nummer: number;
  text: string;
  typ: Fragetyp;
  loesung: string;
  antworten: AuswertungAntwort[];
  richtig: number;
  gesamt: number;
}

export interface ImportErgebnis {
  katalog: KatalogDetail;
  hinweise: string[];
}

export interface Wiederkehrcode {
  code: string;
  gueltig_bis: string;
}

// ------------------------------------------------------------- Spieler

export interface Element {
  kennung: string;
  text: string;
}

export interface Loesung {
  anzeige: string;
  texte: string[];
  zahl: number | null;
  toleranz: number | null;
  optionen: number[];
  ziele: Ziel[];
  reihenfolge: string[];
  zuordnung: Record<string, string>;
}

export interface OeffentlicheFrage {
  nummer: number;
  anzahl: number;
  kategorie: string;
  typ: Fragetyp;
  punkte: number;
  text: string | null;
  hat_bild: boolean;
  optionen: string[];
  mehrfach: boolean;
  elemente: Element[];
  minimum: number | null;
  maximum: number | null;
  schritt: number | null;
  einheit: string;
  links: string[];
  rechts: Element[];
  bildoptionen: string[];
  hat_ton: boolean;
  loesung: Loesung | null;
}

export interface Platz {
  name: string;
  punkte: number;
  rang: number;
  team: string | null;
}

export interface EigeneAntwort {
  wert: Record<string, unknown>;
  eingeloggt: boolean;
  punkte: number | null;
  richtig: boolean | null;
}

export interface Ich {
  name: string;
  punkte: number;
  rang: number;
  antwort: EigeneAntwort | null;
  buzzer_position: number | null;
  buzzer_urteil: Urteil | null;
  team: string | null;
}

export interface Rundenstand {
  code: string;
  titel: string;
  status: Rundenstatus;
  phase: Phase;
  frage: OeffentlicheFrage | null;
  bild_sichtbar: boolean;
  frist: string | null;
  jetzt: string;
  rangliste: Platz[];
  anzahl_antworten: number;
  buzzer: string | null;
  ich: Ich | null;
  teams: TeamPlatz[];
  beitritt_offen: boolean;
}

export interface AntwortEingabe {
  text?: string;
  zahl?: number;
  auswahl?: number[];
  x?: number;
  y?: number;
  reihenfolge?: string[];
  zuordnung?: Record<string, string>;
  eingeloggt?: boolean;
}

// ------------------------------------------------------------- offen

const code = (wert: string) => `/runden/${encodeURIComponent(wert)}`;

export function ladeRundenstand(
  rundencode: string,
  signal?: AbortSignal,
): Promise<Rundenstand> {
  return anfrage<Rundenstand>(code(rundencode), {}, signal);
}

export function trittBei(
  rundencode: string,
  name: string,
  wiederkehrcode?: string,
  teamId?: string,
): Promise<Rundenstand> {
  return sende<Rundenstand>("POST", `${code(rundencode)}/beitreten`, {
    name,
    ...(wiederkehrcode ? { wiederkehrcode } : {}),
    ...(teamId ? { team_id: teamId } : {}),
  });
}

export function wechsleTeam(rundencode: string, teamId: string): Promise<Rundenstand> {
  return sende<Rundenstand>("PUT", `${code(rundencode)}/team`, { team_id: teamId });
}

/** Ton oder Antwortbild der gezeigten Frage. */
export function rundenmediumAdresse(
  rundencode: string,
  schluessel: string,
  frage: number,
): string {
  return adresse(`${code(rundencode)}/medien/${schluessel}?frage=${frage}`);
}

export function antworte(
  rundencode: string,
  eingabe: AntwortEingabe,
): Promise<Rundenstand> {
  return sende<Rundenstand>("PUT", `${code(rundencode)}/antwort`, eingabe);
}

export function buzzere(rundencode: string): Promise<Rundenstand> {
  return sende<Rundenstand>("POST", `${code(rundencode)}/buzzer`);
}

/** Adresse fürs `<img>`; die Frage hängt daran, damit ein neues Bild auch
 *  neu geladen wird und nicht das der vorigen Frage stehen bleibt. */
export function rundenbildAdresse(rundencode: string, frage: number): string {
  return adresse(`${code(rundencode)}/bild?frage=${frage}`);
}

// ------------------------------------------------------------- Kataloge

export function ladeKataloge(signal?: AbortSignal): Promise<Katalog[]> {
  return anfrage<Katalog[]>("/kataloge", {}, signal);
}

export function ladeKatalog(id: string, signal?: AbortSignal): Promise<KatalogDetail> {
  return anfrage<KatalogDetail>(`/kataloge/${id}`, {}, signal);
}

export function legeKatalogAn(titel: string, beschreibung = ""): Promise<KatalogDetail> {
  return sende<KatalogDetail>("POST", "/kataloge", { titel, beschreibung });
}

export function aendereKatalog(
  id: string,
  titel: string,
  beschreibung: string,
): Promise<KatalogDetail> {
  return sende<KatalogDetail>("PUT", `/kataloge/${id}`, { titel, beschreibung });
}

export function loescheKatalog(id: string): Promise<void> {
  return sende<void>("DELETE", `/kataloge/${id}`);
}

export function legeFrageAn(katalogId: string, frage: FrageEingabe): Promise<Frage> {
  return sende<Frage>("POST", `/kataloge/${katalogId}/fragen`, frage);
}

export function aendereFrage(id: string, frage: FrageEingabe): Promise<Frage> {
  return sende<Frage>("PUT", `/fragen/${id}`, frage);
}

export function loescheFrage(id: string): Promise<void> {
  return sende<void>("DELETE", `/fragen/${id}`);
}

export function sortiereFragen(
  katalogId: string,
  fragen: string[],
): Promise<KatalogDetail> {
  return sende<KatalogDetail>("PUT", `/kataloge/${katalogId}/reihenfolge`, { fragen });
}

/** Das Bild geht roh hinaus, mit seinem eigenen Content-Type - kein
 *  Formular-Upload, damit das Backend keine weitere Abhängigkeit braucht. */
export function ladeBildHoch(frageId: string, datei: Blob): Promise<Frage> {
  return anfrage<Frage>(`/fragen/${frageId}/bild`, {
    method: "PUT",
    body: datei,
    headers: { "Content-Type": datei.type || "application/octet-stream" },
  });
}

export function entferneBild(frageId: string): Promise<void> {
  return sende<void>("DELETE", `/fragen/${frageId}/bild`);
}

export function importiereKatalog(datei: Blob): Promise<ImportErgebnis> {
  return anfrage<ImportErgebnis>("/kataloge/import", {
    method: "POST",
    body: datei,
    headers: { "Content-Type": datei.type || "application/zip" },
  });
}

export function exportAdresse(katalogId: string): string {
  return adresse(`/kataloge/${katalogId}/export`);
}

export function ladeMediumHoch(
  frageId: string,
  schluessel: string,
  datei: Blob,
): Promise<Frage> {
  return anfrage<Frage>(`/fragen/${frageId}/medien/${schluessel}`, {
    method: "PUT",
    body: datei,
    headers: { "Content-Type": datei.type || "application/octet-stream" },
  });
}

export function entferneMedium(frageId: string, schluessel: string): Promise<void> {
  return sende<void>("DELETE", `/fragen/${frageId}/medien/${schluessel}`);
}

export function mediumAdresse(
  frageId: string,
  schluessel: string,
  stand: string,
): string {
  return adresse(
    `/fragen/${frageId}/medien/${schluessel}?stand=${encodeURIComponent(stand)}`,
  );
}

export function bildAdresse(frageId: string, stand: string): string {
  return adresse(`/fragen/${frageId}/bild?stand=${encodeURIComponent(stand)}`);
}

// ------------------------------------------------------------- Leitung

export function ladeRunden(signal?: AbortSignal): Promise<Runde[]> {
  return anfrage<Runde[]>("/leitung", {}, signal);
}

export function eroeffneRunde(katalogId: string): Promise<Runde> {
  return sende<Runde>("POST", "/leitung", { katalog_id: katalogId });
}

export function loescheRunde(id: string): Promise<void> {
  return sende<void>("DELETE", `/leitung/${id}`);
}

export function ladeSteuerung(id: string, signal?: AbortSignal): Promise<Steuerung> {
  return anfrage<Steuerung>(`/leitung/${id}`, {}, signal);
}

export type Aktion =
  | { art: "frage"; frage_id: string }
  | { art: "zeigen"; timer: boolean }
  | { art: "sperren" }
  | { art: "oeffnen" }
  | { art: "aufloesen" }
  | { art: "bild"; sichtbar: boolean }
  | { art: "buzzer"; richtig: boolean }
  | { art: "buzzer/zuruecksetzen" }
  | { art: "beenden" }
  | { art: "beitritt"; offen: boolean };

export function steuere(rundeId: string, aktion: Aktion): Promise<Steuerung> {
  const { art, ...daten } = aktion;
  return sende<Steuerung>("POST", `/leitung/${rundeId}/${art}`, daten);
}

export function bewerteAntwort(
  rundeId: string,
  antwortId: string,
  punkte: number,
): Promise<Steuerung> {
  return sende<Steuerung>("PUT", `/leitung/${rundeId}/antworten/${antwortId}`, {
    punkte,
  });
}

export function korrigiere(
  rundeId: string,
  spielerId: string,
  punkte: number,
  grund = "",
): Promise<Steuerung> {
  return sende<Steuerung>("POST", `/leitung/${rundeId}/spieler/${spielerId}/korrektur`, {
    punkte,
    grund,
  });
}

export function stelleWiederkehrAus(
  rundeId: string,
  spielerId: string,
): Promise<Wiederkehrcode> {
  return sende<Wiederkehrcode>(
    "POST",
    `/leitung/${rundeId}/spieler/${spielerId}/wiederkehr`,
  );
}

export function entferneSpieler(rundeId: string, spielerId: string): Promise<void> {
  return sende<void>("DELETE", `/leitung/${rundeId}/spieler/${spielerId}`);
}

export function legeTeamAn(rundeId: string, name: string): Promise<Steuerung> {
  return sende<Steuerung>("POST", `/leitung/${rundeId}/teams`, { name });
}

export function loescheTeam(rundeId: string, teamId: string): Promise<Steuerung> {
  return sende<Steuerung>("DELETE", `/leitung/${rundeId}/teams/${teamId}`);
}

export function weiseTeamZu(
  rundeId: string,
  spielerId: string,
  teamId: string | null,
): Promise<Steuerung> {
  return sende<Steuerung>("PUT", `/leitung/${rundeId}/spieler/${spielerId}/team`, {
    team_id: teamId,
  });
}

export function ladeAuswertung(
  rundeId: string,
  signal?: AbortSignal,
): Promise<FrageAuswertung[]> {
  return anfrage<FrageAuswertung[]>(`/leitung/${rundeId}/auswertung`, {}, signal);
}

export function ergebnisAdresse(rundeId: string): string {
  return adresse(`/leitung/${rundeId}/ergebnis.csv`);
}
