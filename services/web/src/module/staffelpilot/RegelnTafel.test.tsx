import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { RegelnTafel } from "./RegelnTafel";
import * as api from "./api";
import { minuten, regel, stunden, uhrzeit } from "./regelsatz.hilfen";

afterEach(() => {
  vi.restoreAllMocks();
});

async function aufklappen(name: RegExp | string) {
  await userEvent.click(await screen.findByRole("button", { name }));
}

describe("Regelkatalog", () => {
  it("sagt beim leeren Stand, was als Nächstes zu tun ist", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([]);
    render(<RegelnTafel />);

    expect(await screen.findByText("Noch keine Regeln")).toBeInTheDocument();
    expect(screen.getByText(/ersten Prüflauf/)).toBeInTheDocument();
  });

  it("zeigt Namen und Schwere, gruppiert nach Thema", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    render(<RegelnTafel />);

    const liste = await screen.findByRole("list", { name: "Karten und Sperren" });
    expect(within(liste).getByText("Feldverweis auf Dauer")).toBeInTheDocument();
    expect(within(liste).getByText("kritisch")).toBeInTheDocument();
  });

  it("zeigt Erklärung, Weg und Kennung erst beim Aufklappen", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    render(<RegelnTafel />);

    await screen.findByText("Feldverweis auf Dauer");
    expect(screen.queryByText("Meldet jeden Feldverweis auf Dauer.")).toBeNull();

    await aufklappen(/Feldverweis auf Dauer/);

    expect(screen.getByText("Meldet jeden Feldverweis auf Dauer.")).toBeInTheDocument();
    expect(screen.getByText("führt vors Sportgericht")).toBeInTheDocument();
    expect(screen.getByText("red_card")).toBeInTheDocument();
  });

  it("klappt wieder zu", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    render(<RegelnTafel />);

    await aufklappen(/Feldverweis auf Dauer/);
    await aufklappen(/Feldverweis auf Dauer/);

    expect(screen.queryByText("red_card")).toBeNull();
  });

  it("nennt keinen Weg, wenn die Regel zu nichts führt", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel({ weg: "kein" })]);
    render(<RegelnTafel />);

    await aufklappen(/Feldverweis auf Dauer/);
    expect(screen.queryByText(/führt/)).not.toBeInTheDocument();
  });

  it("schaltet eine Regel ab", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    const schalten = vi
      .spyOn(api, "schalteRegel")
      .mockResolvedValue(regel({ aktiv: false, angepasst: true }));
    render(<RegelnTafel />);

    const schalter = await screen.findByRole("checkbox", {
      name: "Feldverweis auf Dauer prüfen",
    });
    await userEvent.click(schalter);

    await waitFor(() => expect(schalten).toHaveBeenCalledWith("r1", false));
    await waitFor(() => expect(schalter).not.toBeChecked());
  });

  it("schaltet sie wieder an", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel({ aktiv: false })]);
    const schalten = vi.spyOn(api, "schalteRegel").mockResolvedValue(regel());
    render(<RegelnTafel />);

    await userEvent.click(
      await screen.findByRole("checkbox", { name: "Feldverweis auf Dauer prüfen" }),
    );

    await waitFor(() => expect(schalten).toHaveBeenCalledWith("r1", true));
  });

  it("lässt den Schalter stehen, wenn das Schalten scheitert", async () => {
    // Sonst zeigte die Oberfläche "aus" und der Prüfdienst meldete weiter -
    // genau die Lücke, vor der diese Ansicht schützen soll.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    vi.spyOn(api, "schalteRegel").mockRejectedValue(new ApiError("kaputt", 500));
    render(<RegelnTafel />);

    const schalter = await screen.findByRole("checkbox", {
      name: "Feldverweis auf Dauer prüfen",
    });
    await userEvent.click(schalter);

    expect(await screen.findByRole("alert")).toHaveTextContent("kaputt");
    expect(schalter).toBeChecked();
  });

  it("zeigt einen Ladefehler statt einer leeren Liste", async () => {
    vi.spyOn(api, "ladeRegeln").mockRejectedValue(new ApiError("kein Zugriff", 403));
    render(<RegelnTafel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });
});

