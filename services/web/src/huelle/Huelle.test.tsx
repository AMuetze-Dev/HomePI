import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mitAnmeldung } from "../testhilfen";
import { Huelle } from "./Huelle";

afterEach(() => {
  vi.restoreAllMocks();
});

function zeige(schlicht = false) {
  render(
    <MemoryRouter>
      {mitAnmeldung(<Huelle schlicht={schlicht}>Inhalt</Huelle>, null)}
    </MemoryRouter>,
  );
}

describe("Hülle", () => {
  it("rahmt den Inhalt mit Marke und Themenwechsel", async () => {
    zeige();

    expect(await screen.findByRole("link", { name: /HomePI/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Erscheinungsbild/ })).toBeInTheDocument();
    expect(screen.getByText("Inhalt")).toBeInTheDocument();
  });

  it("bietet gewöhnlich den Weg zur Anmeldung", async () => {
    zeige();

    expect(await screen.findByRole("link", { name: "Anmelden" })).toBeInTheDocument();
  });

  it("lässt ihn in der schlichten Fassung weg", async () => {
    // Waehrend der Ersteinrichtung gibt es noch kein Konto - ein "Anmelden"
    // daneben waere eine Einladung ins Leere.
    zeige(true);

    expect(await screen.findByText("Inhalt")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Anmelden" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Erscheinungsbild/ })).toBeInTheDocument();
  });
});
