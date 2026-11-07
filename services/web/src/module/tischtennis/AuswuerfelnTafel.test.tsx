import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Auslosung, Turnier } from "./api";
import { AuswuerfelnTafel } from "./AuswuerfelnTafel";

function turnier(rest: Partial<Turnier> = {}): Turnier {
  return {
    id: "t1",
    name: "Betriebsturnier",
    modus: "gruppen_ko",
    zustand: "planung",
    tische: 2,
    best_of: 5,
    punkte_bis: 11,
    minuten_pro_spiel: 12,
    anzahl_gruppen: 2,
    weiter_pro_gruppe: 2,
    runden: 4,
    saat: null,
    runde_angesetzt: 0,
    ko_steht: false,
    anzahl_teilnehmer: 8,
    anzahl_spiele: 0,
    offene_spiele: 0,
    ...rest,
  };
}

const AUSLOSUNG: Auslosung = {
  saat: 4711,
  modus: "gruppen_ko",
  gruppen: [
    { name: "Gruppe A", teilnehmer: ["Anna", "Bernd"] },
    { name: "Gruppe B", teilnehmer: ["Cem", "Dana"] },
  ],
  paarungen: [{ bezeichnung: "Gruppe A, Runde 1", heim: "Anna", gast: "Bernd" }],
  anzahl_spiele: 2,
  dauer_minuten: 24,
  hinweis: "",
};

function aufbauen(abweichend: {
  turnier?: Turnier;
  onLosen?: ReturnType<typeof vi.fn>;
  onUebernehmen?: ReturnType<typeof vi.fn>;
  onZuruecksetzen?: ReturnType<typeof vi.fn>;
}) {
  const onLosen = abweichend.onLosen ?? vi.fn().mockResolvedValue(AUSLOSUNG);
  const onUebernehmen = abweichend.onUebernehmen ?? vi.fn().mockResolvedValue(true);
  const onZuruecksetzen = abweichend.onZuruecksetzen ?? vi.fn().mockResolvedValue(true);

  render(
    <AuswuerfelnTafel
      turnier={abweichend.turnier ?? turnier()}
      onLosen={onLosen}
      onUebernehmen={onUebernehmen}
      onZuruecksetzen={onZuruecksetzen}
    />,
  );

  return { onLosen, onUebernehmen, onZuruecksetzen };
}

describe("Auswürfeln", () => {
  it("verlangt erst Teilnehmer", () => {
    aufbauen({ turnier: turnier({ anzahl_teilnehmer: 1 }) });

    expect(screen.getByText(/Erst die Teilnehmer/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Würfeln" })).not.toBeInTheDocument();
  });

  it("zeigt die Vorschau und sagt, dass nichts gespeichert ist", async () => {
    aufbauen({});

    await userEvent.click(screen.getByRole("button", { name: "Würfeln" }));

    expect(await screen.findByText("Gruppe A")).toBeInTheDocument();
    expect(screen.getByText(/Gespeichert ist davon noch nichts/)).toBeInTheDocument();
    expect(screen.getByText(/Anna gegen Bernd/)).toBeInTheDocument();
  });

  it("würfelt auf Knopfdruck ein zweites Mal", async () => {
    const { onLosen, onUebernehmen } = aufbauen({});

    await userEvent.click(screen.getByRole("button", { name: "Würfeln" }));
    await userEvent.click(await screen.findByRole("button", { name: "Nochmal würfeln" }));

    expect(onLosen).toHaveBeenCalledTimes(2);
    expect(onUebernehmen).not.toHaveBeenCalled();
  });

  it("übernimmt genau die Saat, die zu sehen war", async () => {
    /* Sonst zeigte die Vorschau ein Los und gespeichert wuerde ein
       anderes - der Fehler, den man erst am Spielplan merkt. */
    const { onUebernehmen } = aufbauen({});

    await userEvent.click(screen.getByRole("button", { name: "Würfeln" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Übernehmen und Turnier starten" }),
    );

    expect(onUebernehmen).toHaveBeenCalledWith(4711);
  });

  it("verwirft die Vorschau ohne Nachfrage", async () => {
    const { onUebernehmen } = aufbauen({});

    await userEvent.click(screen.getByRole("button", { name: "Würfeln" }));
    await userEvent.click(await screen.findByRole("button", { name: "Verwerfen" }));

    expect(screen.queryByText("Gruppe A")).not.toBeInTheDocument();
    expect(onUebernehmen).not.toHaveBeenCalled();
  });

  it("nennt beim laufenden Turnier die Saat und den Weg zurück", async () => {
    const { onZuruecksetzen } = aufbauen({
      turnier: turnier({ zustand: "laufend", saat: 99, anzahl_spiele: 12 }),
    });

    expect(screen.getByText("99")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Spielplan verwerfen und zurück/ }),
    );

    expect(onZuruecksetzen).toHaveBeenCalled();
  });

  it("zeigt den Hinweis des Backends wörtlich", async () => {
    aufbauen({
      onLosen: vi
        .fn()
        .mockResolvedValue({ ...AUSLOSUNG, hinweis: "Freilos in Runde 1: Dana" }),
    });

    await userEvent.click(screen.getByRole("button", { name: "Würfeln" }));

    expect(await screen.findByText("Freilos in Runde 1: Dana")).toBeInTheDocument();
  });
});