describe("Werte einer Regel", () => {
  const mitFrist = (rest: Partial<api.Regel> = {}) =>
    regel({
      schluessel: "confirmation_late",
      name: "Bestätigung zu spät (eingebaut)",
      weg: "mahnung",
      parameter: [uhrzeit(), minuten(), stunden()],
      ...rest,
    });

  const angepasst = () =>
    mitFrist({
      angepasst: true,
      parameter: [uhrzeit(), minuten(), stunden({ wert: 6 })],
    });

  it("zeigt sie erst beim Aufklappen, mit Einheit und geltendem Wert", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitFrist()]);
    render(<RegelnTafel />);

    await screen.findByText("Bestätigung zu spät");
    expect(screen.queryByLabelText("Frist am Spieltag")).toBeNull();

    await aufklappen(/Bestätigung zu spät/);

    expect(screen.getByLabelText("Frist am Spieltag")).toHaveValue("18:00");
    expect(screen.getByLabelText("Zeit nach Spielende (Minuten)")).toHaveValue(60);
    expect(screen.getByLabelText("Kulanz (Stunden)")).toHaveValue(0);
  });

  it("nennt zu jedem Wert die Vorgabe", async () => {
    // Wer etwas verstellt hat, soll sehen, wovon er abweicht.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([angepasst()]);
    render(<RegelnTafel />);

    await aufklappen(/Bestätigung zu spät/);

    expect(screen.getByLabelText("Kulanz (Stunden)")).toHaveValue(6);
    expect(
      screen.getByText(/Kommt auf die Frist obendrauf\. Vorgabe: 0\./),
    ).toBeVisible();
  });

  it("rechnet beim Tippen mit, was am Ende gilt", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitFrist()]);
    render(<RegelnTafel />);
    await aufklappen(/Bestätigung zu spät/);

    const feld = screen.getByLabelText("Kulanz (Stunden)");
    await userEvent.clear(feld);
    await userEvent.type(feld, "6");

    expect(screen.getByText(/dazu 6 Std\. Kulanz/)).toBeInTheDocument();
  });

  it("speichert alle Werte und zeigt die Regel als angepasst", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitFrist()]);
    const speichern = vi.spyOn(api, "stelleRegelEin").mockResolvedValue(angepasst());
    render(<RegelnTafel />);
    await aufklappen(/Bestätigung zu spät/);

    const feld = screen.getByLabelText("Kulanz (Stunden)");
    await userEvent.clear(feld);
    await userEvent.type(feld, "6");
    await userEvent.click(screen.getByRole("button", { name: "Werte speichern" }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith("r1", {
        frist_uhrzeit: "18:00",
        nach_spielende: "60",
        kulanz: "6",
      }),
    );
    expect(await screen.findByText("angepasst")).toBeInTheDocument();
  });

  it("zeigt eine angepasste Frist schon in der Zeile", async () => {
    // Sonst müsste man jede Regel öffnen, um zu sehen, was man verstellt hat.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([angepasst()]);
    render(<RegelnTafel />);

    expect(await screen.findByText(/dazu 6 Std\. Kulanz/)).toBeInTheDocument();

    // Offen steht er beim Formular - ein zweites Mal darüber wäre Lärm.
    await aufklappen(/Bestätigung zu spät/);
    expect(screen.getAllByText(/dazu 6 Std\. Kulanz/)).toHaveLength(1);
  });

  it("behält die Eingabe und sagt, was geht, wenn der Wert nicht passt", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitFrist()]);
    vi.spyOn(api, "stelleRegelEin").mockRejectedValue(
      new ApiError("Kulanz: Bitte einen Wert zwischen 0 und 72 angeben.", 422),
    );
    render(<RegelnTafel />);
    await aufklappen(/Bestätigung zu spät/);

    const feld = screen.getByLabelText("Kulanz (Stunden)");
    await userEvent.clear(feld);
    await userEvent.type(feld, "99");
    await userEvent.click(screen.getByRole("button", { name: "Werte speichern" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("zwischen 0 und 72");
    expect(feld).toHaveValue(99);
  });

  it("setzt auf die Vorgabe zurück", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([angepasst()]);
    const speichern = vi.spyOn(api, "stelleRegelEin").mockResolvedValue(mitFrist());
    render(<RegelnTafel />);
    await aufklappen(/Bestätigung zu spät/);

    await userEvent.click(
      screen.getByRole("button", { name: "Auf Vorgabe zurücksetzen" }),
    );

    await waitFor(() => expect(speichern).toHaveBeenCalledWith("r1", {}));
    expect(screen.getByLabelText("Kulanz (Stunden)")).toHaveValue(0);
    expect(
      screen.queryByRole("button", { name: "Auf Vorgabe zurücksetzen" }),
    ).not.toBeInTheDocument();
  });

  it("bietet ohne Änderung weder Speichern noch Zurücksetzen an", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitFrist()]);
    render(<RegelnTafel />);
    await aufklappen(/Bestätigung zu spät/);

    expect(screen.getByRole("button", { name: "Werte speichern" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Auf Vorgabe zurücksetzen" })).toBeNull();
  });

  it("zeigt bei einer Regel ohne Werte kein leeres Formular", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    render(<RegelnTafel />);
    await aufklappen(/Feldverweis auf Dauer/);

    expect(screen.queryByRole("button", { name: "Werte speichern" })).toBeNull();
  });
});

