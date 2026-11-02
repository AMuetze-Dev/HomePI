import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import {
  aendereKonto,
  aenderePerson,
  aenderePosten,
  entferneKategorie,
  entferneKonto,
  entfernePerson,
  entfernePosten,
  ladeFlussbild,
  ladeKategorien,
  ladeKonten,
  ladePersonen,
  ladePosten,
  ladeUebersicht,
  legeGrundgeruestAn,
  legeKategorieAn,
  legeKontoAn,
  legePersonAn,
  legePostenAn,
} from "./api";

function antworteMit(body: unknown, status = 200): ReturnType<typeof vi.fn> {
  const gefaelscht = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal("fetch", gefaelscht);
  return gefaelscht;
}

function ersterAufruf(aufruf: ReturnType<typeof vi.fn>): [string, RequestInit] {
  return aufruf.mock.calls[0] as [string, RequestInit];
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Lesen", () => {
  it("holt den Monatsplan ohne Zeitraum vom Stammpfad", async () => {
    const aufruf = antworteMit({});

    await ladeUebersicht();

    expect(ersterAufruf(aufruf)[0]).toMatch(/\/haushaltsbuch\/$/);
  });

  it("hängt Jahr und Monat an, wenn ein Zeitraum gewählt ist", async () => {
    const aufruf = antworteMit({});

    await ladeUebersicht({ jahr: 2026, monat: 3 });

    expect(ersterAufruf(aufruf)[0]).toContain("jahr=2026&monat=3");
  });

  it("reicht das Abbruchsignal durch", async () => {
    // Ohne das läuft nach einem Seitenwechsel eine Antwort ins Leere und
    // überschreibt den neuen Zustand.
    const aufruf = antworteMit([]);
    const controller = new AbortController();

    await ladePersonen(controller.signal);

    expect(aufruf).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it.each([
    ["Konten", ladeKonten, "/konten"],
    ["Kategorien", ladeKategorien, "/kategorien"],
    ["Posten", ladePosten, "/posten"],
    ["Flussbild", ladeFlussbild, "/flussbild"],
  ])("holt %s vom eigenen Pfad", async (_name, laden, pfad) => {
    const aufruf = antworteMit([]);

    await laden();

    expect(ersterAufruf(aufruf)[0]).toContain(`/haushaltsbuch${pfad}`);
  });
});

describe("Schreiben", () => {
  it("legt eine Person per POST an", async () => {
    const aufruf = antworteMit({}, 201);

    await legePersonAn({ name: "Aaron" });

    const [url, init] = ersterAufruf(aufruf);
    expect(url).toContain("/haushaltsbuch/personen");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ name: "Aaron" });
  });

  it("legt ein Konto mit leerem Inhaber als gemeinsames an", async () => {
    const aufruf = antworteMit({}, 201);

    await legeKontoAn({ name: "DKB1", art: "verteiler", inhaber_id: null });

    expect(JSON.parse(ersterAufruf(aufruf)[1].body as string)).toMatchObject({
      inhaber_id: null,
    });
  });

  it("macht ein Konto wieder gemeinschaftlich", async () => {
    // Ein leeres inhaber_id hieße beim PATCH "nicht angefasst" - deshalb das
    // eigene Feld.
    const aufruf = antworteMit({});

    await aendereKonto("k1", { gemeinschaftlich: true });

    const [url, init] = ersterAufruf(aufruf);
    expect(url).toContain("/konten/k1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ gemeinschaftlich: true });
  });

  it("legt eine Kategorie an und merkt sich, ob sie als Sparen zählt", async () => {
    const aufruf = antworteMit({}, 201);

    await legeKategorieAn({ name: "Investments", zaehlt_als_sparen: true });

    expect(JSON.parse(ersterAufruf(aufruf)[1].body as string)).toEqual({
      name: "Investments",
      zaehlt_als_sparen: true,
    });
  });

  it("ruft das Grundgerüst ohne Körper ab", async () => {
    const aufruf = antworteMit([]);

    await legeGrundgeruestAn();

    const [url, init] = ersterAufruf(aufruf);
    expect(url).toContain("/kategorien/grundgeruest");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("legt einen Posten mit seiner Aufteilung an", async () => {
    const aufruf = antworteMit({}, 201);

    await legePostenAn({
      name: "Miete",
      art: "ausgabe",
      betrag: "900.00",
      intervall_monate: 1,
      faelligkeitsmonat: 1,
      abbuchungstag: null,
      konto_id: "k1",
      kategorie_id: null,
      variabel: false,
      anteile: [{ person_id: "p1", gewicht: 2 }],
    });

    expect(JSON.parse(ersterAufruf(aufruf)[1].body as string)).toMatchObject({
      anteile: [{ person_id: "p1", gewicht: 2 }],
    });
  });

  it("pausiert einen Posten per PATCH", async () => {
    const aufruf = antworteMit({});

    await aenderePosten("x", { aktiv: false });

    expect(JSON.parse(ersterAufruf(aufruf)[1].body as string)).toEqual({ aktiv: false });
  });

  it("ändert eine Person per PATCH", async () => {
    const aufruf = antworteMit({});

    await aenderePerson("p1", { name: "Aaron M." });

    expect(ersterAufruf(aufruf)[1].method).toBe("PATCH");
  });

  it.each([
    ["Person", entfernePerson, "/personen/x"],
    ["Konto", entferneKonto, "/konten/x"],
    ["Kategorie", entferneKategorie, "/kategorien/x"],
    ["Posten", entfernePosten, "/posten/x"],
  ])("entfernt %s per DELETE", async (_name, entfernen, pfad) => {
    const aufruf = antworteMit(null, 204);

    await entfernen("x");

    const [url, init] = ersterAufruf(aufruf);
    expect(url).toContain(pfad);
    expect(init.method).toBe("DELETE");
  });
});

describe("Fehler", () => {
  it("reicht die Meldung aus problem+json weiter", async () => {
    // "HTTP 409" hilft niemandem - der Text des Backends schon.
    antworteMit(
      {
        title: "Wird noch verwendet",
        detail: "Auf diesem Konto liegen noch Posten.",
      },
      409,
    );

    await expect(entferneKonto("k1")).rejects.toThrow(/liegen noch Posten/);
  });

  it("wirft einen ApiError mit Statuscode", async () => {
    antworteMit({ title: "Konto unbekannt" }, 404);

    await expect(ladeKonten()).rejects.toBeInstanceOf(ApiError);
    await expect(ladeKonten()).rejects.toMatchObject({ status: 404 });
  });

  it("kommt mit 204 ohne Körper zurecht", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        json: () => Promise.reject(new Error("kein Körper")),
      }),
    );

    await expect(entfernePosten("x")).resolves.toBeUndefined();
  });
});
