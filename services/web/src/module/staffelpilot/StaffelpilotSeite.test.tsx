import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { alsDatum } from "./datum";
import { StaffelpilotSeite } from "./StaffelpilotSeite";

function staffel(rest: Partial<api.Staffel> = {}): api.Staffel {
  return {
    id: "s1",
    name: "Stadtliga C",
    altersklasse: "maenner",
    spielklasse: "3.Kreisliga (C)",
    saison: "26/27",
    aktiv: true,
    ...rest,
  };
}

function zeile(rest: Partial<api.SpielZeile> = {}): api.SpielZeile {
  return {
    id: "m1",
    dfbnet_id: "M-1",
    datum: "2026-09-13",
    heim: "SG Gittersee",
    gast: "SV Fortschritt",
    ergebnis: "2 : 1",
    abgehakt: false,
    offene_befunde: 1,
    kritische_befunde: 1,
    faellig: true,
    ...rest,
  };
}

function befund(rest: Partial<api.Befund> = {}): api.Befund {
  return {
    id: "b1",
    regel: "rote_karte",
    schwere: "kritisch",
    titel: "Feldverweis auf Dauer",
    text: "Feldverweis in Minute 71.",
    person: "Max Müller",
    mannschaft: "SG Gittersee",
    entscheidung: "offen",
    grund: "",
    weg: "kein",
    vorgang_id: null,
    ...rest,
  };
}

function spiel(rest: Partial<api.Spiel> = {}): api.Spiel {
  return {
    id: "m1",
    staffel_id: "s1",
    dfbnet_id: "M-1",
    datum: "2026-09-13",
    heim: "SG Gittersee",
    gast: "SV Fortschritt",
    ergebnis: "2 : 1",
    abgehakt: false,
    abgehakt_am: null,
    befunde: [befund()],
    ...rest,
  };
}

function uebersicht(rest: Partial<api.Zusammenfassung> = {}): api.Zusammenfassung {
  return {
    spiele: 1,
    offen: 1,
    abgehakt: 0,
    befunde_offen: 1,
    befunde_kritisch: 1,
    staffeln_aktiv: 1,
    vorgaenge_entwurf: 0,
    ...rest,
  };
}

/** Die Startfläche ist die Übersicht. Wer die Warteschlange prüfen will,
 *  geht in die Spielprüfung - im Test wie im Betrieb. */
async function zurSpielpruefung() {
  await userEvent.click(await screen.findByRole("tab", { name: "Spielprüfung" }));
}

function mitDaten(
  staffeln: api.Staffel[] = [staffel()],
  spiele: api.SpielZeile[] = [zeile()],
  zusammenfassung = uebersicht(),
) {
  vi.spyOn(api, "ladeStaffeln").mockResolvedValue(staffeln);
  vi.spyOn(api, "ladeWarteschlange").mockResolvedValue(spiele);
  vi.spyOn(api, "ladeZusammenfassung").mockResolvedValue(zusammenfassung);
}

