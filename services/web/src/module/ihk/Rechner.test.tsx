import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { IhkSeite } from "./IhkSeite";
import { KATALOG } from "./testdaten";

function zeige(suche = "?rechner") {
  return render(
    <MemoryRouter initialEntries={[`/modul/ihk${suche}`]}>
      <IhkSeite />
    </MemoryRouter>,
  );
}

const STUFE: api.Notenstufe = {
  punkte: 91,
  note: 1.5,
  ganze_note: 2,
  grenzfall: true,
  bessere_note: 1,
  fehlen: 1,
  puffer: 10,
};

const LEER: api.GesamtErgebnis = {
  projekt: null,
  bereiche: [],
  teil1: null,
  teil2: null,
  gesamt: null,
  note: null,
  grenzfall: false,
  fehlend: ["projekt"],
};

beforeEach(() => {
  vi.spyOn(api, "ladeKatalog").mockResolvedValue(KATALOG);
  vi.spyOn(api, "rechne").mockResolvedValue({
    ohne_mep: LEER,
    mit_mep: null,
    stufe_ohne_mep: null,
    stufe_mit_mep: null,
    stufe_doku: null,
    stufe_praesentation: null,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Notenrechner", () => {
  it("ist von der Übersicht aus erreichbar", async () => {
    vi.spyOn(api, "ladeTage").mockResolvedValue([]);
    zeige("");
    expect(await screen.findByRole("link", { name: "Notenrechner" })).toHaveAttribute(
      "href",
      "/modul/ihk?rechner",
    );
  });

  it("macht aus Punkten eine Note und nennt den Grenzfall", async () => {
    vi.spyOn(api, "ladeNotenstufe").mockResolvedValue(STUFE);
    zeige();

    await userEvent.type(await screen.findByLabelText("Punkte"), "91");

    expect(await screen.findByText("1,5")).toBeInTheDocument();
    expect(api.ladeNotenstufe).toHaveBeenLastCalledWith(91, expect.anything());
    expect(screen.getByText("Grenzfall")).toBeInTheDocument();
    expect(screen.getByText(/1 P bis zur 1/)).toBeInTheDocument();
  });

  it("rechnet das Gesamtergebnis aus den Teilen", async () => {
    vi.spyOn(api, "rechne").mockResolvedValue({
      ohne_mep: { ...LEER, projekt: 77, teil2: 76, gesamt: 77, note: 2.7, fehlend: [] },
      mit_mep: null,
      stufe_ohne_mep: {
        ...STUFE,
        punkte: 77,
        note: 2.7,
        ganze_note: 3,
        grenzfall: false,
      },
      stufe_mit_mep: null,
      stufe_doku: null,
      stufe_praesentation: null,
    });
    zeige();

    await userEvent.type(await screen.findByLabelText(KATALOG.teil1_label), "80");
    await userEvent.type(screen.getByLabelText("Dokumentation"), "65");

    expect(await screen.findByText(/Gesamt: 77 P/)).toBeInTheDocument();
    expect(api.rechne).toHaveBeenLastCalledWith(
      expect.objectContaining({ teil1: 80, doku: 65, praesentation: null, mep: null }),
      expect.anything(),
    );
  });

  it("zeigt die Ablehnung des Backends wörtlich", async () => {
    vi.spyOn(api, "ladeNotenstufe").mockRejectedValue(
      new ApiError("Punkte gehen von 0 bis 100, nicht 120", 422),
    );
    zeige();

    await userEvent.type(await screen.findByLabelText("Punkte"), "120");

    expect(await screen.findByRole("alert")).toHaveTextContent("0 bis 100");
  });
});
