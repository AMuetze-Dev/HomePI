import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
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
    ...rest,
  };
}

function zeige(module: client.ModulEintrag[]) {
  vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);
  vi.spyOn(client, "fetchModule").mockResolvedValue(module);
  render(
    <MemoryRouter>
      <Start />
    </MemoryRouter>,
  );
}

describe("Startseite", () => {
  it("baut eine Kachel je Artefakt aus dem Manifest", async () => {
    zeige([modul(), modul({ id: "messwerte", titel: "Messwerte" })]);

    const liste = await screen.findByRole("list", { name: "Artefakte" });

    expect(within(liste).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Geräte" })).toHaveAttribute(
      "href",
      "/modul/geraete",
    );
  });

  it("zeigt im Erstzustand, was als Nächstes zu tun ist", async () => {
    // Eine leere Flaeche ohne Erklaerung laesst einen ratlos zurueck.
    zeige([]);

    expect(await screen.findByText(/homepi new/)).toBeInTheDocument();
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
    expect(screen.queryByRole("link", { name: "Kaputt" })).not.toBeInTheDocument();
  });

  it("zeigt zuerst einen Ladehinweis", () => {
    vi.spyOn(client, "fetchHealth").mockReturnValue(new Promise(() => {}));
    vi.spyOn(client, "fetchModule").mockReturnValue(new Promise(() => {}));

    render(
      <MemoryRouter>
        <Start />
      </MemoryRouter>,
    );

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });

  it("meldet, wenn das Manifest nicht abrufbar ist", async () => {
    vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);
    vi.spyOn(client, "fetchModule").mockRejectedValue(new Error("Gateway weg"));

    render(
      <MemoryRouter>
        <Start />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Gateway weg/)).toBeInTheDocument();
  });
});
