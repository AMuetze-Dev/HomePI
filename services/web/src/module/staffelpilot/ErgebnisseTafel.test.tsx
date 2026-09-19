import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { ErgebnisseTafel } from "./ErgebnisseTafel";
import * as api from "./api";

function staffel(rest: Partial<api.Staffel> = {}): api.Staffel {
  return {
    id: "s1",
    name: "Stadtliga C",
    altersklasse: "maenner",
    spielklasse: "3.Kreisliga (C)",
    saison: "26/27",
    aktiv: true,
    ...rest,
  };
}

function werte(rest: Partial<api.Auswertung> = {}): api.Auswertung {
  return {
    befunde: 0,
    offen: 0,
    spiele: 0,
    abgehakt: 0,
    vorgaenge: 0,
    nach_schwere: [],
    nach_regel: [],
    nach_mannschaft: [],
    nach_monat: [],
    ...rest,
  };
}

const GEFUELLT = werte({
  befunde: 5,
  offen: 2,
  spiele: 3,
  abgehakt: 1,
  nach_schwere: [
    { name: "kritisch", anzahl: 1, offen: 1 },
    { name: "warnung", anzahl: 0, offen: 0 },
    { name: "hinweis", anzahl: 4, offen: 1 },
  ],
  nach_regel: [{ name: "spielerfoto_fehlt", anzahl: 4, offen: 1 }],
  nach_mannschaft: [{ name: "SG Gittersee", anzahl: 3, offen: 2 }],
  nach_monat: [{ name: "2026-09", anzahl: 5, offen: 2 }],
});

beforeEach(() => {
  vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Die Ergebnisse", () => {
  it("zeigt die Bilanz der Saison", async () => {
    vi.spyOn(api, "ladeErgebnisse").mockResolvedValue(GEFUELLT);
    render(<ErgebnisseTafel staffeln={[staffel()]} />);

    const bilanz = await screen.findByRole("list", { name: "Bilanz" });
    expect(within(bilanz).getByText("Spiele")).toBeInTheDocument();
    expect(within(bilanz).getByText("noch offen")).toBeInTheDocument();
  });

  it("sagt beim leeren Stand, woher die Zahlen kämen", async () => {
    vi.spyOn(api, "ladeErgebnisse").mockResolvedValue(werte());
    render(<ErgebnisseTafel staffeln={[staffel()]} />);

    expect(await screen.findByText("Noch nichts ausgewertet")).toBeInTheDocument();
  });

  it("gruppiert nach Schwere, Regel, Mannschaft und Monat", async () => {
    vi.spyOn(api, "ladeErgebnisse").mockResolvedValue(GEFUELLT);
    render(<ErgebnisseTafel staffeln={[staffel()]} />);

    expect(await screen.findByRole("list", { name: "Nach Schwere" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Nach Regel" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Nach Mannschaft" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Im Verlauf" })).toBeInTheDocument();
  });

  it("zeigt auch die Schwere mit null", async () => {
    // „Keine Warnungen" ist eine Aussage. Eine fehlende Zeile ist keine.
    vi.spyOn(api, "ladeErgebnisse").mockResolvedValue(GEFUELLT);
    render(<ErgebnisseTafel staffeln={[staffel()]} />);

    const gruppe = await screen.findByRole("list", { name: "Nach Schwere" });
    const warnung = within(gruppe).getByText("Warnung").closest("li")!;
    expect(within(warnung).getByText("0")).toBeInTheDocument();
  });

  it("nennt neben der Zahl, wie viel davon offen ist", async () => {
    vi.spyOn(api, "ladeErgebnisse").mockResolvedValue(GEFUELLT);
    render(<ErgebnisseTafel staffeln={[staffel()]} />);

    const gruppe = await screen.findByRole("list", { name: "Nach Mannschaft" });
    expect(within(gruppe).getByText(/\(2 offen\)/)).toBeInTheDocument();
  });

  it("schreibt den Monat aus", async () => {
    // "2026-09" liest niemand als September.
    vi.spyOn(api, "ladeErgebnisse").mockResolvedValue(GEFUELLT);
    render(<ErgebnisseTafel staffeln={[staffel()]} />);

    const verlauf = await screen.findByRole("list", { name: "Im Verlauf" });
    expect(within(verlauf).getByText("September 2026")).toBeInTheDocument();
  });

  it("filtert nach Staffel", async () => {
    const laden = vi.spyOn(api, "ladeErgebnisse").mockResolvedValue(werte());
    render(<ErgebnisseTafel staffeln={[staffel(), staffel({ id: "s2", name: "D" })]} />);
    await screen.findByText("Noch nichts ausgewertet");

    await userEvent.selectOptions(screen.getByLabelText("Staffel"), "s2");

    await waitFor(() => expect(laden).toHaveBeenLastCalledWith("s2", expect.anything()));
  });

  it("zeigt einen Ladefehler statt leerer Zahlen", async () => {
    vi.spyOn(api, "ladeErgebnisse").mockRejectedValue(new ApiError("kein Zugriff", 403));
    render(<ErgebnisseTafel staffeln={[staffel()]} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });
});
