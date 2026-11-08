import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { DashboardTafel } from "./DashboardTafel";

function turnier(rest: Partial<api.Turnier> = {}): api.Turnier {
  return {
    id: "t1",
    name: "Betriebsturnier",
    modus: "gruppen_ko",
    zustand: "laufend",
    tische: 2,
    best_of: 5,
    punkte_bis: 11,
    minuten_pro_spiel: 12,
    anzahl_gruppen: 2,
    weiter_pro_gruppe: 2,
    runden: 4,
    saat: 7,
    runde_angesetzt: 1,
    ko_steht: false,
    anzahl_teilnehmer: 4,
    anzahl_spiele: 6,
    offene_spiele: 5,
    ...rest,
  };
}

function spiel(rest: Partial<api.Spiel> = {}): api.Spiel {
  return {
    id: "s1",
    nummer: 1,
    phase: "gruppe",
    runde: 1,
    bezeichnung: "Gruppe A, Runde 1",
    gruppe: "Gruppe A",
    heim_id: "p1",
    gast_id: "p2",
    heim: "Anna",
    gast: "Bernd",
    heim_herkunft: null,
    gast_herkunft: null,
    zustand: "geplant",
    tisch: 1,
    saetze: [],
    saetze_heim: 0,
    saetze_gast: 0,
    sieger_id: null,
    freilos: false,
    begonnen_am: null,
    beendet_am: null,
    erwartet_ab: "2026-11-07T18:12:00Z",
    gleich_dran: false,
    ...rest,
  };
}

function dashboard(rest: Partial<api.Dashboard> = {}): api.Dashboard {
  return {
    turnier: turnier(),
    stand: "2026-11-07T18:00:00Z",
    tische: [{ tisch: 1, laeuft: null, danach: [] }],
    naechste: [],
    letzte: [],
    tabellen: [],
    teilnehmer: [
      { id: "p1", name: "Anna", notiz: "", gruppe: "Gruppe A", freilose: 0 },
      { id: "p2", name: "Bernd", notiz: "", gruppe: "Gruppe A", freilose: 0 },
    ],
    fertig: false,
    ...rest,
  };
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("Dashboard", () => {
  it("zeigt zuerst einen Ladehinweis", () => {
    vi.spyOn(api, "ladeDashboard").mockReturnValue(new Promise(() => {}));

    render(<DashboardTafel />);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("sagt im Erstzustand, worauf man wartet", async () => {
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(dashboard({ turnier: null }));

    render(<DashboardTafel />);

    expect(await screen.findByText(/läuft kein Turnier/)).toBeInTheDocument();
  });

  it("zeigt das laufende Spiel mit Satzstand am Tisch", async () => {
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({
        tische: [
          {
            tisch: 1,
            laeuft: spiel({ zustand: "laeuft", saetze_heim: 2, saetze_gast: 1 }),
            danach: [],
          },
        ],
      }),
    );

    render(<DashboardTafel />);

    // Im Tischbereich, nicht bei den Glockenknoepfen - dort steht derselbe
    // Name noch einmal.
    const tische = within(await screen.findByRole("region", { name: "An den Tischen" }));
    expect(tische.getByText("Anna")).toBeInTheDocument();
    expect(tische.getByText("2:1")).toBeInTheDocument();
    expect(tische.getByText("läuft")).toBeInTheDocument();
  });

  it("nennt die nächsten Spiele mit Zeit und Tisch", async () => {
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({ naechste: [spiel({ id: "s2", nummer: 2 })] }),
    );

    render(<DashboardTafel />);

    const naechste = within(await screen.findByRole("region", { name: "Als nächstes" }));
    expect(naechste.getByText(/Anna gegen Bernd/)).toBeInTheDocument();
    expect(naechste.getByText(/Tisch 1/)).toBeInTheDocument();
  });

  it("merkt sich die Glocke im Gerät", async () => {
    /* Nicht auf dem Server: niemand soll ihm sagen muessen, welches Handy
       zu welchem Kollegen gehoert. */
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(dashboard());
    render(<DashboardTafel />);

    await userEvent.click(await screen.findByRole("button", { name: "Anna" }));

    expect(window.localStorage.getItem("homepi.tischtennis.glocke")).toContain("p1");
    expect(screen.getByRole("button", { name: /Anna/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("warnt sichtbar, wenn der eigene Name gleich dran ist", async () => {
    window.localStorage.setItem("homepi.tischtennis.glocke", JSON.stringify(["p1"]));
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({ naechste: [spiel({ gleich_dran: true })] }),
    );

    render(<DashboardTafel />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Gleich dran: Anna gegen Bernd an Tisch 1",
    );
  });

  it("warnt nicht bei fremden Spielen", async () => {
    window.localStorage.setItem("homepi.tischtennis.glocke", JSON.stringify(["p9"]));
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({ naechste: [spiel({ gleich_dran: true })] }),
    );

    render(<DashboardTafel />);

    await screen.findByRole("heading", { name: "Als nächstes" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("meldet einen Fehler beim ersten Abruf", async () => {
    vi.spyOn(api, "ladeDashboard").mockRejectedValue(new ApiError("Gateway weg", 503));

    render(<DashboardTafel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway weg");
  });

  it("zeigt die letzten Ergebnisse", async () => {
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({
        letzte: [
          spiel({
            id: "s0",
            zustand: "beendet",
            saetze_heim: 3,
            saetze_gast: 0,
            sieger_id: "p1",
          }),
        ],
      }),
    );

    render(<DashboardTafel />);

    expect(await screen.findByText("3:0")).toBeInTheDocument();
  });
});
