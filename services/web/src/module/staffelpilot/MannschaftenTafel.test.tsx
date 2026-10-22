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
    vorschlaege: [],
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

describe("Höherklassige Mannschaften eintragen", () => {
  const sg = () =>
    mannschaft({
      id: "m9",
      name: "SpG Kickers 2 / Hafen 2",
      ist_sg: true,
      bestaetigt: false,
      hoehere: [],
      vorschlaege: [],
    });

  const dritte = () =>
    mannschaft({
      id: "m8",
      name: "Dresdner SC 1898 3",
      hoehere: [],
      vorschlaege: ["Dresdner SC 1898 2", "Dresdner SC 1898"],
    });

  async function aufklappen(name: string) {
    await userEvent.click(await screen.findByRole("button", { name: new RegExp(name) }));
  }

  it("bietet die abgeleiteten Mannschaften an, die nicht mitspielen", async () => {
    // "Dresdner SC 1898 2" spielt höherklassig und steht deshalb gar nicht in
    // dieser Staffel - ankreuzen ließ sich vorher nur, wer hier mitspielt.
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([dritte()]);
    render(<MannschaftenListe staffelId="s1" />);
    await aufklappen("Dresdner SC 1898 3");

    expect(
      await screen.findByRole("button", { name: "+ Dresdner SC 1898 2" }),
    ).toBeInTheDocument();
  });

  it("trägt einen Vorschlag auf Klick ein", async () => {
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([dritte()]);
    const speichern = vi
      .spyOn(api, "speichereMannschaften")
      .mockResolvedValue([dritte()]);
    render(<MannschaftenListe staffelId="s1" />);
    await aufklappen("Dresdner SC 1898 3");

    await userEvent.click(screen.getByRole("button", { name: "+ Dresdner SC 1898" }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith("s1", [
        expect.objectContaining({ hoehere: ["Dresdner SC 1898"] }),
      ]),
    );
  });

  it("schlägt bei einer Spielgemeinschaft nichts vor", async () => {
    // "SpG Kickers 2 / Hafen 2" gehört zwei Vereinen; ein Vorschlag wäre
    // geraten, und ein falscher ändert still, wessen Einsätze zählen.
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([sg()]);
    render(<MannschaftenListe staffelId="s1" />);
    await aufklappen("SpG Kickers 2 / Hafen 2");

    await screen.findByLabelText("Höherklassige Mannschaft eintragen");
    expect(screen.queryByRole("button", { name: /^\+ / })).toBeNull();
  });

  it("nimmt für die Spielgemeinschaft einen Namen von Hand", async () => {
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([sg()]);
    const speichern = vi.spyOn(api, "speichereMannschaften").mockResolvedValue([sg()]);
    render(<MannschaftenListe staffelId="s1" />);
    await aufklappen("SpG Kickers 2 / Hafen 2");

    await userEvent.type(
      await screen.findByLabelText("Höherklassige Mannschaft eintragen"),
      "FV Löbtauer Kickers",
    );
    await userEvent.click(screen.getByRole("button", { name: "Eintragen" }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith("s1", [
        expect.objectContaining({ hoehere: ["FV Löbtauer Kickers"] }),
      ]),
    );
  });

  it("lässt einen eingetragenen Namen wieder entfernen", async () => {
    // Ohne diese Liste stand eine von Hand eingetippte Mannschaft nur im Satz
    // darüber - und war nie wieder loszuwerden.
    vi.spyOn(api, "ladeMannschaften").mockResolvedValue([
      mannschaft({ hoehere: ["FV Hafen Dresden"], vorschlaege: [] }),
    ]);
    const speichern = vi.spyOn(api, "speichereMannschaften").mockResolvedValue([mannschaft()]);
    render(<MannschaftenListe staffelId="s1" />);
    await aufklappen("SV Loschwitz 2");

    await userEvent.click(
      await screen.findByRole("button", { name: "FV Hafen Dresden entfernen" }),
    );

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith("s1", [
        expect.objectContaining({ hoehere: [] }),
      ]),
    );
  });
});
