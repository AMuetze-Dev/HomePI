import type { Dashboard, Spiel, Tabelle, Turnier } from "./api";

/**
 * Vorlagen für die Tests dieses Artefakts.
 *
 * Fünf Testdateien brauchen dieselben drei Gebilde, und jede hatte vorher
 * ihre eigene Kopie. Beim Umbau auf „nur der Sieger“ waren das fünf Stellen
 * für dieselbe Änderung — eine zu viel, als dass alle fünf stimmen.
 */

export function turnier(rest: Partial<Turnier> = {}): Turnier {
  return {
    id: "t1",
    name: "Betriebsturnier",
    modus: "gruppen_ko",
    zustand: "planung",
    tische: 2,
    best_of: 3,
    minuten_pro_spiel: 12,
    anzahl_gruppen: 2,
    weiter_pro_gruppe: 2,
    runden: 4,
    saat: null,
    runde_angesetzt: 0,
    ko_steht: false,
    anzahl_teilnehmer: 4,
    anzahl_spiele: 0,
    offene_spiele: 0,
    ...rest,
  };
}

export function spiel(rest: Partial<Spiel> = {}): Spiel {
  return {
    id: "s1",
    nummer: 1,
    phase: "gruppe",
    runde: 1,
    bezeichnung: "Gruppe A, Runde 1",
    gruppe: "Gruppe A",
    heim_id: "p1",
    gast_id: "p2",
    heim: "Anna",
    gast: "Bernd",
    heim_herkunft: null,
    gast_herkunft: null,
    zustand: "geplant",
    tisch: 1,
    sieger_id: null,
    freilos: false,
    begonnen_am: null,
    beendet_am: null,
    erwartet_ab: "2026-11-09T18:12:00Z",
    gleich_dran: false,
    ...rest,
  };
}

export function tabelle(rest: Partial<Tabelle> = {}): Tabelle {
  return {
    titel: "Gruppe A",
    zeilen: [
      {
        platz: 1,
        teilnehmer_id: "p1",
        teilnehmer: "Anna",
        spiele: 1,
        siege: 1,
        niederlagen: 0,
        punkte: 2,
      },
      {
        platz: 2,
        teilnehmer_id: "p2",
        teilnehmer: "Bernd",
        spiele: 1,
        siege: 0,
        niederlagen: 1,
        punkte: 0,
      },
    ],
    entscheidung_offen: [],
    ...rest,
  };
}

export function dashboard(rest: Partial<Dashboard> = {}): Dashboard {
  return {
    turnier: turnier({ zustand: "laufend" }),
    stand: "2026-11-09T18:00:00Z",
    tische: [{ tisch: 1, laeuft: null, danach: [] }],
    spiele: [],
    naechste: [],
    letzte: [],
    tabellen: [],
    teilnehmer: [
      { id: "p1", name: "Anna", notiz: "", gruppe: "Gruppe A", freilose: 0 },
      { id: "p2", name: "Bernd", notiz: "", gruppe: "Gruppe A", freilose: 0 },
    ],
    fertig: false,
    ...rest,
  };
}
