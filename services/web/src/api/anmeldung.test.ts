import { afterEach, describe, expect, it, vi } from "vitest";

import { abmelden, anmelden, holeIch } from "./anmeldung";
import { ApiError } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
});

const BENUTZER = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "pruefer",
  anzeigename: "Prüfer",
  rechte: { geraete: "verwalter" },
};

function antwort(koerper: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(koerper), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function abfangen(ergebnis: Response) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(ergebnis);
}

describe("anmelden", () => {
  it("schickt Name und Passwort und gibt den Benutzer zurück", async () => {
    const fetchSpy = abfangen(antwort(BENUTZER));

    await expect(anmelden("pruefer", "geheim-und-lang")).resolves.toMatchObject({
      name: "pruefer",
    });

    const [pfad, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(pfad).toContain("/auth/anmelden");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(
      JSON.stringify({ name: "pruefer", passwort: "geheim-und-lang" }),
    );
  });

  it("schickt das Sitzungscookie mit", async () => {
    // Ohne credentials kommt das httponly-Cookie nie beim Gateway an.
    const fetchSpy = abfangen(antwort(BENUTZER));

    await anmelden("pruefer", "geheim-und-lang");

    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("include");
  });

  it("nimmt die Meldung aus problem+json, nicht den Statuscode", async () => {
    abfangen(antwort({ title: "Anmeldung fehlgeschlagen", detail: "Stimmt nicht" }, 401));

    await expect(anmelden("pruefer", "falsch")).rejects.toThrow("Stimmt nicht");
  });

  it("fällt auf den Statuscode zurück, wenn kein Körper kommt", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("kein json", { status: 502 }),
    );

    await expect(anmelden("pruefer", "egal")).rejects.toThrow("Fehler 502");
  });

  it("wirft einen ApiError mit dem Status", async () => {
    abfangen(antwort({ detail: "Stimmt nicht" }, 401));

    await expect(anmelden("pruefer", "falsch")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
    });
    expect.assertions(1);
  });
});

describe("abmelden", () => {
  it("kommt mit 204 ohne Körper zurecht", async () => {
    abfangen(new Response(null, { status: 204 }));

    await expect(abmelden()).resolves.toBeUndefined();
  });
});

describe("holeIch", () => {
  it("gibt den angemeldeten Benutzer zurück", async () => {
    abfangen(antwort(BENUTZER));

    await expect(holeIch()).resolves.toMatchObject({ name: "pruefer" });
  });

  it("liefert null statt eines Fehlers, wenn niemand angemeldet ist", async () => {
    // 401 ist hier die Antwort auf die Frage, nicht ein Fehler.
    abfangen(new Response(null, { status: 401 }));

    await expect(holeIch()).resolves.toBeNull();
  });

  it("wirft bei allem anderen", async () => {
    // Ein abgestürztes Gateway soll nicht wie "nicht angemeldet" aussehen.
    abfangen(new Response(null, { status: 503 }));

    await expect(holeIch()).rejects.toBeInstanceOf(ApiError);
  });
});
