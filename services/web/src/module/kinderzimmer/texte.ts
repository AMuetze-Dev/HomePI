import type {
  Art,
  Aufnahme,
  Figur,
  FigurEingabe,
  Farbwort,
  Formwort,
  Knopf,
} from "./api";

export const ARTEN: readonly [Art, string][] = [
  ["familie", "Familie"],
  ["tier", "Tier"],
  ["farbe", "Farbe"],
  ["form", "Form"],
  ["menge", "Menge"],
  ["ritual", "Ritual"],
  ["gefuehl", "Gefühl"],
  ["geschichte", "Geschichte"],
  ["sonstiges", "Sonstiges"],
];

export const FARBEN: readonly [Farbwort, string][] = [
  ["rot", "Rot"],
  ["blau", "Blau"],
  ["gelb", "Gelb"],
  ["gruen", "Grün"],
  ["orange", "Orange"],
  ["lila", "Lila"],
  ["rosa", "Rosa"],
  ["weiss", "Weiß"],
  ["schwarz", "Schwarz"],
  ["braun", "Braun"],
];

export const FORMEN: readonly [Formwort, string][] = [
  ["kreis", "Kreis"],
  ["quadrat", "Quadrat"],
  ["dreieck", "Dreieck"],
  ["rechteck", "Rechteck"],
  ["stern", "Stern"],
  ["herz", "Herz"],
];

export function wortFuer<W extends string>(
  liste: readonly [W, string][],
  wert: W,
): string {
  return liste.find(([w]) => w === wert)?.[1] ?? wert;
}

const ZEIT = new Intl.DateTimeFormat("de-DE", {
  day: "numeric",
  month: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const DATUM = new Intl.DateTimeFormat("de-DE", {
  weekday: "short",
  day: "numeric",
  month: "long",
  year: "numeric",
});

export function zeit(iso: string | null): string {
  return iso === null ? "Zeit unbekannt" : ZEIT.format(new Date(iso));
}

/** `2026-11-20` als „Fr., 20. November 2026" - ohne Zeitzonenverschiebung. */
export function datum(iso: string): string {
  const [jahr = 0, monat = 1, tag = 1] = iso.split("-").map(Number);
  return DATUM.format(new Date(jahr, monat - 1, tag));
}

/** Heute als `YYYY-MM-DD` in der Ortszeit - `toISOString` läge nachts einen Tag daneben. */
export function heute(jetzt: Date = new Date()): string {
  const zwei = (n: number) => String(n).padStart(2, "0");
  return `${jetzt.getFullYear()}-${zwei(jetzt.getMonth() + 1)}-${zwei(jetzt.getDate())}`;
}

export function dauer(ms: number): string {
  return `${(ms / 1000).toLocaleString("de-DE", { maximumFractionDigits: 1, minimumFractionDigits: 1 })} s`;
}

/** Wo eine Aufnahme benutzt wird - dieselbe Regel wie im Backend, nur zum Anzeigen. */
export function verwendungen(
  aufnahme: Aufnahme,
  figuren: readonly Figur[],
  knoepfe: readonly Knopf[],
): string[] {
  return [
    ...figuren
      .filter((f) => f.stimme === aufnahme.id || f.klang === aufnahme.id)
      .map((f) => f.name),
    ...knoepfe.filter((k) => k.klang === aufnahme.id).map((k) => `Knopf ${k.nummer}`),
  ];
}

/** `04A1B2C3` lesbar als `04:A1:B2:C3`. */
export function uidLesbar(uid: string): string {
  return uid.match(/.{1,2}/g)?.join(":") ?? uid;
}

/** Ein leeres Figurformular. */
export const LEERE_FIGUR: FigurEingabe = {
  uid: "",
  name: "",
  art: "familie",
  farbe: null,
  form: null,
  menge: null,
  stimme: null,
  klang: null,
};
