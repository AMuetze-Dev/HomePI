import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Auslosung } from "./api";
import { spiel, turnier } from "./testdaten";
import { TurnierTafel } from "./TurnierTafel";

const AUSLOSUNG: Auslosung = {
  saat: 4711,
  modus: "gruppen_ko",
  gruppen: [{ name: "Gruppe A", teilnehmer: ["Anna", "Bernd"] }],
  paarungen: [{ bezeichnung: "Gruppe A, Runde 1", heim: "Anna", gast: "Bernd" }],
  anzahl_spiele: 1,
  dauer_minuten: 12,
  hinweis: "",
};

const LEUTE = [
  { id: "p1", name: "Anna", notiz: "", gruppe: null, freilose: 0 },
  { id: "p2", name: "Bernd", notiz: "", gruppe: null, freilose: 0 },
];

function aufbauen(abweichend: Partial<Parameters<typeof TurnierTafel>[0]> = {}) {
  const griffe = {
    onTeilnehmerAnlegen: vi.fn().mockResolvedValue(true),
    onTeilnehmerEntfernen: vi.fn(),
    onLosen: vi.fn().mockResolvedValue(AUSLOSUNG),
    onUebernehmen: vi.fn().mockResolvedValue(true),
    onZuruecksetzen: vi.fn(),
    onBeginnen: vi.fn(),
    onSieger: vi.fn(),
    onZuruecknehmen: vi.fn(),
    onNaechsteRunde: vi.fn(),
  };

  const zusammen = { ...griffe, ...abweichend };

  render(
    <TurnierTafel
      turnier={turnier()}
      teilnehmer={LEUTE}
      spiele={[]}
      darfEinrichten
      {...zusammen}
    />,
  );

  return zusammen as typeof griffe;
}

