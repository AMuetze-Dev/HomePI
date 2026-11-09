import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import {
  aendereTeilnehmer,
  aendereTurnier,
  beendeTurnier,
  beginneSpiel,
  entferneTeilnehmer,
  ladeDashboard,
  ladeSpiele,
  ladeTabellen,
  ladeTeilnehmer,
  ladeTurnier,
  ladeTurniere,
  legeTeilnehmerAn,
  legeTurnierAn,
  loescheTurnier,
  loseAus,
  naechsteRunde,
  nimmErgebnisZurueck,
  setzeZurueck,
  trageErgebnisEin,
  wuerfleAus,
  type Einstellungen,
} from "./api";

const EINSTELLUNGEN: Einstellungen = {
  modus: "gruppen_ko",
  tische: 2,
  best_of: 3,
  minuten_pro_spiel: 12,
  anzahl_gruppen: 2,
  weiter_pro_gruppe: 2,
  runden: 4,
};

function antworteMit(body: unknown, status = 200): ReturnType<typeof vi.fn> {
  const gefaelscht = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    headers: new Headers(),
  });
  vi.stubGlobal("fetch", gefaelscht);
  return gefaelscht;
}

/** Pfad und Methode des letzten Aufrufs. */
function aufgerufen(gefaelscht: ReturnType<typeof vi.fn>): [string, string] {
  const [adresse, init] = gefaelscht.mock.calls[0] as [string, RequestInit];
  return [adresse, (init.method ?? "GET").toUpperCase()];
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Tischtennis-API", () => {
  it("lädt die Turniere vom Wurzelpfad", async () => {
    const aufruf = antworteMit([]);

    await expect(ladeTurniere()).resolves.toEqual([]);
    expect(aufgerufen(aufruf)).toEqual([
      expect.stringMatching(/\/tischtennis\/$/),
      "GET",
    ]);
  });

  it("holt das Dashboard ohne Kennung vom öffentlichen Pfad", async () => {
    /* Das ist der Abruf, den ein Besucher ohne Konto macht - er kennt keine
       Turnierkennung. */
    const aufruf = antworteMit({});

    await ladeDashboard();

    expect(aufgerufen(aufruf)).toEqual([
      expect.stringContaining("/tischtennis/dashboard"),
      "GET",
    ]);
  });

  it("holt mit Kennung das Dashboard genau dieses Turniers", async () => {
    const aufruf = antworteMit({});

    await ladeDashboard("t1");

    expect(aufgerufen(aufruf)[0]).toContain("/tischtennis/turnier/t1/dashboard");
  });

  it("kodiert eine Kennung mit Sonderzeichen", async () => {
    const aufruf = antworteMit({});

    await ladeTurnier("a b&c");

    expect(aufgerufen(aufruf)[0]).toContain("/turnier/a%20b%26c");
  });

  it.each([
    [
      "Teilnehmer",
      () => ladeTeilnehmer("t1"),
      "/tischtennis/turnier/t1/teilnehmer",
      "GET",
    ],
    ["Spiele", () => ladeSpiele("t1"), "/tischtennis/turnier/t1/spiele", "GET"],
    ["Tabellen", () => ladeTabellen("t1"), "/tischtennis/turnier/t1/tabellen", "GET"],
  ])("lädt %s", async (_name, aufrufen, pfad, methode) => {
    const aufruf = antworteMit([]);

    await aufrufen();

    expect(aufgerufen(aufruf)).toEqual([expect.stringContaining(pfad), methode]);
  });

  it.each([
    [
      "Turnier anlegen",
      () => legeTurnierAn({ name: "Fest", ...EINSTELLUNGEN }),
      "/tischtennis/turnier",
      "POST",
    ],
    [
      "Einstellungen ändern",
      () => aendereTurnier("t1", EINSTELLUNGEN),
      "/tischtennis/turnier/t1",
      "PUT",
    ],
    ["Turnier löschen", () => loescheTurnier("t1"), "/tischtennis/turnier/t1", "DELETE"],
    [
      "Teilnehmer anlegen",
      () => legeTeilnehmerAn("t1", { name: "Anna" }),
      "/tischtennis/turnier/t1/teilnehmer",
      "POST",
    ],
    [
      "Teilnehmer ändern",
      () => aendereTeilnehmer("p1", { name: "Anna" }),
      "/tischtennis/teilnehmer/p1",
      "PUT",
    ],
    [
      "Teilnehmer entfernen",
      () => entferneTeilnehmer("p1"),
      "/tischtennis/teilnehmer/p1",
      "DELETE",
    ],
    ["auslosen", () => loseAus("t1", 7), "/tischtennis/turnier/t1/auslosung", "POST"],
    [
      "auswürfeln",
      () => wuerfleAus("t1", 7),
      "/tischtennis/turnier/t1/auswuerfeln",
      "POST",
    ],
    [
      "nächste Runde",
      () => naechsteRunde("t1"),
      "/tischtennis/turnier/t1/naechste-runde",
      "POST",
    ],
    [
      "zurücksetzen",
      () => setzeZurueck("t1"),
      "/tischtennis/turnier/t1/zuruecksetzen",
      "POST",
    ],
    ["beenden", () => beendeTurnier("t1"), "/tischtennis/turnier/t1/beenden", "POST"],
    [
      "Spiel beginnen",
      () => beginneSpiel("s1", 2),
      "/tischtennis/spiel/s1/beginnen",
      "POST",
    ],
    [
      "Sieger eintragen",
      () => trageErgebnisEin("s1", "p1"),
      "/tischtennis/spiel/s1/ergebnis",
      "PUT",
    ],
    [
      "Ergebnis zurücknehmen",
      () => nimmErgebnisZurueck("s1"),
      "/tischtennis/spiel/s1/ergebnis",
      "DELETE",
    ],
  ])("schickt %s an den richtigen Endpunkt", async (_name, aufrufen, pfad, methode) => {
    const aufruf = antworteMit({});

    await aufrufen();

    expect(aufgerufen(aufruf)).toEqual([expect.stringContaining(pfad), methode]);
  });

  it("schickt die Saat mit, auch wenn keine gewählt wurde", async () => {
    /* `null` heisst fuer das Backend "zieh eine" - ein fehlendes Feld waere
       dasselbe, aber nur solange niemand das Schema straffer macht. */
    const aufruf = antworteMit({});

    await loseAus("t1");

    const [, init] = aufruf.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ saat: null });
  });

  it("schickt als Ergebnis nur den Sieger", async () => {
    /* Das ist der ganze Umbau in einer Zusicherung: keine Saetze, keine
       Baelle - ein Name. */
    const aufruf = antworteMit({});

    await trageErgebnisEin("s1", "p1");

    const [, init] = aufruf.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ sieger_id: "p1" });
  });

  it("reicht die Meldung des Backends weiter, nicht den Statuscode", async () => {
    antworteMit({ detail: "'Anna' steht schon auf der Liste" }, 409);

    await expect(legeTeilnehmerAn("t1", { name: "Anna" })).rejects.toThrow(
      "'Anna' steht schon auf der Liste",
    );
  });

  it("wirft bei einem Fehler einen ApiError mit Status", async () => {
    antworteMit({ detail: "weg" }, 503);

    await expect(ladeTurniere()).rejects.toBeInstanceOf(ApiError);
  });
});
