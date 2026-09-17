import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import * as api from "../api/einrichtung";
import { mitAnmeldung } from "../testhilfen";
import { Einrichtungstor } from "./Einrichtungstor";

afterEach(() => {
  vi.restoreAllMocks();
});

/**
 * Reihenfolge ist wichtig: `mitAnmeldung` setzt selbst eine Vorgabe für
 * `holeStand` - hier soll aber genau diese Antwort die Frage des Tests sein.
 * Deshalb erst die Hülle bauen, dann die Antwort setzen, dann rendern.
 */
function zeige(antwort: () => void) {
  const element = (
    <MemoryRouter>
      {mitAnmeldung(<Einrichtungstor>Die Anwendung</Einrichtungstor>, null)}
    </MemoryRouter>
  );
  antwort();
  render(element);
}

describe("Einrichtungstor", () => {
  it("lässt die Anwendung durch, wenn schon eingerichtet ist", async () => {
    zeige(() => void vi.spyOn(api, "holeStand").mockResolvedValue({ noetig: false }));

    expect(await screen.findByText("Die Anwendung")).toBeInTheDocument();
  });

  it("zeigt die Maske, solange es keinen Verwalter gibt", async () => {
    zeige(() => void vi.spyOn(api, "holeStand").mockResolvedValue({ noetig: true }));

    expect(
      await screen.findByRole("heading", { name: "Ersteinrichtung" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Die Anwendung")).not.toBeInTheDocument();
  });

  it("zeigt zuerst einen Platzhalter", () => {
    // Sonst blitzt die Einrichtungsmaske bei jedem Seitenaufruf kurz auf.
    zeige(() => void vi.spyOn(api, "holeStand").mockReturnValue(new Promise(() => {})));

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("Die Anwendung")).not.toBeInTheDocument();
  });

  it("nimmt bei einem nicht erreichbaren Gateway 'nicht nötig' an", async () => {
    // Einem Besucher eine Einrichtungsmaske vorzusetzen, die er ohnehin nicht
    // ausfüllen kann, wäre die schlechtere Antwort auf einen Netzfehler.
    zeige(
      () =>
        void vi
          .spyOn(api, "holeStand")
          .mockRejectedValue(new ApiError("Gateway weg", 503)),
    );

    expect(await screen.findByText("Die Anwendung")).toBeInTheDocument();
  });
});
