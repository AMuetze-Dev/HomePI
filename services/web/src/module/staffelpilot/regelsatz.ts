import type { Parameter, Regel } from "./api";

/** Was jemand in die Felder einer Regel getippt hat. Leer heißt: Vorgabe. */
export type Eingaben = Record<string, string>;

/** Wo eine Regel steht, die jemand selbst geschrieben hat. */
const EIGENE = "Eigene Regeln";

/**
 * Die mitgelieferten Regeln nach dem, worum es geht.
 *
 * Nur für die Anzeige, deshalb hier und nicht im Prüfdienst: Sechsundvierzig
 * Regeln untereinander sind eine Liste, in der man sucht; acht Gruppen sind
 * eine, die man überblickt. Eine Regel, die hier fehlt, geht nicht verloren —
 * sie steht unter „Eigene Regeln".
 */
const THEMEN: readonly (readonly [thema: string, regeln: readonly string[]])[] = [
  [
    "Bestätigung und Freigabe",
    [
      "confirmation_late",
      "confirmation_missing",
      "confirmation_comment",
      "confirmation_unlesbar",
      "release_late",
    ],
  ],
  [
    "Spielrecht",
    [
      "player_eligibility",
      "dfbnet_warning",
      "spielrecht_fehlt",
      "pflichtspielrecht_spaeter",
      "meisterschaftsrecht_fehlt",
      "sperrvermerk_dfbnet",
      "gastspielrecht_im_pflichtspiel",
      "zwei_spiele_am_tag",
    ],
  ],
  [
    "Alter und Stammspieler",
    [
      "geburtsdatum_unplausibel",
      "altersklasse_zu_jung",
      "ue32_limit",
      "spieltage_unbekannt",
      "stammspieler_wartefrist",
      "stammspieler_limit",
    ],
  ],
  [
    "Karten und Sperren",
    [
      "red_card",
      "yellow_red_card",
      "verwarnung_fuenf",
      "verwarnung_pokal_zwei",
      "verwarnungszaehler_fehlt",
      "karte_ohne_person",
    ],
  ],
  [
    "Aufstellung",
    [
      "rueckennummer_doppelt",
      "rueckennummer_fehlt",
      "mannschaftsstaerke",
      "einwechslungen_zu_viele",
      "spielfuehrer_fehlt",
    ],
  ],
  [
    "Spielerfoto",
    ["spielerfoto_fehlt", "spielerfoto_zu_alt", "spielerfoto_aus_juniorenzeit"],
  ],
  [
    "Ordnungsdienst",
    ["order_manager_missing", "order_manager_is_player", "order_manager_dual_role"],
  ],
  [
    "Spielverlauf",
    [
      "incidents",
      "documents_present",
      "ergebnis_widerspricht_toren",
      "spielabbruch",
      "spielabbruch_neuansetzung",
      "nichtantreten",
    ],
  ],
  [
    "Wenn nicht geprüft werden konnte",
    ["bericht_ungelesen", "aufstellung_fehlt", "rule_error", "regel_fehlerhaft"],
  ],
];

const THEMA_JE_REGEL = new Map(
  THEMEN.flatMap(([thema, regeln]) => regeln.map((r) => [r, thema] as const)),
);

export function themaZu(schluessel: string): string {
  return THEMA_JE_REGEL.get(schluessel) ?? EIGENE;
}

/** Die Regeln je Thema, in fester Reihenfolge. Leere Themen fallen weg. */
export function nachThemen(
  regeln: readonly Regel[],
): { thema: string; regeln: Regel[] }[] {
  return [...THEMEN.map(([thema]) => thema), EIGENE]
    .map((thema) => ({
      thema,
      regeln: regeln.filter((r) => themaZu(r.schluessel) === thema),
    }))
    .filter((gruppe) => gruppe.regeln.length > 0);
}

/**
 * Der Name ohne seine Herkunft.
 *
 * Der Prüfdienst hängt „(eingebaut)" an, um seine eigenen Regeln von
 * Regeldateien zu unterscheiden. Beim Entscheiden, ob man eine Regel braucht,
 * hilft das nicht.
 */
export function anzeigename(name: string): string {
  return name.replace(/ \(eingebaut\)$/, "");
}

/** Was in den Feldern steht, bevor jemand tippt: der Wert, der gilt. */
export function eingabenAus(parameter: readonly Parameter[]): Eingaben {
  return Object.fromEntries(
    parameter.map((p) => [p.schluessel, String(p.wert ?? p.vorgabe)]),
  );
}

const EINHEIT: Record<Parameter["art"], string> = {
  uhrzeit: "",
  minuten: " (Minuten)",
  stunden: " (Stunden)",
  zahl: "",
};

export function feldname(parameter: Parameter): string {
  return `${parameter.name}${EINHEIT[parameter.art]}`;
}

/**
 * Die Frist einer Regel in einem Satz — oder nichts, wenn sie keine hat.
 *
 * Vier Felder nebeneinander sagen nicht, was am Ende gilt. Der Satz sagt es,
 * und er rechnet beim Tippen mit.
 */
export function fristsatz(parameter: readonly Parameter[], eingaben: Eingaben): string {
  const wert = (schluessel: string): string => {
    const p = parameter.find((kandidat) => kandidat.schluessel === schluessel);
    if (p === undefined) return "";
    const getippt = (eingaben[schluessel] ?? "").trim();
    return getippt || String(p.vorgabe);
  };

  const uhrzeit = wert("frist_uhrzeit");
  if (!uhrzeit) return "";

  const nachSpielende = wert("nach_spielende");
  const nachFreigabe = wert("nach_freigabe");
  const kulanz = wert("kulanz");

  const mindestens = [
    nachSpielende && `${nachSpielende} Min. nach Spielende`,
    nachFreigabe && `${nachFreigabe} Min. nach der Freigabe`,
  ].filter(Boolean);

  let satz = `Frist ${uhrzeit} Uhr`;
  if (mindestens.length > 0) satz += `, mindestens ${mindestens.join(" und ")}`;
  if (kulanz && kulanz !== "0") satz += `, dazu ${kulanz} Std. Kulanz`;
  return `${satz}.`;
}

/** „A", „A und B", „A, B und C". */
export function aufzaehlung(namen: readonly string[]): string {
  if (namen.length <= 1) return namen.join("");
  return `${namen.slice(0, -1).join(", ")} und ${namen[namen.length - 1]}`;
}