describe("Für wen der Regelsatz gilt", () => {
  it("sagt, dass es der eigene ist und ab wann er gilt", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    render(<RegelnTafel />);

    expect(await screen.findByText(/für alle deine Staffeln/)).toBeInTheDocument();
    expect(screen.getByText(/ab dem nächsten Prüflauf/)).toBeInTheDocument();
  });
});

describe("Die Sätze fürs Schreiben", () => {
  const mitSatz = (rest: Partial<api.Regel> = {}) =>
    regel({
      weg: "mahnung",
      vorgabe_sachverhalt: "wurde durch {verein} nicht bestätigt.",
      vorgabe_hinweis: "Ich weise auf § 53 hin.",
      ...rest,
    });

  it("bietet sie nur an, wo überhaupt ein Schreiben entsteht", async () => {
    // Bei "kein" wäre es ein Feld, das nie irgendwo auftaucht.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz({ weg: "kein" })]);
    render(<RegelnTafel />);

    await aufklappen(/Feldverweis auf Dauer/);
    expect(screen.queryByText("Text fürs Schreiben")).not.toBeInTheDocument();
  });

  it("zeigt den mitgelieferten Satz als Platzhalter und nicht als Inhalt", async () => {
    // Wäre er Inhalt, hätte der erste Klick auf Speichern den heutigen
    // Wortlaut eingefroren - samt Paragraf, samt späterer Korrektur.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    render(<RegelnTafel />);
    await aufklappen(/Feldverweis auf Dauer/);

    const feld = screen.getByLabelText("Sachverhalt");
    expect(feld).toHaveValue("");
    expect(feld).toHaveAttribute("placeholder", "wurde durch {verein} nicht bestätigt.");
  });

  it("schickt beide Felder und übernimmt die Antwort", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    const speichern = vi
      .spyOn(api, "formuliereRegel")
      .mockResolvedValue(mitSatz({ sachverhalt: "war anders." }));
    render(<RegelnTafel />);
    await aufklappen(/Feldverweis auf Dauer/);

    await userEvent.type(screen.getByLabelText("Sachverhalt"), "war anders.");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith("r1", {
        sachverhalt: "war anders.",
        hinweis: "",
      }),
    );
    expect(await screen.findByText("eigener")).toBeInTheDocument();
  });

  it("behält die Eingabe, wenn das Speichern scheitert", async () => {
    // Sonst ist die Formulierung weg und der Fehler bleibt unerklärt.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    vi.spyOn(api, "formuliereRegel").mockRejectedValue(new ApiError("zu lang", 422));
    render(<RegelnTafel />);
    await aufklappen(/Feldverweis auf Dauer/);

    const feld = screen.getByLabelText("Sachverhalt");
    await userEvent.type(feld, "war anders.");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("zu lang");
    expect(feld).toHaveValue("war anders.");
  });

  it("verwirft eine Änderung auf Wunsch", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    render(<RegelnTafel />);
    await aufklappen(/Feldverweis auf Dauer/);

    await userEvent.type(screen.getByLabelText("Hinweis"), "anders");
    await userEvent.click(screen.getByRole("button", { name: "Verwerfen" }));

    expect(screen.getByLabelText("Hinweis")).toHaveValue("");
  });

  it("lässt nicht speichern, solange nichts geändert ist", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    render(<RegelnTafel />);
    await aufklappen(/Feldverweis auf Dauer/);

    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });

  it("sagt, dass sie nur für einen selbst gelten", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([mitSatz()]);
    render(<RegelnTafel />);
    await aufklappen(/Feldverweis auf Dauer/);

    expect(screen.getByText(/nur für deine Schreiben/)).toBeInTheDocument();
  });
});

