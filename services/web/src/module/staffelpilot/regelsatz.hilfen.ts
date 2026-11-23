import type { Parameter, Regel, Staffel } from "./api";

/** Bausteine für die Tests rund um den Regelsatz. Nur Tests importieren das. */

export function regel(rest: Partial<Regel> = {}): Regel {
  return {
    id: "r1",
    schluessel: "red_card",
    name: "Feldverweis auf Dauer",
    beschreibung: "Meldet jeden Feldverweis auf Dauer.",
    schwere: "kritisch",
    weg: "sportgericht",
    aktiv: true,
    sachverhalt: "",
    hinweis: "",
    vorgabe_sachverhalt: "",
    vorgabe_hinweis: "",
    parameter: [],
    angepasst: false,
    ...rest,
  };
}

export function uhrzeit(rest: Partial<Parameter> = {}): Parameter {
  return {
    schluessel: "frist_uhrzeit",
    name: "Frist am Spieltag",
    art: "uhrzeit",
    vorgabe: "18:00",
    kleinst: null,
    groesst: null,
    erklaerung: "Bis wann am Spieltag bestätigt sein muss.",
    wert: null,
    ...rest,
  };
}

export function minuten(rest: Partial<Parameter> = {}): Parameter {
  return {
    schluessel: "nach_spielende",
    name: "Zeit nach Spielende",
    art: "minuten",
    vorgabe: 60,
    kleinst: 0,
    groesst: 1440,
    erklaerung: "So lange bleibt nach dem Abpfiff mindestens.",
    wert: null,
    ...rest,
  };
}

export function stunden(rest: Partial<Parameter> = {}): Parameter {
  return {
    schluessel: "kulanz",
    name: "Kulanz",
    art: "stunden",
    vorgabe: 0,
    kleinst: 0,
    groesst: 72,
    erklaerung: "Kommt auf die Frist obendrauf.",
    wert: null,
    ...rest,
  };
}

export function staffel(rest: Partial<Staffel> = {}): Staffel {
  return {
    id: "s1",
    name: "Stadtliga C",
    altersklasse: "maenner",
    spielklasse: "3.Kreisliga (C)",
    saison: "26/27",
    spieltage: 0,
    sportgericht: "",
    aktiv: true,
    staffelleiter: "Aaron",
    leite_ich: true,
    ...rest,
  };
}