beforeEach(() => {
  vi.spyOn(api, "ladeSpiel").mockResolvedValue(spiel());
  vi.spyOn(api, "entscheide").mockResolvedValue(befund({ entscheidung: "kenntnis" }));
  vi.spyOn(api, "hakeAb").mockResolvedValue(spiel({ abgehakt: true }));
  vi.spyOn(api, "loeseHaken").mockResolvedValue(spiel());
  vi.spyOn(api, "legeStaffelAn").mockResolvedValue(staffel());
  vi.spyOn(api, "ladeEinstellungen").mockResolvedValue({
    staffelleiter: "",
    verband: "",
    absender: "",
    pruefzeitraum_tage: 30,
    frist_tage: 14,
    uebertragung_pausiert: true,
  });
  vi.spyOn(api, "ladeVorgaenge").mockResolvedValue([]);
  vi.spyOn(api, "ladeMannschaften").mockResolvedValue([]);
  vi.spyOn(api, "ladeRegeln").mockResolvedValue([]);
  vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
  vi.spyOn(api, "ladeErgebnisse").mockResolvedValue({
    befunde: 0,
    offen: 0,
    spiele: 0,
    abgehakt: 0,
    vorgaenge: 0,
    nach_schwere: [],
    nach_regel: [],
    nach_mannschaft: [],
    nach_monat: [],
  });
  vi.spyOn(api, "ladeOffenenAuftrag").mockResolvedValue(null);
  vi.spyOn(api, "ladeAuftraege").mockResolvedValue([]);
  vi.spyOn(api, "ladeUebertragung").mockResolvedValue({
    pausiert: true,
    offen: 0,
    laeuft: 0,
    fertig: 0,
    fehler: 0,
    fehlerhafte: [],
  });
  vi.spyOn(api, "ladeZugang").mockResolvedValue({
    gespeichert: false,
    benutzer: "",
    schluessel_vorhanden: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Datum", () => {
  it("wird deutsch geschrieben", () => {
    expect(alsDatum("2026-09-13")).toBe("13.09.2026");
  });

  it("bleibt unveraendert, wenn es nicht wie ein Datum aussieht", () => {
    expect(alsDatum("irgendwas")).toBe("irgendwas");
  });
});

describe("StaffelPilot — die vier Zustände", () => {
  it("zeigt beim Laden einen Platzhalter statt eines Sprungs", () => {
    vi.spyOn(api, "ladeStaffeln").mockReturnValue(new Promise(() => {}));
    vi.spyOn(api, "ladeWarteschlange").mockReturnValue(new Promise(() => {}));
    vi.spyOn(api, "ladeZusammenfassung").mockReturnValue(new Promise(() => {}));

    render(<StaffelpilotSeite />);

    expect(screen.getByRole("status", { name: /geladen/i })).toBeInTheDocument();
  });

  it("zeigt die Meldung des Backends wörtlich, wenn das Laden scheitert", async () => {
    vi.spyOn(api, "ladeStaffeln").mockRejectedValue(
      new ApiError("Die Datenbank antwortet nicht", 503),
    );
    vi.spyOn(api, "ladeWarteschlange").mockResolvedValue([]);
    vi.spyOn(api, "ladeZusammenfassung").mockResolvedValue(uebersicht());

    render(<StaffelpilotSeite />);

    expect(await screen.findByText("Die Datenbank antwortet nicht")).toBeInTheDocument();
  });

  it("sagt ohne Staffel schon auf der Übersicht, was zu tun ist", async () => {
    // Wer das Programm zum ersten Mal aufmacht, landet hier - und soll nicht
    // erst eine Fläche suchen müssen.
    mitDaten(
      [],
      [],
      uebersicht({
        spiele: 0,
        offen: 0,
        befunde_offen: 0,
        befunde_kritisch: 0,
        staffeln_aktiv: 0,
      }),
    );

    render(<StaffelpilotSeite />);

    expect(await screen.findByText(/keine aktive staffel/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Staffeln verwalten" }),
    ).toBeInTheDocument();
  });

  it("und auch in der Spielprüfung", async () => {
    mitDaten([], [], uebersicht({ staffeln_aktiv: 0 }));

    render(<StaffelpilotSeite />);
    await zurSpielpruefung();

    expect(await screen.findByText(/noch keine staffel angelegt/i)).toBeInTheDocument();
  });

  it("sagt mit Staffel, aber ohne Spiele, woher die Berichte kommen", async () => {
    mitDaten([staffel()], []);

    render(<StaffelpilotSeite />);
    await zurSpielpruefung();

    expect(await screen.findByText(/keine spielberichte/i)).toBeInTheDocument();
    expect(screen.getByText(/POST \/staffelpilot\/import/)).toBeInTheDocument();
  });

  it("zeigt gefüllt die Paarung und die Zähler", async () => {
    mitDaten();

    render(<StaffelpilotSeite />);
    await zurSpielpruefung();

    expect(await screen.findByText("SG Gittersee – SV Fortschritt")).toBeInTheDocument();
    expect(screen.getByText("1 kritisch")).toBeInTheDocument();
  });

  it("zeigt die Zähler auf der Übersicht", async () => {
    mitDaten();

    render(<StaffelpilotSeite />);

    const ueberblick = await screen.findByRole("list", { name: "Überblick" });
    expect(within(ueberblick).getByText("zu prüfen")).toBeInTheDocument();
  });
});

describe("Ein Spielbericht", () => {
  it("klappt auf und zeigt seine Befunde", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    const kopf = await screen.findByRole("button", {
      name: /SG Gittersee – SV Fortschritt/,
    });

    await userEvent.click(kopf);

    expect(await screen.findByText("Feldverweis auf Dauer")).toBeInTheDocument();
    expect(screen.getByText("Feldverweis in Minute 71.")).toBeInTheDocument();
  });

  it("klappt beim zweiten Klick wieder zu", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    const kopf = await screen.findByRole("button", { name: /SG Gittersee/ });
    await userEvent.click(kopf);
    await screen.findByText("Feldverweis auf Dauer");

    await userEvent.click(kopf);

    await waitFor(() =>
      expect(screen.queryByText("Feldverweis auf Dauer")).not.toBeInTheDocument(),
    );
  });

  it("sagt, dass nichts zu tun ist, wenn der Bericht sauber ist", async () => {
    mitDaten([staffel()], [zeile({ offene_befunde: 0, kritische_befunde: 0 })]);
    vi.spyOn(api, "ladeSpiel").mockResolvedValue(spiel({ befunde: [] }));
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();

    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    expect(await screen.findByText(/keine befunde/i)).toBeInTheDocument();
  });
});

describe("Einen Befund entscheiden", () => {
  it("nimmt ihn zur Kenntnis", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    await userEvent.click(
      await screen.findByRole("button", { name: "Zur Kenntnis genommen" }),
    );

    expect(api.entscheide).toHaveBeenCalledWith("b1", "kenntnis", "");
  });

  it("fragt beim Verwerfen erst nach dem Grund", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    await userEvent.click(await screen.findByRole("button", { name: "Kein Verstoß" }));

    expect(screen.getByRole("textbox", { name: /warum/i })).toBeInTheDocument();
    expect(api.entscheide).not.toHaveBeenCalled();
  });

  it("schickt den Grund mit", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Kein Verstoß" }));

    await userEvent.type(
      screen.getByRole("textbox", { name: /warum/i }),
      "Spieler war spielberechtigt",
    );
    await userEvent.click(screen.getByRole("button", { name: "Verwerfen" }));

    expect(api.entscheide).toHaveBeenCalledWith(
      "b1",
      "verworfen",
      "Spieler war spielberechtigt",
    );
  });

  it("behält die Eingabe, wenn das Verwerfen scheitert", async () => {
    mitDaten();
    vi.spyOn(api, "entscheide").mockRejectedValue(
      new ApiError("Zum Verwerfen eines Befundes gehört eine Begründung", 422),
    );
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Kein Verstoß" }));
    const feld = screen.getByRole("textbox", { name: /warum/i });
    await userEvent.type(feld, "halber Satz");

    await userEvent.click(screen.getByRole("button", { name: "Verwerfen" }));

    expect(
      await screen.findByText("Zum Verwerfen eines Befundes gehört eine Begründung"),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /warum/i })).toHaveValue("halber Satz");
  });

  it("zeigt eine getroffene Entscheidung samt Grund", async () => {
    mitDaten();
    vi.spyOn(api, "ladeSpiel").mockResolvedValue(
      spiel({
        befunde: [befund({ entscheidung: "verworfen", grund: "war spielberechtigt" })],
      }),
    );
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();

    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    expect(await screen.findByText(/Verworfen: war spielberechtigt/)).toBeInTheDocument();
  });
});

