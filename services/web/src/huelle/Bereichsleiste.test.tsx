import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { sichtbareUnterseiten, unterseitenFuer } from "../module/register";
import { Bereichsleiste } from "./Bereichsleiste";

/**
 * Bewusst OHNE <Routes> darum herum - genau so steht die Leiste in der
 * Hülle. Der Pfad kommt deshalb aus useMatch und nicht aus useParams.
 */
function zeige(pfad: string) {
  render(
    <MemoryRouter initialEntries={[pfad]}>
      <Bereichsleiste />
    </MemoryRouter>,
  );
}

describe("Bereichsleiste", () => {
  it("führt zu jedem sichtbaren Bereich des geöffneten Artefakts", () => {
    zeige("/modul/staffelpilot/spiele");

    const leiste = screen.getByRole("navigation", { name: "Bereiche" });

    // Die Zahl kommt aus dem Register und nicht aus dieser Datei: sonst
    // scheitert der Test bei jedem neuen Bereich, ohne dass an der Leiste
    // etwas falsch waere.
    expect(within(leiste).getAllByRole("link")).toHaveLength(
      sichtbareUnterseiten("staffelpilot").length,
    );
    expect(within(leiste).getByRole("link", { name: "Spielprüfung" })).toHaveAttribute(
      "href",
      "/modul/staffelpilot/spiele",
    );
  });

  it("lässt versteckte Unterseiten weg", () => {
    // Eine versteckte Unterseite ist eine echte Adresse, aber kein Reiter -
    // die Einrichtung läuft man einmal durch und danach nie wieder.
    expect(unterseitenFuer("staffelpilot").length).toBeGreaterThan(
      sichtbareUnterseiten("staffelpilot").length,
    );

    zeige("/modul/staffelpilot/spiele");

    expect(screen.queryByRole("link", { name: "Einrichtung" })).not.toBeInTheDocument();
  });

  it("markiert den Bereich, auf dem man steht", () => {
    zeige("/modul/staffelpilot/regeln");

    const hier = screen.getByRole("link", { name: "Regeln" });

    expect(hier).toHaveAttribute("aria-current", "page");
  });

  it("zeigt nichts, wo es nichts zu wechseln gibt", () => {
    // "geraete" hat eine eigene Oberflaeche, aber keine zweite Ebene. Eine
    // leere Leiste waere ein Streifen, der aussieht, als fehle etwas.
    zeige("/modul/geraete");

    expect(
      screen.queryByRole("navigation", { name: "Bereiche" }),
    ).not.toBeInTheDocument();
  });

  it("zeigt auch auf der Startseite nichts", () => {
    zeige("/");

    expect(
      screen.queryByRole("navigation", { name: "Bereiche" }),
    ).not.toBeInTheDocument();
  });
});
