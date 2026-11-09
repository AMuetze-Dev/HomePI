import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Turnier } from "./api";
import { EinstellungenTafel } from "./EinstellungenTafel";

function turnier(rest: Partial<Turnier> = {}): Turnier {
  return {
    id: "t1",
    name: "Betriebsturnier",
    modus: "gruppen_ko",
    zustand: "planung",
    tische: 2,
    best_of: 3,
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

function aufbauen(abweichend: { turnier?: Turnier | null } = {}) {
  const onAnlegen = vi.fn().mockResolvedValue(true);
  const onAendern = vi.fn().mockResolvedValue(true);
  const onBeenden = vi.fn();
  const onLoeschen = vi.fn();

  render(
    <EinstellungenTafel
      turnier={abweichend.turnier === undefined ? turnier() : abweichend.turnier}
      onAnlegen={onAnlegen}
      onAendern={onAendern}
      onBeenden={onBeenden}
      onLoeschen={onLoeschen}
    />,
  );

  return { onAnlegen, onAendern, onBeenden, onLoeschen };
}

describe("Einstellungen", () => {
  it("verlangt ohne Turnier einen Namen", async () => {
    const { onAnlegen } = aufbauen({ turnier: null });

    expect(screen.getByRole("button", { name: "Turnier anlegen" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Name des Turniers"), "Kollegenturnier");
    await userEvent.click(screen.getByRole("button", { name: "Turnier anlegen" }));

    expect(onAnlegen).toHaveBeenCalledWith(
      "Kollegenturnier",
      expect.objectContaining({ modus: "gruppen_ko", tische: 2 }),
    );
  });

  it("fragt beim bestehenden Turnier nicht nach dem Namen", () => {
    aufbauen({});

    expect(screen.queryByLabelText("Name des Turniers")).not.toBeInTheDocument();
  });

  it("erklärt den gewählten Modus", async () => {
    aufbauen({});

    await userEvent.selectOptions(screen.getByLabelText("Spielmodus"), "schweizer");

    expect(screen.getByText(/Feste Rundenzahl/)).toBeInTheDocument();
    expect(screen.getByLabelText("Runden")).toBeInTheDocument();
    expect(screen.queryByLabelText("Gruppen")).not.toBeInTheDocument();
  });

  it("zeigt beim KO-Modus weder Gruppen noch Runden", async () => {
    aufbauen({});

    await userEvent.selectOptions(screen.getByLabelText("Spielmodus"), "ko");

    expect(screen.queryByLabelText("Gruppen")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Runden")).not.toBeInTheDocument();
  });

  it("schätzt Spiele und Dauer aus den Einstellungen", () => {
    /* Die Zahl, nach der der Modus gewaehlt wird - und der Grund, warum sie
       schon im Formular steht und nicht erst in der Vorschau. */
    aufbauen({});

    expect(screen.getByText(/Ergibt etwa 15 Spiele/)).toBeInTheDocument();
  });

  it("schätzt nichts, solange niemand eingetragen ist", () => {
    aufbauen({ turnier: turnier({ anzahl_teilnehmer: 0 }) });

    expect(screen.queryByText(/Ergibt etwa/)).not.toBeInTheDocument();
  });

  it("schlägt eine Gruppenzahl für die eingetragenen Teilnehmer vor", () => {
    aufbauen({ turnier: turnier({ anzahl_teilnehmer: 12 }) });

    expect(screen.getByText(/Vorschlag für 12 Teilnehmer: 3/)).toBeInTheDocument();
  });

  it("sperrt die Regeln, sobald gespielt wird – Tische und Sätze aber nicht", () => {
    /* Ein Formular, das sich abschicken lässt und dann abgelehnt wird, ist
       eine Falle. Deshalb sagt die Fläche es selbst. Die Gewinnsätze
       bleiben offen: sie stehen in keinem Ergebnis und sagen nur, wie
       lange gespielt wird - das darf man abends noch kürzen. */
    aufbauen({ turnier: turnier({ zustand: "laufend" }) });

    expect(screen.getByLabelText("Spielmodus")).toBeDisabled();
    expect(screen.getByLabelText("Gewinnsätze")).toBeEnabled();
    expect(screen.getByLabelText("Tische")).toBeEnabled();
    expect(screen.getByLabelText("Minuten je Spiel")).toBeEnabled();
    expect(screen.getByText(/Der Spielplan steht/)).toBeInTheDocument();
  });

  it("bietet auch einen einzigen Satz an", () => {
    aufbauen({});

    expect(screen.getByRole("option", { name: "Ein Satz" })).toBeInTheDocument();
  });

  it("speichert geänderte Einstellungen", async () => {
    const { onAendern } = aufbauen({});

    const tische = screen.getByLabelText("Tische");
    await userEvent.clear(tische);
    await userEvent.type(tische, "3");
    await userEvent.click(
      screen.getByRole("button", { name: "Einstellungen speichern" }),
    );

    expect(onAendern).toHaveBeenCalledWith(expect.objectContaining({ tische: 3 }));
  });

  it("bietet Beenden und Löschen nur bei einem Turnier an", async () => {
    const { onBeenden, onLoeschen } = aufbauen({});

    await userEvent.click(screen.getByRole("button", { name: "Beenden" }));
    await userEvent.click(screen.getByRole("button", { name: "Löschen" }));

    expect(onBeenden).toHaveBeenCalled();
    expect(onLoeschen).toHaveBeenCalled();
  });

  it("bietet ohne Turnier nichts zum Abschließen an", () => {
    aufbauen({ turnier: null });

    expect(screen.queryByRole("button", { name: "Löschen" })).not.toBeInTheDocument();
  });
});