describe("Einschränken", () => {
  const dreiRegeln = () => [
    // Jede mit eigener Beschreibung: die Vorgabe trägt selbst das Wort
    // "Feldverweis", und dann träfe die Suche danach zwei Regeln.
    regel({
      id: "r1",
      name: "Feldverweis auf Dauer",
      schluessel: "red_card",
      weg: "sportgericht",
      beschreibung: "Meldet jeden Platzverweis.",
    }),
    regel({
      id: "r2",
      name: "Bestätigung fehlt",
      schluessel: "confirmation_missing",
      weg: "mahnung",
      angepasst: true,
      beschreibung: "Eine Mannschaft hat nicht bestätigt.",
    }),
    regel({
      id: "r3",
      name: "Dokumente am Spielbericht",
      schluessel: "documents_present",
      weg: "kein",
      aktiv: false,
      angepasst: true,
      beschreibung: "Nennt Anhänge am Bericht.",
    }),
  ];

  it("zählt, was an und was angepasst ist", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue(dreiRegeln());
    render(<RegelnTafel />);

    expect(await screen.findByText("2 von 3 an · 2 angepasst")).toBeInTheDocument();
  });

  it("lässt das Angepasste weg, wenn nichts angepasst ist", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue([regel()]);
    render(<RegelnTafel />);

    expect(await screen.findByText("1 von 1 an")).toBeInTheDocument();
  });

  it("sucht im Namen", async () => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue(dreiRegeln());
    render(<RegelnTafel />);

    await userEvent.type(await screen.findByLabelText("Suchen"), "Feldverweis");

    expect(await screen.findByText("1 von 3 Regeln zu sehen")).toBeInTheDocument();
    expect(screen.queryByText("Bestätigung fehlt")).toBeNull();
  });

  it("sucht auch in der technischen Kennung", async () => {
    // Beim Nachsehen, warum ein Befund so heißt, hat man die Kennung und
    // nicht den Namen.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue(dreiRegeln());
    render(<RegelnTafel />);

    await userEvent.type(await screen.findByLabelText("Suchen"), "confirmation");

    expect(await screen.findByText("Bestätigung fehlt")).toBeInTheDocument();
    expect(screen.queryByText("Feldverweis auf Dauer")).toBeNull();
  });

  it.each([
    ["Aus", "Dokumente am Spielbericht", 1],
    ["An", "Feldverweis auf Dauer", 2],
    ["Angepasst", "Bestätigung fehlt", 2],
  ])("zeigt auf Wunsch nur: %s", async (wort, name, anzahl) => {
    vi.spyOn(api, "ladeRegeln").mockResolvedValue(dreiRegeln());
    render(<RegelnTafel />);

    await userEvent.click(await screen.findByRole("radio", { name: wort }));

    expect(screen.getByText(name)).toBeInTheDocument();
    expect(screen.getByText(`${anzahl} von 3 Regeln zu sehen`)).toBeInTheDocument();
  });

  it("sagt es, wenn die Einschränkung alles wegnimmt", async () => {
    // Eine leere Liste ohne Erklärung sieht aus wie ein leerer Regelkatalog -
    // und dann sucht jemand den Fehler im Prüfdienst.
    vi.spyOn(api, "ladeRegeln").mockResolvedValue(dreiRegeln());
    render(<RegelnTafel />);

    await userEvent.type(await screen.findByLabelText("Suchen"), "gibtesnicht");

    expect(await screen.findByText(/Keine Regel passt dazu/)).toBeInTheDocument();
  });
});
