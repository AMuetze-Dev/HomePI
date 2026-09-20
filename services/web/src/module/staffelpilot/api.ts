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
  /** 0 heißt *nicht bekannt* — nicht "keine". */
  spieltage: number;
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
  /** Ob das Spiel im Prüfzeitraum liegt. Berechnet, nicht gespeichert. */
  faellig: boolean;
}

export interface Regel {
  id: string;
  schluessel: string;
  name: string;
  beschreibung: string;
  schwere: Schwere;
  weg: Weg;
  aktiv: boolean;
}

// `faellig` faellt weg: der einzelne Bericht wird geoeffnet, weil jemand ihn
// sehen will - ob er im Pruefzeitraum liegt, entscheidet nur die Liste.
export interface Spiel extends Omit<
  SpielZeile,
  "offene_befunde" | "kritische_befunde" | "faellig"
> {
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
  /** Ob der DFBnet-Dienst gerade etwas eintragen darf. Frisch: pausiert. */
  uebertragung_pausiert: boolean;
  /** Ob der Prüfdienst sein Browserfenster zeigt. Frisch: aus. */
  browser_sichtbar: boolean;
}

/** Eine Zeile der Auswertung. */
export interface Posten {
  name: string;
  anzahl: number;
  offen: number;
}

export interface Auswertung {
  befunde: number;
  offen: number;
  spiele: number;
  abgehakt: number;
  vorgaenge: number;
  nach_schwere: Posten[];
  nach_regel: Posten[];
  nach_mannschaft: Posten[];
  nach_monat: Posten[];
}

export type AuftragArt = "pruflauf" | "initialisierung";
export type AuftragZustand =
  "angefordert" | "laeuft" | "fertig" | "abgebrochen" | "gescheitert";

export interface AuftragZeile {
  id: string;
  art: AuftragArt;
  staffel_id: string | null;
  zustand: AuftragZustand;
  schritt: string;
  fortschritt: number;
  gepruefte: number;
  befunde: number;
  meldung: string;
  gestartet_am: string | null;
  beendet_am: string | null;
  angelegt: string;
}

export interface Auftrag extends AuftragZeile {
  protokoll: { zeit: string; text: string }[];
}

export type UebertragungAktion = "prueferfreigabe" | "fallanlage";
export type UebertragungZustand = "offen" | "laeuft" | "fertig" | "fehler";

export interface Uebertragung {
  id: string;
  aktion: UebertragungAktion;
  referenz: string;
  spiel_id: string | null;
  zustand: UebertragungZustand;
  versuche: number;
  letzter_fehler: string;
  erledigt_am: string | null;
  angelegt: string;
}

export interface UebertragungStand {
  pausiert: boolean;
  offen: number;
  laeuft: number;
  fertig: number;
  fehler: number;
  fehlerhafte: Uebertragung[];
}

export interface ZugangStand {
  gespeichert: boolean;
  benutzer: string;
  /** Ohne Schlüssel in der Umgebung lässt sich nichts ablegen. */
  schluessel_vorhanden: boolean;
}