describe("Abhaken", () => {
  it("hakt ab", async () => {
    mitDaten([staffel()], [zeile({ offene_befunde: 0, kritische_befunde: 0 })]);
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    await userEvent.click(await screen.findByRole("button", { name: "Abhaken" }));

    expect(api.hakeAb).toHaveBeenCalledWith("m1");
  });

  it("zeigt die Meldung des Backends, wenn noch Befunde offen sind", async () => {
    mitDaten();
    vi.spyOn(api, "hakeAb").mockRejectedValue(
      new ApiError("1 Befund braucht noch eine Entscheidung", 409),
    );
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    await userEvent.click(await screen.findByRole("button", { name: "Abhaken" }));

    // Gezielt die Meldung, nicht die Standzeile darunter: derselbe Satz
    // steht bewusst an beiden Stellen - einmal als Antwort auf den Klick,
    // einmal als dauerhafter Stand.
    const meldung = await screen.findByRole("alert");
    expect(meldung).toHaveTextContent("1 Befund braucht noch eine Entscheidung");
    // Die Liste bleibt stehen - ein Fehler bei einer Aktion tauscht sie nicht
    // gegen eine Fehlerseite aus.
    expect(screen.getByRole("list", { name: "Spielberichte" })).toBeInTheDocument();
  });

  it("löst den Haken wieder", async () => {
    mitDaten(
      [staffel()],
      [zeile({ abgehakt: true, offene_befunde: 0, kritische_befunde: 0 })],
    );
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    await userEvent.click(await screen.findByRole("button", { name: "Haken entfernen" }));

    expect(api.loeseHaken).toHaveBeenCalledWith("m1");
  });
});

