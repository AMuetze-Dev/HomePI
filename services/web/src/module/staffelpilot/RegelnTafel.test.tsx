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
    sachverhalt: "",
    hinweis: "",
    vorgabe_sachverhalt: "",
    vorgabe_hinweis: "",
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

describe("Die Sätze fürs Schreiben", () => {
  const mitSatz = (rest: Partial<api.Regel> = {}) =>
    regel({
      weg: "mahnung",
      vorgabe_sachverhalt: "wurde durch {verein} nicht bestätigt.",
      vorgabe_hinweis: "Ich weise auf § 53 hin.",
      ...rest,
    });

  it("bietet sie nur an, wo überhaupt ein Schreiben entsteht", async () => {
    // Bei "kein" wäre es ein Feld, das nie irgendwo auftaucht.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz({ weg: "kein" })]);
    render(<RegelnTafel />);

    await screen.findByText("Feldverweis auf Dauer");
    expect(screen.queryByText("Text fürs Schreiben")).not.toBeInTheDocument();
  });

  it("zeigt den mitgelieferten Satz als Platzhalter und nicht als Inhalt", async () => {
    // Wäre er Inhalt, hätte der erste Klick auf Speichern den heutigen
    // Wortlaut eingefroren - samt Paragraf, samt späterer Korrektur.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    render(<RegelnTafel />);

    const feld = await screen.findByLabelText("Sachverhalt");
    expect(feld).toHaveValue("");
    expect(feld).toHaveAttribute("placeholder", "wurde durch {verein} nicht bestätigt.");
  });

  it("schickt beide Felder und übernimmt die Antwort", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    const speichern = vi
      .spyOn(api, "formuliereRegel")
      .mockResolvedValue(mitSatz({ sachverhalt: "war anders." }));
    render(<RegelnTafel />);

    await userEvent.type(await screen.findByLabelText("Sachverhalt"), "war anders.");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith("r1", {
        sachverhalt: "war anders.",
        hinweis: "",
      }),
    );
    expect(await screen.findByText("eigener")).toBeInTheDocument();
  });

  it("behält die Eingabe, wenn das Speichern scheitert", async () => {
    // Sonst ist die Formulierung weg und der Fehler bleibt unerklärt.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    vi.spyOn(api, "formuliereRegel").mockRejectedValue(new ApiError("zu lang", 422));
    render(<RegelnTafel />);

    const feld = await screen.findByLabelText("Sachverhalt");
    await userEvent.type(feld, "war anders.");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("zu lang");
    expect(feld).toHaveValue("war anders.");
  });

  it("lässt nicht speichern, solange nichts geändert ist", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    render(<RegelnTafel />);

    await screen.findByLabelText("Sachverhalt");
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });
});
