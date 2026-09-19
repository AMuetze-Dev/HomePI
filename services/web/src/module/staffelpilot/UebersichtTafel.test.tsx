import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { UebersichtTafel } from "./UebersichtTafel";
import * as api from "./api";

function uebersicht(rest: Partial<api.Zusammenfassung> = {}): api.Zusammenfassung {
  return {
    spiele: 3,
    offen: 2,
    abgehakt: 1,
    befunde_offen: 4,
    befunde_kritisch: 1,
    staffeln_aktiv: 1,
    vorgaenge_entwurf: 0,
    ...rest,
  };
}

function zeile(rest: Partial<api.SpielZeile> = {}): api.SpielZeile {
  return {
    id: "m1",
    dfbnet_id: "M-1",
    datum: "2026-09-13",
    heim: "SG Gittersee",
    gast: "SV Fortschritt",
    ergebnis: "2 : 1",
    abgehakt: false,
    offene_befunde: 1,
    kritische_befunde: 1,
    faellig: true,
    ...rest,
  };
}

function stand(rest: Partial<api.UebertragungStand> = {}): api.UebertragungStand {
  return {
    pausiert: true,
    offen: 0,
    laeuft: 0,
    fertig: 0,
    fehler: 0,
    fehlerhafte: [],
    ...rest,
  };
}

beforeEach(() => {
  vi.spyOn(api, "ladeZusammenfassung").mockResolvedValue(uebersicht());
  vi.spyOn(api, "ladeWarteschlange").mockResolvedValue([zeile()]);
  vi.spyOn(api, "ladeOffenenAuftrag").mockResolvedValue(null);
  vi.spyOn(api, "ladeUebertragung").mockResolvedValue(stand());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Die Übersicht", () => {
  it("zeigt die Zahlen, um die es geht", async () => {
    render(<UebersichtTafel onWechsel={() => {}} />);

    const zahlen = await screen.findByRole("list", { name: "Überblick" });
    expect(within(zahlen).getByText("zu prüfen")).toBeInTheDocument();
    expect(within(zahlen).getByText("kritische Befunde")).toBeInTheDocument();
    expect(within(zahlen).getByText("Entwürfe")).toBeInTheDocument();
  });

  it("führt von jeder Zahl dorthin, wo man etwas damit tut", async () => {
    // Eine Zahl, die nur dasteht, lässt den Leser die Navigation suchen.
    const wechsel = vi.fn();
    render(<UebersichtTafel onWechsel={wechsel} />);

    const zahlen = await screen.findByRole("list", { name: "Überblick" });
    await userEvent.click(within(zahlen).getByRole("button", { name: /zu prüfen/ }));

    expect(wechsel).toHaveBeenCalledWith("spiele");
  });

  it("fragt nur die fälligen Spiele ab", async () => {
    render(<UebersichtTafel onWechsel={() => {}} />);

    await waitFor(() =>
      expect(api.ladeWarteschlange).toHaveBeenCalledWith(
        undefined,
        expect.anything(),
        true,
      ),
    );
  });

  it("zeigt die nächsten Spiele", async () => {
    render(<UebersichtTafel onWechsel={() => {}} />);

    const liste = await screen.findByRole("list", { name: "Als Nächstes" });
    expect(within(liste).getByText("SG Gittersee – SV Fortschritt")).toBeInTheDocument();
  });

  it("lässt abgehakte Spiele weg", async () => {
    // Was erledigt ist, steht nicht unter "als Nächstes".
    vi.spyOn(api, "ladeWarteschlange").mockResolvedValue([zeile({ abgehakt: true })]);
    render(<UebersichtTafel onWechsel={() => {}} />);

    expect(await screen.findByText("Nichts fällig")).toBeInTheDocument();
  });

  it("sagt ohne Staffel, was zuerst zu tun ist", async () => {
    vi.spyOn(api, "ladeZusammenfassung").mockResolvedValue(
      uebersicht({ staffeln_aktiv: 0 }),
    );
    render(<UebersichtTafel onWechsel={() => {}} />);

    expect(await screen.findByText("Keine aktive Staffel")).toBeInTheDocument();
  });

  it("zeigt einen laufenden Auftrag mit seinem Schritt", async () => {
    vi.spyOn(api, "ladeOffenenAuftrag").mockResolvedValue({
      id: "a1",
      art: "pruflauf",
      staffel_id: null,
      zustand: "laeuft",
      schritt: "Prüfe M-1",
      fortschritt: 40,
      gepruefte: 3,
      befunde: 1,
      meldung: "",
      protokoll: [],
      gestartet_am: "2026-09-19T10:00:00Z",
      beendet_am: null,
      angelegt: "2026-09-19T10:00:00Z",
    });
    render(<UebersichtTafel onWechsel={() => {}} />);

    expect(await screen.findByText(/40 % · Prüfe M-1/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zum Prüflauf" })).toBeInTheDocument();
  });

  it("sagt es, wenn eine Übertragung festhängt", async () => {
    vi.spyOn(api, "ladeUebertragung").mockResolvedValue(stand({ fehler: 2 }));
    render(<UebersichtTafel onWechsel={() => {}} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/2 Übertragungen sind/);
  });

  it("schweigt, solange nichts festhängt", async () => {
    render(<UebersichtTafel onWechsel={() => {}} />);
    await screen.findByRole("list", { name: "Überblick" });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("zeigt einen Ladefehler statt leerer Zahlen", async () => {
    vi.spyOn(api, "ladeZusammenfassung").mockRejectedValue(
      new ApiError("kein Zugriff", 403),
    );
    render(<UebersichtTafel onWechsel={() => {}} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });
});
