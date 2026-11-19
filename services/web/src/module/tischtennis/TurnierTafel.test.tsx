import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Auslosung, Liste } from "./api";
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

const LISTEN: Liste[] = [
  { id: "l1", name: "Stammtisch", namen: ["Anna", "Cem", "Dana"] },
];

function aufbauen(abweichend: Partial<Parameters<typeof TurnierTafel>[0]> = {}) {
  const griffe = {
    onTeilnehmerAnlegen: vi.fn().mockResolvedValue(true),
    onTeilnehmerEntfernen: vi.fn(),
    onListeLaden: vi
      .fn()
      .mockResolvedValue({ eingetragen: [LEUTE[0], LEUTE[1]], schon_dabei: ["Anna"] }),
    onListeSpeichern: vi.fn().mockResolvedValue(true),
    onListeLoeschen: vi.fn(),
    onLosen: vi.fn().mockResolvedValue(AUSLOSUNG),
    onUebernehmen: vi.fn().mockResolvedValue(true),
    onZuruecksetzen: vi.fn(),
    onBeginnen: vi.fn(),
    onSieger: vi.fn(),
    onZuruecknehmen: vi.fn(),
    onVerschieben: vi.fn(),
    onNaechsteRunde: vi.fn(),
  };

  const zusammen = { ...griffe, ...abweichend };

  render(
    <TurnierTafel
      turnier={turnier()}
      teilnehmer={LEUTE}
      spiele={[]}
      listen={LISTEN}
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

  it("entfernt einen Namen erst nach dem Aufklappen", async () => {
    /* Kein Kreuz an jedem Namen: Bei zwanzig Leuten waren das zwanzig
       Knöpfe, und gesucht hat man trotzdem einen Namen. */
    const { onTeilnehmerEntfernen } = aufbauen();

    expect(
      screen.queryByRole("button", { name: "Anna entfernen" }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Anna" }));
    await userEvent.click(screen.getByRole("button", { name: "Anna entfernen" }));

    expect(onTeilnehmerEntfernen).toHaveBeenCalledWith("p1");
  });

  it("zählt die Namen durch", () => {
    aufbauen();

    const liste = screen.getByRole("list", { name: "Eingetragene Namen" });
    expect(within(liste).getAllByRole("listitem")).toHaveLength(2);
    expect(within(liste).getByText("01")).toBeInTheDocument();
  });

  /* Gespeicherte Listen: einmal tippen, vor jedem Turnier laden. */
  it("zeigt die Listen mit der Zahl ihrer Namen", () => {
    aufbauen();

    expect(
      screen.getByRole("heading", { name: "Gespeicherte Listen" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Stammtisch/ })).toHaveTextContent(
      "3 Namen",
    );
  });

  it("erklärt im Erstzustand, wozu es Listen gibt", () => {
    aufbauen({ listen: [] });

    expect(screen.getByText(/Noch keine Liste/)).toBeInTheDocument();
  });

  it("lädt eine Liste und sagt, was passiert ist", async () => {
    const { onListeLaden } = aufbauen();

    await userEvent.click(screen.getByRole("button", { name: /Stammtisch/ }));
    await userEvent.click(screen.getByRole("button", { name: "Übernehmen" }));

    expect(onListeLaden).toHaveBeenCalledWith("l1");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "2 eingetragen, 1 war schon dabei",
    );
  });

  it("löscht eine Liste aus der Ausklappung", async () => {
    const { onListeLoeschen } = aufbauen();

    await userEvent.click(screen.getByRole("button", { name: /Stammtisch/ }));
    await userEvent.click(screen.getByRole("button", { name: "Liste löschen" }));

    expect(onListeLoeschen).toHaveBeenCalledWith("l1");
  });

  it("speichert die eingetragenen Namen als neue Liste", async () => {
    const { onListeSpeichern } = aufbauen();

    expect(screen.queryByLabelText("Name der Liste")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Als Liste speichern" }));
    await userEvent.type(screen.getByLabelText("Name der Liste"), "Testlauf");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(onListeSpeichern).toHaveBeenCalledWith("Testlauf", undefined);
    expect(screen.queryByLabelText("Name der Liste")).not.toBeInTheDocument();
  });

  it("überschreibt eine Liste gleichen Namens - und sagt das vorher", async () => {
    const { onListeSpeichern } = aufbauen();

    await userEvent.click(screen.getByRole("button", { name: "Als Liste speichern" }));
    await userEvent.type(screen.getByLabelText("Name der Liste"), "stammtisch");

    expect(screen.getByText(/ersetzt die 3 Namen/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Überschreiben" }));

    expect(onListeSpeichern).toHaveBeenCalledWith("Stammtisch", "l1");
  });

  it("behält das Formular offen, wenn das Speichern fehlschlägt", async () => {
    aufbauen({ onListeSpeichern: vi.fn().mockResolvedValue(false) });

    await userEvent.click(screen.getByRole("button", { name: "Als Liste speichern" }));
    await userEvent.type(screen.getByLabelText("Name der Liste"), "Testlauf");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(screen.getByLabelText("Name der Liste")).toHaveValue("Testlauf");
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

  it("stellt ein Freilos nicht in die Liste der offenen Spiele", () => {
    /* Ein Freilos ist kein Spiel: niemand steht dafuer am Tisch, und
       solange sein Platz noch nicht feststeht, steht es trotzdem auf
       "geplant". In der Zaehlung "noch X zu spielen" waere es eine zu viel,
       und ein "gewinnt"-Knopf daran waere eine Handlung ins Leere. Im
       Raster steht es weiter - dort erklaert es, warum einer durch ist. */
    aufbauen({
      turnier: LAEUFT,
      spiele: [
        spiel(),
        spiel({
          id: "s2",
          nummer: 2,
          bezeichnung: "Halbfinale, Freilos",
          freilos: true,
          gast: null,
          gast_id: null,
          gast_herkunft: "Freilos",
        }),
      ],
    });

    expect(
      screen.getByRole("heading", { name: /Noch 1 zu spielen/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Halbfinale, Freilos")).not.toBeInTheDocument();
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

describe("Turnier: Listen, die lang werden", () => {
  const LAEUFT = turnier({ zustand: "laufend", anzahl_spiele: 2, offene_spiele: 1 });

  it("schreibt die Paarung über die Siegerknöpfe", () => {
    /* Die Knöpfe sagen "Anna gewinnt" - wer gegen wen spielt, musste man
       sich aus zwei Knöpfen zusammensetzen. */
    aufbauen({ turnier: LAEUFT, spiele: [spiel()] });

    expect(screen.getByText("Anna gegen Bernd")).toBeInTheDocument();
  });

  it("bietet Zurücknehmen erst in der geöffneten Zeile an", async () => {
    /* Bei einem Turnier mit vierzig Spielen standen hier vierzig Knöpfe -
       für eine Handlung, die man einmal am Abend braucht. */
    const { onZuruecknehmen } = aufbauen({
      turnier: LAEUFT,
      spiele: [spiel({ zustand: "beendet", sieger_id: "p1" })],
    });

    expect(
      screen.queryByRole("button", { name: /Ergebnis von Spiel 1 zurücknehmen/ }),
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^Anna gegen Bernd/ }));
    await userEvent.click(
      screen.getByRole("button", { name: /Ergebnis von Spiel 1 zurücknehmen/ }),
    );

    expect(onZuruecknehmen).toHaveBeenCalledWith("s1");
  });

  it("zeigt die neuesten Ergebnisse zuerst und kürzt lange Listen", async () => {
    const ergebnisse = Array.from({ length: 14 }, (_, i) =>
      spiel({
        id: `e${i}`,
        nummer: i + 1,
        zustand: "beendet",
        sieger_id: "p1",
        beendet_am: `2026-11-09T18:${String(i).padStart(2, "0")}:00Z`,
      }),
    );
    aufbauen({ turnier: LAEUFT, spiele: ergebnisse });

    const liste = within(screen.getByRole("list", { name: "Gewertet" }));
    expect(liste.getAllByRole("listitem")).toHaveLength(10);

    await userEvent.click(screen.getByRole("button", { name: "Alle 14 zeigen" }));

    expect(liste.getAllByRole("listitem")).toHaveLength(14);
  });
});
