import { describe, expect, it } from "vitest";

import { anzeigename, fristsatz, nachThemen, themaZu } from "./regelsatz";
import { regel, uhrzeit, stunden, minuten } from "./regelsatz.hilfen";

describe("Themen", () => {
  it("ordnet die mitgelieferten Regeln zu", () => {
    expect(themaZu("confirmation_late")).toBe("Bestätigung und Freigabe");
    expect(themaZu("red_card")).toBe("Karten und Sperren");
    expect(themaZu("spielerfoto_zu_alt")).toBe("Spielerfoto");
  });

  it("kennt eigene Regeln nicht und sagt das", () => {
    expect(themaZu("meine_regel")).toBe("Eigene Regeln");
  });

  it("gruppiert in fester Reihenfolge und lässt leere Themen weg", () => {
    const gruppen = nachThemen([
      regel({ id: "1", schluessel: "meine_regel" }),
      regel({ id: "2", schluessel: "red_card" }),
      regel({ id: "3", schluessel: "confirmation_late" }),
      regel({ id: "4", schluessel: "yellow_red_card" }),
    ]);

    expect(gruppen.map((g) => [g.thema, g.regeln.length])).toEqual([
      ["Bestätigung und Freigabe", 1],
      ["Karten und Sperren", 2],
      ["Eigene Regeln", 1],
    ]);
  });
});

describe("Anzeigename", () => {
  it("lässt die Herkunft weg", () => {
    // Wo eine Regel im Quelltext steht, hilft beim Entscheiden nicht.
    expect(anzeigename("Bestätigung zu spät (eingebaut)")).toBe("Bestätigung zu spät");
  });

  it("rührt andere Klammern nicht an", () => {
    expect(anzeigename("Spielabbruch (Neuansetzung)")).toBe(
      "Spielabbruch (Neuansetzung)",
    );
  });
});

describe("Fristsatz", () => {
  const parameter = [
    uhrzeit(),
    minuten({ schluessel: "nach_spielende", vorgabe: 60 }),
    minuten({ schluessel: "nach_freigabe", vorgabe: 60 }),
    stunden(),
  ];

  it("sagt die Vorgabe in einem Satz", () => {
    expect(fristsatz(parameter, {})).toBe(
      "Frist 18:00 Uhr, mindestens 60 Min. nach Spielende und 60 Min. nach der Freigabe.",
    );
  });

  it("nennt die Kulanz, wenn es eine gibt", () => {
    expect(fristsatz(parameter, { kulanz: "6" })).toBe(
      "Frist 18:00 Uhr, mindestens 60 Min. nach Spielende und 60 Min. nach der Freigabe, dazu 6 Std. Kulanz.",
    );
  });

  it("nimmt ein geleertes Feld als Vorgabe", () => {
    expect(fristsatz(parameter, { frist_uhrzeit: "", kulanz: "" })).toContain(
      "Frist 18:00 Uhr",
    );
  });

  it("kommt ohne die Freigabe aus", () => {
    expect(fristsatz([uhrzeit(), minuten(), stunden()], {})).toBe(
      "Frist 18:00 Uhr, mindestens 60 Min. nach Spielende.",
    );
  });

  it("schweigt bei einer Regel ohne Frist", () => {
    expect(fristsatz([stunden()], {})).toBe("");
    expect(fristsatz([], {})).toBe("");
  });
});
