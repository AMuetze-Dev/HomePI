import type { Katalog, Pruefling, PrueflingKurz, Tag, TeilErgebnis } from "./api";

/** Ein verkleinerter Katalog: genug Struktur für jede Art von Zeile. */
export const KATALOG: Katalog = {
  doku: [
    {
      id: "doku.1",
      nr: "1",
      label: "Form",
      max: 2,
      kinder: [
        {
          id: "doku.1.1",
          label: "Umfang",
          art: "points",
          max: 1,
          hinweis: "",
          kinder: [],
        },
        {
          id: "doku.1.2",
          label: "Gliederung",
          art: "points",
          max: 1,
          hinweis: "logisch aufgebaut",
          kinder: [],
        },
      ],
      bloecke: [
        { id: "doku.1", knoten: [] },
        { id: "doku.1.1", knoten: ["doku.1.1", "doku.1.2"] },
      ],
    },
    {
      id: "doku.5",
      nr: "5",
      label: "Umsetzung",
      max: 2,
      kinder: [
        {
          id: "doku.5.1",
          label: "Qualitätssicherung",
          art: "group",
          max: 2,
          hinweis: "",
          kinder: [
            {
              id: "doku.5.1.1",
              label: "Tests",
              art: "points",
              max: 2,
              hinweis: "",
              kinder: [],
            },
          ],
        },
        {
          id: "doku.5.5",
          label: "Mängel",
          art: "malus",
          max: -2,
          hinweis: "",
          kinder: [],
        },
      ],
      bloecke: [
        { id: "doku.5", knoten: [] },
        { id: "doku.5.1", knoten: ["doku.5.1", "doku.5.1.1"] },
        { id: "doku.5.5", knoten: ["doku.5.5"] },
      ],
    },
  ],
  praesentation: [
    {
      id: "praesi.1",
      nr: "1",
      label: "Aufbau",
      max: 10,
      kinder: [
        {
          id: "praesi.1.1",
          label: "Projektziel",
          art: "scale",
          max: null,
          hinweis: "",
          kinder: [],
        },
        {
          id: "praesi.1.2",
          label: "Projektumfeld",
          art: "scale",
          max: null,
          hinweis: "",
          kinder: [],
        },
      ],
      bloecke: [{ id: "praesi.1", knoten: [] }],
    },
  ],
  skala: [1, 0.75, 0.5, 0.25, 0],
  korrekturarten: ["Erstkorrektur", "Zweitkorrektur", "Information"],
  notenbaender: [
    { von: 100, bis: 92, note: 1 },
    { von: 91, bis: 0, note: 2 },
  ],
  teil1_label: "Einrichten IT-gestützter Arbeitsplatz",
  bereiche: [
    { id: "planen_softwareprodukt", label: "Planen Softwareprodukt" },
    { id: "algorithmen", label: "Entwicklung Algorithmen" },
    { id: "wiso", label: "WiSo" },
  ],
  projekt_label: "Planung und Umsetzen Softwareprojekt",
  praesi_grenze_min: 15,
  gesamt_grenze_min: 30,
};

export function tag(rest: Partial<Tag> = {}): Tag {
  return {
    id: "t1",
    datum: "2026-06-18",
    ort: "Köln",
    korrektor: "K. Orrektor",
    anzahl_prueflinge: 0,
    ...rest,
  };
}

const STATUS = {
  runtergeladen: false,
  kontrolliert: false,
  abgestimmt: false,
  hochgeladen: false,
};

export function kurz(rest: Partial<PrueflingKurz> = {}): PrueflingKurz {
  return {
    id: "p1",
    reihenfolge: 1,
    name: "Muster, Max",
    ident: "",
    korrekturart: "Erstkorrektur",
    status: STATUS,
    doku_punkte: null,
    doku_note: null,
    praesi_punkte: null,
    praesi_note: null,
    ...rest,
  };
}

function teil(rest: Partial<TeilErgebnis> = {}): TeilErgebnis {
  return {
    sektionen: [],
    gesamt: null,
    note: null,
    grenzfall: false,
    fehlend: [],
    ...rest,
  };
}

const GESAMT = {
  projekt: null,
  bereiche: [],
  teil1: null,
  teil2: null,
  gesamt: null,
  note: null,
  grenzfall: false,
  fehlend: ["projekt", "teil1"],
};

export function pruefling(rest: Partial<Pruefling> = {}): Pruefling {
  return {
    id: "p1",
    tag: tag({ anzahl_prueflinge: 1 }),
    reihenfolge: 1,
    name: "Muster, Max",
    ident: "",
    korrekturart: "Erstkorrektur",
    status: STATUS,
    bewertung: {
      doku: {},
      doku_bemerkungen: {},
      praesi_skala: {},
      praesi_punkte: {},
      praesi_bemerkungen: {},
      notizen: "",
      fragen: "",
    },
    teilnoten: {
      teil1: null,
      planen_softwareprodukt: null,
      algorithmen: null,
      wiso: null,
      mep: null,
    },
    zeiten: { praesi_start: null, praesi_ende: null, fg_start: null, fg_ende: null },
    dokumente: [],
    auswertung: {
      doku: teil({
        sektionen: [
          {
            id: "doku.1",
            nr: "1",
            label: "Form",
            max: 2,
            wert: null,
            vollstaendig: false,
            vorschlag: null,
          },
          {
            id: "doku.5",
            nr: "5",
            label: "Umsetzung",
            max: 2,
            wert: null,
            vollstaendig: false,
            vorschlag: null,
          },
        ],
        fehlend: ["doku.1.1", "doku.1.2", "doku.5.1.1", "doku.5.5"],
      }),
      praesentation: teil({
        sektionen: [
          {
            id: "praesi.1",
            nr: "1",
            label: "Aufbau",
            max: 10,
            wert: null,
            vollstaendig: false,
            vorschlag: null,
          },
        ],
        fehlend: ["praesi.1"],
      }),
      gesamt_ohne_mep: GESAMT,
      gesamt_mit_mep: null,
    },
    jetzt: "2026-06-18T09:00:00Z",
    ...rest,
  };
}
