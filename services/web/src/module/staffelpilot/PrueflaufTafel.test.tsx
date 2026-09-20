import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { PrueflaufTafel } from "./PrueflaufTafel";
import { ergebnisSatz } from "./ergebnis";
import * as api from "./api";

function staffel(rest: Partial<api.Staffel> = {}): api.Staffel {
  return {
    id: "s1",
    name: "Stadtliga C",
    altersklasse: "maenner",
    spielklasse: "3.Kreisliga (C)",
    saison: "26/27",
  spieltage: 0,
    aktiv: true,
    ...rest,
  };
}

function auftrag(rest: Partial<api.Auftrag> = {}): api.Auftrag {
  return {
    id: "a1",
    art: "pruflauf",
    staffel_id: null,
    zustand: "angefordert",
    schritt: "",
    fortschritt: 0,
    gepruefte: 0,
    befunde: 0,
    meldung: "",
    protokoll: [],
    gestartet_am: null,
    beendet_am: null,
    angelegt: "2026-09-19T10:00:00Z",
    ...rest,
  };
}

function stand(rest: Partial<api.UebertragungStand> = {}): api.UebertragungStand {
  return {
    pausiert: true,
    offen: 0,
    laeuft: 0,
    fertig: 0,
    fehler: 0,
    fehlerhafte: [],
    ...rest,
  };
}

function mitStand(
  offen: api.Auftrag | null = null,
  verlauf: api.AuftragZeile[] = [],
  uebertragung = stand(),
) {
  vi.spyOn(api, "ladeOffenenAuftrag").mockResolvedValue(offen);
  vi.spyOn(api, "ladeAuftraege").mockResolvedValue(verlauf);
  vi.spyOn(api, "ladeUebertragung").mockResolvedValue(uebertragung);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Einen Prüflauf anfordern", () => {
  it("sagt, dass hier nichts läuft", async () => {
    // Die eine Zusage dieser Flaeche: der Knopf fordert an, er startet nicht.
    mitStand();
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    expect(await screen.findByText(/Gearbeitet wird im Prüfdienst/)).toBeInTheDocument();
  });

  it("fordert an", async () => {
    mitStand();
    const fordern = vi.spyOn(api, "fordereAuftragAn").mockResolvedValue(auftrag());
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Prüflauf anfordern" }),
    );

    await waitFor(() => expect(fordern).toHaveBeenCalledWith("pruflauf", undefined));
  });

  it("fordert die Saisondaten als eigene Art an", async () => {
    mitStand();
    const fordern = vi.spyOn(api, "fordereAuftragAn").mockResolvedValue(auftrag());
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Saisondaten holen" }),
    );

    await waitFor(() =>
      expect(fordern).toHaveBeenCalledWith("initialisierung", undefined),
    );
  });

  it("bietet die Staffelwahl erst ab zwei Staffeln", async () => {
    mitStand();
    render(<PrueflaufTafel staffeln={[staffel()]} />);
    await screen.findByRole("button", { name: "Prüflauf anfordern" });

    expect(screen.queryByRole("combobox", { name: "Staffel" })).not.toBeInTheDocument();
  });

  it("zeigt die Meldung des Backends, wenn schon einer läuft", async () => {
    mitStand();
    vi.spyOn(api, "fordereAuftragAn").mockRejectedValue(
      new ApiError("Es ist bereits ein Auftrag unterwegs.", 409),
    );
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Prüflauf anfordern" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(/bereits ein Auftrag/);
  });
});

