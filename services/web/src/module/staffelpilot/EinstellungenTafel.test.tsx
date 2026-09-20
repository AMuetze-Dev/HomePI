import { render, screen, waitFor, within } from "@testing-library/react";
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
    uebertragung_pausiert: true,
    browser_sichtbar: false,
    ...rest,
  };
}

function mitWerten(rest: Partial<api.Einstellungen> = {}) {
  vi.spyOn(api, "ladeEinstellungen").mockResolvedValue(werte(rest));
  // Die Zugangskarte sitzt auf derselben Fläche. Ohne Antwort meldet sie
  // ihrerseits einen Fehler - und dann stehen zwei Meldungen da.
  vi.spyOn(api, "ladeZugang").mockResolvedValue({
    gespeichert: false,
    benutzer: "",
    schluessel_vorhanden: true,
  });
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

    const formular = screen.getByRole("button", { name: "Speichern" }).closest("form")!;
    expect(await within(formular).findByRole("alert")).toHaveTextContent(
      /zwischen 1 und 90/,
    );
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

    const formular = screen.getByRole("button", { name: "Speichern" }).closest("form")!;
    await within(formular).findByRole("alert");
    expect(screen.getByDisplayValue("Neuer Verband")).toBeInTheDocument();
  });

  it("zeigt einen Fehler beim Laden statt eines leeren Formulars", async () => {
    vi.spyOn(api, "ladeZugang").mockResolvedValue({
      gespeichert: false,
      benutzer: "",
      schluessel_vorhanden: true,
    });
    vi.spyOn(api, "ladeEinstellungen").mockRejectedValue(
      new ApiError("kein Zugriff", 403),
    );
    render(<EinstellungenTafel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });

  describe("Beim Prüfen zusehen", () => {
    it("ist aus, solange niemand ihn einschaltet", async () => {
      mitWerten();
      render(<EinstellungenTafel />);

      const schalter = await screen.findByRole("checkbox", { name: /zusehen/i });
      expect(schalter).not.toBeChecked();
    });

    it("zeigt an, wenn er an ist", async () => {
      mitWerten({ browser_sichtbar: true });
      render(<EinstellungenTafel />);

      expect(await screen.findByRole("checkbox", { name: /zusehen/i })).toBeChecked();
    });

    it("schickt die Änderung mit", async () => {
      mitWerten();
      const speichern = vi
        .spyOn(api, "speichereEinstellungen")
        .mockResolvedValue(werte({ browser_sichtbar: true }));
      render(<EinstellungenTafel />);

      await userEvent.click(await screen.findByRole("checkbox", { name: /zusehen/i }));
      await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

      await waitFor(() =>
        expect(speichern).toHaveBeenCalledWith(
          expect.objectContaining({ browser_sichtbar: true }),
        ),
      );
    });

    it("sagt, dass im Container nichts zu sehen ist", async () => {
      // Sonst legt jemand den Schalter um, sieht nichts und sucht den Fehler
      // im Prüflauf.
      mitWerten();
      render(<EinstellungenTafel />);

      expect(await screen.findByText(/kein(en)? Bildschirm/i)).toBeInTheDocument();
    });
  });
});
