import type {
  Aufnahme,
  Einstellungen,
  Ereignis,
  Figur,
  Geraet,
  Spiel,
  Tagebucheintrag,
  Uebersicht,
} from "./api";

export function spiel(rest: Partial<Spiel> = {}): Spiel {
  return {
    id: "licht-und-klang",
    nummer: 1,
    phase: 1,
    titel: "Licht und Klang",
    alter: "ab 5 Monaten",
    ablauf: "Drückt sie auf einen großen Knopf, leuchtet ein Licht.",
    foerdert: "Das Gefühl „Ich kann etwas bewirken“.",
    warum: "In Rovee-Colliers Experimenten lernten schon drei Monate alte Babys …",
    bereit: true,
    aktiv: true,
    ...rest,
  };
}

export function uebersicht(rest: Partial<Uebersicht> = {}): Uebersicht {
  return {
    phasen: [
      { nummer: 1, titel: "Ich bewirke etwas", alter: "5–9 Monate" },
      { nummer: 2, titel: "Dinge verschwinden nicht", alter: "8–18 Monate" },
    ],
    spiele: [
      spiel(),
      spiel({ id: "stimmen", nummer: 2, titel: "Vertraute Stimmen" }),
      spiel({
        id: "kuckuck",
        nummer: 3,
        phase: 2,
        titel: "Kuckuck",
        bereit: false,
        aktiv: false,
        warum: "Jean Piaget versteckte ein Spielzeug unter einem Tuch.",
      }),
    ],
    stand: "9f2c4a1b0e7d3c55",
    zahlen: { figuren: 0, aufnahmen: 0, geraete: 0 },
    ...rest,
  };
}

export function einstellungen(rest: Partial<Einstellungen> = {}): Einstellungen {
  return {
    lautstaerke_max: 40,
    helligkeit_max: 40,
    ruhe_nach_min: 10,
    startspiel: "licht-und-klang",
    spiele_aktiv: ["licht-und-klang", "stimmen"],
    knoepfe: [{ nummer: 1, farbe: "#FFB000", klang: null }],
    ...rest,
  };
}

export function aufnahme(rest: Partial<Aufnahme> = {}): Aufnahme {
  return {
    id: "a1",
    titel: "Oma sagt Hallo",
    art: "stimme",
    dauer_ms: 2000,
    bytes: 88244,
    sha256: "a".repeat(64),
    angelegt: "2026-11-20T08:00:00Z",
    ...rest,
  };
}

export function figur(rest: Partial<Figur> = {}): Figur {
  return {
    id: "f1",
    uid: "04A1B2C3D4E5F6",
    name: "Oma",
    art: "familie",
    farbe: null,
    form: null,
    menge: null,
    stimme: null,
    klang: null,
    ...rest,
  };
}

export function geraet(rest: Partial<Geraet> = {}): Geraet {
  return {
    id: "g1",
    name: "Spielkiste",
    zuletzt_gesehen: null,
    firmware: null,
    stand_aktuell: null,
    angelegt: "2026-11-20T08:00:00Z",
    ...rest,
  };
}

export function ereignis(rest: Partial<Ereignis> = {}): Ereignis {
  return {
    id: 1,
    geraet: "Spielkiste",
    art: "knopf",
    text: "Knopf 1 gedrückt",
    zeitpunkt: "2026-11-20T08:15:00Z",
    empfangen: "2026-11-20T08:15:01Z",
    ...rest,
  };
}

export function notiz(rest: Partial<Tagebucheintrag> = {}): Tagebucheintrag {
  return {
    id: "t1",
    datum: "2026-11-20",
    text: "Hat gelacht, als Omas Stimme kam.",
    ...rest,
  };
}
