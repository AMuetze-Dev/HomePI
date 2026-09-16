import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { GeraeteSeite } from "./GeraeteSeite";

function geraet(rest: Partial<api.Geraet> = {}): api.Geraet {
  return {
    id: "1",
    name: "Stehlampe",
    raum: "Wohnzimmer",
    zustand: "bereit",
    eingeschaltet: false,
    ...rest,
  };
}

function uebersicht(rest: Partial<api.Zusammenfassung> = {}): api.Zusammenfassung {
  return {
    anzahl: 1,
    eingeschaltet: 0,
    in_wartung: 0,
    raeume: { Wohnzimmer: 1 },
    ...rest,
  };
}

function mitDaten(geraete: api.Geraet[], zusammenfassung = uebersicht()) {
  vi.spyOn(api, "ladeGeraete").mockResolvedValue(geraete);
  vi.spyOn(api, "ladeZusammenfassung").mockResolvedValue(zusammenfassung);
}

beforeEach(() => {
  vi.spyOn(api, "legeGeraetAn").mockResolvedValue(geraet());
  vi.spyOn(api, "schalteGeraet").mockResolvedValue(geraet({ eingeschaltet: true }));
  vi.spyOn(api, "entferneGeraet").mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Geräteseite", () => {
  it("zeigt Überblick und Liste", async () => {
    mitDaten([geraet()]);

    render(<GeraeteSeite />);

    expect(
      await screen.findByText(/1 Geräte, davon 0 eingeschaltet/),
    ).toBeInTheDocument();
    const tabelle = screen.getByRole("table");
    expect(within(tabelle).getByText("Stehlampe")).toBeInTheDocument();
  });

  it("nennt die Wartungsgeräte nur, wenn es welche gibt", async () => {
    mitDaten([geraet()], uebersicht({ in_wartung: 2 }));

    render(<GeraeteSeite />);

    expect(await screen.findByText(/2 in Wartung/)).toBeInTheDocument();
  });

  it("sagt im Erstzustand, was zu tun ist", async () => {
    mitDaten([], uebersicht({ anzahl: 0, raeume: {} }));

    render(<GeraeteSeite />);

    expect(await screen.findByText(/Noch kein Gerät angelegt/)).toBeInTheDocument();
  });

  it("schaltet ein Gerät und lädt danach neu", async () => {
    mitDaten([geraet()]);
    render(<GeraeteSeite />);
    const knopf = await screen.findByRole("button", { name: /Stehlampe einschalten/ });

    await userEvent.click(knopf);

    expect(api.schalteGeraet).toHaveBeenCalledWith("1", true);
    await waitFor(() => expect(api.ladeGeraete).toHaveBeenCalledTimes(2));
  });

  it("sperrt den Schaltknopf bei Wartung", async () => {
    // Die Regel steht im Backend; die Oberfläche soll den Fehler gar nicht
    // erst auslösen lassen.
    mitDaten([geraet({ zustand: "wartung" })]);

    render(<GeraeteSeite />);

    expect(await screen.findByRole("button", { name: /einschalten/ })).toBeDisabled();
  });

  it("entfernt ein Gerät", async () => {
    mitDaten([geraet()]);
    render(<GeraeteSeite />);

    await userEvent.click(await screen.findByRole("button", { name: /entfernen/i }));

    expect(api.entferneGeraet).toHaveBeenCalledWith("1");
  });

  it("legt ein Gerät an und leert danach das Formular", async () => {
    mitDaten([]);
    render(<GeraeteSeite />);

    await userEvent.type(await screen.findByLabelText("Name"), "Deckenlampe");
    await userEvent.type(screen.getByLabelText("Raum"), "Küche");
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    expect(api.legeGeraetAn).toHaveBeenCalledWith({ name: "Deckenlampe", raum: "Küche" });
    await waitFor(() => expect(screen.getByLabelText("Name")).toHaveValue(""));
  });

  it("behält die Eingabe, wenn das Anlegen fehlschlägt", async () => {
    // Sonst tippt man nach einem doppelten Namen alles neu.
    mitDaten([]);
    vi.spyOn(api, "legeGeraetAn").mockRejectedValue(
      new ApiError("Ein Gerät namens 'Stehlampe' existiert bereits", 409),
    );
    render(<GeraeteSeite />);

    await userEvent.type(await screen.findByLabelText("Name"), "Stehlampe");
    await userEvent.type(screen.getByLabelText("Raum"), "Bad");
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/existiert bereits/);
    expect(screen.getByLabelText("Name")).toHaveValue("Stehlampe");
    expect(screen.getByLabelText("Raum")).toHaveValue("Bad");
  });

  it("zeigt die Meldung des Backends, nicht nur den Statuscode", async () => {
    mitDaten([geraet({ zustand: "bereit" })]);
    vi.spyOn(api, "schalteGeraet").mockRejectedValue(
      new ApiError("Das Gerät steht auf Wartung", 409),
    );
    render(<GeraeteSeite />);

    await userEvent.click(await screen.findByRole("button", { name: /einschalten/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Das Gerät steht auf Wartung",
    );
  });

  it("ersetzt die Liste nicht durch eine Fehlerseite, wenn eine Aktion scheitert", async () => {
    mitDaten([geraet()]);
    vi.spyOn(api, "entferneGeraet").mockRejectedValue(new ApiError("Geht nicht", 500));
    render(<GeraeteSeite />);

    await userEvent.click(await screen.findByRole("button", { name: /entfernen/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("sperrt den Absendeknopf, solange ein Feld leer ist", async () => {
    mitDaten([]);
    render(<GeraeteSeite />);

    const knopf = await screen.findByRole("button", { name: "Anlegen" });
    expect(knopf).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Name"), "X");
    expect(knopf).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Raum"), "Y");
    expect(knopf).toBeEnabled();
  });

  it("meldet, wenn die Liste gar nicht geladen werden kann", async () => {
    vi.spyOn(api, "ladeGeraete").mockRejectedValue(new ApiError("Gateway weg", 503));
    vi.spyOn(api, "ladeZusammenfassung").mockRejectedValue(
      new ApiError("Gateway weg", 503),
    );

    render(<GeraeteSeite />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway weg");
  });
});
