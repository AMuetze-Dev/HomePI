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
    ...rest,
  };
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

  it("sagt ohne Staffel, was als Nächstes zu tun ist", async () => {
    mitDaten([], [], uebersicht({ spiele: 0, offen: 0, befunde_offen: 0, befunde_kritisch: 0 }));

    render(<StaffelpilotSeite />);

    expect(await screen.findByText(/noch keine staffel angelegt/i)).toBeInTheDocument();
  });

  it("sagt mit Staffel, aber ohne Spiele, woher die Berichte kommen", async () => {
    mitDaten([staffel()], []);

    render(<StaffelpilotSeite />);

    expect(await screen.findByText(/keine spielberichte/i)).toBeInTheDocument();
    expect(screen.getByText(/POST \/staffelpilot\/import/)).toBeInTheDocument();
  });

  it("zeigt gefüllt die Paarung und die Zähler", async () => {
    mitDaten();

    render(<StaffelpilotSeite />);

    expect(await screen.findByText("SG Gittersee – SV Fortschritt")).toBeInTheDocument();
    expect(screen.getByText("1 kritisch")).toBeInTheDocument();
    const ueberblick = screen.getByRole("list", { name: "Überblick" });
    expect(within(ueberblick).getByText("zu prüfen")).toBeInTheDocument();
  });
});

describe("Ein Spielbericht", () => {
  it("klappt auf und zeigt seine Befunde", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    const kopf = await screen.findByRole("button", { name: /SG Gittersee – SV Fortschritt/ });

    await userEvent.click(kopf);

    expect(await screen.findByText("Feldverweis auf Dauer")).toBeInTheDocument();
    expect(screen.getByText("Feldverweis in Minute 71.")).toBeInTheDocument();
  });

  it("klappt beim zweiten Klick wieder zu", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
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

    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    expect(await screen.findByText(/keine befunde/i)).toBeInTheDocument();
  });
});

describe("Einen Befund entscheiden", () => {
  it("nimmt ihn zur Kenntnis", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    await userEvent.click(await screen.findByRole("button", { name: "Zur Kenntnis genommen" }));

    expect(api.entscheide).toHaveBeenCalledWith("b1", "kenntnis", "");
  });

  it("fragt beim Verwerfen erst nach dem Grund", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    await userEvent.click(await screen.findByRole("button", { name: "Kein Verstoß" }));

    expect(screen.getByRole("textbox", { name: /warum/i })).toBeInTheDocument();
    expect(api.entscheide).not.toHaveBeenCalled();
  });

  it("schickt den Grund mit", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Kein Verstoß" }));

    await userEvent.type(
      screen.getByRole("textbox", { name: /warum/i }),
      "Spieler war spielberechtigt",
    );
    await userEvent.click(screen.getByRole("button", { name: "Verwerfen" }));

    expect(api.entscheide).toHaveBeenCalledWith("b1", "verworfen", "Spieler war spielberechtigt");
  });

  it("behält die Eingabe, wenn das Verwerfen scheitert", async () => {
    mitDaten();
    vi.spyOn(api, "entscheide").mockRejectedValue(
      new ApiError("Zum Verwerfen eines Befundes gehört eine Begründung", 422),
    );
    render(<StaffelpilotSeite />);
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
      spiel({ befunde: [befund({ entscheidung: "verworfen", grund: "war spielberechtigt" })] }),
    );
    render(<StaffelpilotSeite />);

    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    expect(await screen.findByText(/Verworfen: war spielberechtigt/)).toBeInTheDocument();
  });
});

describe("Abhaken", () => {
  it("hakt ab", async () => {
    mitDaten([staffel()], [zeile({ offene_befunde: 0, kritische_befunde: 0 })]);
    render(<StaffelpilotSeite />);
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
    mitDaten([staffel()], [zeile({ abgehakt: true, offene_befunde: 0, kritische_befunde: 0 })]);
    render(<StaffelpilotSeite />);
    await userEvent.click(await screen.findByRole("button", { name: /SG Gittersee/ }));

    await userEvent.click(await screen.findByRole("button", { name: "Haken entfernen" }));

    expect(api.loeseHaken).toHaveBeenCalledWith("m1");
  });
});

describe("Staffeln", () => {
  it("legt eine an und leert das Formular", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByRole("heading", { name: "Staffel anlegen" });

    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Ü35 1. Stadtklasse");
    await userEvent.type(screen.getByRole("textbox", { name: "Spielklasse" }), "1.Kreisklasse");
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    expect(api.legeStaffelAn).toHaveBeenCalledWith({
      name: "Ü35 1. Stadtklasse",
      altersklasse: "maenner",
      spielklasse: "1.Kreisklasse",
      saison: "",
    });
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(""));
  });

  it("behält die Eingabe, wenn das Anlegen scheitert", async () => {
    mitDaten();
    vi.spyOn(api, "legeStaffelAn").mockRejectedValue(
      new ApiError("Eine Staffel namens 'Stadtliga C' gibt es bereits", 409),
    );
    render(<StaffelpilotSeite />);
    await screen.findByRole("heading", { name: "Staffel anlegen" });
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Stadtliga C");
    await userEvent.type(screen.getByRole("textbox", { name: "Spielklasse" }), "3.Kreisliga (C)");

    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    expect(
      await screen.findByText("Eine Staffel namens 'Stadtliga C' gibt es bereits"),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("Stadtliga C");
  });

  it("bietet den Filter erst ab zwei Staffeln an", async () => {
    mitDaten();
    render(<StaffelpilotSeite />);
    await screen.findByText("SG Gittersee – SV Fortschritt");

    expect(screen.queryByRole("combobox", { name: "Staffel" })).not.toBeInTheDocument();
  });

  it("filtert nach Staffel", async () => {
    mitDaten([staffel(), staffel({ id: "s2", name: "Ü35 1. Stadtklasse" })]);
    render(<StaffelpilotSeite />);
    const filter = await screen.findByRole("combobox", { name: "Staffel" });

    await userEvent.selectOptions(filter, "s2");

    await waitFor(() =>
      expect(api.ladeWarteschlange).toHaveBeenLastCalledWith("s2", expect.anything()),
    );
  });
});
