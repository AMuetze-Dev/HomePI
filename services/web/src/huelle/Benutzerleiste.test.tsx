import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/anmeldung";
import { AnmeldungProvider } from "../anmeldung/AnmeldungProvider";
import { TESTBENUTZER, mitAnmeldung } from "../testhilfen";
import { Benutzerleiste } from "./Benutzerleiste";

afterEach(() => {
  vi.restoreAllMocks();
});

function zeige(benutzer: api.Benutzer | null, pfad = "/") {
  render(
    <MemoryRouter initialEntries={[pfad]}>
      {mitAnmeldung(<Benutzerleiste />, benutzer)}
    </MemoryRouter>,
  );
}

describe("Benutzerleiste", () => {
  it("zeigt den Anzeigenamen und einen Weg hinaus", async () => {
    zeige(TESTBENUTZER);

    expect(await screen.findByText("Prüfer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abmelden" })).toBeInTheDocument();
  });

  it("bietet den Weg hinein, wenn niemand angemeldet ist", async () => {
    zeige(null);

    expect(await screen.findByRole("link", { name: "Anmelden" })).toHaveAttribute(
      "href",
      "/anmelden",
    );
  });

  it("wirbt auf der Anmeldeseite nicht für die Anmeldeseite", async () => {
    zeige(null, "/anmelden");

    await waitFor(() =>
      expect(screen.queryByRole("link", { name: "Anmelden" })).not.toBeInTheDocument(),
    );
  });

  it("zeigt nichts, solange unklar ist, wer angemeldet ist", () => {
    // Sonst blitzt bei jedem Seitenaufruf kurz "Anmelden" auf.
    vi.spyOn(api, "holeIch").mockReturnValue(new Promise(() => {}));
    render(
      <MemoryRouter>
        <AnmeldungProvider>
          <Benutzerleiste />
        </AnmeldungProvider>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: "Anmelden" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Abmelden" })).not.toBeInTheDocument();
  });

  it("meldet ab", async () => {
    const abmelden = vi.spyOn(api, "abmelden").mockResolvedValue(undefined);
    zeige(TESTBENUTZER);
    const knopf = await screen.findByRole("button", { name: "Abmelden" });

    await userEvent.click(knopf);

    expect(abmelden).toHaveBeenCalled();
    expect(await screen.findByRole("link", { name: "Anmelden" })).toBeInTheDocument();
  });
});
