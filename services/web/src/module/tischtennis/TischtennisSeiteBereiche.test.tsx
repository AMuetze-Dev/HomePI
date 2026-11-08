import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Benutzer } from "../../api/anmeldung";
import { ApiError } from "../../api/client";
import { TESTBENUTZER, mitAnmeldung } from "../../testhilfen";
import * as api from "./api";
import { TischtennisSeite } from "./TischtennisSeite";

/**
 * Die Bereiche der Turnierleitung, von außen.
 *
 * Die Tafeln selbst sind je einzeln geprüft; hier geht es um die Verdrahtung:
 * landet der Knopf wirklich am richtigen Endpunkt, und wird danach neu
 * geladen. Das ist die Stelle, an der ein vertippter Aufruf sonst erst am
 * Turniertag auffällt.
 */

const LEITER: Benutzer = { ...TESTBENUTZER, rechte: { tischtennis: "verwalter" } };
const NUTZER: Benutzer = { ...TESTBENUTZER, rechte: { tischtennis: "nutzer" } };

function turnier(rest: Partial<api.Turnier> = {}): api.Turnier {
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

function spiel(rest: Partial<api.Spiel> = {}): api.Spiel {
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

const LAUFEND = turnier({
  zustand: "laufend",
  anzahl_spiele: 12,
  offene_spiele: 12,
  saat: 7,
});

beforeEach(() => {
  vi.spyOn(api, "ladeTurniere").mockResolvedValue([turnier()]);
  vi.spyOn(api, "ladeTurnier").mockResolvedValue(turnier());
  vi.spyOn(api, "ladeTeilnehmer").mockResolvedValue([]);
  vi.spyOn(api, "ladeSpiele").mockResolvedValue([]);
  vi.spyOn(api, "ladeTabellen").mockResolvedValue([]);
  vi.spyOn(api, "legeTeilnehmerAn").mockResolvedValue({
    id: "p1",
    name: "Anna",
    notiz: "",
    gruppe: null,
    freilose: 0,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Teilnehmer führen", () => {
  it("trägt einen Namen ein und lädt danach neu", async () => {
    render(mitAnmeldung(<TischtennisSeite unterseite="teilnehmer" />, LEITER));

    await userEvent.type(await screen.findByLabelText("Name"), "Anna");
    await userEvent.click(screen.getByRole("button", { name: "Eintragen" }));

    expect(api.legeTeilnehmerAn).toHaveBeenCalledWith("t1", { name: "Anna", notiz: "" });
    // Zweimal: einmal beim Aufbau, einmal nach der Aktion.
    expect(api.ladeTeilnehmer).toHaveBeenCalledTimes(2);
  });

  it("entfernt einen Teilnehmer", async () => {
    vi.spyOn(api, "ladeTeilnehmer").mockResolvedValue([
      { id: "p1", name: "Anna", notiz: "", gruppe: null, freilose: 0 },
    ]);
    vi.spyOn(api, "entferneTeilnehmer").mockResolvedValue(undefined);
    render(mitAnmeldung(<TischtennisSeite unterseite="teilnehmer" />, LEITER));

    await userEvent.click(await screen.findByRole("button", { name: "Anna entfernen" }));

    expect(api.entferneTeilnehmer).toHaveBeenCalledWith("p1");
  });

  it("benennt einen Teilnehmer um", async () => {
    vi.spyOn(api, "ladeTeilnehmer").mockResolvedValue([
      { id: "p1", name: "Anna", notiz: "", gruppe: null, freilose: 0 },
    ]);
    vi.spyOn(api, "aendereTeilnehmer").mockResolvedValue({
      id: "p1",
      name: "Annemarie",
      notiz: "",
      gruppe: null,
      freilose: 0,
    });
    render(mitAnmeldung(<TischtennisSeite unterseite="teilnehmer" />, LEITER));

    await userEvent.click(await screen.findByRole("button", { name: "Anna umbenennen" }));
    // In der Zeile suchen und nicht auf der ganzen Flaeche: das Formular
    // darueber hat ein Feld mit derselben Beschriftung.
    const zeile = within(screen.getByRole("listitem"));
    const zeilenfeld = zeile.getByLabelText("Name");
    await userEvent.clear(zeilenfeld);
    await userEvent.type(zeilenfeld, "Annemarie");
    await userEvent.click(zeile.getByRole("button", { name: "Speichern" }));

    expect(api.aendereTeilnehmer).toHaveBeenCalledWith("p1", {
      name: "Annemarie",
      notiz: "",
    });
  });

  it("zeigt die Meldung des Backends wörtlich und behält die Eingabe", async () => {
    vi.spyOn(api, "legeTeilnehmerAn").mockRejectedValue(
      new ApiError("Anna steht schon auf der Liste", 409),
    );
    render(mitAnmeldung(<TischtennisSeite unterseite="teilnehmer" />, LEITER));

    await userEvent.type(await screen.findByLabelText("Name"), "Anna");
    await userEvent.click(screen.getByRole("button", { name: "Eintragen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "steht schon auf der Liste",
    );
    expect(screen.getByLabelText("Name")).toHaveValue("Anna");
  });
});

describe("Auswürfeln", () => {
  it("würfelt und übernimmt genau dieses Los", async () => {
    vi.spyOn(api, "loseAus").mockResolvedValue({
      saat: 4711,
      modus: "gruppen_ko",
      gruppen: [{ name: "Gruppe A", teilnehmer: ["Anna", "Bernd"] }],
      paarungen: [{ bezeichnung: "Gruppe A, Runde 1", heim: "Anna", gast: "Bernd" }],
      anzahl_spiele: 1,
      dauer_minuten: 12,
      hinweis: "",
    });
    vi.spyOn(api, "wuerfleAus").mockResolvedValue(LAUFEND);
    render(mitAnmeldung(<TischtennisSeite unterseite="auswuerfeln" />, LEITER));

    await userEvent.click(await screen.findByRole("button", { name: "Würfeln" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Übernehmen und Turnier starten" }),
    );

    expect(api.loseAus).toHaveBeenCalledWith("t1", undefined);
    expect(api.wuerfleAus).toHaveBeenCalledWith("t1", 4711);
  });

  it("zeigt einen abgelehnten Wurf als Meldung", async () => {
    vi.spyOn(api, "loseAus").mockRejectedValue(
      new ApiError("4 Teilnehmer reichen nicht fuer 3 Gruppen", 409),
    );
    render(mitAnmeldung(<TischtennisSeite unterseite="auswuerfeln" />, LEITER));

    await userEvent.click(await screen.findByRole("button", { name: "Würfeln" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("reichen nicht");
  });

  it("setzt den Spielplan zurück", async () => {
    vi.spyOn(api, "ladeTurnier").mockResolvedValue(LAUFEND);
    vi.spyOn(api, "setzeZurueck").mockResolvedValue(turnier());
    render(mitAnmeldung(<TischtennisSeite unterseite="auswuerfeln" />, LEITER));

    await userEvent.click(
      await screen.findByRole("button", { name: /Spielplan verwerfen und zurück/ }),
    );

    expect(api.setzeZurueck).toHaveBeenCalledWith("t1");
  });

  it("lässt nur Verwalter würfeln", async () => {
    render(mitAnmeldung(<TischtennisSeite unterseite="auswuerfeln" />, NUTZER));

    expect(
      await screen.findByText(/Auswürfeln darf, wer dieses Artefakt verwaltet/),
    ).toBeInTheDocument();
  });
});

describe("Spielplan führen", () => {
  it("pfeift an und setzt die nächste Runde an", async () => {
    vi.spyOn(api, "ladeTurnier").mockResolvedValue(
      turnier({ zustand: "laufend", offene_spiele: 0 }),
    );
    vi.spyOn(api, "ladeSpiele").mockResolvedValue([spiel()]);
    vi.spyOn(api, "beginneSpiel").mockResolvedValue(spiel({ zustand: "laeuft" }));
    vi.spyOn(api, "naechsteRunde").mockResolvedValue(turnier({ zustand: "laufend" }));
    render(mitAnmeldung(<TischtennisSeite unterseite="spielplan" />, LEITER));

    await userEvent.click(
      await screen.findByRole("button", { name: "Spiel 1 beginnen" }),
    );
    expect(api.beginneSpiel).toHaveBeenCalledWith("s1");

    await userEvent.click(screen.getByRole("button", { name: "Ansetzen" }));
    expect(api.naechsteRunde).toHaveBeenCalledWith("t1");
  });

  it("wertet ein Spiel und nimmt es wieder zurück", async () => {
    vi.spyOn(api, "ladeTurnier").mockResolvedValue(LAUFEND);
    vi.spyOn(api, "ladeSpiele").mockResolvedValue([spiel({ zustand: "laeuft" })]);
    vi.spyOn(api, "trageErgebnisEin").mockResolvedValue(spiel({ zustand: "beendet" }));
    vi.spyOn(api, "nimmErgebnisZurueck").mockResolvedValue(spiel());
    render(mitAnmeldung(<TischtennisSeite unterseite="spielplan" />, LEITER));

    await userEvent.click(
      await screen.findByRole("button", { name: /Ergebnis für Spiel 1/ }),
    );
    await userEvent.type(screen.getByLabelText("Satz 1, Anna"), "11");
    await userEvent.type(screen.getByLabelText("Satz 1, Bernd"), "9");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(api.trageErgebnisEin).toHaveBeenCalledWith("s1", [{ heim: 11, gast: 9 }]);

    await userEvent.click(
      screen.getByRole("button", { name: "Ergebnis von Spiel 1 zurücknehmen" }),
    );
    expect(api.nimmErgebnisZurueck).toHaveBeenCalledWith("s1");
  });

  it("zeigt ein abgelehntes Ergebnis mit dem Satz des Backends", async () => {
    vi.spyOn(api, "ladeTurnier").mockResolvedValue(LAUFEND);
    vi.spyOn(api, "ladeSpiele").mockResolvedValue([spiel({ zustand: "laeuft" })]);
    vi.spyOn(api, "trageErgebnisEin").mockRejectedValue(
      new ApiError(
        "Ein Satz endet mit mindestens zwei Punkten Vorsprung, nicht 11:10",
        422,
      ),
    );
    render(mitAnmeldung(<TischtennisSeite unterseite="spielplan" />, LEITER));

    await userEvent.click(
      await screen.findByRole("button", { name: /Ergebnis für Spiel 1/ }),
    );
    await userEvent.type(screen.getByLabelText("Satz 1, Anna"), "11");
    await userEvent.type(screen.getByLabelText("Satz 1, Bernd"), "10");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("zwei Punkten Vorsprung");
  });
});

describe("Tabellen und Einstellungen", () => {
  it("zeigt die Tabellen des gewählten Turniers", async () => {
    vi.spyOn(api, "ladeTabellen").mockResolvedValue([
      {
        titel: "Gruppe A",
        zeilen: [
          {
            platz: 1,
            teilnehmer_id: "p1",
            teilnehmer: "Anna",
            spiele: 1,
            siege: 1,
            niederlagen: 0,
            punkte: 2,
            saetze_fuer: 3,
            saetze_gegen: 0,
            baelle_fuer: 33,
            baelle_gegen: 10,
            satzdifferenz: 3,
            balldifferenz: 23,
          },
        ],
      },
    ]);
    render(mitAnmeldung(<TischtennisSeite unterseite="tabellen" />, LEITER));

    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Gruppe A")).toBeInTheDocument();
  });

  it("speichert Einstellungen, beendet und löscht", async () => {
    vi.spyOn(api, "aendereTurnier").mockResolvedValue(turnier({ tische: 3 }));
    vi.spyOn(api, "beendeTurnier").mockResolvedValue(turnier({ zustand: "beendet" }));
    vi.spyOn(api, "loescheTurnier").mockResolvedValue(undefined);
    render(mitAnmeldung(<TischtennisSeite unterseite="einstellungen" />, LEITER));

    await userEvent.click(
      await screen.findByRole("button", { name: "Einstellungen speichern" }),
    );
    expect(api.aendereTurnier).toHaveBeenCalledWith(
      "t1",
      expect.objectContaining({ tische: 2 }),
    );

    await userEvent.click(screen.getByRole("button", { name: "Beenden" }));
    expect(api.beendeTurnier).toHaveBeenCalledWith("t1");

    await userEvent.click(screen.getByRole("button", { name: "Löschen" }));
    expect(api.loescheTurnier).toHaveBeenCalledWith("t1");
  });

  it("legt ein erstes Turnier an", async () => {
    vi.spyOn(api, "ladeTurniere").mockResolvedValue([]);
    vi.spyOn(api, "legeTurnierAn").mockResolvedValue(turnier());
    render(mitAnmeldung(<TischtennisSeite unterseite="einstellungen" />, LEITER));

    await userEvent.type(
      await screen.findByLabelText("Name des Turniers"),
      "Kollegenturnier",
    );
    await userEvent.click(screen.getByRole("button", { name: "Turnier anlegen" }));

    expect(api.legeTurnierAn).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Kollegenturnier" }),
    );
  });

  it("hält einen Nutzer ohne Verwaltungsrecht von den Einstellungen fern", async () => {
    render(mitAnmeldung(<TischtennisSeite unterseite="einstellungen" />, NUTZER));

    expect(
      await screen.findByText(/Die Einstellungen ändert, wer dieses Artefakt verwaltet/),
    ).toBeInTheDocument();
  });

  it("weist ohne Turnier und ohne Verwaltungsrecht freundlich ab", async () => {
    vi.spyOn(api, "ladeTurniere").mockResolvedValue([]);
    render(mitAnmeldung(<TischtennisSeite unterseite="teilnehmer" />, NUTZER));

    expect(await screen.findByText(/Noch kein Turnier/)).toBeInTheDocument();
  });

  it("lässt zwischen mehreren Turnieren wählen", async () => {
    const zweites = turnier({ id: "t2", name: "Weihnachtsturnier" });
    vi.spyOn(api, "ladeTurniere").mockResolvedValue([turnier(), zweites]);
    vi.spyOn(api, "ladeTurnier").mockImplementation((id) =>
      Promise.resolve(id === "t2" ? zweites : turnier()),
    );
    render(mitAnmeldung(<TischtennisSeite unterseite="teilnehmer" />, LEITER));

    await userEvent.selectOptions(await screen.findByLabelText("Turnier"), "t2");

    // Als Überschrift, nicht als Eintrag in der Auswahl - dort steht der
    // Name auch vorher schon.
    expect(
      await screen.findByRole("heading", { name: "Weihnachtsturnier" }),
    ).toBeInTheDocument();
  });
});
