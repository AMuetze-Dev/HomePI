import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import {
  aendereStaffel,
  aendereVorgang,
  brichAuftragAb,
  fordereAuftragAn,
  entscheide,
  hakeAb,
  ladeSpiel,
  ladeStaffeln,
  ladeWarteschlange,
  ladeZusammenfassung,
  ladeAlleBefunde,
  ladeAuftrag,
  ladeAuftraege,
  ladeEinstellungen,
  ladeMannschaften,
  ladeOffenenAuftrag,
  ladeUebertragung,
  ladeZugang,
  ladeVorgaenge,
  legeStaffelAn,
  legeVorgangAn,
  loescheStaffel,
  loescheZugang,
  loeseHaken,
  nimmEntscheidungZurueck,
  setzeUebertragungPause,
  setzeVorgangZustand,
  speichereEinstellungen,
  speichereMannschaften,
  speichereZugang,
  verwerfeVorgang,
  wiederholeUebertragung,
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

describe("Einstellungen, Mannschaften und Vorgänge", () => {
  const werte = {
    staffelleiter: "Aaron Mütze",
    verband: "",
    absender: "",
    pruefzeitraum_tage: 30,
    frist_tage: 14,
  };

  it("lädt die Einstellungen", async () => {
    const holen = antworteMit(werte);

    await expect(ladeEinstellungen()).resolves.toEqual(werte);
    expect(holen.mock.calls[0]?.[0]).toContain("/staffelpilot/einstellungen");
  });

  it("schickt nur die geänderten Felder", async () => {
    // Ein ausgelassenes Feld bleibt im Backend stehen. Alles mitzuschicken
    // hiesse, einen alten Wert zurueckzuschreiben.
    const holen = antworteMit(werte);

    await speichereEinstellungen({ frist_tage: 21 });

    expect(holen.mock.calls[0]?.[1]).toMatchObject({
      method: "PUT",
      body: JSON.stringify({ frist_tage: 21 }),
    });
  });

  it("lädt die Mannschaften einer Staffel", async () => {
    const holen = antworteMit([]);

    await ladeMannschaften("s1");

    expect(holen.mock.calls[0]?.[0]).toContain("/staffelpilot/staffeln/s1/mannschaften");
  });

  it("schickt die Mannschaften als vollständige Meldung", async () => {
    const holen = antworteMit([]);

    await speichereMannschaften("s1", [
      { name: "SV Loschwitz 2", hoehere: ["SV Loschwitz"] },
    ]);

    expect(holen.mock.calls[0]?.[1]).toMatchObject({ method: "PUT" });
    expect(String(holen.mock.calls[0]?.[1]?.body)).toContain("SV Loschwitz");
  });

  it("filtert die Vorgänge nach Zustand", async () => {
    const holen = antworteMit([]);

    await ladeVorgaenge("entwurf");

    expect(holen.mock.calls[0]?.[0]).toContain("/vorgaenge?zustand=entwurf");
  });

  it("legt einen Vorgang am Befund an", async () => {
    const holen = antworteMit({});

    await legeVorgangAn("b1", { grund: "Tätlichkeit" });

    expect(holen.mock.calls[0]?.[0]).toContain("/befunde/b1/vorgang");
    expect(holen.mock.calls[0]?.[1]).toMatchObject({ method: "POST" });
  });

  it("ändert einen Vorgang mit PATCH", async () => {
    const holen = antworteMit({});

    await aendereVorgang("v1", { text: "Eigene Fassung." });

    expect(holen.mock.calls[0]?.[1]).toMatchObject({ method: "PATCH" });
  });

  it("stellt einen Vorgang weiter", async () => {
    const holen = antworteMit({});

    await setzeVorgangZustand("v1", "versandt");

    expect(holen.mock.calls[0]?.[0]).toContain("/vorgaenge/v1/zustand");
    expect(String(holen.mock.calls[0]?.[1]?.body)).toContain("versandt");
  });

  it("verwirft einen Vorgang und erwartet keinen Körper", async () => {
    antworteMit(null, 204);

    await expect(verwerfeVorgang("v1")).resolves.toBeUndefined();
  });

  it("gibt die Meldung des Backends weiter", async () => {
    antworteMit({ detail: "'frist_tage' muss zwischen 1 und 90 liegen" }, 422);

    await expect(speichereEinstellungen({ frist_tage: 0 })).rejects.toThrow(
      /zwischen 1 und 90/,
    );
  });

  it("schickt bei jedem Aufruf das Sitzungscookie mit", async () => {
    // Ohne `credentials` antwortet das Gateway mit 401, egal was sonst
    // stimmt - das Artefakt ist geschuetzt.
    const holen = antworteMit(werte);

    await ladeEinstellungen();

    expect(holen.mock.calls[0]?.[1]).toMatchObject({ credentials: "include" });
  });
});

describe("Staffeln, Befunde und Aufträge", () => {
  it("ändert nur die mitgeschickten Felder einer Staffel", async () => {
    const holen = antworteMit(staffel);

    await aendereStaffel("s1", { aktiv: false });

    expect(holen.mock.calls[0]?.[0]).toContain("/staffeln/s1");
    expect(holen.mock.calls[0]?.[1]).toMatchObject({
      method: "PATCH",
      body: JSON.stringify({ aktiv: false }),
    });
  });

  it("löscht eine Staffel und erwartet keinen Körper", async () => {
    antworteMit(null, 204);

    await expect(loescheStaffel("s1")).resolves.toBeUndefined();
  });

  it("nimmt eine Entscheidung mit DELETE zurück", async () => {
    // Kein eigener Pfad: es ist dieselbe Ressource, nur weg.
    const holen = antworteMit({});

    await nimmEntscheidungZurueck("b1");

    expect(holen.mock.calls[0]?.[0]).toContain("/befunde/b1/entscheidung");
    expect(holen.mock.calls[0]?.[1]).toMatchObject({ method: "DELETE" });
  });

  it("holt alle Befunde ohne Frage, wenn nichts gefiltert wird", async () => {
    const holen = antworteMit([]);

    await ladeAlleBefunde();

    expect(String(holen.mock.calls[0]?.[0])).toMatch(/\/befunde$/);
  });

  it("hängt beide Filter an", async () => {
    const holen = antworteMit([]);

    await ladeAlleBefunde({ staffelId: "s1", nurOffen: true });

    expect(holen.mock.calls[0]?.[0]).toContain("staffel_id=s1");
    expect(holen.mock.calls[0]?.[0]).toContain("nur_offen=true");
  });

  it("liest die Auftragsliste", async () => {
    const holen = antworteMit([]);

    await ladeAuftraege();

    expect(String(holen.mock.calls[0]?.[0])).toMatch(/\/auftraege$/);
  });

  it("liest den offenen Auftrag und verträgt null", async () => {
    // Die Oberflaeche fragt das im Takt ab; null ist ein Ergebnis, kein
    // Fehler.
    antworteMit(null);

    await expect(ladeOffenenAuftrag()).resolves.toBeNull();
  });

  it("liest einen einzelnen Auftrag", async () => {
    const holen = antworteMit({});

    await ladeAuftrag("a1");

    expect(holen.mock.calls[0]?.[0]).toContain("/auftraege/a1");
  });

  it("fordert einen Prüflauf an, ohne Staffel", async () => {
    const holen = antworteMit({});

    await fordereAuftragAn();

    expect(holen.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ art: "pruflauf", staffel_id: null }),
    });
  });

  it("fordert eine Initialisierung für eine Staffel an", async () => {
    const holen = antworteMit({});

    await fordereAuftragAn("initialisierung", "s1");

    expect(String(holen.mock.calls[0]?.[1]?.body)).toContain("initialisierung");
    expect(String(holen.mock.calls[0]?.[1]?.body)).toContain("s1");
  });

  it("bricht ab, indem es den Abschluss meldet", async () => {
    const holen = antworteMit({});

    await brichAuftragAb("a1");

    expect(holen.mock.calls[0]?.[0]).toContain("/auftraege/a1/abschluss");
    expect(String(holen.mock.calls[0]?.[1]?.body)).toContain("abgebrochen");
  });
});