/** Ein Befund mit dem Spiel, zu dem er gehört. */
export interface BefundZeile {
  id: string;
  spiel_id: string;
  staffel_id: string;
  dfbnet_id: string;
  datum: string;
  heim: string;
  gast: string;
  regel: string;
  schwere: Schwere;
  titel: string;
  person: string;
  mannschaft: string;
  entscheidung: Entscheidung;
  grund: string;
  weg: Weg;
  vorgang_id: string | null;
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

/** Was in ein Mailfenster gehört — und nichts, was es abschickt. */
export interface Mailentwurf {
  /** Vorschlag. Wer die Mail bekommt, entscheidet der Staffelleiter. */
  empfaenger: string;
  betreff: string;
  text: string;
  /** Adresse des gefüllten Formulars, leer bei einem Sportgerichtsfall. */
  anhang: string;
  /** Felder des Vordrucks, die niemand kennt. */
  fehlende_felder: string[];
}

export interface NeueStaffel {
  name: string;
  altersklasse: Altersklasse;
  spielklasse: string;
  saison?: string;
  spieltage?: number;
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
  nurFaellig = false,
): Promise<SpielZeile[]> {
  const teile = [];
  if (staffelId) teile.push(`staffel_id=${encodeURIComponent(staffelId)}`);
  if (nurFaellig) teile.push("nur_faellig=true");
  const frage = teile.length > 0 ? `?${teile.join("&")}` : "";
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

export function ladeMailentwurf(id: string, signal?: AbortSignal): Promise<Mailentwurf> {
  return anfrage<Mailentwurf>(`/vorgaenge/${id}/mail`, {}, signal);
}

/**
 * Die Adresse des ausgefüllten Mahnungsformulars.
 *
 * Als Link und nicht als Abruf: das PDF geht in den Download-Ordner oder in
 * den Viewer des Browsers, und beides kann die Seite nicht besser.
 */
export function mahnungAdresse(id: string): string {
  return `${BASE_URL}/staffelpilot/vorgaenge/${id}/mahnung.pdf`;
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

// ── Regelkatalog ─────────────────────────────────────────────────────────

export function ladeRegeln(signal?: AbortSignal): Promise<Regel[]> {
  return anfrage<Regel[]>("/regeln", {}, signal);
}

/** Der Schalter gehört dem Staffelleiter; geprüft wird trotzdem im Prüfdienst. */
export function schalteRegel(id: string, aktiv: boolean): Promise<Regel> {
  return anfrage<Regel>(`/regeln/${id}`, mitKoerper("PATCH", { aktiv }));
}

// ── Eine Staffel ändern ──────────────────────────────────────────────────

/** Nur die mitgeschickten Felder. Ausgelassene bleiben stehen. */
export function aendereStaffel(
  id: string,
  daten: Partial<Omit<Staffel, "id">>,
): Promise<Staffel> {
  return anfrage<Staffel>(`/staffeln/${id}`, mitKoerper("PATCH", daten));
}

export function loescheStaffel(id: string): Promise<void> {
  return anfrage<void>(`/staffeln/${id}`, { method: "DELETE" });
}

// ── Eine Entscheidung zurücknehmen ───────────────────────────────────────

/**
 * Der Befund ist danach wieder offen und das Spiel nicht mehr abgehakt.
 * Ist zu dem Befund schon ein Schreiben hinaus, antwortet das Backend mit
 * 409 — dann erst den Vorgang zurückholen.
 */
export function nimmEntscheidungZurueck(befundId: string): Promise<Befund> {
  return anfrage<Befund>(`/befunde/${befundId}/entscheidung`, { method: "DELETE" });
}

// ── Alle Befunde ─────────────────────────────────────────────────────────

export function ladeAlleBefunde(
  optionen: { staffelId?: string | undefined; nurOffen?: boolean } = {},
  signal?: AbortSignal,
): Promise<BefundZeile[]> {
  const teile = [];
  if (optionen.staffelId)
    teile.push(`staffel_id=${encodeURIComponent(optionen.staffelId)}`);
  if (optionen.nurOffen) teile.push("nur_offen=true");
  const frage = teile.length > 0 ? `?${teile.join("&")}` : "";
  return anfrage<BefundZeile[]>(`/befunde${frage}`, {}, signal);
}

// ── Aufträge: Prüflauf und Initialisierung ───────────────────────────────

export function ladeAuftraege(signal?: AbortSignal): Promise<AuftragZeile[]> {
  return anfrage<AuftragZeile[]>("/auftraege", {}, signal);
}

/** `null`, wenn keiner unterwegs ist — kein 404, das wird im Takt abgefragt. */
export function ladeOffenenAuftrag(signal?: AbortSignal): Promise<Auftrag | null> {
  return anfrage<Auftrag | null>("/auftraege/offen", {}, signal);
}

export function ladeAuftrag(id: string, signal?: AbortSignal): Promise<Auftrag> {
  return anfrage<Auftrag>(`/auftraege/${id}`, {}, signal);
}

/**
 * Fordert an — startet nicht. Gearbeitet wird im DFBnet-Dienst; solange der
 * nicht läuft, bleibt der Auftrag auf „angefordert" stehen.
 */
export function fordereAuftragAn(
  art: AuftragArt = "pruflauf",
  staffelId?: string,
): Promise<Auftrag> {
  return anfrage<Auftrag>(
    "/auftraege",
    mitKoerper("POST", { art, staffel_id: staffelId ?? null }),
  );
}

export function brichAuftragAb(id: string): Promise<Auftrag> {
  return anfrage<Auftrag>(
    `/auftraege/${id}/abschluss`,
    mitKoerper("POST", { zustand: "abgebrochen" }),
  );
}

// ── Übertragung nach DFBnet ──────────────────────────────────────────────

export function ladeUebertragung(signal?: AbortSignal): Promise<UebertragungStand> {
  return anfrage<UebertragungStand>("/uebertragungen", {}, signal);
}

/** Der eine Schalter, der entscheidet, ob draußen etwas passiert. */
export function setzeUebertragungPause(pausiert: boolean): Promise<UebertragungStand> {
  return anfrage<UebertragungStand>(
    "/uebertragungen/pause",
    mitKoerper("POST", { pausiert }),
  );
}

/** Ohne Kennung alle gescheiterten. */
export function wiederholeUebertragung(id?: string): Promise<UebertragungStand> {
  const frage = id ? `?uebertragung_id=${encodeURIComponent(id)}` : "";
  return anfrage<UebertragungStand>(`/uebertragungen/wiederholen${frage}`, {
    method: "POST",
  });
}

// ── DFBnet-Zugang ────────────────────────────────────────────────────────

export function ladeZugang(signal?: AbortSignal): Promise<ZugangStand> {
  return anfrage<ZugangStand>("/zugang", {}, signal);
}

/** Das Passwort kommt hier nie zurück. */
export function speichereZugang(benutzer: string, passwort: string): Promise<void> {
  return anfrage<void>("/zugang", mitKoerper("PUT", { benutzer, passwort }));
}

export function loescheZugang(): Promise<void> {
  return anfrage<void>("/zugang", { method: "DELETE" });
}

// ── Ergebnisse: die Auswertung ───────────────────────────────────────────

export function ladeErgebnisse(
  staffelId?: string,
  signal?: AbortSignal,
): Promise<Auswertung> {
  const frage = staffelId ? `?staffel_id=${encodeURIComponent(staffelId)}` : "";
  return anfrage<Auswertung>(`/ergebnisse${frage}`, {}, signal);
}
