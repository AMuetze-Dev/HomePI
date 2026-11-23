import { describe, expect, it } from "vitest";

import { BEREICHSTITEL } from "./haushaltsbuch/daten";
import {
  BREITE_VOREINSTELLUNG,
  breiteFuer,
  ersteUnterseite,
  OBERFLAECHEN,
  oberflaecheFuer,
  sichtbareUnterseiten,
  traegtTitelSelbst,
  unterseitenFuer,
} from "./register";

describe("Das Register der Oberflächen", () => {
  it("nennt für Staffelpilot die Bereiche in dieser Reihenfolge", () => {
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
      "Regeldateien",
      "Einstellungen",
      "DFBnet-Zugang",
      "Leitfaden",
      "Einrichtung",
    ]);
  });

  it("nennt die Bereiche des Haushaltsbuchs so wie das Modul selbst", () => {
    // Die Wörter stehen zweimal: hier und in haushaltsbuch/daten.ts, weil die
    // Fläche ihren Titel schon braucht, solange sie lädt - und ein Import
    // zurück ins Register wäre ein Zyklus. Läuft das auseinander, heißt die
    // Fläche anders als der Eintrag, über den man sie aufgemacht hat.
    expect(unterseitenFuer("haushaltsbuch").map((u) => [u.id, u.wort])).toEqual(
      Object.entries(BEREICHSTITEL),
    );
  });

  it("hält die Einrichtung aus der Leiste heraus", () => {
    // Ein Weg und keine Fläche: einmal durchlaufen, danach nur noch bei
    // Bedarf. Als Dauereintrag stünde er ab dem zweiten Tag nur im Weg --
    // eine echte Adresse bleibt er trotzdem, sonst liesse er sich weder
    // verlinken noch nach einem Neuladen fortsetzen.
    expect(sichtbareUnterseiten("staffelpilot").map((u) => u.id)).not.toContain(
      "einrichten",
    );
    expect(unterseitenFuer("staffelpilot").map((u) => u.id)).toContain("einrichten");
  });

  it("lässt ein Artefakt ohne Bereiche seinen Titel selbst tragen", () => {
    // Die Verwaltung hat keine zweite Ebene - die Angabe steht deshalb am
    // Artefakt und nicht an einem Bereich. Ohne diesen Weg stuende ueber
    // ihrer Tafel ein zweites Mal "Verwaltung".
    expect(traegtTitelSelbst("verwaltung")).toBe(true);
    expect(traegtTitelSelbst("staffelpilot", "uebersicht")).toBe(true);
    expect(traegtTitelSelbst("gibtsnicht")).toBe(false);
  });

  it("macht den ersten Bereich zur Startfläche", () => {
    expect(ersteUnterseite("staffelpilot")).toBe("uebersicht");
  });

  it("gibt Modulen ohne Bereiche auch keine", () => {
    // Ein Artefakt ohne zweite Ebene bekommt keine leere Leiste, sondern
    // gar keine - der Platz gehört dann dem Inhalt.
    expect(unterseitenFuer("verwaltung")).toEqual([]);
    expect(ersteUnterseite("verwaltung")).toBeUndefined();
  });

  it("gibt jedem Artefakt die Breite, die seine Flächen brauchen", () => {
    expect(breiteFuer("staffelpilot")).toBe("voll");
    expect(breiteFuer("verwaltung")).toBe("weit");
    // Und wer nichts sagt, bekommt die mittlere.
    expect(breiteFuer("gibtsnicht")).toBe(BREITE_VOREINSTELLUNG);
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
