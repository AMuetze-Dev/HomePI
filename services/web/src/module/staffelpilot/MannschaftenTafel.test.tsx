import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { MannschaftenTafel } from "./MannschaftenTafel";
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

function mannschaft(rest: Partial<api.Mannschaft> = {}): api.Mannschaft {
  return {
    id: "t1",
    name: "SV Loschwitz 2",
    verein: "SV Loschwitz",
    nummer: 2,
    ist_sg: false,
    hoehere: ["SV Loschwitz"],
    bestaetigt: false,
    unsicher: false,
    ...rest,
  };
}

const ERSTE = mannschaft({ id: "t0", name: "SV Loschwitz", nummer: 1, hoehere: [] });

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Mannschaften", () => {
  it("verlangt zuerst eine Staffel", () => {
    render(<MannschaftenTafel staffeln={[]} />);

    expect(screen.getByText("Noch keine Staffel angelegt")).toBeInTheDocument();
  });

  it("sagt beim leeren Stand, woher die Meldung kommt", async () => {
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([]);
    render(<MannschaftenTafel staffeln={[staffel()]} />);

    expect(await screen.findByText("Keine Mannschaften gemeldet")).toBeInTheDocument();
  });

  it("zeigt den geratenen Aufbau als geraten", async () => {
    // Der Unterschied zwischen "geraten" und "bestaetigt" ist der ganze Zweck
    // dieser Ansicht: ein falscher Schluss faellt sonst nie auf.
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([ERSTE, mannschaft()]);
    render(<MannschaftenTafel staffeln={[staffel()]} />);

    const liste = await screen.findByRole("list", { name: "Mannschaften" });
    expect(within(liste).getAllByText("geraten")).toHaveLength(2);
    expect(within(liste).getByText("Darüber: SV Loschwitz")).toBeInTheDocument();
  });

  it("markiert eine Spielgemeinschaft zum Prüfen", async () => {
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([
      mannschaft({
        name: "SG Gittersee/Coschütz",
        ist_sg: true,
        unsicher: true,
        hoehere: [],
      }),
    ]);
    render(<MannschaftenTafel staffeln={[staffel()]} />);

    const liste = await screen.findByRole("list", { name: "Mannschaften" });
    expect(within(liste).getByText("SG")).toBeInTheDocument();
    expect(within(liste).getByText("prüfen")).toBeInTheDocument();
  });

  it("schickt die Zuordnung, sobald jemand sie ändert", async () => {
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([
      ERSTE,
      mannschaft({ hoehere: [] }),
    ]);
    const speichern = vi
      .spyOn(api, "speichereMannschaften")
      .mockResolvedValue([ERSTE, mannschaft({ bestaetigt: true })]);
    render(<MannschaftenTafel staffeln={[staffel()]} />);

    const karten = await screen.findAllByRole("button", { expanded: false });
    await userEvent.click(karten[1]!);
    await userEvent.click(await screen.findByRole("checkbox", { name: "SV Loschwitz" }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith(
        "s1",
        expect.arrayContaining([
          expect.objectContaining({ name: "SV Loschwitz 2", hoehere: ["SV Loschwitz"] }),
        ]),
      ),
    );
  });

  it("bietet sich selbst nicht als höherklassig an", async () => {
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([ERSTE, mannschaft()]);
    render(<MannschaftenTafel staffeln={[staffel()]} />);

    const karten = await screen.findAllByRole("button", { expanded: false });
    await userEvent.click(karten[1]!);

    const auswahl = await screen.findByRole("list", {
      name: "Höherklassig als SV Loschwitz 2",
    });
    expect(
      within(auswahl).getByRole("checkbox", { name: "SV Loschwitz" }),
    ).toBeInTheDocument();
    expect(
      within(auswahl).queryByRole("checkbox", { name: "SV Loschwitz 2" }),
    ).not.toBeInTheDocument();
  });

  it("zeigt die Meldung des Backends, statt sie zu verschlucken", async () => {
    vi.spyOn(api, "ladeMannschaften").mockRejectedValue(
      new ApiError("kein Zugriff", 403),
    );
    render(<MannschaftenTafel staffeln={[staffel()]} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });

  it("wechselt die Staffel", async () => {
    const laden = vi.spyOn(api, "ladeMannschaften").mockResolvedValue([]);
    render(
      <MannschaftenTafel
        staffeln={[staffel(), staffel({ id: "s2", name: "Stadtliga D" })]}
      />,
    );
    await screen.findByText("Keine Mannschaften gemeldet");

    await userEvent.selectOptions(screen.getByLabelText("Staffel"), "s2");

    await waitFor(() => expect(laden).toHaveBeenCalledWith("s2", expect.anything()));
  });
});
