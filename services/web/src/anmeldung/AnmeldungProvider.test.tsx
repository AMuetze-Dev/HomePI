import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/anmeldung";
import { AnmeldungProvider } from "./AnmeldungProvider";
import { useAnmeldung } from "./kontext";

afterEach(() => {
  vi.restoreAllMocks();
});

const BENUTZER: api.Benutzer = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "leiter",
  anzeigename: "Staffelleiter",
  rechte: { staffelpilot: "nutzer" },
  passwort_wechseln: false,
};

function Probe() {
  const { zustand, benutzer, darf, abmelden } = useAnmeldung();
  return (
    <div>
      <p data-testid="zustand">{zustand}</p>
      <p data-testid="name">{benutzer?.name ?? "-"}</p>
      <p data-testid="liest">{String(darf("staffelpilot"))}</p>
      <p data-testid="verwaltet">{String(darf("staffelpilot", "verwalter"))}</p>
      <p data-testid="fremd">{String(darf("geraete"))}</p>
      <button onClick={() => void abmelden()}>Abmelden</button>
    </div>
  );
}

function zeige(benutzer: api.Benutzer | null) {
  vi.spyOn(api, "holeIch").mockResolvedValue(benutzer);
  render(
    <AnmeldungProvider>
      <Probe />
    </AnmeldungProvider>,
  );
}

describe("Anmeldekontext", () => {
  it("fragt beim Start, wer angemeldet ist", async () => {
    zeige(BENUTZER);

    await waitFor(() =>
      expect(screen.getByTestId("zustand")).toHaveTextContent("angemeldet"),
    );
    expect(screen.getByTestId("name")).toHaveTextContent("leiter");
  });

  it("unterscheidet 'weiß ich noch nicht' von 'niemand'", () => {
    // Ohne diese Unterscheidung blitzt bei jedem Seitenaufruf kurz das
    // Anmeldeformular auf, obwohl der Benutzer angemeldet ist.
    vi.spyOn(api, "holeIch").mockReturnValue(new Promise(() => {}));
    render(
      <AnmeldungProvider>
        <Probe />
      </AnmeldungProvider>,
    );

    expect(screen.getByTestId("zustand")).toHaveTextContent("laedt");
  });

  it("gilt als abgemeldet, wenn das Gateway nicht antwortet", async () => {
    vi.spyOn(api, "holeIch").mockRejectedValue(new Error("Gateway weg"));
    render(
      <AnmeldungProvider>
        <Probe />
      </AnmeldungProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("zustand")).toHaveTextContent("abgemeldet"),
    );
  });

  describe("darf", () => {
    it("gilt nur für das eigene Artefakt", async () => {
      // Der Kern des Rechtemodells: es gibt keinen globalen Administrator.
      zeige(BENUTZER);
      await waitFor(() =>
        expect(screen.getByTestId("zustand")).toHaveTextContent("angemeldet"),
      );

      expect(screen.getByTestId("liest")).toHaveTextContent("true");
      expect(screen.getByTestId("fremd")).toHaveTextContent("false");
    });

    it("achtet auf die Rangfolge der Rollen", async () => {
      zeige(BENUTZER);
      await waitFor(() =>
        expect(screen.getByTestId("zustand")).toHaveTextContent("angemeldet"),
      );

      expect(screen.getByTestId("verwaltet")).toHaveTextContent("false");
    });

    it("verneint alles, solange niemand angemeldet ist", async () => {
      zeige(null);
      await waitFor(() =>
        expect(screen.getByTestId("zustand")).toHaveTextContent("abgemeldet"),
      );

      expect(screen.getByTestId("liest")).toHaveTextContent("false");
    });
  });

  describe("abmelden", () => {
    it("meldet ab", async () => {
      const abmelden = vi.spyOn(api, "abmelden").mockResolvedValue(undefined);
      zeige(BENUTZER);
      await waitFor(() =>
        expect(screen.getByTestId("zustand")).toHaveTextContent("angemeldet"),
      );

      await userEvent.click(screen.getByRole("button", { name: "Abmelden" }));

      expect(abmelden).toHaveBeenCalled();
      expect(screen.getByTestId("zustand")).toHaveTextContent("abgemeldet");
    });

    it("meldet auch dann ab, wenn der Aufruf scheitert", async () => {
      // Wer abmelden sagt, soll nicht angemeldet bleiben, weil das Netz
      // gerade weg war.
      vi.spyOn(api, "abmelden").mockRejectedValue(new Error("Netz weg"));
      zeige(BENUTZER);
      await waitFor(() =>
        expect(screen.getByTestId("zustand")).toHaveTextContent("angemeldet"),
      );

      await userEvent.click(screen.getByRole("button", { name: "Abmelden" }));

      await waitFor(() =>
        expect(screen.getByTestId("zustand")).toHaveTextContent("abgemeldet"),
      );
    });
  });

  it("verlangt einen Provider darüber", () => {
    // Sonst scheitert die Ansicht irgendwo tiefer an undefined.
    const still = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<Probe />)).toThrow(/AnmeldungProvider/);

    still.mockRestore();
  });
});
