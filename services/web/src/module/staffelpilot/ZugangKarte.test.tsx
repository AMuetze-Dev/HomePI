import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { ZugangKarte } from "./ZugangKarte";
import * as api from "./api";

function stand(rest: Partial<api.ZugangStand> = {}): api.ZugangStand {
  return { gespeichert: false, benutzer: "", schluessel_vorhanden: true, ...rest };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DFBnet-Zugang", () => {
  it("sagt, dass das Passwort nie zurückkommt", async () => {
    vi.spyOn(api, "ladeZugang").mockResolvedValue(stand());
    render(<ZugangKarte />);

    expect(await screen.findByText(/kommt nie wieder heraus/)).toBeInTheDocument();
  });

  it("warnt vor dem Tippen, wenn kein Schlüssel da ist", async () => {
    // Gespeichert wuerde dann naemlich nichts - das soll dastehen, bevor
    // jemand ein Passwort eingibt.
    vi.spyOn(api, "ladeZugang").mockResolvedValue(stand({ schluessel_vorhanden: false }));
    render(<ZugangKarte />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/STAFFELPILOT_SCHLUESSEL/);
  });

  it("sperrt dann auch den Knopf", async () => {
    vi.spyOn(api, "ladeZugang").mockResolvedValue(stand({ schluessel_vorhanden: false }));
    render(<ZugangKarte />);

    await userEvent.type(await screen.findByLabelText(/Benutzername/), "wer");
    await userEvent.type(screen.getByLabelText(/Passwort/), "geheim");

    expect(screen.getByRole("button", { name: "Zugang hinterlegen" })).toBeDisabled();
  });

  it("hinterlegt und leert danach das Passwortfeld", async () => {
    // Was dort stünde, wäre ab jetzt eine Kopie von etwas, das nirgends mehr
    // im Klartext liegt.
    vi.spyOn(api, "ladeZugang")
      .mockResolvedValueOnce(stand())
      .mockResolvedValue(stand({ gespeichert: true, benutzer: "sl42" }));
    const speichern = vi.spyOn(api, "speichereZugang").mockResolvedValue(undefined);
    render(<ZugangKarte />);

    await userEvent.type(await screen.findByLabelText(/Benutzername/), "sl42");
    const passwortfeld = screen.getByLabelText(/Passwort/);
    await userEvent.type(passwortfeld, "geheim-und-lang");
    await userEvent.click(screen.getByRole("button", { name: "Zugang hinterlegen" }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith("sl42", "geheim-und-lang"),
    );
    expect(passwortfeld).toHaveValue("");
  });

  it("zeigt, für wen etwas hinterlegt ist", async () => {
    vi.spyOn(api, "ladeZugang").mockResolvedValue(
      stand({ gespeichert: true, benutzer: "sl42" }),
    );
    render(<ZugangKarte />);

    expect(await screen.findByText("sl42")).toBeInTheDocument();
  });

  it("entfernt", async () => {
    vi.spyOn(api, "ladeZugang").mockResolvedValue(
      stand({ gespeichert: true, benutzer: "sl42" }),
    );
    const loeschen = vi.spyOn(api, "loescheZugang").mockResolvedValue(undefined);
    render(<ZugangKarte />);

    await userEvent.click(await screen.findByRole("button", { name: "Entfernen" }));

    await waitFor(() => expect(loeschen).toHaveBeenCalled());
  });

  it("bietet das Entfernen nicht an, wenn nichts hinterlegt ist", async () => {
    vi.spyOn(api, "ladeZugang").mockResolvedValue(stand());
    render(<ZugangKarte />);
    await screen.findByLabelText(/Benutzername/);

    expect(screen.queryByRole("button", { name: "Entfernen" })).not.toBeInTheDocument();
  });

  it("zeigt die Meldung des Backends, statt sie zu verschlucken", async () => {
    vi.spyOn(api, "ladeZugang").mockResolvedValue(stand());
    vi.spyOn(api, "speichereZugang").mockRejectedValue(
      new ApiError("STAFFELPILOT_SCHLUESSEL ist kein gültiger Fernet-Schlüssel", 503),
    );
    render(<ZugangKarte />);

    await userEvent.type(await screen.findByLabelText(/Benutzername/), "sl42");
    await userEvent.type(screen.getByLabelText(/Passwort/), "geheim");
    await userEvent.click(screen.getByRole("button", { name: "Zugang hinterlegen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Fernet/);
  });

  it("wirft die Eingabe nicht weg, wenn die Antwort spät kommt", async () => {
    // Der Fehler, den erst ein Oberflächentest gegen den echten Stack gefunden
    // hat: das Formular stand schon da, die Antwort des Servers setzte den
    // Benutzernamen auf den gespeicherten Wert zurück — bei einer frischen
    // Installation auf leer. Wer schnell tippte, fand danach einen Knopf, der
    // sich nicht drücken ließ.
    let antworten: (s: api.ZugangStand) => void = () => {};
    vi.spyOn(api, "ladeZugang").mockReturnValue(
      new Promise<api.ZugangStand>((aufloesen) => {
        antworten = aufloesen;
      }),
    );
    render(<ZugangKarte />);

    // Solange nichts da ist, gibt es auch nichts zu tippen.
    expect(screen.queryByRole("textbox", { name: /Benutzername/ })).toBeNull();
    expect(screen.getByRole("status", { name: /wird geladen/ })).toBeInTheDocument();

    antworten({ gespeichert: false, benutzer: "", schluessel_vorhanden: true });

    const feld = await screen.findByRole("textbox", { name: /Benutzername/ });
    await userEvent.type(feld, "beispiel");

    expect(feld).toHaveValue("beispiel");
    expect(screen.getByRole("button", { name: "Zugang hinterlegen" })).toBeDisabled();
  });
});