describe("Übertragung und Zugang", () => {
  it("liest den Stand der Übertragung", async () => {
    const holen = antworteMit({});

    await ladeUebertragung();

    expect(String(holen.mock.calls[0]?.[0])).toMatch(/\/uebertragungen$/);
  });

  it("setzt die Pause", async () => {
    const holen = antworteMit({});

    await setzeUebertragungPause(false);

    expect(holen.mock.calls[0]?.[0]).toContain("/uebertragungen/pause");
    expect(String(holen.mock.calls[0]?.[1]?.body)).toContain("false");
  });

  it("wiederholt ohne Kennung alle gescheiterten", async () => {
    const holen = antworteMit({});

    await wiederholeUebertragung();

    expect(String(holen.mock.calls[0]?.[0])).toMatch(/wiederholen$/);
  });

  it("wiederholt mit Kennung nur eine", async () => {
    const holen = antworteMit({});

    await wiederholeUebertragung("u1");

    expect(holen.mock.calls[0]?.[0]).toContain("uebertragung_id=u1");
  });

  it("liest den Stand des Zugangs", async () => {
    const holen = antworteMit({});

    await ladeZugang();

    expect(String(holen.mock.calls[0]?.[0])).toMatch(/\/zugang$/);
  });

  it("hinterlegt den Zugang mit PUT und erwartet keinen Körper zurück", async () => {
    const holen = antworteMit(null, 204);

    await expect(speichereZugang("sl42", "geheim")).resolves.toBeUndefined();
    expect(holen.mock.calls[0]?.[1]).toMatchObject({ method: "PUT" });
  });

  it("entfernt den Zugang", async () => {
    const holen = antworteMit(null, 204);

    await loescheZugang();

    expect(holen.mock.calls[0]?.[1]).toMatchObject({ method: "DELETE" });
  });
});
