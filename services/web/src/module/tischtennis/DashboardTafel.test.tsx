import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { DashboardTafel } from "./DashboardTafel";
import { dashboard, spiel, tabelle, turnier } from "./testdaten";

/* Das Modul wird ersetzt, nicht bespitzelt: ein vi.spyOn ueber die
   Modulgrenze greift unter der Abdeckungs-Instrumentierung nicht mehr, und
   dann wird aus "melden wurde nicht gerufen" eine Zusage, die immer haelt.
   Alles ausser melden bleibt echt - die Glocke im localStorage wird weiter
   mit der richtigen Funktion geprueft. */
const { meldeSpion } = vi.hoisted(() => ({ meldeSpion: vi.fn() }));
vi.mock("./glocke", async (original) => {
  const echt = await original<typeof import("./glocke")>();
  return { ...echt, melden: meldeSpion };
});

beforeEach(() => {
  window.localStorage.clear();
  meldeSpion.mockClear();
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

  it("nennt die nächsten Spiele an ihrem Tisch", async () => {
    /* Die Warteschlange steht am Tisch, nicht in einem zweiten Abschnitt
       darunter. Bei einem Tisch sagten beide genau dasselbe - und die
       Dopplung kostete einen halben Bildschirm. */
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({
        tische: [{ tisch: 1, laeuft: null, danach: [spiel({ id: "s2", nummer: 2 })] }],
      }),
    );

    render(<DashboardTafel />);

    const tische = within(await screen.findByRole("region", { name: "An den Tischen" }));
    expect(tische.getByText(/Anna gegen Bernd/)).toBeInTheDocument();
    expect(tische.getByText("Tisch 1")).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Als nächstes" }),
    ).not.toBeInTheDocument();
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
    /* Und die Gruppentabelle ist weg: steht das Raster, ist sie
       Vergangenheit. Wer im Viertelfinale steht, interessiert nicht mehr,
       mit welchem Punktestand er dorthin kam. */
    expect(screen.queryByRole("heading", { name: "Gruppe A" })).not.toBeInTheDocument();
  });

  it("zeigt die Tabelle, solange noch kein Raster steht", async () => {
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({ tabellen: [tabelle()], spiele: [spiel()] }),
    );

    render(<DashboardTafel />);

    expect(await screen.findByRole("heading", { name: "Gruppe A" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "KO-Raster" })).not.toBeInTheDocument();
  });

  it("zeigt die Verliererrunde als eigenen Strang", async () => {
    /* Sieger- und Verliererzweig zaehlen ihre Runden getrennt. In einer
       Spaltenreihe stuende das Halbfinale neben der dritten
       Verliererrunde, als waeren sie derselbe Weg. */
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({
        spiele: [
          spiel({ id: "k1", phase: "ko", bezeichnung: "Sieger-Finale", gruppe: null }),
          spiel({
            id: "v1",
            phase: "ko_verlierer",
            bezeichnung: "Verlierer-Runde 1",
            gruppe: null,
          }),
          spiel({ id: "f1", phase: "ko_finale", bezeichnung: "Endspiel", gruppe: null }),
        ],
      }),
    );

    render(<DashboardTafel />);

    expect(
      await screen.findByRole("group", { name: "Verliererrunde" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Endspiel" })).toBeInTheDocument();
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

  it("meldet sich, wenn der eigene Name gleich dran ist", async () => {
    /* Das war vorher ein Warnband oben auf der Seite. Es ist weg: die
       Warteschlange sagt dasselbe, und das Band stand bei jedem Abruf
       ueber dem, was gerade passiert. Die Zusage ist die Meldung - sie
       erreicht einen auch dann, wenn man gerade nicht hinsieht. */
    window.localStorage.setItem("homepi.tischtennis.glocke", JSON.stringify(["p1"]));
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({
        naechste: [spiel({ gleich_dran: true })],
        tische: [{ tisch: 1, laeuft: null, danach: [spiel({ gleich_dran: true })] }],
      }),
    );

    render(<DashboardTafel />);

    const tische = within(await screen.findByRole("region", { name: "An den Tischen" }));
    expect(tische.getByText("gleich dran")).toBeInTheDocument();
    expect(tische.getByLabelText("Glocke an")).toBeInTheDocument();
    expect(meldeSpion).toHaveBeenCalled();
  });

  it("meldet sich nicht bei fremden Spielen", async () => {
    window.localStorage.setItem("homepi.tischtennis.glocke", JSON.stringify(["p9"]));
    vi.spyOn(api, "ladeDashboard").mockResolvedValue(
      dashboard({
        naechste: [spiel({ gleich_dran: true })],
        tische: [{ tisch: 1, laeuft: null, danach: [spiel({ gleich_dran: true })] }],
      }),
    );

    render(<DashboardTafel />);

    await screen.findByRole("region", { name: "An den Tischen" });
    expect(meldeSpion).not.toHaveBeenCalled();
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

    /* Zugeklappt, weil Nachschlagewerk: offen stand es zwischen dem, was
       gerade passiert, und dem Spielplan. Aufgeklappt steht es da. */
    const griff = await screen.findByText(/Zuletzt gespielt/);
    await userEvent.click(griff);

    const klappe = griff.closest("details");
    expect(klappe).not.toBeNull();
    const letzte = within(klappe as HTMLElement);
    expect(letzte.getByText("Anna")).toBeInTheDocument();
    expect(letzte.getByText("Bernd")).toBeInTheDocument();
  });
});
