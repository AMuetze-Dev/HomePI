import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./client";
import { schnittstelle } from "./schnittstelle";

function antworteMit(
  body: unknown,
  status = 200,
  ohneKoerper = false,
): ReturnType<typeof vi.fn> {
  const gefaelscht = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: ohneKoerper
      ? () => Promise.reject(new SyntaxError("kein JSON"))
      : () => Promise.resolve(body),
  });
  vi.stubGlobal("fetch", gefaelscht);
  return gefaelscht;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("schnittstelle", () => {
  it("setzt den Pfad des Artefakts davor", async () => {
    const aufruf = antworteMit([]);

    await schnittstelle("/messwerte").anfrage("/reihen");

    expect(aufruf).toHaveBeenCalledWith(
      expect.stringMatching(/\/messwerte\/reihen$/),
      expect.anything(),
    );
  });

  it("schickt das Sitzungscookie mit - ohne es ist jedes Artefakt verschlossen", async () => {
    const aufruf = antworteMit([]);

    await schnittstelle("/messwerte").anfrage("/");

    expect(aufruf).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("reicht das Abbruchsignal durch", async () => {
    const aufruf = antworteMit([]);
    const controller = new AbortController();

    await schnittstelle("/x").anfrage("/", {}, controller.signal);

    expect(aufruf).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("sendet Daten als JSON", async () => {
    const aufruf = antworteMit({ id: "1" }, 201);

    await schnittstelle("/x").sende("POST", "/", { name: "Lampe" });

    const [, init] = aufruf.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "Lampe" }));
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(new Headers(init.headers).get("Accept")).toBe("application/json");
  });

  it("sendet ohne Daten keinen Körper", async () => {
    const aufruf = antworteMit(undefined, 204);

    await schnittstelle("/x").sende("DELETE", "/1");

    const [, init] = aufruf.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBeUndefined();
  });

  it("baut Adressen für den Browser", () => {
    expect(schnittstelle("/x").adresse("/a.pdf")).toMatch(/\/x\/a\.pdf$/);
  });

  it("liefert bei 204 nichts", async () => {
    antworteMit(undefined, 204);

    await expect(schnittstelle("/x").sende("DELETE", "/1")).resolves.toBeUndefined();
  });

  it("wirft die Meldung des Backends, nicht den Statuscode", async () => {
    antworteMit({ title: "Konflikt", detail: "Den Namen gibt es schon" }, 409);

    const fehler = await schnittstelle("/x")
      .anfrage("/")
      .catch((e: unknown) => e);

    expect(fehler).toBeInstanceOf(ApiError);
    expect((fehler as ApiError).message).toBe("Den Namen gibt es schon");
    expect((fehler as ApiError).status).toBe(409);
  });

  it("nimmt den Titel, wenn es kein detail gibt", async () => {
    antworteMit({ title: "Keine Berechtigung" }, 403);

    await expect(schnittstelle("/x").anfrage("/")).rejects.toThrow("Keine Berechtigung");
  });

  it("nennt bei einer Antwort ohne JSON den Statuscode", async () => {
    antworteMit(undefined, 502, true);

    await expect(schnittstelle("/x").anfrage("/")).rejects.toThrow("Fehler 502");
  });

  it("nennt bei abgelehnten Feldern, welches", async () => {
    // Sonst steht beim Benutzer nur "entspricht nicht dem erwarteten
    // Schema" - und er sucht im ganzen Formular.
    antworteMit(
      {
        title: "Ungültige Anfrage",
        detail: "Die Anfrage entspricht nicht dem erwarteten Schema",
        fehler: [
          { feld: "body.name", problem: "String should have at least 1 character" },
        ],
      },
      422,
    );

    await expect(schnittstelle("/x").anfrage("/")).rejects.toThrow(
      "Die Anfrage entspricht nicht dem erwarteten Schema (name)",
    );
  });
});
