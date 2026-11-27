import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { IhkSeite } from "./IhkSeite";
import { KATALOG, pruefling } from "./testdaten";

vi.mock("./PdfAnsicht", () => ({ PdfAnsicht: () => null }));

function zeige(suche: string) {
  return render(
    <MemoryRouter initialEntries={[`/modul/ihk${suche}`]}>
      <IhkSeite />
    </MemoryRouter>,
  );
}

const SAMMLUNG: api.Frage[] = [
  { id: "q1", text: "Was ist ACID?", thema: "Datenbanken" },
  { id: "q2", text: "Was ist ein Subnetz?", thema: "Netzwerk" },
  { id: "q3", text: "Was ist Scrum?", thema: "" },
];

const INDEX: api.FgFrage = {
  id: "f1",
  text: "Was ist ein Index?",
  wert: null,
  quelle: "q9",
};

beforeEach(() => {
  vi.spyOn(api, "ladeKatalog").mockResolvedValue(KATALOG);
  vi.spyOn(api, "ladeFragen").mockResolvedValue(SAMMLUNG);
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function fachgespraech(fragen: api.FgFrage[] = [INDEX]) {
  const p = pruefling();
  p.bewertung.fg_fragen = fragen;
  vi.spyOn(api, "ladePruefling").mockResolvedValue(p);
  vi.spyOn(api, "aendereBewertung").mockResolvedValue(p);
  zeige("?pruefling=p1");
  await userEvent.click(await screen.findByRole("radio", { name: "Präsentation" }));
  return screen.getByRole("region", { name: /Fachgespräch/ });
}

// ── Fachgespräch ─────────────────────────────────────────────────────────────

describe("Fachgespräch", () => {
  it("bewertet jede gestellte Frage auf der Skala", async () => {
    const fg = await fachgespraech();
    const zeile = within(fg).getByRole("group", { name: "Was ist ein Index?" });
    await userEvent.click(within(zeile).getByRole("button", { name: "75 %" }));

    expect(api.aendereBewertung).toHaveBeenCalledWith("p1", {
      fg_fragen: [{ ...INDEX, wert: 0.75 }],
    });
  });

  it("hat keine festen Kriterien mehr", async () => {
    const fg = await fachgespraech([]);
    expect(within(fg).getByText(/Noch keine Frage gestellt/)).toBeInTheDocument();
  });

  it("nimmt eine eigene Frage auf", async () => {
    const fg = await fachgespraech();
    await userEvent.type(
      within(fg).getByRole("textbox", { name: "Eigene Frage" }),
      "Warum Docker?{Enter}",
    );

    expect(api.aendereBewertung).toHaveBeenCalledWith("p1", {
      fg_fragen: [INDEX, { text: "Warum Docker?", wert: null, quelle: null }],
    });
  });

  it("entfernt eine Frage", async () => {
    const fg = await fachgespraech();
    await userEvent.click(
      within(fg).getByRole("button", { name: "„Was ist ein Index?“ entfernen" }),
    );
    expect(api.aendereBewertung).toHaveBeenCalledWith("p1", { fg_fragen: [] });
  });

  it("zieht eine Frage aus der Sammlung und stellt sie", async () => {
    vi.spyOn(api, "zieheFrage")
      .mockResolvedValueOnce(SAMMLUNG[0]!)
      .mockResolvedValueOnce({ id: "q4", text: "Was ist 3NF?", thema: "Datenbanken" });
    const fg = await fachgespraech();

    await userEvent.selectOptions(
      await within(fg).findByRole("combobox", { name: "Thema" }),
      "Datenbanken",
    );
    await userEvent.click(within(fg).getByRole("button", { name: "Frage ziehen" }));
    // Schon gestellte Fragen der Sammlung kommen nicht noch einmal.
    expect(api.zieheFrage).toHaveBeenLastCalledWith("Datenbanken", ["q9"]);
    expect(await within(fg).findByText("Was ist ACID?")).toBeInTheDocument();

    await userEvent.click(within(fg).getByRole("button", { name: "Andere ziehen" }));
    expect(api.zieheFrage).toHaveBeenLastCalledWith("Datenbanken", ["q9", "q1"]);
    expect(await within(fg).findByText("Was ist 3NF?")).toBeInTheDocument();

    await userEvent.click(within(fg).getByRole("button", { name: "Stellen" }));
    expect(api.aendereBewertung).toHaveBeenCalledWith("p1", {
      fg_fragen: [INDEX, { text: "Was ist 3NF?", wert: null, quelle: "q4" }],
    });
  });

  it("sagt wörtlich, wenn nichts mehr zu ziehen ist", async () => {
    vi.spyOn(api, "zieheFrage").mockRejectedValue(
      new ApiError("Alle Fragen der Sammlung wurden schon gestellt", 404),
    );
    const fg = await fachgespraech();
    await userEvent.click(
      await within(fg).findByRole("button", { name: "Frage ziehen" }),
    );
    expect(await within(fg).findByRole("alert")).toHaveTextContent(
      "Alle Fragen der Sammlung wurden schon gestellt",
    );
  });
});

// ── Fragensammlung ───────────────────────────────────────────────────────────

describe("Fragensammlung", () => {
  it("erklärt im Erstzustand, wozu sie da ist", async () => {
    vi.mocked(api.ladeFragen).mockResolvedValue([]);
    zeige("?fragen");
    expect(await screen.findByText(/Noch keine Fragen/)).toBeInTheDocument();
  });

  it("ordnet die Fragen nach Thema", async () => {
    zeige("?fragen");
    const db = await screen.findByRole("region", { name: "Datenbanken" });
    expect(within(db).getByText("Was ist ACID?")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Netzwerk" })).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Ohne Thema" })).getByText(
        "Was ist Scrum?",
      ),
    ).toBeInTheDocument();
  });

  it("findet Fragen über die Suche", async () => {
    zeige("?fragen");
    await userEvent.type(
      await screen.findByRole("searchbox", { name: "Fragen durchsuchen" }),
      "subnetz",
    );
    expect(screen.getByText("Was ist ein Subnetz?")).toBeInTheDocument();
    expect(screen.queryByText("Was ist ACID?")).not.toBeInTheDocument();
  });

  it("nimmt eine Frage auf", async () => {
    vi.spyOn(api, "legeFrageAn").mockResolvedValue({
      id: "q5",
      text: "Was ist REST?",
      thema: "Web",
    });
    zeige("?fragen");
    await userEvent.type(
      await screen.findByRole("textbox", { name: "Frage" }),
      "Was ist REST?",
    );
    await userEvent.type(screen.getByRole("combobox", { name: "Thema" }), "Web");
    await userEvent.click(screen.getByRole("button", { name: "Aufnehmen" }));

    expect(api.legeFrageAn).toHaveBeenCalledWith({ text: "Was ist REST?", thema: "Web" });
    expect(await screen.findByRole("region", { name: "Web" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Frage" })).toHaveValue("");
  });

  it("nimmt viele auf einmal auf, eine je Zeile", async () => {
    vi.spyOn(api, "legeFragenAn").mockResolvedValue({ angelegt: 2, doppelt: 1 });
    zeige("?fragen");
    await userEvent.click(
      await screen.findByRole("button", { name: "Mehrere auf einmal" }),
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Eine Frage je Zeile" }),
      "A?{Enter}B?{Enter}Was ist ACID?",
    );
    await userEvent.click(screen.getByRole("button", { name: "Alle aufnehmen" }));

    expect(api.legeFragenAn).toHaveBeenCalledWith({
      thema: "",
      texte: "A?\nB?\nWas ist ACID?",
    });
    expect(await screen.findByText("2 aufgenommen, 1 gab es schon.")).toBeInTheDocument();
    expect(api.ladeFragen).toHaveBeenCalledTimes(2);
  });

  it("entfernt eine Frage nach Rückfrage", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "entferneFrage").mockResolvedValue();
    zeige("?fragen");
    await userEvent.click(
      await screen.findByRole("button", { name: "„Was ist ACID?“ entfernen" }),
    );
    expect(api.entferneFrage).toHaveBeenCalledWith("q1");
    expect(screen.queryByText("Was ist ACID?")).not.toBeInTheDocument();
  });

  it("ändert Text und Thema einer Frage", async () => {
    vi.spyOn(api, "aendereFrage").mockResolvedValue({
      id: "q1",
      text: "Was bedeutet ACID?",
      thema: "Datenbanken",
    });
    zeige("?fragen");
    await userEvent.click(
      await screen.findByRole("button", { name: "„Was ist ACID?“ ändern" }),
    );
    const feld = screen.getByRole("textbox", { name: "Text der Frage" });
    await userEvent.clear(feld);
    await userEvent.type(feld, "Was bedeutet ACID?");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(api.aendereFrage).toHaveBeenCalledWith("q1", {
      text: "Was bedeutet ACID?",
      thema: "Datenbanken",
    });
    expect(await screen.findByText("Was bedeutet ACID?")).toBeInTheDocument();
  });
});
