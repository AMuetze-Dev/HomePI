import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { EinstellungenTafel } from "./EinstellungenTafel";
import * as api from "./api";

function werte(rest: Partial<api.Einstellungen> = {}): api.Einstellungen {
  return {
    staffelleiter: "Aaron Mütze",
    verband: "Kreisverband Dresden",
    absender: "staffelleitung@example.org",
    pruefzeitraum_tage: 30,
    frist_tage: 14,
    ...rest,
  };
}

function mitWerten(rest: Partial<api.Einstellungen> = {}) {
  vi.spyOn(api, "ladeEinstellungen").mockResolvedValue(werte(rest));
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Einstellungen", () => {
  it("zeigt, was gespeichert ist", async () => {
    mitWerten();
    render(<EinstellungenTafel />);

    expect(await screen.findByDisplayValue("Aaron Mütze")).toBeInTheDocument();
    expect(screen.getByDisplayValue("30")).toBeInTheDocument();
  });

  it("schickt die geänderten Felder", async () => {
    mitWerten();
    const speichern = vi
      .spyOn(api, "speichereEinstellungen")
      .mockResolvedValue(werte({ staffelleiter: "Erika Beispiel" }));
    render(<EinstellungenTafel />);

    const feld = await screen.findByLabelText(/Staffelleiter/);
    await userEvent.clear(feld);
    await userEvent.type(feld, "Erika Beispiel");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith(
        expect.objectContaining({ staffelleiter: "Erika Beispiel" }),
      ),
    );
  });

  it("übernimmt die Antwort und nicht die Eingabe", async () => {
    // Das Backend trimmt und setzt Vorgaben ein. Was dort steht, ist der Stand.
    mitWerten();
    vi.spyOn(api, "speichereEinstellungen").mockResolvedValue(
      werte({ staffelleiter: "Getrimmt" }),
    );
    render(<EinstellungenTafel />);

    const feld = await screen.findByLabelText(/Staffelleiter/);
    await userEvent.clear(feld);
    await userEvent.type(feld, "  Getrimmt  ");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(await screen.findByDisplayValue("Getrimmt")).toBeInTheDocument();
    expect(await screen.findByText("Gespeichert.")).toBeInTheDocument();
  });

  it("zeigt die Meldung des Backends, statt sie zu verschlucken", async () => {
    mitWerten();
    vi.spyOn(api, "speichereEinstellungen").mockRejectedValue(
      new ApiError("'frist_tage' muss zwischen 1 und 90 liegen", 422),
    );
    render(<EinstellungenTafel />);

    await screen.findByLabelText(/Staffelleiter/);
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/zwischen 1 und 90/);
  });

  it("behält die Eingabe, wenn das Speichern scheitert", async () => {
    mitWerten();
    vi.spyOn(api, "speichereEinstellungen").mockRejectedValue(
      new ApiError("kaputt", 500),
    );
    render(<EinstellungenTafel />);

    const feld = await screen.findByLabelText(/Verband/);
    await userEvent.clear(feld);
    await userEvent.type(feld, "Neuer Verband");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await screen.findByRole("alert");
    expect(screen.getByDisplayValue("Neuer Verband")).toBeInTheDocument();
  });

  it("zeigt einen Fehler beim Laden statt eines leeren Formulars", async () => {
    vi.spyOn(api, "ladeEinstellungen").mockRejectedValue(
      new ApiError("kein Zugriff", 403),
    );
    render(<EinstellungenTafel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });
});