describe("Staffeln", () => {
  it("legt eine an und leert das Formular", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await userEvent.click(await screen.findByRole("tab", { name: "Staffeln" }));
    await screen.findByRole("heading", { name: "Staffel anlegen" });

    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      "Ü35 1. Stadtklasse",
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Spielklasse" }),
      "1.Kreisklasse",
    );
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    expect(api.legeStaffelAn).toHaveBeenCalledWith({
      name: "Ü35 1. Stadtklasse",
      altersklasse: "maenner",
      spielklasse: "1.Kreisklasse",
      saison: "",
      spieltage: 0,
    });
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(""),
    );
  });

  it("behält die Eingabe, wenn das Anlegen scheitert", async () => {
    mitDaten();
    vi.spyOn(api, "legeStaffelAn").mockRejectedValue(
      new ApiError("Eine Staffel namens 'Stadtliga C' gibt es bereits", 409),
    );
    render(<StaffelpilotSeite />);
    await userEvent.click(await screen.findByRole("tab", { name: "Staffeln" }));
    await screen.findByRole("heading", { name: "Staffel anlegen" });
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Stadtliga C");
    await userEvent.type(
      screen.getByRole("textbox", { name: "Spielklasse" }),
      "3.Kreisliga (C)",
    );

    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    expect(
      await screen.findByText("Eine Staffel namens 'Stadtliga C' gibt es bereits"),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("Stadtliga C");
  });

  it("bietet den Filter erst ab zwei Staffeln an", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await screen.findByText("SG Gittersee – SV Fortschritt");

    expect(screen.queryByRole("combobox", { name: "Staffel" })).not.toBeInTheDocument();
  });

  it("filtert nach Staffel", async () => {
    mitDaten([staffel(), staffel({ id: "s2", name: "Ü35 1. Stadtklasse" })]);
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    const filter = await screen.findByRole("combobox", { name: "Staffel" });

    await userEvent.selectOptions(filter, "s2");

    await waitFor(() =>
      expect(api.ladeWarteschlange).toHaveBeenLastCalledWith(
        "s2",
        expect.anything(),
        false,
      ),
    );
  });
});

