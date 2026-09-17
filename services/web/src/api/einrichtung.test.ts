import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./client";
import { einrichten, holeStand } from "./einrichtung";

afterEach(() => {
  vi.restoreAllMocks();
});

const BENUTZER = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "aaron",
  anzeigename: "Aaron",
  rechte: { verwaltung: "verwalter" },
};

function antwort(koerper: unknown, status = 200): Response {
  return new Response(JSON.stringify(koerper), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function abfangen(ergebnis: Response) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(ergebnis);
}

describe("holeStand", () => {
  it("gibt zurück, ob eingerichtet werden muss", async () => {
    abfangen(antwort({ noetig: true }));

    await expect(holeStand()).resolves.toEqual({ noetig: true });
  });

  it("fragt /auth/einrichtung", async () => {
    const fetchSpy = abfangen(antwort({ noetig: false }));

    await holeStand();

    expect(fetchSpy.mock.calls[0]?.[0]).toContain("/auth/einrichtung");
  });
});

describe("einrichten", () => {
  it("schickt Token, Name und Passwort", async () => {
    const fetchSpy = abfangen(antwort(BENUTZER));

    await einrichten({ token: "tok", name: "aaron", passwort: "langes-passwort" });

    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(
      JSON.stringify({ token: "tok", name: "aaron", passwort: "langes-passwort" }),
    );
  });

  it("schickt das Cookie mit", async () => {
    // Der erste Verwalter wird gleich angemeldet - ohne credentials käme das
    // Set-Cookie zwar an, würde aber nicht übernommen.
    const fetchSpy = abfangen(antwort(BENUTZER));

    await einrichten({ token: "tok", name: "aaron", passwort: "langes-passwort" });

    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("include");
  });

  it("nimmt die Meldung aus problem+json", async () => {
    abfangen(antwort({ detail: "Das Einrichtungstoken stimmt nicht" }, 401));

    await expect(
      einrichten({ token: "falsch", name: "aaron", passwort: "langes-passwort" }),
    ).rejects.toThrow("Einrichtungstoken stimmt nicht");
  });

  it("wirft einen ApiError mit dem Status", async () => {
    abfangen(antwort({ detail: "schon eingerichtet" }, 409));

    await expect(
      einrichten({ token: "tok", name: "aaron", passwort: "langes-passwort" }),
    ).rejects.toMatchObject({ name: "ApiError", status: 409 });
  });

  it("fällt auf den Statuscode zurück, wenn kein Körper kommt", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("kein json", { status: 502 }),
    );

    await expect(
      einrichten({ token: "tok", name: "aaron", passwort: "langes-passwort" }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
