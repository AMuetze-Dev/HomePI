import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Benutzer } from "../../api/anmeldung";
import { ApiError } from "../../api/client";
import { TESTBENUTZER, mitAnmeldung } from "../../testhilfen";
import * as api from "./api";
import { TischtennisSeite } from "./TischtennisSeite";

const LEITER: Benutzer = { ...TESTBENUTZER, rechte: { tischtennis: "verwalter" } };
const ZUSCHAUER: Benutzer = { ...TESTBENUTZER, rechte: {} };

export function turnier(rest: Partial<api.Turnier> = {}): api.Turnier {
  return {
    id: "t1",
    name: "Betriebsturnier",
    modus: "gruppen_ko",
    zustand: "planung",
    tische: 2,
    best_of: 5,
    punkte_bis: 11,
    minuten_pro_spiel: 12,
    anzahl_gruppen: 2,
    weiter_pro_gruppe: 2,
    runden: 4,
    saat: null,
    runde_angesetzt: 0,
    ko_steht: false,
    anzahl_teilnehmer: 0,
    anzahl_spiele: 0,
    offene_spiele: 0,
    ...rest,
  };
}

function dashboard(rest: Partial<api.Dashboard> = {}): api.Dashboard {
  return {
    turnier: null,
    stand: "2026-11-07T18:00:00Z",
    tische: [],
    naechste: [],
    letzte: [],
    tabellen: [],
    teilnehmer: [],
    fertig: false,
    ...rest,
  };
}

beforeEach(() => {
  vi.spyOn(api, "ladeTurniere").mockResolvedValue([turnier()]);
  vi.spyOn(api, "ladeTurnier").mockResolvedValue(turnier());
  vi.spyOn(api, "ladeTeilnehmer").mockResolvedValue([]);
  vi.spyOn(api, "ladeSpiele").mockResolvedValue([]);
  vi.spyOn(api, "ladeTabellen").mockResolvedValue([]);
  vi.spyOn(api, "ladeDashboard").mockResolvedValue(dashboard());
  vi.spyOn(api, "legeTeilnehmerAn").mockResolvedValue({
    id: "p1",
    name: "Anna",
    notiz: "",
    gruppe: null,
    freilose: 0,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Tischtennisturnier", () => {
  it("zeigt zuerst einen Ladehinweis", () => {
    vi.spyOn(api, "ladeTurniere").mockReturnValue(new Promise(() => {}));

    render(mitAnmeldung(<TischtennisSeite unterseite="teilnehmer" />, LEITER));

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });

  it("meldet, wenn das Gateway nicht erreichbar ist", async () => {
    vi.spyOn(api, "ladeTurniere").mockRejectedValue(new ApiError("Gateway weg", 503));

    render(mitAnmeldung(<TischtennisSeite unterseite="teilnehmer" />, LEITER));

    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway weg");
  });

  it("führt den Verwalter ohne Turnier zum Anlegen", async () => {
    vi.spyOn(api, "ladeTurniere").mockResolvedValue([]);

    render(mitAnmeldung(<TischtennisSeite unterseite="einstellungen" />, LEITER));

    expect(await screen.findByLabelText("Name des Turniers")).toBeInTheDocument();
  });

  it("zeigt die Teilnehmerliste mit dem Turniernamen", async () => {
    vi.spyOn(api, "ladeTeilnehmer").mockResolvedValue([
      { id: "p1", name: "Anna", notiz: "Technik", gruppe: null, freilose: 0 },
    ]);

    render(mitAnmeldung(<TischtennisSeite unterseite="teilnehmer" />, LEITER));

    expect(await screen.findByText("Betriebsturnier")).toBeInTheDocument();
    expect(screen.getByText("Anna")).toBeInTheDocument();
  });

  it("schickt einen Zuschauer zum Dashboard statt ihn abzuweisen", async () => {
    /* Der haeufigste Aufrufer dieses Artefakts hat kein Recht darauf - er
       soll nicht vor einer Fehlermeldung landen, sondern vor dem Hinweis,
       wo der Stand steht. */
    render(mitAnmeldung(<TischtennisSeite unterseite="spielplan" />, ZUSCHAUER));

    expect(await screen.findByText(/Turnierleitung/)).toBeInTheDocument();
  });

  it("zeigt dem Zuschauer das Dashboard ohne Anmeldung", async () => {
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({ turnier: turnier({ zustand: "laufend" }) }),
    );

    render(mitAnmeldung(<TischtennisSeite unterseite="dashboard" />, null));

    expect(
      await screen.findByRole("heading", { name: "An den Tischen" }),
    ).toBeInTheDocument();
  });

  it("holt für das Dashboard nur den einen Abruf", async () => {
    /* Ein Besucher soll nicht auf Spielplan, Tabellen und Teilnehmer warten,
       die er auf dieser Flaeche gar nicht sieht. */
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({ turnier: turnier({ zustand: "laufend" }) }),
    );

    render(mitAnmeldung(<TischtennisSeite unterseite="dashboard" />, null));

    await screen.findByRole("heading", { name: "Glocke" });
    expect(api.ladeSpiele).not.toHaveBeenCalled();
    expect(api.ladeTabellen).not.toHaveBeenCalled();
  });
});