describe("Die Reiter", () => {
  it("fangen bei der Übersicht an", async () => {
    // Die Fläche, die man morgens aufmacht - wie in der alten Seitenleiste.
    mitDaten();
    render(<StaffelpilotSeite />);

    expect(await screen.findByRole("list", { name: "Überblick" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Übersicht" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("tragen die Punkte der alten Seitenleiste", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("list", { name: "Überblick" });

    const namen = screen.getAllByRole("tab").map((k) => k.textContent);

    expect(namen).toEqual([
      "Übersicht",
      "Spielprüfung",
      "Prüflauf",
      "Ergebnisse",
      "Staffeln",
      "Vorgänge",
      "Regeln",
      "Einstellungen",
      "DFBnet-Zugang",
    ]);
  });

  it("führen zu den Vorgängen", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("list", { name: "Überblick" });

    await userEvent.click(screen.getByRole("tab", { name: "Vorgänge" }));

    expect(await screen.findByText("Keine Vorgänge")).toBeInTheDocument();
  });

  it("führen zu den Einstellungen", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("list", { name: "Überblick" });

    await userEvent.click(screen.getByRole("tab", { name: "Einstellungen" }));

    expect(await screen.findByLabelText(/Staffelleiter/)).toBeInTheDocument();
  });

  it("führen zu den Staffeln, und die Mannschaften stehen dort", async () => {
    // Eine Staffel wird einmal im Jahr eingerichtet, und dazu gehört, wer
    // darin spielt. Zwei Flächen dafür wären ein Weg zu viel.
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("list", { name: "Überblick" });

    await userEvent.click(screen.getByRole("tab", { name: "Staffeln" }));
    await userEvent.click(await screen.findByRole("button", { name: /Stadtliga C/ }));

    expect(
      await screen.findByRole("heading", { name: "Mannschaften" }),
    ).toBeInTheDocument();
  });
});

describe("Aus einem Befund einen Entwurf machen", () => {
  it("bietet nichts an, wenn der Prüflauf keinen Weg gemeldet hat", async () => {
    // Die meisten Befunde sind Hinweise. Fuer sie einen Knopf anzubieten
    // hiesse, Arbeit vorzuschlagen, die es nicht gibt.
    mitDaten();
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByText("SG Gittersee – SV Fortschritt"));

    await screen.findByText("Feldverweis auf Dauer");
    expect(screen.queryByRole("button", { name: /entwerfen/ })).not.toBeInTheDocument();
  });

  it("bietet die Mahnung an, wenn der Weg dorthin führt", async () => {
    mitDaten();
    vi.spyOn(api, "ladeSpiel").mockResolvedValue(
      spiel({ befunde: [befund({ weg: "mahnung" })] }),
    );
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByText("SG Gittersee – SV Fortschritt"));

    expect(
      await screen.findByRole("button", { name: "Mahnung entwerfen" }),
    ).toBeInTheDocument();
  });

  it("legt den Entwurf an", async () => {
    mitDaten();
    vi.spyOn(api, "ladeSpiel").mockResolvedValue(
      spiel({ befunde: [befund({ weg: "sportgericht" })] }),
    );
    const anlegen = vi.spyOn(api, "legeVorgangAn").mockResolvedValue({
      id: "v1",
      befund_id: "b1",
      art: "sportgericht",
      aktenzeichen: "26-27-0001",
      verein: "SG Gittersee",
      betroffener: "Max Müller",
      betreff: "Antrag",
      zustand: "entwurf",
      grund: "",
      empfaenger: "",
      text: "",
      versandt_am: null,
    });
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByText("SG Gittersee – SV Fortschritt"));

    await userEvent.click(
      await screen.findByRole("button", { name: "Antrag entwerfen" }),
    );

    await waitFor(() => expect(anlegen).toHaveBeenCalledWith("b1"));
  });

  it("zeigt statt des Knopfes, dass der Entwurf schon steht", async () => {
    mitDaten();
    vi.spyOn(api, "ladeSpiel").mockResolvedValue(
      spiel({ befunde: [befund({ weg: "mahnung", vorgang_id: "v1" })] }),
    );
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByText("SG Gittersee – SV Fortschritt"));

    expect(await screen.findByText(/Entwurf angelegt/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /entwerfen/ })).not.toBeInTheDocument();
  });
});

describe("Nur fällige", () => {
  it("fragt die Warteschlange gefiltert ab", async () => {
    // Der haeufigste Handgriff am Montag: was ist seit dem Wochenende faellig.
    mitDaten();
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await screen.findByText("SG Gittersee – SV Fortschritt");

    await userEvent.click(screen.getByRole("button", { name: "Nur fällige" }));

    await waitFor(() =>
      expect(api.ladeWarteschlange).toHaveBeenLastCalledWith(
        undefined,
        expect.anything(),
        true,
      ),
    );
  });

  it("markiert ein Spiel außerhalb des Prüfzeitraums", async () => {
    mitDaten([staffel()], [zeile({ faellig: false })]);
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();

    expect(await screen.findByText("außerhalb des Prüfzeitraums")).toBeInTheDocument();
  });

  it("markiert ein abgehaktes Spiel nicht zusätzlich", async () => {
    // Zwei Etiketten fuer denselben Umstand sind eines zu viel: abgehakt
    // heisst erledigt, und dann ist der Zeitraum keine Auskunft mehr.
    mitDaten([staffel()], [zeile({ faellig: false, abgehakt: true })]);
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();

    const liste = await screen.findByRole("list", { name: "Spielberichte" });
    expect(within(liste).getByText("abgehakt")).toBeInTheDocument();
    expect(
      within(liste).queryByText("außerhalb des Prüfzeitraums"),
    ).not.toBeInTheDocument();
  });

  it("führt zu den Regeln", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("list", { name: "Überblick" });

    await userEvent.click(screen.getByRole("tab", { name: "Regeln" }));

    expect(await screen.findByText("Kein Regelkatalog")).toBeInTheDocument();
  });
});

