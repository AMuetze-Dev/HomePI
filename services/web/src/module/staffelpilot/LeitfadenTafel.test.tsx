import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OBERFLAECHEN } from "../register";
import { LeitfadenTafel, SCHRITTE } from "./LeitfadenTafel";

describe("Leitfaden", () => {
  it("erklärt den Weg in sechs Schritten", () => {
    render(<LeitfadenTafel onWechsel={vi.fn()} />);

    const liste = screen.getByRole("list", { name: "Die sechs Schritte" });
    expect(
      within(liste)
        .getAllByRole("heading")
        .map((h) => h.textContent),
    ).toEqual([
      "Einrichten",
      "Regeln einstellen",
      "Prüflauf starten",
      "Befunde entscheiden",
      "Schreiben vorbereiten",
      "Abhaken",
    ]);
  });

  it("führt von jedem Schritt dorthin", async () => {
    const gehe = vi.fn();
    render(<LeitfadenTafel onWechsel={gehe} />);

    await userEvent.click(screen.getByRole("button", { name: "Zu den Regeln" }));

    expect(gehe).toHaveBeenCalledWith("regeln");
  });

  it("verweist nur auf Bereiche, die es gibt", () => {
    // Ein Verweis auf einen unbekannten Bereich landet stumm auf der
    // Übersicht - der Knopf täte dann nichts Erkennbares.
    const bereiche = OBERFLAECHEN.find((o) => o.id === "staffelpilot")?.unterseiten ?? [];
    const ids = bereiche.map((b) => b.id);

    for (const schritt of SCHRITTE) expect(ids).toContain(schritt.ziel);
  });

  it("steht selbst in der Navigation", () => {
    const bereiche = OBERFLAECHEN.find((o) => o.id === "staffelpilot")?.unterseiten ?? [];
    const leitfaden = bereiche.find((b) => b.id === "leitfaden");

    expect(leitfaden).toBeDefined();
    expect(leitfaden?.versteckt).not.toBe(true);
  });

  it("zeigt am Beispiel, wie man eine Frist lockert", () => {
    render(<LeitfadenTafel onWechsel={vi.fn()} />);

    expect(screen.getByText(/am selben Tag/)).toBeInTheDocument();
    expect(screen.getByText(/Kulanz/)).toBeInTheDocument();
  });

  it("sagt, was nicht von allein passiert", () => {
    render(<LeitfadenTafel onWechsel={vi.fn()} />);

    expect(screen.getByText(/Verschickt wird nichts/)).toBeInTheDocument();
  });
});
