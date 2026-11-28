import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "./api";
import { loesungstext } from "./texte";
import { frage } from "./testdaten";

let aufrufe: { url: string; init: RequestInit }[] = [];

beforeEach(() => {
  aufrufe = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init: RequestInit) => {
      aufrufe.push({ url, init });
      return Promise.resolve(new Response("{}", { status: 200 }));
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function letzter() {
  const aufruf = aufrufe.at(-1)!;
  return {
    pfad: aufruf.url,
    methode: aufruf.init.method ?? "GET",
    koerper:
      typeof aufruf.init.body === "string"
        ? (JSON.parse(aufruf.init.body) as unknown)
        : aufruf.init.body,
  };
}

describe("Pfade zum Backend", () => {
  it("schickt das Cookie bei jedem Aufruf mit", async () => {
    await api.ladeRundenstand("ABC234");
    expect(aufrufe[0]!.init.credentials).toBe("include");
    expect(letzter()).toMatchObject({ pfad: "/quiz/runden/ABC234", methode: "GET" });
  });

  it.each<[string, () => Promise<unknown>, string, string, unknown]>([
    [
      "beitreten",
      () => api.trittBei("ABC234", "Anna"),
      "POST",
      "/quiz/runden/ABC234/beitreten",
      { name: "Anna" },
    ],
    [
      "wiederkehren",
      () => api.trittBei("ABC234", "Anna", "ABCD-EFGH"),
      "POST",
      "/quiz/runden/ABC234/beitreten",
      { name: "Anna", wiederkehrcode: "ABCD-EFGH" },
    ],
    [
      "antworten",
      () => api.antworte("ABC234", { text: "x" }),
      "PUT",
      "/quiz/runden/ABC234/antwort",
      { text: "x" },
    ],
    [
      "buzzern",
      () => api.buzzere("ABC234"),
      "POST",
      "/quiz/runden/ABC234/buzzer",
      undefined,
    ],
    ["kataloge", () => api.ladeKataloge(), "GET", "/quiz/kataloge", undefined],
    ["katalog", () => api.ladeKatalog("k1"), "GET", "/quiz/kataloge/k1", undefined],
    [
      "katalog anlegen",
      () => api.legeKatalogAn("Quiz"),
      "POST",
      "/quiz/kataloge",
      { titel: "Quiz", beschreibung: "" },
    ],
    [
      "katalog ändern",
      () => api.aendereKatalog("k1", "Neu", "x"),
      "PUT",
      "/quiz/kataloge/k1",
      { titel: "Neu", beschreibung: "x" },
    ],
    [
      "katalog löschen",
      () => api.loescheKatalog("k1"),
      "DELETE",
      "/quiz/kataloge/k1",
      undefined,
    ],
    [
      "frage anlegen",
      () => api.legeFrageAn("k1", frage()),
      "POST",
      "/quiz/kataloge/k1/fragen",
      frage(),
    ],
    [
      "frage ändern",
      () => api.aendereFrage("f1", frage()),
      "PUT",
      "/quiz/fragen/f1",
      frage(),
    ],
    [
      "frage löschen",
      () => api.loescheFrage("f1"),
      "DELETE",
      "/quiz/fragen/f1",
      undefined,
    ],
    [
      "sortieren",
      () => api.sortiereFragen("k1", ["b", "a"]),
      "PUT",
      "/quiz/kataloge/k1/reihenfolge",
      { fragen: ["b", "a"] },
    ],
    [
      "bild löschen",
      () => api.entferneBild("f1"),
      "DELETE",
      "/quiz/fragen/f1/bild",
      undefined,
    ],
    ["runden", () => api.ladeRunden(), "GET", "/quiz/leitung", undefined],
    [
      "eröffnen",
      () => api.eroeffneRunde("k1"),
      "POST",
      "/quiz/leitung",
      { katalog_id: "k1" },
    ],
    [
      "runde löschen",
      () => api.loescheRunde("r1"),
      "DELETE",
      "/quiz/leitung/r1",
      undefined,
    ],
    ["steuerung", () => api.ladeSteuerung("r1"), "GET", "/quiz/leitung/r1", undefined],
    [
      "zeigen",
      () => api.steuere("r1", { art: "zeigen", timer: true }),
      "POST",
      "/quiz/leitung/r1/zeigen",
      { timer: true },
    ],
    [
      "sperren",
      () => api.steuere("r1", { art: "sperren" }),
      "POST",
      "/quiz/leitung/r1/sperren",
      {},
    ],
    [
      "bewerten",
      () => api.bewerteAntwort("r1", "a1", 3),
      "PUT",
      "/quiz/leitung/r1/antworten/a1",
      { punkte: 3 },
    ],
    [
      "korrektur",
      () => api.korrigiere("r1", "s1", -1, "Vorsagen"),
      "POST",
      "/quiz/leitung/r1/spieler/s1/korrektur",
      { punkte: -1, grund: "Vorsagen" },
    ],
    [
      "wiederkehrcode",
      () => api.stelleWiederkehrAus("r1", "s1"),
      "POST",
      "/quiz/leitung/r1/spieler/s1/wiederkehr",
      undefined,
    ],
    [
      "spieler entfernen",
      () => api.entferneSpieler("r1", "s1"),
      "DELETE",
      "/quiz/leitung/r1/spieler/s1",
      undefined,
    ],
  ])("%s", async (_name, aufruf, methode, pfad, koerper) => {
    await aufruf();
    expect(letzter()).toEqual({ pfad, methode, koerper });
  });

  it("lädt ein Bild roh mit seinem eigenen Typ hoch", async () => {
    const datei = new Blob(["x"], { type: "image/png" });
    await api.ladeBildHoch("f1", datei);
    const { init } = aufrufe.at(-1)!;
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(datei);
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("image/png");
  });

  it("baut Bildadressen, die sich je Frage und Stand ändern", () => {
    expect(api.rundenbildAdresse("ABC234", 3)).toBe("/quiz/runden/ABC234/bild?frage=3");
    expect(api.bildAdresse("f1", "2")).toBe("/quiz/fragen/f1/bild?stand=2");
  });
});

describe("Lösung in einer Zeile", () => {
  it.each<[api.FrageDaten, string]>([
    [{ typ: "freitext", loesungen: ["Paris", "paris"] }, "Paris / paris"],
    [{ typ: "bild", loesungen: [] }, "bewertest du von Hand"],
    [{ typ: "bild", loesungen: ["Turm"] }, "Turm"],
    [{ typ: "zahl", loesung: 2.5, toleranz: 0, einheit: "m" }, "2,5 m"],
    [{ typ: "zahl", loesung: 16, toleranz: 1, einheit: "" }, "16 (± 1)"],
    [
      {
        typ: "schaetzung",
        minimum: 0,
        maximum: 10,
        schritt: 1,
        loesung: 3.7,
        einheit: "Mio",
      },
      "3,7 Mio - wer am nächsten liegt",
    ],
    [
      {
        typ: "auswahl",
        optionen: [
          { text: "Rot", richtig: true },
          { text: "Blau", richtig: false },
        ],
      },
      "Rot",
    ],
    [{ typ: "buzzer", loesung: "" }, "bewertest du von Hand"],
    [{ typ: "buzzer", loesung: "Zugspitze" }, "Zugspitze"],
    [{ typ: "hotspot", ziele: [{ x: 1, y: 1, radius: 5 }] }, "1 Stelle im Bild"],
    [{ typ: "sortieren", elemente: ["a", "b"] }, "a → b"],
  ])("%j", (daten, erwartet) => {
    expect(loesungstext(frage({ daten }))).toBe(erwartet);
  });
});
