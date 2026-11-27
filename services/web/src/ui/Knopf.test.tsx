import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Knopf } from "./Knopf";

describe("Ein gesperrter Knopf", () => {
  it("sagt beim Darüberfahren, warum er gesperrt ist", () => {
    // Ein blasser Knopf allein lässt raten, was fehlt.
    render(
      <Knopf disabled grund="Erst einen Namen eintragen">
        Eintragen
      </Knopf>,
    );

    expect(screen.getByTitle("Erst einen Namen eintragen")).toContainElement(
      screen.getByRole("button", { name: "Eintragen" }),
    );
  });

  it("schweigt, sobald er geht", () => {
    // Ein Grund an einem Knopf, der funktioniert, wäre eine falsche Auskunft.
    render(<Knopf grund="Erst einen Namen eintragen">Eintragen</Knopf>);

    expect(screen.queryByTitle("Erst einen Namen eintragen")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eintragen" })).toBeEnabled();
  });
});
