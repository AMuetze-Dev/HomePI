import { schnittstelle } from "../../api/schnittstelle";

const { anfrage, sende } = schnittstelle("/haushaltsbuch");

/**
 * Geldbeträge kommen als Zeichenkette, nicht als Zahl.
 *
 * Das Backend rechnet in Decimal und gibt genau das aus, was es gerechnet
 * hat. Würde die Oberfläche daraus ein `number` machen, wären 0,1 + 0,2
 * wieder 0,30000000000000004 — und zwar ausgerechnet bei der einen Zahl, die
 * jemand gegen seinen Kontoauszug hält. Zum Rechnen gibt es `alsZahl`, zum
 * Anzeigen `alsEuro`; beides steht in geld.ts.
 */
export type Betrag = string;

export type Kontoart = "verteiler" | "verbrauch" | "sparen" | "ruecklage";
export type Postenart = "einnahme" | "ausgabe";
export type Knotenart = "einnahme" | "konto" | "kategorie" | "posten";

export interface Person {
  id: string;
  name: string;
  reihenfolge: number;
}

export interface Konto {
  id: string;
  name: string;
  art: Kontoart;
  /** null heißt gemeinschaftlich. */
  inhaber_id: string | null;
  notiz: string;
  reihenfolge: number;
}

export interface Kategorie {
  id: string;
  name: string;
  zaehlt_als_sparen: boolean;
  reihenfolge: number;
}

export interface Anteil {
  person_id: string;
  gewicht: number;
}

export interface Posten {
  id: string;
  name: string;
  art: Postenart;
  betrag: Betrag;
  intervall_monate: number;
  faelligkeitsmonat: number;
  abbuchungstag: number | null;
  konto_id: string;
  kategorie_id: string | null;
  variabel: boolean;
  aktiv: boolean;
  anteile: Anteil[];
}

export interface PostenZeile {
  id: string;
  name: string;
  art: Postenart;
  konto: string;
  kategorie: string;
  betrag: Betrag;
  monatsrate: Betrag;
  intervall_monate: number;
  faelligkeitsmonat: number;
  abbuchungstag: number | null;
  faellige_monate: number[];
  faellig_im_monat: boolean;
  ruecklagenstand: Betrag;
  anteile: Record<string, Betrag>;
}

export interface Kategoriesumme {
  kategorie: string;
  betrag: Betrag;
  zaehlt_als_sparen: boolean;
}

export interface PersonBilanz {
  person_id: string;
  name: string;
  einnahmen: Betrag;
  eigene_ausgaben: Betrag;
  einzahlung_gemeinschaft: Betrag;
  gutschrift_gemeinschaft: Betrag;
  ausgaben_gesamt: Betrag;
  feste_kosten: Betrag;
  sparen: Betrag;
  variabel: Betrag;
  moeglich: Betrag;
  rest: Betrag;
  sparquote: Betrag;
  moegliche_sparquote: Betrag;
  nach_kategorie: Kategoriesumme[];
}

export interface Gemeinschaftsbilanz {
  einnahmen: Betrag;
  ausgaben: Betrag;
  bedarf: Betrag;
  ohne_aufteilung: string[];
}

export interface Uebersicht {
  jahr: number;
  monat: number;
  personen: PersonBilanz[];
  gemeinschaft: Gemeinschaftsbilanz;
  faellig: PostenZeile[];
  ruecklagen: PostenZeile[];
  ruecklagen_summe: Betrag;
  alle: PostenZeile[];
}

export interface Knoten {
  id: string;
  beschriftung: string;
  art: Knotenart;
  ebene: number;
  betrag: Betrag;
}

export interface Fluss {
  von: string;
  nach: string;
  betrag: Betrag;
}

export interface Flussbild {
  knoten: Knoten[];
  fluesse: Fluss[];
  ebenen: number;
}

export interface NeuePerson {
  name: string;
}

export interface NeuesKonto {
  name: string;
  art: Kontoart;
  inhaber_id: string | null;
  notiz?: string;
}

export interface NeueKategorie {
  name: string;
  zaehlt_als_sparen: boolean;
}

export interface NeuerPosten {
  name: string;
  art: Postenart;
  betrag: string;
  intervall_monate: number;
  faelligkeitsmonat: number;
  abbuchungstag: number | null;
  konto_id: string;
  kategorie_id: string | null;
  variabel: boolean;
  anteile: Anteil[];
}

/** Was sich an einem Posten ändern lässt, ohne ihn neu anzulegen. */
export type PostenAenderung = Partial<NeuerPosten> & {
  aktiv?: boolean;
  kategorie_loeschen?: boolean;
  tag_loeschen?: boolean;
};

export function ladeUebersicht(
  zeitraum?: { jahr: number; monat: number },
  signal?: AbortSignal,
): Promise<Uebersicht> {
  const pfad = zeitraum ? `/?jahr=${zeitraum.jahr}&monat=${zeitraum.monat}` : "/";
  return anfrage<Uebersicht>(pfad, {}, signal);
}

export function ladeFlussbild(signal?: AbortSignal): Promise<Flussbild> {
  return anfrage<Flussbild>("/flussbild", {}, signal);
}

export function ladePersonen(signal?: AbortSignal): Promise<Person[]> {
  return anfrage<Person[]>("/personen", {}, signal);
}

export function legePersonAn(daten: NeuePerson): Promise<Person> {
  return sende<Person>("POST", "/personen", daten);
}

export function aenderePerson(id: string, daten: Partial<NeuePerson>): Promise<Person> {
  return sende<Person>("PATCH", `/personen/${id}`, daten);
}

export function entfernePerson(id: string): Promise<void> {
  return sende<void>("DELETE", `/personen/${id}`);
}

export function ladeKonten(signal?: AbortSignal): Promise<Konto[]> {
  return anfrage<Konto[]>("/konten", {}, signal);
}

export function legeKontoAn(daten: NeuesKonto): Promise<Konto> {
  return sende<Konto>("POST", "/konten", daten);
}

export function aendereKonto(
  id: string,
  daten: Partial<NeuesKonto> & { gemeinschaftlich?: boolean },
): Promise<Konto> {
  return sende<Konto>("PATCH", `/konten/${id}`, daten);
}

export function entferneKonto(id: string): Promise<void> {
  return sende<void>("DELETE", `/konten/${id}`);
}

export function ladeKategorien(signal?: AbortSignal): Promise<Kategorie[]> {
  return anfrage<Kategorie[]>("/kategorien", {}, signal);
}

export function legeKategorieAn(daten: NeueKategorie): Promise<Kategorie> {
  return sende<Kategorie>("POST", "/kategorien", daten);
}

/** Legt die üblichen Kategorien an - und nur die, die noch fehlen. */
export function legeGrundgeruestAn(): Promise<Kategorie[]> {
  return sende<Kategorie[]>("POST", "/kategorien/grundgeruest");
}

export function entferneKategorie(id: string): Promise<void> {
  return sende<void>("DELETE", `/kategorien/${id}`);
}

export function ladePosten(signal?: AbortSignal): Promise<Posten[]> {
  return anfrage<Posten[]>("/posten", {}, signal);
}

export function legePostenAn(daten: NeuerPosten): Promise<Posten> {
  return sende<Posten>("POST", "/posten", daten);
}

export function aenderePosten(id: string, daten: PostenAenderung): Promise<Posten> {
  return sende<Posten>("PATCH", `/posten/${id}`, daten);
}

export function entfernePosten(id: string): Promise<void> {
  return sende<void>("DELETE", `/posten/${id}`);
}
