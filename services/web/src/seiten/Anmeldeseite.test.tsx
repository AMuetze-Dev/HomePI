import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type * as api from "../api/anmeldung";
import { TESTBENUTZER, mitAnmeldung } from "../testhilfen";
import { Anmeldeseite } from "./Anmeldeseite";

afterEach(() => {
  vi.restoreAllMocks();
});

function zeige(benutzer: api.Benutzer | null) {
  render(
    <MemoryRouter initialEntries={["/anmelden"]}>
      {mitAnmeldung(
        <Routes>
          <Route path="/anmelden" element={<Anmeldeseite />} />
          <Route path="/" element={<p>Übersicht</p>} />
        </Routes>,
        benutzer,
      )}
    </MemoryRouter>,
  );
}

describe("Anmeldeseite", () => {
  it("zeigt das Formular, wenn niemand angemeldet ist", async () => {
    zeige(null);

    expect(await screen.findByRole("heading", { name: "Anmelden" })).toBeInTheDocument();
  });

  it("schickt einen Angemeldeten zurück zur Übersicht", async () => {
    // Sonst landet man nach dem Anmelden wieder auf dem Anmeldeformular.
    zeige(TESTBENUTZER);

    await waitFor(() => expect(screen.getByText("Übersicht")).toBeInTheDocument());
  });
});
