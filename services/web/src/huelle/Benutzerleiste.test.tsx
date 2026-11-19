import { render, screen, waitFor } from "@testing-library/react";
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
  it("führt mit dem Kürzel zu den Einstellungen", async () => {
    // Der volle Name stand hier vorher und wurde bei jedem zweiten Konto
    // abgeschnitten. Ausgeschrieben steht er dort, wohin das Kuerzel fuehrt.
    zeige(TESTBENUTZER);

    const verweis = await screen.findByRole("link", { name: /Prüfer/ });

    expect(verweis).toHaveAttribute("href", "/einstellungen");
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
    expect(screen.queryByRole("link", { name: /Prüfer/ })).not.toBeInTheDocument();
  });

  it("trägt das Abmelden nicht mehr in der Kopfzeile", async () => {
    // Es ist die seltenste Handlung dieser Oberflaeche und stand als Knopf
    // dauerhaft neben einer, die man staendig braucht. Sein Platz ist die
    // Navigation.
    zeige(TESTBENUTZER);
    await screen.findByRole("link", { name: /Prüfer/ });

    expect(screen.queryByRole("button", { name: "Abmelden" })).not.toBeInTheDocument();
  });
});
