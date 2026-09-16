import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import {
  entferneGeraet,
  ladeGeraete,
  ladeZusammenfassung,
  legeGeraetAn,
  schalteGeraet,
  type Geraet,
} from "./api";

const geraet: Geraet = {
  id: "1",
  name: "Stehlampe",
  raum: "Wohnzimmer",
  zustand: "bereit",
  eingeschaltet: false,
};

function antworteMit(body: unknown, status = 200): ReturnType<typeof vi.fn> {
  const gefaelscht = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal("fetch", gefaelscht);
  return gefaelscht;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Geräte-API", () => {
  it("lädt die Liste", async () => {
    antworteMit([geraet]);

    await expect(ladeGeraete()).resolves.toEqual([geraet]);
  });

  it("lädt die Zusammenfassung vom eigenen Pfad", async () => {
    const aufruf = antworteMit({
      anzahl: 0,
      eingeschaltet: 0,
      in_wartung: 0,
      raeume: {},
    });

    await ladeZusammenfassung();

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringContaining("/geraete/zusammenfassung"),
      expect.anything(),
    );
  });

  it("legt per POST an", async () => {
    const aufruf = antworteMit(geraet, 201);

    await legeGeraetAn({ name: "Lampe", raum: "Küche" });

    const [, init] = aufruf.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ name: "Lampe", raum: "Küche" });
  });

  it("schaltet per PATCH", async () => {
    const aufruf = antworteMit(geraet);

    await schalteGeraet("1", true);

    const [url, init] = aufruf.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/geraete/1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ eingeschaltet: true });
  });

  it("kommt mit 204 ohne Körper zurecht", async () => {
    // Beim Entfernen antwortet das Backend ohne Inhalt - ein json() darauf
    // wuerde werfen.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        json: () => Promise.reject(new Error("kein Körper")),
      }),
    );

    await expect(entferneGeraet("1")).resolves.toBeUndefined();
  });

  it("reicht die Meldung aus problem+json weiter", async () => {
    // "HTTP 409" hilft niemandem - der Text des Backends schon.
    antworteMit(
      {
        title: "Name bereits vergeben",
        detail: "Ein Gerät namens 'X' existiert bereits",
      },
      409,
    );

    await expect(legeGeraetAn({ name: "X", raum: "Y" })).rejects.toThrow(
      /existiert bereits/,
    );
  });

  it("nimmt title, wenn es kein detail gibt", async () => {
    antworteMit({ title: "Gerät unbekannt" }, 404);

    await expect(ladeGeraete()).rejects.toThrow("Gerät unbekannt");
  });

  it("fällt auf den Statuscode zurück, wenn die Antwort kein JSON ist", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: () => Promise.reject(new Error("kein JSON")),
      }),
    );

    await expect(ladeGeraete()).rejects.toThrow("Fehler 502");
  });

  it("wirft einen ApiError mit Statuscode", async () => {
    antworteMit({ title: "Weg" }, 503);

    await expect(ladeGeraete()).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
    });
    await expect(ladeGeraete()).rejects.toBeInstanceOf(ApiError);
  });

  it("reicht das Abbruchsignal durch", async () => {
    const aufruf = antworteMit([]);
    const controller = new AbortController();

    await ladeGeraete(controller.signal);

    expect(aufruf).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ signal: controller.signal }),
    );
  });
});
