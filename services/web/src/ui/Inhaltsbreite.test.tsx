import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Inhaltsbreite } from "./Inhaltsbreite";

describe("Inhaltsbreite", () => {
  it("nimmt ohne Angabe die mittlere Spalte", () => {
    render(<Inhaltsbreite>Inhalt</Inhaltsbreite>);

    expect(screen.getByText("Inhalt").className).toMatch(/normal/);
  });

  it("gibt jeder Stufe eine eigene Klasse", () => {
    // Vier Stufen, vier verschiedene Klassen - sonst wäre eine davon
    // wirkungslos, ohne dass es jemandem auffiele.
    const klassen = (["text", "normal", "weit", "voll"] as const).map((breite) => {
      const { container, unmount } = render(
        <Inhaltsbreite breite={breite}>x</Inhaltsbreite>,
      );
      const klasse = (container.firstElementChild as HTMLElement).className;
      unmount();
      return klasse;
    });

    expect(new Set(klassen).size).toBe(4);
  });
});