describe("Ein laufender Auftrag", () => {
  it("sagt beim Warten, dass er wartet — statt Fortschritt vorzutäuschen", async () => {
    mitStand(auftrag());
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    expect(await screen.findByText(/Wartet auf den Prüfdienst/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Fortschritt" })).toHaveAttribute(
      "aria-valuenow",
      "0",
    );
  });

  it("zeigt Zahl und Balken", async () => {
    // Ein Balken allein ist auf einem Telefon bei schlechtem Licht nicht
    // abzulesen.
    mitStand(auftrag({ zustand: "laeuft", fortschritt: 40, schritt: "Prüfe M-1" }));
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    expect(await screen.findByText(/40 % · Prüfe M-1/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Fortschritt" })).toHaveAttribute(
      "aria-valuenow",
      "40",
    );
  });

  it("zeigt das Protokoll", async () => {
    mitStand(
      auftrag({
        zustand: "laeuft",
        protokoll: [{ zeit: "2026-09-19T10:00:05", text: "Angemeldet" }],
      }),
    );
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    const protokoll = await screen.findByRole("list", { name: "Protokoll" });
    expect(within(protokoll).getByText(/Angemeldet/)).toBeInTheDocument();
  });

  it("bricht ab", async () => {
    mitStand(auftrag());
    const abbrechen = vi
      .spyOn(api, "brichAuftragAb")
      .mockResolvedValue(auftrag({ zustand: "abgebrochen" }));
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    await userEvent.click(await screen.findByRole("button", { name: "Abbrechen" }));

    await waitFor(() => expect(abbrechen).toHaveBeenCalledWith("a1"));
  });

  it("bietet währenddessen keinen zweiten Lauf an", async () => {
    mitStand(auftrag());
    render(<PrueflaufTafel staffeln={[staffel()]} />);
    await screen.findByRole("button", { name: "Abbrechen" });

    expect(
      screen.queryByRole("button", { name: "Prüflauf anfordern" }),
    ).not.toBeInTheDocument();
  });
});

describe("Der Verlauf", () => {
  it("sagt beim leeren Stand, was hier stünde", async () => {
    mitStand();
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    expect(await screen.findByText("Noch kein Lauf")).toBeInTheDocument();
  });

  it("zeigt Ergebnis und Meldung", async () => {
    mitStand(null, [
      auftrag({
        zustand: "gescheitert",
        gepruefte: 12,
        befunde: 3,
        meldung: "DFBnet weg",
      }),
    ]);
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    // Die Meldung geht vor: sie sagt, was los war, die Zahlen nur, wie viel.
    const liste = await screen.findByRole("list", { name: "Bisherige Läufe" });
    expect(within(liste).getByText("DFBnet weg")).toBeInTheDocument();
    expect(within(liste).getByText("Gescheitert")).toBeInTheDocument();
  });
});

describe("Die Übertragung", () => {
  it("sagt ausdrücklich, dass sie angehalten ist", async () => {
    mitStand();
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    expect(await screen.findByText(/Die Übertragung ist angehalten/)).toBeInTheDocument();
  });

  it("gibt sie frei", async () => {
    mitStand();
    const setzen = vi
      .spyOn(api, "setzeUebertragungPause")
      .mockResolvedValue(stand({ pausiert: false }));
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Übertragung freigeben" }),
    );

    await waitFor(() => expect(setzen).toHaveBeenCalledWith(false));
  });

  it("zählt, was vorgemerkt und was gescheitert ist", async () => {
    mitStand(null, [], stand({ offen: 2, fertig: 5, fehler: 1 }));
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    const zahlen = await screen.findByRole("list", { name: "Übertragung" });
    expect(within(zahlen).getByText("2")).toBeInTheDocument();
    expect(within(zahlen).getByText("5")).toBeInTheDocument();
  });

  it("schreibt die gescheiterten aus", async () => {
    // Sie sind das Einzige, wozu jemand etwas tun muss.
    mitStand(
      null,
      [],
      stand({
        fehler: 1,
        fehlerhafte: [
          {
            id: "u1",
            aktion: "prueferfreigabe",
            referenz: "M-1",
            spiel_id: null,
            zustand: "fehler",
            versuche: 3,
            letzter_fehler: "Zeitüberschreitung",
            erledigt_am: null,
            angelegt: "2026-09-19T10:00:00Z",
          },
        ],
      }),
    );
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    const liste = await screen.findByRole("list", { name: "Gescheiterte Übertragungen" });
    expect(within(liste).getByText(/Zeitüberschreitung/)).toBeInTheDocument();
    expect(within(liste).getByText(/3 Versuche/)).toBeInTheDocument();
  });

  it("wiederholt alle gescheiterten auf einmal", async () => {
    mitStand(null, [], stand({ fehler: 2 }));
    const wiederholen = vi
      .spyOn(api, "wiederholeUebertragung")
      .mockResolvedValue(stand({ offen: 2 }));
    render(<PrueflaufTafel staffeln={[staffel()]} />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Gescheiterte wiederholen" }),
    );

    await waitFor(() => expect(wiederholen).toHaveBeenCalledWith());
  });

  it("bietet das Wiederholen nicht an, wenn nichts gescheitert ist", async () => {
    mitStand();
    render(<PrueflaufTafel staffeln={[staffel()]} />);
    await screen.findByRole("list", { name: "Übertragung" });

    expect(
      screen.queryByRole("button", { name: "Gescheiterte wiederholen" }),
    ).not.toBeInTheDocument();
  });
});

describe("Was ein beendeter Auftrag gebracht hat", () => {
  it("nennt die Meldung, wenn es eine gibt", () => {
    // "0 geprüft, 0 Befunde" unter "Keine aktive Staffel" ist keine Auskunft.
    const satz = ergebnisSatz(
      auftrag({
        zustand: "fertig",
        meldung: "Keine aktive Staffel — erst eine anlegen.",
      }),
    );

    expect(satz).toBe("Keine aktive Staffel — erst eine anlegen.");
  });

  it("zählt beim Prüflauf, was geprüft wurde", () => {
    expect(ergebnisSatz(auftrag({ zustand: "fertig", gepruefte: 12, befunde: 3 }))).toBe(
      "12 geprüft, 3 Befunde",
    );
  });

  it("sagt beim leeren Prüflauf, warum nichts kam", () => {
    expect(ergebnisSatz(auftrag({ zustand: "fertig" }))).toBe(
      "Keine Spielberichte im Prüfzeitraum",
    );
  });

  it("verwechselt eine Initialisierung nicht mit einem Prüflauf", () => {
    // Sie holt Mannschaften und prüft nichts - "0 geprüft" wäre eine
    // Verwechslung und keine Null.
    const satz = ergebnisSatz(auftrag({ art: "initialisierung", zustand: "fertig" }));

    expect(satz).toBe("Mannschaften geholt");
    expect(satz).not.toContain("geprüft");
  });

  it("sagt beim wartenden Auftrag, worauf er wartet", () => {
    expect(ergebnisSatz(auftrag({ zustand: "angefordert" }))).toBe(
      "Wartet auf den Prüfdienst",
    );
  });
});

describe("Wenn ein Lauf zu Ende ist", () => {
  it("sagt die Tafel Bescheid", async () => {
    // Ohne das steht die Spielprüfung noch auf dem Stand von vorhin, und die
    // frisch eingespielten Berichte erscheinen erst nach einem Neuladen.
    // Genau das hat der Oberflächentest gefunden.
    //
    // Echte Uhr statt `vi.useFakeTimers`: der Takt startet erst, wenn der
    // erste Ladevorgang durch ist, und dieses Zusammenspiel aus Versprechen
    // und Zeitgeber lässt sich mit gestellter Zeit nicht ehrlich nachstellen.
    const fertig = vi.fn();
    vi.spyOn(api, "ladeAuftraege").mockResolvedValue([]);
    vi.spyOn(api, "ladeUebertragung").mockResolvedValue(stand());
    const offen = vi
      .spyOn(api, "ladeOffenenAuftrag")
      .mockResolvedValue(auftrag({ zustand: "laeuft" }));

    render(<PrueflaufTafel staffeln={[staffel()]} onFertig={fertig} />);
    await screen.findByRole("button", { name: "Abbrechen" });
    expect(fertig).not.toHaveBeenCalled();

    offen.mockResolvedValue(null);

    await waitFor(() => expect(fertig).toHaveBeenCalledTimes(1), { timeout: 8000 });
  }, 12_000);

  it("aber nicht, wenn ohnehin keiner lief", async () => {
    const fertig = vi.fn();
    mitStand();

    render(<PrueflaufTafel staffeln={[staffel()]} onFertig={fertig} />);
    await screen.findByRole("button", { name: "Prüflauf anfordern" });

    expect(fertig).not.toHaveBeenCalled();
  });
});