describe("Eine Entscheidung zurücknehmen", () => {
  it("bietet es am entschiedenen Befund an", async () => {
    mitDaten();
    vi.spyOn(api, "ladeSpiel").mockResolvedValue(
      spiel({ befunde: [befund({ entscheidung: "kenntnis" })] }),
    );
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByText("SG Gittersee – SV Fortschritt"));

    expect(
      await screen.findByRole("button", { name: "Zurücknehmen" }),
    ).toBeInTheDocument();
  });

  it("bietet es am offenen Befund nicht an", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByText("SG Gittersee – SV Fortschritt"));

    await screen.findByText("Feldverweis auf Dauer");
    expect(
      screen.queryByRole("button", { name: "Zurücknehmen" }),
    ).not.toBeInTheDocument();
  });

  it("nimmt zurück", async () => {
    mitDaten();
    vi.spyOn(api, "ladeSpiel").mockResolvedValue(
      spiel({ befunde: [befund({ entscheidung: "verworfen", grund: "kein Verstoß" })] }),
    );
    const zurueck = vi.spyOn(api, "nimmEntscheidungZurueck").mockResolvedValue(befund());
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByText("SG Gittersee – SV Fortschritt"));

    await userEvent.click(await screen.findByRole("button", { name: "Zurücknehmen" }));

    await waitFor(() => expect(zurueck).toHaveBeenCalledWith("b1"));
  });

  it("zeigt die Meldung, wenn schon ein Schreiben hinaus ist", async () => {
    // Der Verein hat es. Ein Befund, der hier wieder "offen" heisst, waere
    // eine Akte, die dem widerspricht.
    mitDaten();
    vi.spyOn(api, "ladeSpiel").mockResolvedValue(
      spiel({ befunde: [befund({ entscheidung: "kenntnis", vorgang_id: "v1" })] }),
    );
    vi.spyOn(api, "nimmEntscheidungZurueck").mockRejectedValue(
      new ApiError("Zu diesem Befund ist ein Schreiben versandt.", 409),
    );
    render(<StaffelpilotSeite />);
    await zurSpielpruefung();
    await userEvent.click(await screen.findByText("SG Gittersee – SV Fortschritt"));

    await userEvent.click(await screen.findByRole("button", { name: "Zurücknehmen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Schreiben versandt/);
  });
});

describe("Die neuen Reiter", () => {
  it("führen zu den Ergebnissen", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("list", { name: "Überblick" });

    await userEvent.click(screen.getByRole("tab", { name: "Ergebnisse" }));

    expect(await screen.findByRole("list", { name: "Bilanz" })).toBeInTheDocument();
  });

  it("führen zum DFBnet-Zugang", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("list", { name: "Überblick" });

    await userEvent.click(screen.getByRole("tab", { name: "DFBnet-Zugang" }));

    expect(
      await screen.findByRole("heading", { name: "DFBnet-Zugang" }),
    ).toBeInTheDocument();
  });

  it("führen zum Prüflauf", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("list", { name: "Überblick" });

    await userEvent.click(screen.getByRole("tab", { name: "Prüflauf" }));

    expect(
      await screen.findByRole("button", { name: "Prüflauf anfordern" }),
    ).toBeInTheDocument();
  });

  it("halten die Einstellungen frei vom Zugang", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("list", { name: "Überblick" });

    await userEvent.click(screen.getByRole("tab", { name: "Einstellungen" }));

    await screen.findByLabelText(/Staffelleiter/);
    expect(
      screen.queryByRole("heading", { name: "DFBnet-Zugang" }),
    ).not.toBeInTheDocument();
  });
});
