import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlanGrafik } from "./PlanGrafik";
import { spiel, tabelle } from "./testdaten";

function ko(rest: Parameters<typeof spiel>[0] = {}) {
  return spiel({ phase: "ko", gruppe: null, ...rest });
}

describe("Der Plan als Bild", () => {
  it("sagt, wenn es noch nichts zu zeigen gibt", () => {
    render(<PlanGrafik tabellen={[]} spiele={[]} />);

    expect(screen.getByText(/Noch kein Spielplan/)).toBeInTheDocument();
  });

  it("zeigt je Gruppe eine Karte mit Rangfolge und Begegnungen", () => {
    render(<PlanGrafik tabellen={[tabelle()]} spiele={[spiel()]} />);

    // "Anna" steht zweimal in der Karte: in der Rangfolge und in der
    // Begegnung darunter. Beides ist richtig, also beides pruefen.
    const gruppe = within(screen.getByRole("region", { name: "Gruppe A" }));
    expect(gruppe.getAllByText("Anna")).toHaveLength(2);
    expect(gruppe.getByText(/1 Sieg$/)).toBeInTheDocument();
    expect(gruppe.getByText("gegen")).toBeInTheDocument();
  });

  it("nennt einen offenen Gleichstand beim Namen", () => {
    /* Ohne diesen Satz stünde da eine Tabelle mit zwei Zweiten und keine
       Erklärung, warum noch ein Spiel kommt. */
    render(
      <PlanGrafik
        tabellen={[tabelle({ entscheidung_offen: ["Anna", "Bernd"] })]}
        spiele={[]}
      />,
    );

    expect(
      screen.getByText(/Punktgleich an der Grenze: Anna und Bernd/),
    ).toBeInTheDocument();
  });

  it("zeichnet das Raster Runde für Runde", () => {
    render(
      <PlanGrafik
        tabellen={[]}
        spiele={[
          ko({ id: "h1", nummer: 1, runde: 1, bezeichnung: "Halbfinale" }),
          ko({
            id: "h2",
            nummer: 2,
            runde: 1,
            bezeichnung: "Halbfinale",
            heim: "Cem",
            gast: "Dana",
            heim_id: "p3",
            gast_id: "p4",
          }),
          ko({
            id: "f1",
            nummer: 3,
            runde: 2,
            bezeichnung: "Endspiel",
            heim: null,
            gast: null,
            heim_id: null,
            gast_id: null,
            heim_herkunft: "Sieger aus Spiel 1",
            gast_herkunft: "Sieger aus Spiel 2",
          }),
        ]}
      />,
    );

    const raster = within(screen.getByRole("group", { name: "KO-Raster" }));
    expect(raster.getAllByRole("heading", { name: "Halbfinale" })).toHaveLength(1);
    expect(raster.getByRole("heading", { name: "Endspiel" })).toBeInTheDocument();
    expect(raster.getByText("Sieger aus Spiel 1")).toBeInTheDocument();
  });

  it("hebt im Raster hervor, wer weiter ist", () => {
    render(
      <PlanGrafik
        tabellen={[]}
        spiele={[ko({ zustand: "beendet", sieger_id: "p1", bezeichnung: "Endspiel" })]}
      />,
    );

    const raster = within(screen.getByRole("group", { name: "KO-Raster" }));
    expect(raster.getByText("weiter")).toBeInTheDocument();
  });

  it("nennt ein Freilos beim Namen statt eine Leerstelle zu zeigen", () => {
    render(
      <PlanGrafik
        tabellen={[tabelle()]}
        spiele={[
          spiel({
            gast: null,
            gast_id: null,
            gast_herkunft: "Freilos",
            freilos: true,
            zustand: "beendet",
            sieger_id: "p1",
          }),
        ]}
      />,
    );

    expect(screen.getByText("Freilos")).toBeInTheDocument();
  });
});
