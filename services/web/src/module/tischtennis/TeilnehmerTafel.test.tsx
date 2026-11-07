import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Teilnehmer, Turnier } from "./api";
import { TeilnehmerTafel } from "./TeilnehmerTafel";

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
    anzahl_teilnehmer: 0,
    anzahl_spiele: 0,
    offene_spiele: 0,
    ...rest,
  };
}

function wer(rest: Partial<Teilnehmer> = {}): Teilnehmer {
  return { id: "p1", name: "Anna", notiz: "", gruppe: null, freilose: 0, ...rest };
}

function aufbauen(abweichend: {
  turnier?: Turnier;
  teilnehmer?: Teilnehmer[];
  onAnlegen?: ReturnType<typeof vi.fn>;
  onAendern?: ReturnType<typeof vi.fn>;
  onEntfernen?: ReturnType<typeof vi.fn>;
}) {
  const onAnlegen = abweichend.onAnlegen ?? vi.fn().mockResolvedValue(true);
  const onAendern = abweichend.onAendern ?? vi.fn().mockResolvedValue(true);
  const onEntfernen = abweichend.onEntfernen ?? vi.fn();

  render(
    <TeilnehmerTafel
      turnier={abweichend.turnier ?? turnier()}
      teilnehmer={abweichend.teilnehmer ?? []}
      onAnlegen={onAnlegen}
      onAendern={onAendern}
      onEntfernen={onEntfernen}
    />,
  );

  return { onAnlegen, onAendern, onEntfernen };
}

describe("Teilnehmer", () => {
  it("sagt im Erstzustand, was zu tun ist", () => {
    aufbauen({});

    expect(screen.getByText(/Noch niemand dabei/)).toBeInTheDocument();
  });

  it("trägt einen Namen ein und leert danach das Feld", async () => {
    const { onAnlegen } = aufbauen({});

    await userEvent.type(screen.getByLabelText("Name"), "Anna");
    await userEvent.click(screen.getByRole("button", { name: "Eintragen" }));

    expect(onAnlegen).toHaveBeenCalledWith({ name: "Anna", notiz: "" });
    expect(screen.getByLabelText("Name")).toHaveValue("");
  });

  it("behält die Eingabe, wenn das Eintragen fehlschlägt", async () => {
    // Sonst tippt man nach einem doppelten Namen alles neu.
    const { onAnlegen } = aufbauen({ onAnlegen: vi.fn().mockResolvedValue(false) });

    await userEvent.type(screen.getByLabelText("Name"), "Anna");
    await userEvent.click(screen.getByRole("button", { name: "Eintragen" }));

    expect(onAnlegen).toHaveBeenCalled();
    expect(screen.getByLabelText("Name")).toHaveValue("Anna");
  });

  it("zeigt Notiz und Gruppe an der Zeile", () => {
    aufbauen({ teilnehmer: [wer({ notiz: "Technik", gruppe: "Gruppe A" })] });

    expect(screen.getByText(/Technik/)).toBeInTheDocument();
    expect(screen.getByText("Gruppe A")).toBeInTheDocument();
  });

  it("benennt um, ohne die Liste zu verlassen", async () => {
    const { onAendern } = aufbauen({ teilnehmer: [wer()] });

    await userEvent.click(screen.getByRole("button", { name: "Anna umbenennen" }));
    // In der Zeile, nicht im Formular darueber: beide heissen "Name".
    const zeile = within(screen.getByRole("listitem"));
    const feld = zeile.getByLabelText("Name");
    await userEvent.clear(feld);
    await userEvent.type(feld, "Annemarie");
    await userEvent.click(zeile.getByRole("button", { name: "Speichern" }));

    expect(onAendern).toHaveBeenCalledWith("p1", { name: "Annemarie", notiz: "" });
  });

  it("sperrt die Liste, sobald der Spielplan steht", () => {
    /* Wer jetzt dazukaeme, haette keine Spiele - das sagt die Flaeche
       selbst und nicht erst das Backend. */
    aufbauen({ turnier: turnier({ zustand: "laufend" }), teilnehmer: [wer()] });

    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Anna entfernen" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Der Spielplan steht/)).toBeInTheDocument();
  });
});
