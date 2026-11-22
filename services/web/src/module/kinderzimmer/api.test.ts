import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { einstellungen } from "./testdaten";

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

function aufruf(gefaelscht: ReturnType<typeof vi.fn>): [string, RequestInit] {
  return gefaelscht.mock.calls[0] as [string, RequestInit];
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Pfade und Methoden", () => {
  it.each([
    ["ladeUebersicht", () => api.ladeUebersicht(), "/kinderzimmer/", "GET"],
    [
      "ladeEinstellungen",
      () => api.ladeEinstellungen(),
      "/kinderzimmer/einstellungen",
      "GET",
    ],
    ["ladeAufnahmen", () => api.ladeAufnahmen(), "/kinderzimmer/aufnahmen", "GET"],
    ["ladeFiguren", () => api.ladeFiguren(), "/kinderzimmer/figuren", "GET"],
    [
      "ladeUnbekannte",
      () => api.ladeUnbekannte(),
      "/kinderzimmer/figuren/unbekannt",
      "GET",
    ],
    ["ladeGeraete", () => api.ladeGeraete(), "/kinderzimmer/geraete", "GET"],
    ["ladeProtokoll", () => api.ladeProtokoll(), "/kinderzimmer/protokoll", "GET"],
    ["ladeTagebuch", () => api.ladeTagebuch(), "/kinderzimmer/tagebuch", "GET"],
    [
      "speichereEinstellungen",
      () => api.speichereEinstellungen(einstellungen()),
      "/kinderzimmer/einstellungen",
      "PUT",
    ],
    [
      "aendereAufnahme",
      () => api.aendereAufnahme("a 1", { titel: "Oma", art: "stimme" }),
      "/kinderzimmer/aufnahmen/a%201",
      "PUT",
    ],
    [
      "entferneAufnahme",
      () => api.entferneAufnahme("a1"),
      "/kinderzimmer/aufnahmen/a1",
      "DELETE",
    ],
    [
      "legeFigurAn",
      () =>
        api.legeFigurAn({
          uid: "04A1B2C3",
          name: "Kuh",
          art: "tier",
          farbe: null,
          form: null,
          menge: null,
          stimme: null,
          klang: null,
        }),
      "/kinderzimmer/figuren",
      "POST",
    ],
    [
      "aendereFigur",
      () =>
        api.aendereFigur("f1", {
          uid: "04A1B2C3",
          name: "Kuh",
          art: "tier",
          farbe: null,
          form: null,
          menge: null,
          stimme: null,
          klang: null,
        }),
      "/kinderzimmer/figuren/f1",
      "PUT",
    ],
    [
      "entferneFigur",
      () => api.entferneFigur("f1"),
      "/kinderzimmer/figuren/f1",
      "DELETE",
    ],
    ["legeGeraetAn", () => api.legeGeraetAn("Kiste"), "/kinderzimmer/geraete", "POST"],
    [
      "stelleTokenAus",
      () => api.stelleTokenAus("g1"),
      "/kinderzimmer/geraete/g1/token",
      "POST",
    ],
    [
      "entferneGeraet",
      () => api.entferneGeraet("g1"),
      "/kinderzimmer/geraete/g1",
      "DELETE",
    ],
    [
      "schreibeTagebuch",
      () => api.schreibeTagebuch({ datum: "2026-11-20", text: "Gelacht" }),
      "/kinderzimmer/tagebuch",
      "POST",
    ],
    [
      "entferneTagebuch",
      () => api.entferneTagebuch("t1"),
      "/kinderzimmer/tagebuch/t1",
      "DELETE",
    ],
  ])("%s", async (_name, aufrufen, pfad, methode) => {
    const gefaelscht = antworteMit({});

    await aufrufen();

    const [adresse, init] = aufruf(gefaelscht);
    expect(adresse).toMatch(
      new RegExp(`${pfad.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`),
    );
    expect(init.method ?? "GET").toBe(methode);
    expect(init.credentials).toBe("include");
  });
});

describe("ladeAufnahmeHoch", () => {
  it("schickt die WAV roh und Titel und Art in der Adresse", async () => {
    const gefaelscht = antworteMit({ id: "a1" }, 201);
    const wav = new Blob(["RIFF"], { type: "audio/wav" });

    await api.ladeAufnahmeHoch("Oma & Opa", "stimme", wav);

    const [adresse, init] = aufruf(gefaelscht);
    expect(adresse).toContain("/kinderzimmer/aufnahmen?titel=Oma+%26+Opa&art=stimme");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(wav);
    expect(init.headers).toMatchObject({ "Content-Type": "audio/wav" });
  });

  it("reicht die Meldung des Backends durch", async () => {
    antworteMit({ detail: "Die Aufnahme hat 44100 Hz, erwartet sind 22050 Hz." }, 422);

    await expect(api.ladeAufnahmeHoch("x", "klang", new Blob())).rejects.toEqual(
      new ApiError("Die Aufnahme hat 44100 Hz, erwartet sind 22050 Hz.", 422),
    );
  });
});

describe("Adressen für den Browser", () => {
  it("zeigt für eine Aufnahme auf ihre Datei", () => {
    expect(api.aufnahmeAdresse("a1")).toMatch(/\/kinderzimmer\/aufnahmen\/a1\/datei$/);
  });

  it("nennt dem Gerät eine volle Adresse", () => {
    expect(api.geraeteAdresse()).toMatch(/^https?:\/\/.+\/kinderzimmer$/);
  });
});
