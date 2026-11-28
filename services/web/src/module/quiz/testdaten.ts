import type {
  Frage,
  Katalog,
  OeffentlicheFrage,
  Runde,
  Rundenstand,
  Steuerung,
} from "./api";

export const JETZT = "2026-11-28T20:00:00Z";

export function oeffentlicheFrage(
  mehr: Partial<OeffentlicheFrage> = {},
): OeffentlicheFrage {
  return {
    nummer: 1,
    anzahl: 5,
    kategorie: "Erdkunde",
    typ: "freitext",
    punkte: 2,
    text: "Hauptstadt von Frankreich?",
    hat_bild: false,
    optionen: [],
    mehrfach: false,
    elemente: [],
    minimum: null,
    maximum: null,
    schritt: null,
    einheit: "",
    links: [],
    rechts: [],
    bildoptionen: [],
    hat_ton: false,
    loesung: null,
    ...mehr,
  };
}

export function rundenstand(mehr: Partial<Rundenstand> = {}): Rundenstand {
  return {
    code: "ABC234",
    titel: "Kneipenquiz",
    status: "laeuft",
    phase: "offen",
    frage: oeffentlicheFrage(),
    bild_sichtbar: false,
    frist: null,
    jetzt: JETZT,
    rangliste: [
      { name: "Anna", punkte: 4, rang: 1, team: null },
      { name: "Ben", punkte: 1, rang: 2, team: null },
    ],
    anzahl_antworten: 1,
    buzzer: null,
    teams: [],
    beitritt_offen: true,
    ich: {
      name: "Anna",
      punkte: 4,
      rang: 1,
      antwort: null,
      buzzer_position: null,
      buzzer_urteil: null,
      team: null,
    },
    ...mehr,
  };
}

export function frage(mehr: Partial<Frage> = {}): Frage {
  return {
    id: "f1",
    position: 1,
    text: "Hauptstadt von Frankreich?",
    kategorie: "Erdkunde",
    punkte: 2,
    zeitlimit: 30,
    hat_bild: false,
    medien: [],
    daten: { typ: "freitext", loesungen: ["Paris"] },
    ...mehr,
  };
}

export function runde(mehr: Partial<Runde> = {}): Runde {
  return {
    id: "r1",
    code: "ABC234",
    katalog_id: "k1",
    katalog_titel: "Kneipenquiz",
    status: "laeuft",
    anzahl_spieler: 2,
    angelegt: JETZT,
    beitritt_offen: true,
    ...mehr,
  };
}

export function katalog(mehr: Partial<Katalog> = {}): Katalog {
  return {
    id: "k1",
    titel: "Kneipenquiz",
    beschreibung: "",
    anzahl_fragen: 2,
    geaendert: JETZT,
    ...mehr,
  };
}

export function steuerung(mehr: Partial<Steuerung> = {}): Steuerung {
  const fragen = [
    frage(),
    frage({
      id: "f2",
      text: "Wer buzzert?",
      daten: { typ: "buzzer", loesung: "Zugspitze" },
    }),
  ];
  return {
    runde: runde(),
    phase: "offen",
    frage: fragen[0]!,
    fragen,
    beantwortet: [],
    bild_sichtbar: false,
    frist: null,
    jetzt: JETZT,
    spieler: [
      {
        id: "s1",
        name: "Anna",
        punkte: 4,
        rang: 1,
        zuletzt_gesehen: JETZT,
        verbunden: true,
        team_id: null,
      },
      {
        id: "s2",
        name: "Ben",
        punkte: 1,
        rang: 2,
        zuletzt_gesehen: JETZT,
        verbunden: false,
        team_id: null,
      },
    ],
    antworten: [
      {
        id: "a1",
        spieler_id: "s1",
        spieler: "Anna",
        anzeige: "Paris",
        eingeloggt: true,
        punkte: null,
        richtig: null,
        wert: { text: "Paris" },
      },
    ],
    buzzer: [],
    teams: [],
    ...mehr,
  };
}
