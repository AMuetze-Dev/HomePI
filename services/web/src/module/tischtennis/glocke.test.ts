import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  benachrichtigen,
  erlaubnisFragen,
  geweckte,
  laeuten,
  melden,
  merken,
  ruettele,
  tonVorbereiten,
  umschalten,
} from "./glocke";

const SCHLUESSEL = "homepi.tischtennis.glocke";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("Die Glocke im Gerät", () => {
  it("fängt leer an", () => {
    expect(geweckte()).toEqual([]);
  });

  it("merkt sich eine Auswahl über den Seitenaufruf hinaus", () => {
    merken(["p1", "p2"]);

    expect(geweckte()).toEqual(["p1", "p2"]);
  });

  it("schaltet an und wieder aus", () => {
    expect(umschalten([], "p1")).toEqual(["p1"]);
    expect(umschalten(["p1"], "p1")).toEqual([]);
    expect(geweckte()).toEqual([]);
  });

  it("überlebt kaputten Inhalt im Speicher", () => {
    /* Ein privates Fenster, eine alte Version, ein Fingerabdruck-Blocker:
       eine Seite, die daran scheitert, zeigt das Turnier nicht mehr an. */
    window.localStorage.setItem(SCHLUESSEL, "{kein json");

    expect(geweckte()).toEqual([]);
  });

  it("wirft nichts, wenn der Speicher gesperrt ist", () => {
    const gesperrt = () => {
      throw new Error("Website-Daten sind gesperrt");
    };
    vi.spyOn(window.localStorage, "getItem").mockImplementation(gesperrt);
    vi.spyOn(window.localStorage, "setItem").mockImplementation(gesperrt);

    expect(geweckte()).toEqual([]);
    expect(() => merken(["p1"])).not.toThrow();
  });

  it("verwirft Einträge, die keine Kennungen sind", () => {
    window.localStorage.setItem(SCHLUESSEL, JSON.stringify(["p1", 7, null]));

    expect(geweckte()).toEqual(["p1"]);
  });
});

describe("Melden", () => {
  it("bleibt still, wenn die Umgebung keinen Ton kann", () => {
    // jsdom hat kein AudioContext - das darf die Seite nicht aufhalten.
    expect(() => tonVorbereiten()).not.toThrow();
    expect(() => laeuten()).not.toThrow();
    expect(() => ruettele()).not.toThrow();
    expect(() => melden("Titel", "Text")).not.toThrow();
  });

  it("vibriert, wo das Gerät es kann", () => {
    const vibrieren = vi.fn();
    vi.stubGlobal("navigator", { ...window.navigator, vibrate: vibrieren });

    ruettele();

    expect(vibrieren).toHaveBeenCalled();
  });

  it("fragt nicht nach, wenn die Erlaubnis schon erteilt ist", async () => {
    const nachfrage = vi.fn();
    vi.stubGlobal("Notification", {
      permission: "granted",
      requestPermission: nachfrage,
    });

    await expect(erlaubnisFragen()).resolves.toBe(true);
    expect(nachfrage).not.toHaveBeenCalled();
  });

  it("fragt nicht erneut, wenn sie verweigert wurde", async () => {
    /* Eine zweite Nachfrage zeigt der Browser gar nicht mehr an - sie waere
       nur ein Versprechen, das die Seite nicht halten kann. */
    const nachfrage = vi.fn();
    vi.stubGlobal("Notification", { permission: "denied", requestPermission: nachfrage });

    await expect(erlaubnisFragen()).resolves.toBe(false);
    expect(nachfrage).not.toHaveBeenCalled();
  });

  it("fragt, wenn noch nichts entschieden ist", async () => {
    const nachfrage = vi.fn().mockResolvedValue("granted");
    vi.stubGlobal("Notification", {
      permission: "default",
      requestPermission: nachfrage,
    });

    await expect(erlaubnisFragen()).resolves.toBe(true);
    expect(nachfrage).toHaveBeenCalled();
  });

  it("benachrichtigt nur mit Erlaubnis", () => {
    const erzeugt = vi.fn();
    class Falsche {
      static permission = "denied";
      constructor(titel: string, rest: unknown) {
        erzeugt(titel, rest);
      }
    }
    vi.stubGlobal("Notification", Falsche);

    benachrichtigen("Gleich dran", "Anna gegen Bernd");

    expect(erzeugt).not.toHaveBeenCalled();
  });

  it("benachrichtigt mit Titel und Text", () => {
    const erzeugt = vi.fn();
    class Echte {
      static permission = "granted";
      constructor(titel: string, rest: { body?: string }) {
        erzeugt(titel, rest.body);
      }
    }
    vi.stubGlobal("Notification", Echte);

    benachrichtigen("Gleich dran", "Anna gegen Bernd");

    expect(erzeugt).toHaveBeenCalledWith("Gleich dran", "Anna gegen Bernd");
  });
});
