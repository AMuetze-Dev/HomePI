import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchHealth } from "./client";

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
