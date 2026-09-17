import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import {
  entscheide,
  hakeAb,
  ladeSpiel,
  ladeStaffeln,
  ladeWarteschlange,
  ladeZusammenfassung,
  legeStaffelAn,
  loeseHaken,
  type Staffel,
} from "./api";

const staffel: Staffel = {
  id: "s1",
  name: "Stadtliga C",
  altersklasse: "maenner",
  spielklasse: "3.Kreisliga (C)",
  saison: "26/27",
  aktiv: true,
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

describe("StaffelPilot-API", () => {
  it("lädt die Staffeln", async () => {
    antworteMit([staffel]);

    await expect(ladeStaffeln()).resolves.toEqual([staffel]);
  });

  it("lädt die Warteschlange ohne Filter vom Wurzelpfad", async () => {
    const aufruf = antworteMit([]);

    await ladeWarteschlange();

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringMatching(/\/staffelpilot\/$/),
      expect.anything(),
    );
  });

  it("hängt die Staffel als Abfrageparameter an", async () => {
    const aufruf = antworteMit([]);

    await ladeWarteschlange("s1");

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringContaining("/staffelpilot/?staffel_id=s1"),
      expect.anything(),
    );
  });

  it("kodiert eine Kennung, die Sonderzeichen enthält", async () => {
    const aufruf = antworteMit([]);

    await ladeWarteschlange("a b&c");

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringContaining("staffel_id=a%20b%26c"),
      expect.anything(),
    );
  });

  it("lädt die Zusammenfassung vom eigenen Pfad", async () => {
    const aufruf = antworteMit({
      spiele: 0,
      offen: 0,
      abgehakt: 0,
      befunde_offen: 0,
      befunde_kritisch: 0,
      staffeln_aktiv: 0,
    });

    await ladeZusammenfassung();

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringContaining("/staffelpilot/zusammenfassung"),
      expect.anything(),
    );
  });

  it("lädt einen Spielbericht", async () => {
    const aufruf = antworteMit({});

    await ladeSpiel("m1");

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringContaining("/staffelpilot/spiele/m1"),
      expect.anything(),
    );
  });

  it("legt eine Staffel per POST an", async () => {
    const aufruf = antworteMit(staffel, 201);

    await legeStaffelAn({
      name: "Neu",
      altersklasse: "ue35",
      spielklasse: "1.Kreisklasse",
    });

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringContaining("/staffelpilot/staffeln"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("schickt die Entscheidung samt Grund", async () => {
    const aufruf = antworteMit({});

    await entscheide("b1", "verworfen", "war spielberechtigt");

    const [, init] = aufruf.mock.calls[0] as [string, { body: string }];
    expect(JSON.parse(init.body)).toEqual({
      art: "verworfen",
      grund: "war spielberechtigt",
    });
  });

  it("setzt den Haken per POST", async () => {
    const aufruf = antworteMit({});

    await hakeAb("m1");

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringContaining("/staffelpilot/spiele/m1/haken"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("löst den Haken per DELETE", async () => {
    const aufruf = antworteMit({});

    await loeseHaken("m1");

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringContaining("/staffelpilot/spiele/m1/haken"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});

describe("Fehler", () => {
  it("nimmt den Text aus problem+json", async () => {
    antworteMit(
      {
        title: "Es sind noch Befunde offen",
        detail: "1 Befund braucht noch eine Entscheidung",
      },
      409,
    );

    await expect(hakeAb("m1")).rejects.toThrow("1 Befund braucht noch eine Entscheidung");
  });

  it("nimmt den Titel, wenn kein Detail dabeisteht", async () => {
    antworteMit({ title: "Staffel unbekannt" }, 404);

    await expect(ladeSpiel("x")).rejects.toThrow("Staffel unbekannt");
  });

  it("fällt auf den Statuscode zurück, wenn der Körper kein JSON ist", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: () => Promise.reject(new Error("kein JSON")),
      }),
    );

    await expect(ladeStaffeln()).rejects.toThrow("Fehler 502");
  });

  it("wirft einen ApiError mit dem Statuscode", async () => {
    antworteMit({ detail: "weg" }, 404);

    await expect(ladeStaffeln()).rejects.toBeInstanceOf(ApiError);
    antworteMit({ detail: "weg" }, 404);
    await expect(ladeStaffeln()).rejects.toMatchObject({ status: 404 });
  });

  it("gibt bei 204 nichts zurück", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        json: () => Promise.reject(new Error("kein Körper")),
      }),
    );

    await expect(loeseHaken("m1")).resolves.toBeUndefined();
  });
});
