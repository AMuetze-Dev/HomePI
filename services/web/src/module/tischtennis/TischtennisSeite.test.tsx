import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Benutzer } from "../../api/anmeldung";
import { ApiError } from "../../api/client";
import { TESTBENUTZER, mitAnmeldung } from "../../testhilfen";
import * as api from "./api";
import { dashboard, spiel, tabelle, turnier } from "./testdaten";
import { TischtennisSeite } from "./TischtennisSeite";

const LEITER: Benutzer = { ...TESTBENUTZER, rechte: { tischtennis: "verwalter" } };
const NUTZER: Benutzer = { ...TESTBENUTZER, rechte: { tischtennis: "nutzer" } };
const ZUSCHAUER: Benutzer = { ...TESTBENUTZER, rechte: {} };

const LAEUFT = turnier({
  zustand: "laufend",
  anzahl_spiele: 1,
  offene_spiele: 1,
  saat: 7,
});

beforeEach(() => {
  vi.spyOn(api, "ladeTurniere").mockResolvedValue([turnier()]);
  vi.spyOn(api, "ladeTurnier").mockResolvedValue(turnier());
  vi.spyOn(api, "ladeTeilnehmer").mockResolvedValue([
    { id: "p1", name: "Anna", notiz: "", gruppe: null, freilose: 0 },
  ]);
  vi.spyOn(api, "ladeSpiele").mockResolvedValue([]);
  vi.spyOn(api, "ladeTabellen").mockResolvedValue([]);
  vi.spyOn(api, "ladeDashboard").mockResolvedValue(dashboard());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Tischtennisturnier", () => {
  it("zeigt zuerst einen Ladehinweis", () => {
    vi.spyOn(api, "ladeTurniere").mockReturnValue(new Promise(() => {}));

    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, LEITER));

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });

  it("meldet, wenn das Gateway nicht erreichbar ist", async () => {
    vi.spyOn(api, "ladeTurniere").mockRejectedValue(new ApiError("Gateway weg", 503));

    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, LEITER));

    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway weg");
  });

  it("führt den Verwalter ohne Turnier zum Anlegen", async () => {
    vi.spyOn(api, "ladeTurniere").mockResolvedValue([]);

    render(mitAnmeldung(<TischtennisSeite unterseite="einstellungen" />, LEITER));

    expect(await screen.findByLabelText("Name des Turniers")).toBeInTheDocument();
  });

  it("schickt einen Zuschauer zum Dashboard statt ihn abzuweisen", async () => {
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, ZUSCHAUER));

    expect(await screen.findByText(/Turnierleitung/)).toBeInTheDocument();
  });

  it("zeigt dem Besucher das Dashboard ohne Anmeldung", async () => {
    render(mitAnmeldung(<TischtennisSeite unterseite="dashboard" />, null));

    expect(
      await screen.findByRole("heading", { name: "An den Tischen" }),
    ).toBeInTheDocument();
  });

  it("holt für das Dashboard nur den einen Abruf", async () => {
    /* Ein Besucher soll nicht auf vier Abfragen warten, die er auf dieser
       Fläche gar nicht sieht. */
    render(mitAnmeldung(<TischtennisSeite unterseite="dashboard" />, null));

    await screen.findByRole("region", { name: "An den Tischen" });
    expect(api.ladeSpiele).not.toHaveBeenCalled();
    expect(api.ladeTabellen).not.toHaveBeenCalled();
  });
});

