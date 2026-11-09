import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { DashboardTafel } from "./DashboardTafel";
import { dashboard, spiel, tabelle, turnier } from "./testdaten";

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

  it("zeigt das laufende Spiel an seinem Tisch", async () => {
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({
        tische: [{ tisch: 1, laeuft: spiel({ zustand: "laeuft" }), danach: [] }],
      }),
    );

    render(<DashboardTafel />);

    const tische = within(await screen.findByRole("region", { name: "An den Tischen" }));
    expect(tische.getByText("Anna")).toBeInTheDocument();
    expect(tische.getByText("Bernd")).toBeInTheDocument();
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

  it("zeigt den Plan als Bild: Gruppen und Raster", async () => {
    /* Die Umstellung, um die es geht: der Plan ist eine Grafik und keine
       Liste aus achtzehn Zeilen. */
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({
        tabellen: [tabelle()],
        spiele: [
          spiel(),
          spiel({
            id: "k1",
            nummer: 7,
            phase: "ko",
            runde: 1,
            bezeichnung: "Endspiel",
            gruppe: null,
            heim: null,
            heim_id: null,
            heim_herkunft: "Sieger aus Spiel 3",
          }),
        ],
      }),
    );

    render(<DashboardTafel />);

    expect(await screen.findByRole("group", { name: "KO-Raster" })).toBeInTheDocument();
    expect(screen.getByText("Sieger aus Spiel 3")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Gruppe A" })).toBeInTheDocument();
  });

  it("merkt sich die Glocke im Gerät", async () => {
    /* Nicht auf dem Server: niemand soll ihm sagen müssen, welches Handy
       zu welchem Kollegen gehört. */
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

  it("hebt den Sieger in den letzten Ergebnissen hervor", async () => {
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({
        turnier: turnier({ zustand: "laufend" }),
        letzte: [spiel({ zustand: "beendet", sieger_id: "p1" })],
      }),
    );

    render(<DashboardTafel />);

    const letzte = within(
      await screen.findByRole("region", { name: "Zuletzt gespielt" }),
    );
    expect(letzte.getByText("Anna")).toBeInTheDocument();
    expect(letzte.getByText("Bernd")).toBeInTheDocument();
  });
});
