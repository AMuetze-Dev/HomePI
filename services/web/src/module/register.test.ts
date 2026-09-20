import { describe, expect, it } from "vitest";

import {
  BREITE_VOREINSTELLUNG,
  breiteFuer,
  ersteUnterseite,
  OBERFLAECHEN,
  oberflaecheFuer,
  unterseitenFuer,
} from "./register";

describe("Das Register der Oberflächen", () => {
  it("nennt für Staffelpilot die neun Bereiche in dieser Reihenfolge", () => {
    // Die Reihenfolge ist keine Formalie: Der erste Bereich ist die Fläche,
    // auf der man morgens landet, und die Leiste liest die Liste von oben.
    expect(unterseitenFuer("staffelpilot").map((u) => u.wort)).toEqual([
      "Übersicht",
      "Spielprüfung",
      "Prüflauf",
      "Ergebnisse",
      "Staffeln",
      "Vorgänge",
      "Regeln",
      "Einstellungen",
      "DFBnet-Zugang",
    ]);
  });

  it("macht den ersten Bereich zur Startfläche", () => {
    expect(ersteUnterseite("staffelpilot")).toBe("uebersicht");
  });

  it("gibt Modulen ohne Bereiche auch keine", () => {
    // Ein Artefakt ohne zweite Ebene bekommt keine leere Leiste, sondern
    // gar keine - der Platz gehört dann dem Inhalt.
    expect(unterseitenFuer("geraete")).toEqual([]);
    expect(ersteUnterseite("geraete")).toBeUndefined();
  });

  it("gibt Staffelpilot die volle Breite und den anderen die mittlere", () => {
    expect(breiteFuer("staffelpilot")).toBe("voll");
    expect(breiteFuer("geraete")).toBe("normal");
  });

  it("lässt einen Bereich von der Breite seines Moduls abweichen", () => {
    // Die Spielprüfung lebt von der Breite, das Zugangsformular nicht: Ein
    // Eingabefeld über die ganze Monitorbreite ist unlesbar.
    expect(breiteFuer("staffelpilot", "spiele")).toBe("voll");
    expect(breiteFuer("staffelpilot", "zugang")).toBe("text");
    expect(breiteFuer("staffelpilot", "staffeln")).toBe("normal");
  });

  it("fällt für einen Bereich ohne eigene Angabe auf das Modul zurück", () => {
    expect(breiteFuer("staffelpilot", "uebersicht")).toBe("voll");
    // Und für einen erfundenen Bereich ebenso - die Seite leitet den ohnehin
    // auf den ersten um, aber die Breite darf dabei nicht undefiniert sein.
    expect(breiteFuer("staffelpilot", "gibtsnicht")).toBe("voll");
  });

  it("fällt für unbekannte Artefakte auf die Voreinstellung zurück", () => {
    // Ein Artefakt ohne eigene Oberfläche bekommt die generische Ansicht -
    // und die braucht trotzdem eine Breite.
    expect(oberflaecheFuer("gibtsnicht")).toBeUndefined();
    expect(breiteFuer("gibtsnicht")).toBe(BREITE_VOREINSTELLUNG);
    expect(unterseitenFuer("gibtsnicht")).toEqual([]);
  });

  it("vergibt jede Kennung nur einmal", () => {
    // Zwei Einträge mit derselben Kennung wären ein stiller Fehler: Der
    // zweite würde nie gefunden, weil die Suche beim ersten stehenbleibt.
    const kennungen = OBERFLAECHEN.map((o) => o.id);
    expect(new Set(kennungen).size).toBe(kennungen.length);
  });

  it("hält die Bereichskennungen je Modul eindeutig und adresstauglich", () => {
    for (const oberflaeche of OBERFLAECHEN) {
      const ids = (oberflaeche.unterseiten ?? []).map((u) => u.id);
      expect(new Set(ids).size, `${oberflaeche.id}: doppelte Bereiche`).toBe(ids.length);
      for (const id of ids) {
        // Die Kennung landet in der Adresse. Umlaute und Großbuchstaben
        // wären dort eine Quelle für Verwechslungen.
        expect(id, `${oberflaeche.id}/${id}`).toMatch(/^[a-z][a-z0-9-]*$/);
      }
    }
  });
});
