import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("sagt vorgelesen, wer weiter ist - sichtbar traegt das die Zeile", () => {
    // Sichtbar ist der Sieger halbfett und hat einen Strich an der Kante,
    // der Verlierer tritt zurueck. Ein Etikett "weiter" dahinter sagte
    // dasselbe ein zweites Mal, und zwar in der Haelfte aller Zeilen des
    // Rasters. Schriftschnitt und Strich kommen bei einem Screenreader
    // aber nicht an - deshalb bleibt das Wort fuer ihn stehen.
    render(
      <PlanGrafik
        tabellen={[]}
        spiele={[ko({ zustand: "beendet", sieger_id: "p1", bezeichnung: "Endspiel" })]}
      />,
    );

    const raster = within(screen.getByRole("group", { name: "KO-Raster" }));
    const wort = raster.getByText("weiter");

    expect(wort).toHaveClass("nur-vorlesen");
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

describe("Verweise im Raster", () => {
  /* Oben das Halbfinale (Spiel 3), unten die Verliererrunde, die dessen
     Verlierer auffaengt - zwei Karten, ein Verweis dazwischen. */
  const spiele = [
    ko({ id: "a", nummer: 3, runde: 1, bezeichnung: "Halbfinale" }),
    ko({
      id: "b",
      nummer: 4,
      runde: 1,
      bezeichnung: "Halbfinale",
      heim: "Cem",
      gast: "Dana",
      heim_id: "p3",
      gast_id: "p4",
    }),
    spiel({
      id: "v",
      nummer: 5,
      phase: "ko_verlierer",
      gruppe: null,
      runde: 1,
      bezeichnung: "Verliererrunde 1",
      heim: null,
      gast: null,
      heim_id: null,
      gast_id: null,
      heim_herkunft: "Verlierer aus Spiel 3",
      gast_herkunft: "Verlierer aus Spiel 4",
      heim_aus_spiel: 3,
      gast_aus_spiel: 4,
    }),
  ];

  it("zeigt an jeder Paarung ihre Nummer", () => {
    // Sonst verweist "Verlierer aus Spiel 3" auf etwas, das nirgends steht -
    // und an der Wand im Saal hovert niemand.
    render(<PlanGrafik tabellen={[]} spiele={spiele} />);

    const oben = within(screen.getByRole("group", { name: "KO-Raster" }));
    expect(oben.getByRole("listitem", { name: "Spiel 3" })).toHaveTextContent("3");
  });

  it("hebt beim Zeigen auf die Herkunft das Spiel hervor, aus dem sie kommt", async () => {
    const benutzer = userEvent.setup();
    render(<PlanGrafik tabellen={[]} spiele={spiele} />);
    const verweis = screen.getByRole("button", { name: "Verlierer aus Spiel 3" });
    const ziel = screen.getByRole("listitem", { name: "Spiel 3" });

    expect(ziel).not.toHaveAttribute("aria-current");
    await benutzer.hover(verweis);
    expect(ziel).toHaveAttribute("aria-current", "true");
    // Nur das eine: Spiel 4 bleibt, wie es ist.
    expect(screen.getByRole("listitem", { name: "Spiel 4" })).not.toHaveAttribute(
      "aria-current",
    );

    await benutzer.unhover(verweis);
    expect(ziel).not.toHaveAttribute("aria-current");
  });

  it("haelt die Hervorhebung nach einem Tippen fest, bis man wieder tippt", async () => {
    // Am Telefon gibt es kein Zeigen - dort ist Tippen die einzige Geste,
    // und die Hervorhebung muss stehen bleiben, waehrend man hinsieht.
    const benutzer = userEvent.setup();
    render(<PlanGrafik tabellen={[]} spiele={spiele} />);
    const verweis = screen.getByRole("button", { name: "Verlierer aus Spiel 3" });
    const ziel = screen.getByRole("listitem", { name: "Spiel 3" });

    await benutzer.click(verweis);
    await benutzer.unhover(verweis);
    expect(ziel).toHaveAttribute("aria-current", "true");
    expect(verweis).toHaveAttribute("aria-pressed", "true");

    await benutzer.click(verweis);
    await benutzer.unhover(verweis);
    expect(ziel).not.toHaveAttribute("aria-current");
  });

  it("macht einen Namen, der schon feststeht, nicht zum Knopf", () => {
    // Steht der Name da, ist die Frage "wer kommt hierher" beantwortet.
    render(
      <PlanGrafik
        tabellen={[]}
        spiele={[ko({ nummer: 7, runde: 2, heim_aus_spiel: 3, gast_aus_spiel: 4 })]}
      />,
    );

    expect(screen.queryByRole("button", { name: /Anna/ })).not.toBeInTheDocument();
  });
});
