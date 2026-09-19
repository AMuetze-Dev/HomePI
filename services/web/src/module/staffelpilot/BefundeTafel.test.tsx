import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { BefundeTafel } from "./BefundeTafel";
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

function zeile(rest: Partial<api.BefundZeile> = {}): api.BefundZeile {
  return {
    id: "b1",
    spiel_id: "m1",
    staffel_id: "s1",
    dfbnet_id: "M-1",
    datum: "2026-09-13",
    heim: "SG Gittersee",
    gast: "SV Fortschritt",
    regel: "rote_karte",
    schwere: "kritisch",
    titel: "Feldverweis auf Dauer",
    person: "Max Müller",
    mannschaft: "SG Gittersee",
    entscheidung: "offen",
    grund: "",
    weg: "sportgericht",
    vorgang_id: null,
    ...rest,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Alle Befunde", () => {
  it("sagt beim leeren Stand, woher sie kommen", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
    render(<BefundeTafel staffeln={[staffel()]} />);

    expect(await screen.findByText("Keine Befunde")).toBeInTheDocument();
  });

  it("trägt das Spiel an jeder Zeile", async () => {
    // Ohne das Spiel an der Zeile ist ein Befund nicht zuzuordnen.
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([zeile()]);
    render(<BefundeTafel staffeln={[staffel()]} />);

    const liste = await screen.findByRole("list", { name: "Befunde" });
    expect(within(liste).getByText(/SG Gittersee – SV Fortschritt/)).toBeInTheDocument();
    expect(within(liste).getByText(/13\.09\.2026/)).toBeInTheDocument();
    expect(within(liste).getByText("Feldverweis auf Dauer")).toBeInTheDocument();
  });

  it("zählt, wie viele es sind", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([zeile(), zeile({ id: "b2" })]);
    render(<BefundeTafel staffeln={[staffel()]} />);

    expect(await screen.findByText("2 Befunde")).toBeInTheDocument();
  });

  it("filtert auf offene", async () => {
    const laden = vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
    render(<BefundeTafel staffeln={[staffel()]} />);
    await screen.findByText("Keine Befunde");

    await userEvent.click(screen.getByRole("button", { name: "Nur offene" }));

    await waitFor(() =>
      expect(laden).toHaveBeenLastCalledWith(
        { staffelId: undefined, nurOffen: true },
        expect.anything(),
      ),
    );
  });

  it("sagt beim leeren Filter etwas anderes", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
    render(<BefundeTafel staffeln={[staffel()]} />);
    await screen.findByText("Keine Befunde");

    await userEvent.click(screen.getByRole("button", { name: "Nur offene" }));

    expect(await screen.findByText("Nichts offen")).toBeInTheDocument();
  });

  it("filtert nach Staffel", async () => {
    const laden = vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
    render(
      <BefundeTafel staffeln={[staffel(), staffel({ id: "s2", name: "Stadtliga D" })]} />,
    );
    await screen.findByText("Keine Befunde");

    await userEvent.selectOptions(screen.getByLabelText("Staffel"), "s2");

    await waitFor(() =>
      expect(laden).toHaveBeenLastCalledWith(
        { staffelId: "s2", nurOffen: false },
        expect.anything(),
      ),
    );
  });

  it("zeigt die Entscheidung mit ihrem Grund", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([
      zeile({ entscheidung: "verworfen", grund: "Spieler war spielberechtigt" }),
    ]);
    render(<BefundeTafel staffeln={[staffel()]} />);

    const liste = await screen.findByRole("list", { name: "Befunde" });
    expect(within(liste).getByText("verworfen")).toBeInTheDocument();
    expect(within(liste).getByText("Spieler war spielberechtigt")).toBeInTheDocument();
  });

  it("markiert eine Zeile, zu der ein Vorgang gehört", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([zeile({ vorgang_id: "v1" })]);
    render(<BefundeTafel staffeln={[staffel()]} />);

    const liste = await screen.findByRole("list", { name: "Befunde" });
    expect(within(liste).getByText("Vorgang")).toBeInTheDocument();
  });

  it("zeigt einen Ladefehler statt einer leeren Liste", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockRejectedValue(new ApiError("kein Zugriff", 403));
    render(<BefundeTafel staffeln={[staffel()]} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });
});
