import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Tabelle, Tabellenzeile } from "./api";
import { TabellenTafel } from "./TabellenTafel";

function zeile(rest: Partial<Tabellenzeile> = {}): Tabellenzeile {
  return {
    platz: 1,
    teilnehmer_id: "p1",
    teilnehmer: "Anna",
    spiele: 3,
    siege: 3,
    niederlagen: 0,
    punkte: 6,
    saetze_fuer: 9,
    saetze_gegen: 2,
    baelle_fuer: 110,
    baelle_gegen: 70,
    satzdifferenz: 7,
    balldifferenz: 40,
    ...rest,
  };
}

const GRUPPE_A: Tabelle = {
  titel: "Gruppe A",
  zeilen: [
    zeile(),
    zeile({ platz: 2, teilnehmer_id: "p2", teilnehmer: "Bernd", punkte: 4 }),
  ],
};

describe("Tabellen", () => {
  it("sagt, dass es noch keine gibt", () => {
    render(<TabellenTafel tabellen={[]} />);

    expect(screen.getByText(/Noch keine Tabelle/)).toBeInTheDocument();
  });

  it("zeigt je Gruppe eine Tabelle mit ihrem Namen", () => {
    render(
      <TabellenTafel tabellen={[GRUPPE_A, { titel: "Gruppe B", zeilen: [zeile()] }]} />,
    );

    expect(screen.getByText("Gruppe A")).toBeInTheDocument();
    expect(screen.getByText("Gruppe B")).toBeInTheDocument();
    expect(screen.getAllByRole("table")).toHaveLength(2);
  });

  it("nennt Platz, Punkte, Sätze und Bälle in einer Zeile", () => {
    render(<TabellenTafel tabellen={[GRUPPE_A]} />);

    const anna = within(screen.getByRole("row", { name: /Anna/ }));
    expect(anna.getByText("9:2")).toBeInTheDocument();
    expect(anna.getByText("110:70")).toBeInTheDocument();
    expect(anna.getByText("6")).toBeInTheDocument();
  });

  it("behält die Reihenfolge des Backends", () => {
    /* Sortiert wird dort - Punkte, direkter Vergleich, Satzdifferenz. Hier
       noch einmal zu sortieren hiesse, die Regel zweimal zu haben, und eine
       der beiden waere irgendwann anderer Meinung. */
    render(
      <TabellenTafel
        tabellen={[
          {
            titel: "Tabelle",
            zeilen: [
              zeile({ platz: 1, teilnehmer: "Zacharias", punkte: 6 }),
              zeile({ platz: 2, teilnehmer: "Anna", punkte: 6 }),
            ],
          },
        ]}
      />,
    );

    const namen = screen.getAllByRole("rowheader").map((zelle) => zelle.textContent);
    expect(namen).toEqual(["Zacharias", "Anna"]);
  });
});
