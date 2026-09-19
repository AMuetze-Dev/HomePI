import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StaffelnTafel } from "./StaffelnTafel";
import * as api from "./api";

function staffel(rest: Partial<api.Staffel> = {}): api.Staffel {
  return {
    id: "s1",
    name: "Stadtliga C",
    altersklasse: "maenner",
    spielklasse: "3.Kreisliga (C)",
    saison: "26/27",
    spieltage: 0,
    aktiv: true,
    ...rest,
  };
}

function tafel(staffeln: api.Staffel[] = [staffel()]) {
  const anlegen = vi.fn().mockResolvedValue(true);
  const aendern = vi.fn().mockResolvedValue(true);
  const loeschen = vi.fn().mockResolvedValue(true);
  render(
    <StaffelnTafel
      staffeln={staffeln}
      onAnlegen={anlegen}
      onAendern={aendern}
      onLoeschen={loeschen}
    />,
  );
  return { anlegen, aendern, loeschen };
}

beforeEach(() => {
  vi.spyOn(api, "ladeMannschaften").mockResolvedValue([]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Staffeln verwalten", () => {
  it("sagt beim leeren Stand, warum der Name genau stimmen muss", () => {
    tafel([]);

    expect(screen.getByText("Noch keine Staffel angelegt")).toBeInTheDocument();
    expect(
      screen.getByText(/sonst findet der Prüfdienst sie dort nicht wieder/),
    ).toBeInTheDocument();
  });

  it("zeigt Spielklasse, Altersklasse, Saison und Zustand", () => {
    tafel();

    const liste = screen.getByRole("list", { name: "Staffeln" });
    expect(within(liste).getByText("3.Kreisliga (C)")).toBeInTheDocument();
    expect(within(liste).getByText("Männer")).toBeInTheDocument();
    expect(within(liste).getByText("26/27")).toBeInTheDocument();
    expect(within(liste).getByText("aktiv")).toBeInTheDocument();
  });

  it("legt eine an und leert das Formular", async () => {
    const { anlegen } = tafel([]);

    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Ü35");
    await userEvent.type(
      screen.getByRole("textbox", { name: "Spielklasse" }),
      "1.Kreisklasse",
    );
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    await waitFor(() =>
      expect(anlegen).toHaveBeenCalledWith({
        name: "Ü35",
        spielklasse: "1.Kreisklasse",
        saison: "",
        // Ein leeres Feld heißt *nicht bekannt*, und genau dafür steht die 0.
        spieltage: 0,
        altersklasse: "maenner",
      }),
    );
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("");
  });

  it("nimmt die Spieltage entgegen", async () => {
    const { anlegen } = tafel([]);

    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Ü35");
    await userEvent.type(
      screen.getByRole("textbox", { name: "Spielklasse" }),
      "1.Kreisklasse",
    );
    await userEvent.type(screen.getByRole("textbox", { name: "Spieltage" }), "26");
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    await waitFor(() =>
      expect(anlegen).toHaveBeenCalledWith(expect.objectContaining({ spieltage: 26 })),
    );
  });

  it("macht aus einer unsinnigen Eingabe kein geratenes Ergebnis", async () => {
    // 0 heißt *nicht bekannt*. Aus "zwanzig" eine 20 zu raten wäre schlimmer,
    // als nichts zu wissen: die U23-Ausnahme fiele an den falschen Spieltagen.
    const { anlegen } = tafel([]);

    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Ü35");
    await userEvent.type(
      screen.getByRole("textbox", { name: "Spielklasse" }),
      "1.Kreisklasse",
    );
    await userEvent.type(screen.getByRole("textbox", { name: "Spieltage" }), "zwanzig");
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    await waitFor(() =>
      expect(anlegen).toHaveBeenCalledWith(expect.objectContaining({ spieltage: 0 })),
    );
  });

  it("behält die Eingabe, wenn das Anlegen scheitert", async () => {
    render(
      <StaffelnTafel
        staffeln={[]}
        onAnlegen={vi.fn().mockResolvedValue(false)}
        onAendern={vi.fn()}
        onLoeschen={vi.fn()}
      />,
    );

    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Ü35");
    await userEvent.type(
      screen.getByRole("textbox", { name: "Spielklasse" }),
      "1.Kreisklasse",
    );
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("Ü35"),
    );
  });

  it("ändert Name, Spielklasse und Saison", async () => {
    const { aendern } = tafel();
    await userEvent.click(screen.getByRole("button", { name: /Stadtliga C/ }));

    // Zwei Formulare auf der Fläche: das der Karte und das zum Anlegen.
    const karte = (await screen.findByRole("button", { name: "Speichern" })).closest(
      "form",
    )!;
    const feld = within(karte).getByRole("textbox", { name: "Name" });
    await userEvent.clear(feld);
    await userEvent.type(feld, "Stadtliga D");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() =>
      expect(aendern).toHaveBeenCalledWith(
        "s1",
        expect.objectContaining({ name: "Stadtliga D" }),
      ),
    );
  });

  it("legt still und setzt wieder aktiv", async () => {
    const { aendern } = tafel();
    await userEvent.click(screen.getByRole("button", { name: /Stadtliga C/ }));

    await userEvent.click(await screen.findByRole("button", { name: "Stilllegen" }));

    await waitFor(() => expect(aendern).toHaveBeenCalledWith("s1", { aktiv: false }));
  });

  it("nennt die stillgelegte auch so", () => {
    tafel([staffel({ aktiv: false })]);

    const liste = screen.getByRole("list", { name: "Staffeln" });
    expect(within(liste).getByText("stillgelegt")).toBeInTheDocument();
    expect(screen.queryByText("aktiv")).not.toBeInTheDocument();
  });

  it("fragt vor dem Löschen nach und sagt, was mitgeht", async () => {
    // Es nimmt jeden Spielbericht dieser Staffel mit, und das ist die Arbeit
    // einer Saison.
    const { loeschen } = tafel();
    await userEvent.click(screen.getByRole("button", { name: /Stadtliga C/ }));

    await userEvent.click(await screen.findByRole("button", { name: "Staffel löschen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /alle Spielberichte und Befunde/,
    );
    expect(loeschen).not.toHaveBeenCalled();
  });

  it("löscht erst nach der Bestätigung", async () => {
    const { loeschen } = tafel();
    await userEvent.click(screen.getByRole("button", { name: /Stadtliga C/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Staffel löschen" }));

    await userEvent.click(screen.getByRole("button", { name: "Endgültig löschen" }));

    await waitFor(() => expect(loeschen).toHaveBeenCalledWith("s1"));
  });

  it("lässt sich die Rückfrage abbrechen", async () => {
    const { loeschen } = tafel();
    await userEvent.click(screen.getByRole("button", { name: /Stadtliga C/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Staffel löschen" }));

    await userEvent.click(screen.getByRole("button", { name: "Abbrechen" }));

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(loeschen).not.toHaveBeenCalled();
  });

  it("zeigt die Mannschaften derselben Staffel", async () => {
    tafel();

    await userEvent.click(screen.getByRole("button", { name: /Stadtliga C/ }));

    expect(
      await screen.findByRole("heading", { name: "Mannschaften" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(api.ladeMannschaften).toHaveBeenCalledWith("s1", expect.anything()),
    );
  });
});
