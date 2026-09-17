import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "./api/client";
import { App } from "./App";
import { mitAnmeldung } from "./testhilfen";

afterEach(() => {
  vi.restoreAllMocks();
});

const geraete: client.ModulEintrag = {
  id: "geraete",
  titel: "Geräte",
  pfad: "/geraete",
  beschreibung: "",
  icon: "kachel",
  version: "1.0.0",
  status: "bereit",
  zugang: "geschuetzt",
};

function zeige(pfad: string) {
  vi.spyOn(client, "fetchHealth").mockResolvedValue({
    status: "ok",
    version: "1.0.0",
    checks: { database: true },
  });
  vi.spyOn(client, "fetchModule").mockResolvedValue([geraete]);
  vi.spyOn(client, "fetchEndpunkte").mockResolvedValue([]);

  render(<MemoryRouter initialEntries={[pfad]}>{mitAnmeldung(<App />)}</MemoryRouter>);
}

describe("App", () => {
  it("zeigt unter / die Startseite", async () => {
    zeige("/");

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Übersicht",
    );
  });

  it("zeigt die Hülle mit Marke und Themenwechsel um jede Ansicht", async () => {
    zeige("/");

    expect(await screen.findByRole("link", { name: /HomePI/ })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("button", { name: /Erscheinungsbild/ })).toBeInTheDocument();
  });

  it("zeigt unter /modul/:id die Modulseite", async () => {
    zeige("/modul/geraete");

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Geräte");
  });

  it("führt einen unbekannten Pfad zur Startseite statt ins Leere", async () => {
    zeige("/voellig/woanders");

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Übersicht",
    );
  });
});