describe("Turnier: vor dem Auswürfeln", () => {
  it("zeigt Namen und Würfel auf einer Fläche", () => {
    /* Der Umbau in einem Test: Teilnehmer und Auswürfeln waren zwei
       Reiter, jetzt sind sie ein Handgriff hintereinander. */
    aufbauen();

    expect(screen.getByRole("heading", { name: "Wer spielt mit?" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Auswürfeln" })).toBeInTheDocument();
  });

  it("trägt einen Namen ein und leert danach das Feld", async () => {
    const { onTeilnehmerAnlegen } = aufbauen();

    await userEvent.type(screen.getByLabelText("Name"), "Cem");
    await userEvent.click(screen.getByRole("button", { name: "Eintragen" }));

    expect(onTeilnehmerAnlegen).toHaveBeenCalledWith("Cem");
    expect(screen.getByLabelText("Name")).toHaveValue("");
  });

  it("behält die Eingabe, wenn das Eintragen fehlschlägt", async () => {
    const { onTeilnehmerAnlegen } = aufbauen({
      onTeilnehmerAnlegen: vi.fn().mockResolvedValue(false),
    });

    await userEvent.type(screen.getByLabelText("Name"), "Anna");
    await userEvent.click(screen.getByRole("button", { name: "Eintragen" }));

    expect(onTeilnehmerAnlegen).toHaveBeenCalled();
    expect(screen.getByLabelText("Name")).toHaveValue("Anna");
  });

  it("entfernt einen Namen", async () => {
    const { onTeilnehmerEntfernen } = aufbauen();

    await userEvent.click(screen.getByRole("button", { name: "Anna entfernen" }));

    expect(onTeilnehmerEntfernen).toHaveBeenCalledWith("p1");
  });

  it("würfelt und übernimmt genau dieses Los", async () => {
    const { onLosen, onUebernehmen } = aufbauen();

    await userEvent.click(screen.getByRole("button", { name: "Würfeln" }));
    await userEvent.click(await screen.findByRole("button", { name: /Übernehmen/ }));

    expect(onLosen).toHaveBeenCalled();
    expect(onUebernehmen).toHaveBeenCalledWith(4711);
  });

  it("verwirft die Vorschau ohne Nachfrage", async () => {
    const { onUebernehmen } = aufbauen();

    await userEvent.click(screen.getByRole("button", { name: "Würfeln" }));
    await userEvent.click(await screen.findByRole("button", { name: "Verwerfen" }));

    expect(screen.queryByText("Gruppe A")).not.toBeInTheDocument();
    expect(onUebernehmen).not.toHaveBeenCalled();
  });

  it("lässt nur Verwalter würfeln", () => {
    aufbauen({ darfEinrichten: false });

    expect(screen.queryByRole("button", { name: "Würfeln" })).not.toBeInTheDocument();
    expect(
      screen.getByText(/Auswürfeln darf, wer dieses Artefakt verwaltet/),
    ).toBeInTheDocument();
  });
});

describe("Turnier: während gespielt wird", () => {
  const LAEUFT = turnier({
    zustand: "laufend",
    anzahl_spiele: 2,
    offene_spiele: 1,
    saat: 7,
  });

  it("wertet ein Spiel mit einem Tippen auf den Namen", async () => {
    /* Das ganze Ergebnis: ein Name. Kein Formular, keine Sätze. */
    const { onSieger } = aufbauen({ turnier: LAEUFT, spiele: [spiel()] });

    await userEvent.click(screen.getByRole("button", { name: "Bernd gewinnt" }));

    expect(onSieger).toHaveBeenCalledWith("s1", "p2");
  });

  it("pfeift ein Spiel an", async () => {
    const { onBeginnen } = aufbauen({ turnier: LAEUFT, spiele: [spiel()] });

    await userEvent.click(screen.getByRole("button", { name: "Spiel 1 anpfeifen" }));

    expect(onBeginnen).toHaveBeenCalledWith("s1");
  });

  it("zeigt bei noch unbekannten Gegnern keine Knöpfe", () => {
    aufbauen({
      turnier: LAEUFT,
      spiele: [
        spiel({
          heim: null,
          heim_id: null,
          heim_herkunft: "Sieger aus Spiel 3",
          bezeichnung: "Endspiel",
        }),
      ],
    });

    expect(screen.getByText(/Sieger aus Spiel 3/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /gewinnt/ })).not.toBeInTheDocument();
  });

  it("nimmt ein Ergebnis zurück", async () => {
    const { onZuruecknehmen } = aufbauen({
      turnier: LAEUFT,
      spiele: [spiel({ zustand: "beendet", sieger_id: "p1" })],
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Ergebnis von Spiel 1 zurücknehmen" }),
    );

    expect(onZuruecknehmen).toHaveBeenCalledWith("s1");
  });

  it("bietet das Raster an, sobald alles gewertet ist", async () => {
    const { onNaechsteRunde } = aufbauen({
      turnier: turnier({ zustand: "laufend", offene_spiele: 0 }),
      spiele: [spiel({ zustand: "beendet", sieger_id: "p1" })],
    });

    await userEvent.click(screen.getByRole("button", { name: "KO-Raster ansetzen" }));

    expect(onNaechsteRunde).toHaveBeenCalled();
  });

  it("sagt am Ende, dass das Turnier durch ist", () => {
    aufbauen({
      turnier: turnier({ zustand: "beendet", offene_spiele: 0, ko_steht: true }),
      spiele: [spiel({ zustand: "beendet", sieger_id: "p1" })],
    });

    expect(screen.getByText(/Das Turnier ist durch/)).toBeInTheDocument();
  });

  it("nennt die Saat und den Weg zurück", async () => {
    const { onZuruecksetzen } = aufbauen({ turnier: LAEUFT, spiele: [spiel()] });

    expect(screen.getByText(/Saat 7/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Spielplan verwerfen" }));

    expect(onZuruecksetzen).toHaveBeenCalled();
  });
});
