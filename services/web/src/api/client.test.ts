import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchEndpunkte, fetchHealth, fetchModule } from "./client";

function antworteMit(body: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    }),
  );
}

const gesund = { status: "ok", version: "0.1.0", checks: { database: true } };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchHealth", () => {
  it("liefert den Bericht bei 200", async () => {
    antworteMit(gesund);

    await expect(fetchHealth()).resolves.toEqual(gesund);
  });

  it("liefert den Bericht auch bei 503", async () => {
    // Genau dann ist der Inhalt interessant: die Oberflaeche soll anzeigen
    // koennen, WAS kaputt ist, statt nur einen Fehler zu werfen.
    const krank = { status: "down", version: "0.1.0", checks: { database: false } };
    antworteMit(krank, 503);

    await expect(fetchHealth()).resolves.toEqual(krank);
  });

  it("wirft bei anderen Fehlercodes", async () => {
    antworteMit({}, 500);

    await expect(fetchHealth()).rejects.toBeInstanceOf(ApiError);
  });

  it("wirft, wenn die Antwort nicht die erwartete Form hat", async () => {
    antworteMit({ irgendwas: true });

    await expect(fetchHealth()).rejects.toThrow(/erwartete Form/);
  });

  it("reicht das Abbruchsignal durch", async () => {
    antworteMit(gesund);
    const controller = new AbortController();

    await fetchHealth(controller.signal);

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/health"),
      expect.objectContaining({ signal: controller.signal }),
    );
  });
});

describe("fetchModule", () => {
  const eintrag = {
    id: "geraete",
    titel: "Geräte",
    pfad: "/geraete",
    beschreibung: "",
    icon: "kachel",
    version: "1.0.0",
    status: "bereit",
  };

  it("liefert das Manifest", async () => {
    antworteMit([eintrag]);

    await expect(fetchModule()).resolves.toEqual([eintrag]);
  });

  it("wertet 404 als 'kein Gateway', nicht als Fehler", async () => {
    // Ein Dienst ohne Module ist kein Fehlerfall - die Startseite soll dann
    // eine leere Liste zeigen und keine Fehlermeldung.
    antworteMit({}, 404);

    await expect(fetchModule()).resolves.toEqual([]);
  });

  it("wirft bei einer Antwort in falscher Form", async () => {
    antworteMit([{ nur: "quatsch" }]);

    await expect(fetchModule()).rejects.toThrow(/erwartete Form/);
  });

  it("wirft bei Serverfehlern", async () => {
    antworteMit({}, 500);

    await expect(fetchModule()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("fetchEndpunkte", () => {
  const schema = {
    paths: {
      "/geraete/": { get: { summary: "Liste" } },
      "/geraete/{id}": { get: {}, delete: { description: "Entfernen" } },
      "/messwerte/": { get: { summary: "Fremd" } },
      "/health": { get: { summary: "Betrieb" } },
    },
  };

  it("nimmt nur die Pfade des Moduls", async () => {
    antworteMit(schema);

    const endpunkte = await fetchEndpunkte("/geraete");

    expect(endpunkte.map((e) => e.pfad)).toEqual([
      "/geraete/",
      "/geraete/{id}",
      "/geraete/{id}",
    ]);
  });

  it("nimmt summary, sonst description, sonst nichts", async () => {
    antworteMit(schema);

    const endpunkte = await fetchEndpunkte("/geraete");

    expect(endpunkte[0]?.beschreibung).toBe("Liste");
    expect(endpunkte.find((e) => e.methode === "DELETE")?.beschreibung).toBe("Entfernen");
    expect(
      endpunkte.find((e) => e.methode === "GET" && e.pfad === "/geraete/{id}")
        ?.beschreibung,
    ).toBe("");
  });

  it("liefert nichts statt zu werfen, wenn es kein Schema gibt", async () => {
    antworteMit({}, 404);

    await expect(fetchEndpunkte("/geraete")).resolves.toEqual([]);
  });

  it("kommt mit einem Schema ohne paths zurecht", async () => {
    antworteMit({ openapi: "3.1.0" });

    await expect(fetchEndpunkte("/geraete")).resolves.toEqual([]);
  });
});
