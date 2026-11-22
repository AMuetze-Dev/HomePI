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

  it("führt auch ohne Konto zu den Einstellungen", async () => {
    // Das Farbschema gehört dem Gerät, nicht dem Konto. Wer noch keins hat,
    // soll trotzdem in den Dunkelmodus wechseln können.
    zeige(null);

    expect(await screen.findByRole("link", { name: "Einstellungen" })).toHaveAttribute(
      "href",
      "/einstellungen",
    );
  });

  it("führt auch von der Anmeldeseite zu den Einstellungen", async () => {
    // Gerade dort sitzt man nachts vor einem hellen Formular.
    zeige(null, "/anmelden");

    expect(
      await screen.findByRole("link", { name: "Einstellungen" }),
    ).toBeInTheDocument();
  });

  it("nennt die Einstellungen nicht ein zweites Mal, wenn man schon dort ist", async () => {
    // Der Pfad links sagt bereits "HomePI / Einstellungen". Am Telefon
    // stand das Wort sonst zweimal in einer Zeile.
    zeige(null, "/einstellungen");

    expect(await screen.findByRole("link", { name: "Anmelden" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Einstellungen" })).not.toBeInTheDocument();
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
