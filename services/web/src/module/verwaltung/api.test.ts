import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import {
  entzieheRecht,
  ladeArtefakte,
  ladeKonten,
  legeKontoAn,
  loescheKonto,
  setzeAktiv,
  setzeAnzeigename,
  setzePasswort,
  setzeRecht,
} from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

const KONTO = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "gast",
  anzeigename: "Gast",
  aktiv: true,
  rechte: {},
  angelegt: null,
  verwalter: false,
  passwort_wechseln: false,
};

function antwort(koerper: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(koerper), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function abfangen(ergebnis = antwort(KONTO)) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(ergebnis);
}

function aufruf(spy: ReturnType<typeof abfangen>): [string, RequestInit] {
  return spy.mock.calls[0] as [string, RequestInit];
}

describe("Verwaltungs-API", () => {
  it("spricht unter /verwaltung und schickt das Cookie mit", async () => {
    const spy = abfangen(antwort([KONTO]));

    await ladeKonten();

    const [pfad, init] = aufruf(spy);
    expect(pfad).toContain("/verwaltung/benutzer");
    expect(init.credentials).toBe("include");
  });

  it("holt die Artefakte", async () => {
    const spy = abfangen(antwort([]));

    await ladeArtefakte();

    expect(aufruf(spy)[0]).toContain("/verwaltung/artefakte");
  });

  it("legt ein Konto an", async () => {
    const spy = abfangen(antwort(KONTO, 201));

    await legeKontoAn({ name: "gast" });

    const [, init] = aufruf(spy);
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "gast" }));
  });

  it("sperrt und entsperrt", async () => {
    const spy = abfangen();

    await setzeAktiv(KONTO.id, false);

    const [pfad, init] = aufruf(spy);
    expect(pfad).toContain(`/verwaltung/benutzer/${KONTO.id}`);
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ aktiv: false }));
  });

  it("setzt den Anzeigenamen", async () => {
    const spy = abfangen();

    await setzeAnzeigename(KONTO.id, "Gast im Haus");

    expect(aufruf(spy)[1].body).toBe(JSON.stringify({ anzeigename: "Gast im Haus" }));
  });

  it("laesst ein Startpasswort erzeugen und gibt es zurueck", async () => {
    const spy = abfangen(antwort({ startpasswort: "abcd-efgh-ijkl-mnop" }));

    const ergebnis = await setzePasswort(KONTO.id);

    const [pfad, init] = aufruf(spy);
    expect(pfad).toContain("/passwort");
    expect(init.method).toBe("PUT");
    expect(ergebnis.startpasswort).toBe("abcd-efgh-ijkl-mnop");
  });

  it("schickt dabei gar keinen Koerper", async () => {
    // Kein Feld, in das ein Verwalter ein Passwort schreiben koennte - hier
    // faengt die Regel an, und das Backend lehnt den Rest ab.
    const spy = abfangen(antwort({ startpasswort: "abcd-efgh-ijkl-mnop" }));

    await setzePasswort(KONTO.id);

    expect(aufruf(spy)[1].body).toBeUndefined();
  });

  it("löscht ein Konto", async () => {
    const spy = abfangen(new Response(null, { status: 204 }));

    await loescheKonto(KONTO.id);

    expect(aufruf(spy)[1].method).toBe("DELETE");
  });

  it("setzt ein Recht je Artefakt", async () => {
    const spy = abfangen();

    await setzeRecht(KONTO.id, "geraete", "nutzer");

    const [pfad, init] = aufruf(spy);
    expect(pfad).toContain(`/rechte/geraete`);
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify({ rolle: "nutzer" }));
  });

  it("entzieht ein Recht", async () => {
    const spy = abfangen();

    await entzieheRecht(KONTO.id, "geraete");

    expect(aufruf(spy)[1].method).toBe("DELETE");
  });

  it("nimmt die Meldung aus problem+json, nicht den Statuscode", async () => {
    // "Das geht nicht am eigenen Konto" sagt mehr als "HTTP 409".
    abfangen(antwort({ detail: "Löschen geht nicht am eigenen Konto." }, 409));

    await expect(loescheKonto(KONTO.id)).rejects.toThrow("eigenen Konto");
  });

  it("fällt auf den Statuscode zurück, wenn kein Körper kommt", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("kein json", { status: 502 }),
    );

    await expect(ladeKonten()).rejects.toBeInstanceOf(ApiError);
  });
});