describe("Der Bereich Turnier", () => {
  it("trägt einen Teilnehmer ein und lädt danach neu", async () => {
    vi.spyOn(api, "legeTeilnehmerAn").mockResolvedValue({
      id: "p2",
      name: "Bernd",
      notiz: "",
      gruppe: null,
      freilose: 0,
    });
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, LEITER));

    await userEvent.type(await screen.findByLabelText("Name"), "Bernd");
    await userEvent.click(screen.getByRole("button", { name: "Eintragen" }));

    expect(api.legeTeilnehmerAn).toHaveBeenCalledWith("t1", { name: "Bernd" });
    // Zweimal: einmal beim Aufbau, einmal nach der Aktion.
    expect(api.ladeTeilnehmer).toHaveBeenCalledTimes(2);
  });

  it("zeigt die Meldung des Backends wörtlich und behält die Eingabe", async () => {
    vi.spyOn(api, "legeTeilnehmerAn").mockRejectedValue(
      new ApiError("Anna steht schon auf der Liste", 409),
    );
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, LEITER));

    await userEvent.type(await screen.findByLabelText("Name"), "Anna");
    await userEvent.click(screen.getByRole("button", { name: "Eintragen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "steht schon auf der Liste",
    );
    expect(screen.getByLabelText("Name")).toHaveValue("Anna");
  });

  it("würfelt aus demselben Bereich heraus", async () => {
    vi.spyOn(api, "loseAus").mockResolvedValue({
      saat: 4711,
      modus: "gruppen_ko",
      gruppen: [{ name: "Gruppe A", teilnehmer: ["Anna", "Bernd"] }],
      paarungen: [],
      anzahl_spiele: 1,
      dauer_minuten: 12,
      hinweis: "",
    });
    vi.spyOn(api, "wuerfleAus").mockResolvedValue(LAEUFT);
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, LEITER));

    await userEvent.click(await screen.findByRole("button", { name: "Würfeln" }));
    await userEvent.click(await screen.findByRole("button", { name: /Übernehmen/ }));

    expect(api.wuerfleAus).toHaveBeenCalledWith("t1", 4711);
  });

  it("wertet ein Spiel mit einem Tippen auf den Sieger", async () => {
    vi.spyOn(api, "ladeTurnier").mockResolvedValue(LAEUFT);
    vi.spyOn(api, "ladeSpiele").mockResolvedValue([spiel()]);
    vi.spyOn(api, "trageErgebnisEin").mockResolvedValue(
      spiel({ zustand: "beendet", sieger_id: "p1" }),
    );
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, LEITER));

    await userEvent.click(await screen.findByRole("button", { name: "Anna gewinnt" }));

    expect(api.trageErgebnisEin).toHaveBeenCalledWith("s1", "p1");
  });

  it("schiebt ein Spiel in der Warteschlange", async () => {
    /* Wer gerade nicht da ist, haelt sonst den ganzen Plan auf. Trotzdem
       anzupfeifen waere die schlechtere Loesung: dann stimmt die
       Warteschlange im Dashboard nicht, und die Glocke laeutet beim
       Falschen. */
    vi.spyOn(api, "ladeTurnier").mockResolvedValue(LAEUFT);
    vi.spyOn(api, "ladeSpiele").mockResolvedValue([spiel()]);
    vi.spyOn(api, "verschiebeSpiel").mockResolvedValue(spiel());
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, LEITER));

    await userEvent.click(
      await screen.findByRole("button", { name: "Spiel 1 nach hinten schieben" }),
    );

    expect(api.verschiebeSpiel).toHaveBeenCalledWith("s1", "runter");
  });

  it("lässt ohne Verwaltungsrecht nicht schieben", async () => {
    vi.spyOn(api, "ladeTurnier").mockResolvedValue(LAEUFT);
    vi.spyOn(api, "ladeSpiele").mockResolvedValue([spiel()]);
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, NUTZER));

    await screen.findByRole("button", { name: "Anna gewinnt" });
    expect(
      screen.queryByRole("button", { name: /nach hinten schieben/ }),
    ).not.toBeInTheDocument();
  });

  it("setzt die nächste Runde an", async () => {
    vi.spyOn(api, "ladeTurnier").mockResolvedValue(
      turnier({ zustand: "laufend", offene_spiele: 0 }),
    );
    vi.spyOn(api, "ladeSpiele").mockResolvedValue([
      spiel({ zustand: "beendet", sieger_id: "p1" }),
    ]);
    vi.spyOn(api, "naechsteRunde").mockResolvedValue(turnier({ zustand: "laufend" }));
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, LEITER));

    await userEvent.click(
      await screen.findByRole("button", { name: "KO-Raster ansetzen" }),
    );

    expect(api.naechsteRunde).toHaveBeenCalledWith("t1");
  });

  it("lässt einen Nutzer ohne Verwaltungsrecht werten, aber nicht würfeln", async () => {
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, NUTZER));

    expect(await screen.findByLabelText("Name")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Würfeln" })).not.toBeInTheDocument();
  });
});

describe("Der Bereich Einstellungen", () => {
  it("speichert geänderte Einstellungen", async () => {
    vi.spyOn(api, "aendereTurnier").mockResolvedValue(turnier({ tische: 3 }));
    render(mitAnmeldung(<TischtennisSeite unterseite="einstellungen" />, LEITER));

    await userEvent.click(
      await screen.findByRole("button", { name: "Einstellungen speichern" }),
    );

    expect(api.aendereTurnier).toHaveBeenCalledWith(
      "t1",
      expect.objectContaining({ tische: 2 }),
    );
  });

  it("hält einen Nutzer ohne Verwaltungsrecht fern", async () => {
    render(mitAnmeldung(<TischtennisSeite unterseite="einstellungen" />, NUTZER));

    expect(
      await screen.findByText(/Die Einstellungen ändert, wer dieses Artefakt verwaltet/),
    ).toBeInTheDocument();
  });

  it("lässt zwischen mehreren Turnieren wählen", async () => {
    const zweites = turnier({ id: "t2", name: "Weihnachtsturnier" });
    vi.spyOn(api, "ladeTurniere").mockResolvedValue([turnier(), zweites]);
    vi.spyOn(api, "ladeTurnier").mockImplementation((id) =>
      Promise.resolve(id === "t2" ? zweites : turnier()),
    );
    vi.spyOn(api, "ladeTabellen").mockResolvedValue([tabelle()]);
    render(mitAnmeldung(<TischtennisSeite unterseite="turnier" />, LEITER));

    await userEvent.selectOptions(await screen.findByLabelText("Turnier"), "t2");

    // Der Turniername steht jetzt neben dem Titel der Fläche und nicht
    // mehr als eigene Überschrift darüber: Die Fläche heißt "Turnier", und
    // welches gemeint ist, gehört daneben.
    // Der Name steht zweimal: einmal als gewaehlte Option im Auswahlfeld,
    // einmal neben dem Titel der Flaeche. Gemeint ist der zweite.
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1, name: "Turnier" }).parentElement,
      ).toHaveTextContent("Weihnachtsturnier"),
    );
  });
});
