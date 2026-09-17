import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { RegelnTafel } from "./RegelnTafel";
import * as api from "./api";

function regel(rest: Partial<api.Regel> = {}): api.Regel {
  return {
    id: "r1",
    schluessel: "rote_karte",
    name: "Feldverweis auf Dauer",
    beschreibung: "Meldet jeden Feldverweis auf Dauer.",
    schwere: "kritisch",
    weg: "sportgericht",
    aktiv: true,
    ...rest,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Regelkatalog", () => {
  it("sagt beim leeren Stand, wer den Katalog liefert", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([]);
    render(<RegelnTafel />);

    expect(await screen.findByText("Kein Regelkatalog")).toBeInTheDocument();
  });

  it("zeigt Name, Schwere und Weg", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    render(<RegelnTafel />);

    const liste = await screen.findByRole("list", { name: "Regeln" });
    expect(within(liste).getByText("kritisch")).toBeInTheDocument();
    expect(within(liste).getByText("führt vors Sportgericht")).toBeInTheDocument();
    expect(within(liste).getByText("rote_karte")).toBeInTheDocument();
  });

  it("nennt keinen Weg, wenn die Regel zu nichts führt", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel({ weg: "kein" })]);
    render(<RegelnTafel />);

    await screen.findByRole("list", { name: "Regeln" });
    expect(screen.queryByText(/führt/)).not.toBeInTheDocument();
  });

  it("schaltet eine Regel ab", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    const schalten = vi
      .spyOn(api, "schalteRegel")
      .mockResolvedValue(regel({ aktiv: false }));
    render(<RegelnTafel />);

    await userEvent.click(
      await screen.findByRole("checkbox", { name: /Feldverweis auf Dauer/ }),
    );

    await waitFor(() => expect(schalten).toHaveBeenCalledWith("r1", false));
    expect(await screen.findByText(/Abgeschaltet/)).toBeInTheDocument();
  });

  it("schaltet sie wieder an", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel({ aktiv: false })]);
    const schalten = vi.spyOn(api, "schalteRegel").mockResolvedValue(regel());
    render(<RegelnTafel />);

    await userEvent.click(
      await screen.findByRole("checkbox", { name: /Feldverweis auf Dauer/ }),
    );

    await waitFor(() => expect(schalten).toHaveBeenCalledWith("r1", true));
  });

  it("lässt den Haken stehen, wenn das Schalten scheitert", async () => {
    // Sonst zeigte die Oberflaeche "aus" und der Pruefdienst meldete weiter -
    // genau die Luecke, vor der diese Ansicht schuetzen soll.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    vi.spyOn(api, "schalteRegel").mockRejectedValue(new ApiError("kaputt", 500));
    render(<RegelnTafel />);

    const haken = await screen.findByRole("checkbox", { name: /Feldverweis auf Dauer/ });
    await userEvent.click(haken);

    await screen.findByRole("alert");
    expect(haken).toBeChecked();
  });

  it("zeigt einen Ladefehler statt einer leeren Liste", async () => {
    vi.spyOn(api, "ladeRegeln").mockRejectedValue(new ApiError("kein Zugriff", 403));
    render(<RegelnTafel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });
});
