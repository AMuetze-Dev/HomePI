import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Spiel, Turnier } from "./api";
import { SpielplanTafel } from "./SpielplanTafel";

function turnier(rest: Partial<Turnier> = {}): Turnier {
  return {
    id: "t1",
    name: "Betriebsturnier",
    modus: "gruppen_ko",
    zustand: "laufend",
    tische: 2,
    best_of: 5,
    punkte_bis: 11,
    minuten_pro_spiel: 12,
    anzahl_gruppen: 2,
    weiter_pro_gruppe: 2,
    runden: 4,
    saat: 7,
    runde_angesetzt: 1,
    ko_steht: false,
    anzahl_teilnehmer: 4,
    anzahl_spiele: 2,
    offene_spiele: 2,
    ...rest,
  };
}

function spiel(rest: Partial<Spiel> = {}): Spiel {
  return {
    id: "s1",
    nummer: 1,
    phase: "gruppe",
    runde: 1,
    bezeichnung: "Gruppe A, Runde 1",
    gruppe: "Gruppe A",
    heim_id: "p1",
    gast_id: "p2",
    heim: "Anna",
    gast: "Bernd",
    heim_herkunft: null,
    gast_herkunft: null,
    zustand: "geplant",
    tisch: 1,
    saetze: [],
    saetze_heim: 0,
    saetze_gast: 0,
    sieger_id: null,
    freilos: false,
    begonnen_am: null,
    beendet_am: null,
    erwartet_ab: "2026-11-07T18:12:00Z",
    gleich_dran: false,
    ...rest,
  };
}

function aufbauen(abweichend: {
  turnier?: Turnier;
  spiele?: Spiel[];
  onErgebnis?: ReturnType<typeof vi.fn>;
}) {
  const onBeginnen = vi.fn();
  const onErgebnis = abweichend.onErgebnis ?? vi.fn().mockResolvedValue(true);
  const onZuruecknehmen = vi.fn();
  const onNaechsteRunde = vi.fn();

  render(
    <SpielplanTafel
      turnier={abweichend.turnier ?? turnier()}
      spiele={abweichend.spiele ?? [spiel()]}
      onBeginnen={onBeginnen}
      onErgebnis={onErgebnis}
      onZuruecknehmen={onZuruecknehmen}
      onNaechsteRunde={onNaechsteRunde}
    />,
  );

  return { onBeginnen, onErgebnis, onZuruecknehmen, onNaechsteRunde };
}

describe("Spielplan", () => {
  it("sagt im Erstzustand, wo der Plan entsteht", () => {
    aufbauen({ spiele: [] });

    expect(screen.getByText(/Noch kein Spielplan/)).toBeInTheDocument();
  });

  it("zeigt Paarung, Bezeichnung und Zeit", () => {
    aufbauen({});

    expect(screen.getByText("Anna gegen Bernd")).toBeInTheDocument();
    expect(screen.getByText(/Gruppe A, Runde 1/)).toBeInTheDocument();
  });

  it("pfeift ein Spiel an", async () => {
    const { onBeginnen } = aufbauen({});

    await userEvent.click(screen.getByRole("button", { name: "Spiel 1 beginnen" }));

    expect(onBeginnen).toHaveBeenCalledWith("s1");
  });

  it("schickt nur die ausgefüllten Sätze", async () => {
    /* Wer nach drei Saetzen fertig ist, soll nicht zwei Nullen eintragen
       muessen. */
    const { onErgebnis } = aufbauen({ spiele: [spiel({ zustand: "laeuft" })] });

    await userEvent.click(screen.getByRole("button", { name: /Ergebnis für Spiel 1/ }));
    await userEvent.type(screen.getByLabelText("Satz 1, Anna"), "11");
    await userEvent.type(screen.getByLabelText("Satz 1, Bernd"), "9");
    await userEvent.type(screen.getByLabelText("Satz 2, Anna"), "11");
    await userEvent.type(screen.getByLabelText("Satz 2, Bernd"), "7");
    await userEvent.type(screen.getByLabelText("Satz 3, Anna"), "11");
    await userEvent.type(screen.getByLabelText("Satz 3, Bernd"), "5");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(onErgebnis).toHaveBeenCalledWith("s1", [
      { heim: 11, gast: 9 },
      { heim: 11, gast: 7 },
      { heim: 11, gast: 5 },
    ]);
  });

  it("füllt das Formular mit dem schon eingetragenen Stand", async () => {
    aufbauen({
      spiele: [
        spiel({ zustand: "laeuft", saetze: [{ heim: 11, gast: 9 }], saetze_heim: 1 }),
      ],
    });

    await userEvent.click(screen.getByRole("button", { name: /Ergebnis für Spiel 1/ }));

    expect(screen.getByLabelText("Satz 1, Anna")).toHaveValue(11);
    expect(screen.getByLabelText("Satz 2, Anna")).toHaveValue(null);
  });

  it("nimmt ein Ergebnis zurück", async () => {
    const { onZuruecknehmen } = aufbauen({
      spiele: [spiel({ zustand: "beendet", sieger_id: "p1", saetze_heim: 3 })],
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Ergebnis von Spiel 1 zurücknehmen" }),
    );

    expect(onZuruecknehmen).toHaveBeenCalledWith("s1");
  });

  it("bietet kein Formular, solange die Gegner nicht feststehen", () => {
    aufbauen({
      spiele: [
        spiel({
          heim_id: null,
          heim: null,
          heim_herkunft: "Sieger aus Spiel 5",
          bezeichnung: "Endspiel",
        }),
      ],
    });

    expect(screen.getByText(/Sieger aus Spiel 5/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Ergebnis/ })).not.toBeInTheDocument();
  });

  it("bietet das KO-Raster an, sobald die Gruppenphase durch ist", async () => {
    const { onNaechsteRunde } = aufbauen({
      turnier: turnier({ offene_spiele: 0 }),
      spiele: [spiel({ zustand: "beendet", sieger_id: "p1" })],
    });

    expect(screen.getByText(/KO-Raster aus den Gruppentabellen/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ansetzen" }));

    expect(onNaechsteRunde).toHaveBeenCalled();
  });

  it("sagt am Ende, dass das Turnier durch ist", () => {
    aufbauen({
      turnier: turnier({ zustand: "beendet", offene_spiele: 0, ko_steht: true }),
      spiele: [spiel({ zustand: "beendet", sieger_id: "p1" })],
    });

    expect(screen.getByText(/Das Turnier ist durch/)).toBeInTheDocument();
  });

  it("zeigt ein Freilos als solches und ohne Knöpfe", () => {
    aufbauen({
      spiele: [
        spiel({
          freilos: true,
          zustand: "beendet",
          gast_id: null,
          gast: null,
          gast_herkunft: "Freilos",
          bezeichnung: "Runde 1, Freilos",
        }),
      ],
    });

    expect(screen.getByText("Freilos")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Ergebnis/ })).not.toBeInTheDocument();
  });
});
