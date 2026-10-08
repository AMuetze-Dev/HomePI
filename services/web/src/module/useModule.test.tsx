import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import type { Benutzer } from "../api/anmeldung";
import { AnmeldungKontext, type Anmeldung } from "../anmeldung/kontext";
import { TESTBENUTZER } from "../testhilfen";
import { useModule } from "./useModule";

afterEach(() => {
  vi.restoreAllMocks();
});

function modul(id: string): client.ModulEintrag {
  return {
    id,
    titel: id,
    pfad: `/${id}`,
    beschreibung: "",
    icon: "",
    version: "1.0.0",
    status: "bereit",
    zugang: "geschuetzt",
  };
}

function anmeldung(benutzer: Benutzer, mussPasswortWechseln: boolean): Anmeldung {
  return {
    zustand: "angemeldet",
    mussPasswortWechseln,
    benutzer,
    anmelden: vi.fn(),
    abmelden: vi.fn(),
    uebernimm: vi.fn(),
    darf: () => true,
  };
}

function Anzeige() {
  const zustand = useModule();
  if (zustand.phase !== "fertig") return <p>{zustand.phase}</p>;
  return <p>{zustand.module.map((m) => m.id).join(",") || "leer"}</p>;
}

describe("Das geteilte Manifest", () => {
  it("holt es neu, sobald der Passwortwechsel erledigt ist", async () => {
    // Bis zum Wechsel behandelt das Backend das Konto beim Manifest wie einen
    // Besucher - es kommt also leer zurück. Danach sieht dasselbe Konto seine
    // Artefakte. Hängt der Zwischenspeicher nur an der Kennung, bleibt die
    // Übersicht nach dem Wechsel leer: dieselbe Kennung, alter Stand. Genau
    // daran sind die Oberflächentests gescheitert.
    const holen = vi
      .spyOn(client, "fetchModule")
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([modul("geraete")]);

    const benutzer = { ...TESTBENUTZER, passwort_wechseln: true };
    const { rerender } = render(
      <AnmeldungKontext.Provider value={anmeldung(benutzer, true)}>
        <Anzeige />
      </AnmeldungKontext.Provider>,
    );
    expect(await screen.findByText("leer")).toBeInTheDocument();

    rerender(
      <AnmeldungKontext.Provider
        value={anmeldung({ ...benutzer, passwort_wechseln: false }, false)}
      >
        <Anzeige />
      </AnmeldungKontext.Provider>,
    );

    expect(await screen.findByText("geraete")).toBeInTheDocument();
    expect(holen).toHaveBeenCalledTimes(2);
  });

  it("holt es neu, wenn sich die Rechte ändern", async () => {
    // Ein Verwalter vergibt ein Recht; beim nächsten Abruf von /auth/ich
    // kommt der Benutzer mit neuen Rechten zurück. Das Manifest ist genau eine
    // Funktion dieser Rechte - es muss mitgehen.
    const holen = vi
      .spyOn(client, "fetchModule")
      .mockResolvedValueOnce([modul("geraete")])
      .mockResolvedValueOnce([modul("geraete"), modul("staffelpilot")]);

    const { rerender } = render(
      <AnmeldungKontext.Provider value={anmeldung(TESTBENUTZER, false)}>
        <Anzeige />
      </AnmeldungKontext.Provider>,
    );
    expect(await screen.findByText("geraete")).toBeInTheDocument();

    const mehr = {
      ...TESTBENUTZER,
      rechte: { ...TESTBENUTZER.rechte, staffelpilot: "leser" as const },
    };
    rerender(
      <AnmeldungKontext.Provider value={anmeldung(mehr, false)}>
        <Anzeige />
      </AnmeldungKontext.Provider>,
    );

    expect(await screen.findByText("geraete,staffelpilot")).toBeInTheDocument();
    expect(holen).toHaveBeenCalledTimes(2);
  });

  it("holt es NICHT neu, wenn sich nur das Objekt ändert", async () => {
    // Jeder Abruf von /auth/ich liefert ein neues Benutzerobjekt mit gleichem
    // Inhalt. Hinge der Schlüssel am Objekt, käme bei jedem Seitenwechsel ein
    // zweiter Abruf - genau das sollte der Zwischenspeicher verhindern.
    const holen = vi.spyOn(client, "fetchModule").mockResolvedValue([modul("geraete")]);

    const { rerender } = render(
      <AnmeldungKontext.Provider value={anmeldung({ ...TESTBENUTZER }, false)}>
        <Anzeige />
      </AnmeldungKontext.Provider>,
    );
    expect(await screen.findByText("geraete")).toBeInTheDocument();

    rerender(
      <AnmeldungKontext.Provider
        value={anmeldung({ ...TESTBENUTZER, rechte: { ...TESTBENUTZER.rechte } }, false)}
      >
        <Anzeige />
      </AnmeldungKontext.Provider>,
    );

    await waitFor(() => expect(screen.getByText("geraete")).toBeInTheDocument());
    expect(holen).toHaveBeenCalledTimes(1);
  });
});
