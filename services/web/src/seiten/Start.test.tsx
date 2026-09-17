import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import { mitAnmeldung } from "../testhilfen";
import { Start } from "./Start";

afterEach(() => {
  vi.restoreAllMocks();
});

const gesund: client.Health = {
  status: "ok",
  version: "1.0.0",
  checks: { database: true },
};

function modul(rest: Partial<client.ModulEintrag> = {}): client.ModulEintrag {
  return {
    id: "geraete",
    titel: "Geräte",
    pfad: "/geraete",
    beschreibung: "",
    icon: "kachel",
    version: "1.0.0",
    status: "bereit",
    zugang: "geschuetzt",
    ...rest,
  };
}

function zeige(module: client.ModulEintrag[], angemeldet = true) {
  vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);
  vi.spyOn(client, "fetchModule").mockResolvedValue(module);
  render(
    <MemoryRouter>{mitAnmeldung(<Start />, angemeldet ? undefined : null)}</MemoryRouter>,
  );
}

describe("Startseite", () => {
  it("baut eine Kachel je Artefakt aus dem Manifest", async () => {
    zeige([modul(), modul({ id: "messwerte", titel: "Messwerte" })]);

    const liste = await screen.findByRole("list", { name: "Artefakte" });

    expect(within(liste).getAllByRole("listitem")).toHaveLength(2);
    // Der Verweis umschliesst die ganze Kachel; sein zugaenglicher Name ist
    // deshalb der Kachelinhalt, nicht nur die Ueberschrift.
    expect(screen.getByRole("link", { name: /Geräte/ })).toHaveAttribute(
      "href",
      "/modul/geraete",
    );
  });

  it("zeigt im Erstzustand, was als Nächstes zu tun ist", async () => {
    // Eine leere Flaeche ohne Erklaerung laesst einen ratlos zurueck.
    zeige([]);

    expect(await screen.findByText(/homepi new/)).toBeInTheDocument();
  });

  it("bietet die Anmeldung an, statt 'kein Artefakt' zu behaupten", async () => {
    // Abgemeldet ist die Liste berechtigterweise leer. Der Hinweis, man solle
    // ein Artefakt anlegen, waere hier schlicht die falsche Auskunft.
    zeige([], false);

    expect(await screen.findByRole("heading", { name: "Anmelden" })).toBeInTheDocument();
    expect(screen.queryByText(/homepi new/)).not.toBeInTheDocument();
  });

  it("zeigt oeffentliche Artefakte auch ohne Anmeldung", async () => {
    zeige([modul({ id: "start", titel: "Start", zugang: "oeffentlich" })], false);

    expect(await screen.findByRole("list", { name: "Artefakte" })).toBeInTheDocument();
  });

  it("benennt ein defektes Artefakt, statt es wegzulassen", async () => {
    zeige([
      modul({
        id: "kaputt",
        titel: "Kaputt",
        status: "fehler",
        beschreibung: "ImportError",
      }),
    ]);

    const meldung = await screen.findByRole("alert");

    expect(meldung).toHaveTextContent(/ImportError/);
    // Eine kaputte Kachel darf nicht anklickbar sein
    expect(screen.queryByRole("link", { name: /Kaputt/ })).not.toBeInTheDocument();
    expect(screen.getByText("Fehler")).toBeInTheDocument();
  });

  it("zeigt zuerst einen Ladehinweis", () => {
    vi.spyOn(client, "fetchHealth").mockReturnValue(new Promise(() => {}));
    vi.spyOn(client, "fetchModule").mockReturnValue(new Promise(() => {}));

    render(<MemoryRouter>{mitAnmeldung(<Start />)}</MemoryRouter>);

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });

  it("meldet, wenn das Manifest nicht abrufbar ist", async () => {
    vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);
    vi.spyOn(client, "fetchModule").mockRejectedValue(new Error("Gateway weg"));

    render(<MemoryRouter>{mitAnmeldung(<Start />)}</MemoryRouter>);

    expect(await screen.findByText(/Gateway weg/)).toBeInTheDocument();
  });
});
