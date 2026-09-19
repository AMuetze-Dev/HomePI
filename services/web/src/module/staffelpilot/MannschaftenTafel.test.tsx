import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { MannschaftenListe } from "./MannschaftenTafel";
import * as api from "./api";

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

describe("Mannschaften einer Staffel", () => {
  it("sagt beim leeren Stand, woher die Meldung kommt", async () => {
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([]);
    render(<MannschaftenListe staffelId="s1" />);

    expect(
      await screen.findByText(/Noch keine Mannschaften gemeldet/),
    ).toBeInTheDocument();
  });

  it("zeigt den geratenen Aufbau als geraten", async () => {
    // Der Unterschied zwischen "geraten" und "bestaetigt" ist der ganze Zweck
    // dieser Ansicht: ein falscher Schluss faellt sonst nie auf.
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([ERSTE, mannschaft()]);
    render(<MannschaftenListe staffelId="s1" />);

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
    render(<MannschaftenListe staffelId="s1" />);

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
    render(<MannschaftenListe staffelId="s1" />);

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
    render(<MannschaftenListe staffelId="s1" />);

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
    render(<MannschaftenListe staffelId="s1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });
});
