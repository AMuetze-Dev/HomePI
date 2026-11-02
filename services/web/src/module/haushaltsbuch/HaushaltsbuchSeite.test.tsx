import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { verschiebe } from "./daten";
import { HaushaltsbuchSeite } from "./HaushaltsbuchSeite";

const AARON = "11111111-1111-1111-1111-111111111111";
const JESSI = "22222222-2222-2222-2222-222222222222";
const GEMEINSAM = "33333333-3333-3333-3333-333333333333";
const WOHNEN = "44444444-4444-4444-4444-444444444444";
const MIETE = "55555555-5555-5555-5555-555555555555";

function personen(): api.Person[] {
  return [
    { id: AARON, name: "Aaron", reihenfolge: 0 },
    { id: JESSI, name: "Jessi", reihenfolge: 1 },
  ];
}

function konten(): api.Konto[] {
  return [
    {
      id: GEMEINSAM,
      name: "DKB1",
      art: "verteiler",
      inhaber_id: null,
      notiz: "",
      reihenfolge: 0,
    },
  ];
}

function kategorien(): api.Kategorie[] {
  return [{ id: WOHNEN, name: "Wohnen", zaehlt_als_sparen: false, reihenfolge: 0 }];
}

function posten(rest: Partial<api.Posten> = {}): api.Posten {
  return {
    id: MIETE,
    name: "Miete",
    art: "ausgabe",
    betrag: "900.00",
    intervall_monate: 1,
    faelligkeitsmonat: 1,
    abbuchungstag: 1,
    konto_id: GEMEINSAM,
    kategorie_id: WOHNEN,
    variabel: false,
    aktiv: true,
    anteile: [
      { person_id: JESSI, gewicht: 1 },
      { person_id: AARON, gewicht: 2 },
    ],
    ...rest,
  };
}

function zeile(): api.PostenZeile {
  return {
    id: MIETE,
    name: "Miete",
    art: "ausgabe",
    konto: "DKB1",
    kategorie: "Wohnen",
    betrag: "900.00",
    monatsrate: "900.00",
    intervall_monate: 1,
    faelligkeitsmonat: 1,
    abbuchungstag: 1,
    faellige_monate: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    faellig_im_monat: true,
    ruecklagenstand: "0.00",
    anteile: { [JESSI]: "300.00", [AARON]: "600.00" },
  };
}

function bilanz(name: string, einzahlung: string): api.PersonBilanz {
  return {
    person_id: name === "Aaron" ? AARON : JESSI,
    name,
    einnahmen: "3000.00",
    eigene_ausgaben: "0.00",
    einzahlung_gemeinschaft: einzahlung,
    gutschrift_gemeinschaft: "0.00",
    ausgaben_gesamt: einzahlung,
    feste_kosten: einzahlung,
    sparen: "0.00",
    variabel: "0.00",
    moeglich: "2400.00",
    rest: "2400.00",
    sparquote: "0.0",
    moegliche_sparquote: "80.0",
    nach_kategorie: [
      { kategorie: "Wohnen", betrag: einzahlung, zaehlt_als_sparen: false },
    ],
  };
}

function uebersicht(rest: Partial<api.Uebersicht> = {}): api.Uebersicht {
  return {
    jahr: 2026,
    monat: 6,
    personen: [bilanz("Aaron", "600.00"), bilanz("Jessi", "300.00")],
    gemeinschaft: {
      einnahmen: "0.00",
      ausgaben: "900.00",
      bedarf: "900.00",
      ohne_aufteilung: [],
    },
    faellig: [zeile()],
    ruecklagen: [],
    ruecklagen_summe: "0.00",
    alle: [zeile()],
    ...rest,
  };
}

function flussbild(): api.Flussbild {
  return {
    ebenen: 2,
    knoten: [
      { id: "konto:a", beschriftung: "DKB1", art: "konto", ebene: 0, betrag: "900.00" },
      {
        id: "kategorie:w",
        beschriftung: "Wohnen",
        art: "kategorie",
        ebene: 1,
        betrag: "900.00",
      },
    ],
    fluesse: [{ von: "konto:a", nach: "kategorie:w", betrag: "900.00" }],
  };
}

/** Alle sechs Abrufe der Hülle auf einmal - sonst hängt jeder Test im Laden. */
function alles(rest: Partial<Parameters<typeof mocke>[0]> = {}) {
  return mocke({
    uebersicht: uebersicht(),
    flussbild: flussbild(),
    personen: personen(),
    konten: konten(),
    kategorien: kategorien(),
    posten: [posten()],
    ...rest,
  });
}

function mocke(daten: {
  uebersicht: api.Uebersicht;
  flussbild: api.Flussbild;
  personen: api.Person[];
  konten: api.Konto[];
  kategorien: api.Kategorie[];
  posten: api.Posten[];
}) {
  vi.spyOn(api, "ladeUebersicht").mockResolvedValue(daten.uebersicht);
  vi.spyOn(api, "ladeFlussbild").mockResolvedValue(daten.flussbild);
  vi.spyOn(api, "ladePersonen").mockResolvedValue(daten.personen);
  vi.spyOn(api, "ladeKonten").mockResolvedValue(daten.konten);
  vi.spyOn(api, "ladeKategorien").mockResolvedValue(daten.kategorien);
  vi.spyOn(api, "ladePosten").mockResolvedValue(daten.posten);
  return daten;
}

beforeEach(() => {
  vi.spyOn(api, "legePostenAn").mockResolvedValue(posten());
  vi.spyOn(api, "aenderePosten").mockResolvedValue(posten({ aktiv: false }));
  vi.spyOn(api, "entfernePosten").mockResolvedValue(undefined);
  vi.spyOn(api, "legePersonAn").mockResolvedValue(personen()[0]!);
  vi.spyOn(api, "entfernePerson").mockResolvedValue(undefined);
  vi.spyOn(api, "legeKontoAn").mockResolvedValue(konten()[0]!);
  vi.spyOn(api, "legeKategorieAn").mockResolvedValue(kategorien()[0]!);
  vi.spyOn(api, "legeGrundgeruestAn").mockResolvedValue(kategorien());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Monatsrechnung der Hülle", () => {
  it("zählt über den Jahreswechsel richtig weiter", () => {
    // Mit einem Date statt der Monatszahl landet der 31. Januar plus einen
    // Monat im März.
    expect(verschiebe({ jahr: 2026, monat: 12 }, 1)).toEqual({ jahr: 2027, monat: 1 });
    expect(verschiebe({ jahr: 2026, monat: 1 }, -1)).toEqual({ jahr: 2025, monat: 12 });
  });
});

describe("Haushaltsbuch", () => {
  it("zeigt zuerst einen Ladehinweis", () => {
    alles();
    vi.spyOn(api, "ladeUebersicht").mockReturnValue(new Promise(() => {}));

    render(<HaushaltsbuchSeite />);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("meldet, wenn gar nichts geladen werden kann", async () => {
    alles();
    vi.spyOn(api, "ladeUebersicht").mockRejectedValue(new ApiError("Gateway weg", 503));

    render(<HaushaltsbuchSeite />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway weg");
  });

  it("sagt im Erstzustand, was zu tun ist", async () => {
    alles({
      posten: [],
      uebersicht: uebersicht({ personen: [], faellig: [], alle: [] }),
    });

    render(<HaushaltsbuchSeite />);

    expect(await screen.findByText(/Noch kein Posten erfasst/)).toBeInTheDocument();
  });
});

describe("Monatsplan", () => {
  it("zeigt, wer wie viel in die Gemeinschaft einzahlt", async () => {
    alles();

    render(<HaushaltsbuchSeite unterseite="uebersicht" />);

    const gemeinsam = await screen.findByLabelText("Einzahlungen in die Gemeinschaft");
    expect(within(gemeinsam).getByText(/600,00/)).toBeInTheDocument();
    expect(within(gemeinsam).getByText(/300,00/)).toBeInTheDocument();
  });

  it("warnt vor gemeinsamen Posten, die niemand trägt", async () => {
    // Die zahlt sonst niemand, und auffallen würde es erst beim Kontoauszug.
    alles({
      uebersicht: uebersicht({
        gemeinschaft: {
          einnahmen: "0.00",
          ausgaben: "900.00",
          bedarf: "900.00",
          ohne_aufteilung: ["Strom"],
        },
      }),
    });

    render(<HaushaltsbuchSeite unterseite="uebersicht" />);

    expect(await screen.findByText(/Strom/)).toBeInTheDocument();
  });

  it("holt beim Monatswechsel den neuen Monat", async () => {
    alles();
    render(<HaushaltsbuchSeite unterseite="uebersicht" />);
    await screen.findByRole("button", { name: "Heute" });

    const vorher = vi.mocked(api.ladeUebersicht).mock.calls.at(-1)?.[0];
    await userEvent.click(screen.getByRole("button", { name: "Einen Monat vor" }));

    const nachher = vi.mocked(api.ladeUebersicht).mock.calls.at(-1)?.[0];
    expect(nachher).not.toEqual(vorher);
  });

  it("kommt über 'Heute' und einen Schritt zurück wieder in diesen Monat", async () => {
    alles();
    render(<HaushaltsbuchSeite unterseite="uebersicht" />);
    await screen.findByRole("button", { name: "Heute" });

    await userEvent.click(screen.getByRole("button", { name: "Einen Monat zurück" }));
    await userEvent.click(screen.getByRole("button", { name: "Heute" }));

    const heute = new Date();
    expect(vi.mocked(api.ladeUebersicht).mock.calls.at(-1)?.[0]).toEqual({
      jahr: heute.getFullYear(),
      monat: heute.getMonth() + 1,
    });
  });

  it("macht eine Unterdeckung als solche kenntlich", async () => {
    // Ein Minus ist leicht zu übersehen - ein Etikett nicht.
    const knapp = { ...bilanz("Aaron", "600.00"), rest: "-120.00" };
    alles({ uebersicht: uebersicht({ personen: [knapp] }) });

    render(<HaushaltsbuchSeite unterseite="uebersicht" />);

    expect(await screen.findByText("Unterdeckung")).toBeInTheDocument();
  });

  it("zeichnet keinen Balken für eine Person ohne Einkommen", async () => {
    const ohne = { ...bilanz("Jessi", "0.00"), einnahmen: "0.00", feste_kosten: "0.00" };
    alles({ uebersicht: uebersicht({ personen: [ohne] }) });

    render(<HaushaltsbuchSeite unterseite="uebersicht" />);

    await screen.findByText("Jessi");
    expect(screen.queryByRole("img", { name: /Jessi:/ })).not.toBeInTheDocument();
  });

  it("nennt den Rücklagenstand, nicht nur den Jahresbetrag", async () => {
    const kfz: api.PostenZeile = {
      ...zeile(),
      id: "kfz",
      name: "Kfz-Versicherung",
      betrag: "600.00",
      monatsrate: "50.00",
      intervall_monate: 12,
      faellige_monate: [1],
      faellig_im_monat: false,
      ruecklagenstand: "250.00",
    };
    alles({ uebersicht: uebersicht({ ruecklagen: [kfz], ruecklagen_summe: "250.00" }) });

    render(<HaushaltsbuchSeite unterseite="uebersicht" />);

    const tabelle = await screen.findByRole("table", { name: "Rücklagen" });
    // Einmal in der Zeile, einmal in der Summe darunter.
    expect(within(tabelle).getAllByText(/250,00/)).toHaveLength(2);
    expect(within(tabelle).getByText("jährlich (Jan)")).toBeInTheDocument();
    expect(within(tabelle).getByText(/^50,00/)).toBeInTheDocument();
  });
});

describe("Posten", () => {
  it("zeigt die Aufteilung als Verhältnis", async () => {
    alles();

    render(<HaushaltsbuchSeite unterseite="posten" />);

    expect(await screen.findByText("Jessi 1 : Aaron 2")).toBeInTheDocument();
  });

  it("pausiert einen Posten, statt ihn zu löschen", async () => {
    alles();
    render(<HaushaltsbuchSeite unterseite="posten" />);

    await userEvent.click(await screen.findByRole("button", { name: /Miete pausieren/ }));

    expect(api.aenderePosten).toHaveBeenCalledWith(MIETE, { aktiv: false });
  });

  it("nimmt ein Komma als Dezimaltrennzeichen an", async () => {
    // Auf einer deutschen Tastatur tippt man 549,09 - das Backend will einen
    // Punkt, und niemand soll das wissen müssen.
    alles({ posten: [] });
    render(<HaushaltsbuchSeite unterseite="posten" />);

    await userEvent.type(await screen.findByLabelText("Name"), "Kfz");
    await userEvent.type(screen.getByLabelText(/Betrag je Abbuchung/), "549,09");
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    expect(api.legePostenAn).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Kfz", betrag: "549.09" }),
    );
  });

  it("fragt den Fälligkeitsmonat erst, wenn er gebraucht wird", async () => {
    alles({ posten: [] });
    render(<HaushaltsbuchSeite unterseite="posten" />);

    await screen.findByLabelText("Rhythmus");
    expect(screen.queryByLabelText(/Erstmals fällig/)).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Rhythmus"), "12");

    expect(await screen.findByLabelText(/Erstmals fällig/)).toBeInTheDocument();
  });

  it("behält die Eingabe, wenn das Anlegen fehlschlägt", async () => {
    alles({ posten: [] });
    vi.spyOn(api, "legePostenAn").mockRejectedValue(
      new ApiError("Ein Posten namens 'Kfz' gibt es bereits", 409),
    );
    render(<HaushaltsbuchSeite unterseite="posten" />);

    await userEvent.type(await screen.findByLabelText("Name"), "Kfz");
    await userEvent.type(screen.getByLabelText(/Betrag je Abbuchung/), "10");
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/gibt es bereits/);
    expect(screen.getByLabelText("Name")).toHaveValue("Kfz");
  });

  it("warnt, solange ein gemeinsamer Posten niemandem gehört", async () => {
    alles({ posten: [] });

    render(<HaushaltsbuchSeite unterseite="posten" />);

    expect(
      await screen.findByText(/Ohne Aufteilung zahlt diesen Posten niemand/),
    ).toBeInTheDocument();
  });

  it("entfernt einen Posten", async () => {
    alles();
    render(<HaushaltsbuchSeite unterseite="posten" />);

    await userEvent.click(await screen.findByRole("button", { name: "Miete entfernen" }));

    expect(api.entfernePosten).toHaveBeenCalledWith(MIETE);
  });

  it("nimmt Art, Kategorie und Gewichte aus dem Formular", async () => {
    alles({ posten: [] });
    render(<HaushaltsbuchSeite unterseite="posten" />);

    await userEvent.type(await screen.findByLabelText("Name"), "Kindergeld");
    await userEvent.type(screen.getByLabelText(/Betrag je Abbuchung/), "250");
    await userEvent.selectOptions(screen.getByLabelText("Art"), "einnahme");
    await userEvent.selectOptions(screen.getByLabelText("Kategorie"), WOHNEN);
    await userEvent.type(screen.getByLabelText("Aaron"), "1");
    await userEvent.type(screen.getByLabelText("Jessi"), "1");
    await userEvent.click(screen.getByLabelText(/Frei verfügbar/));
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    expect(api.legePostenAn).toHaveBeenCalledWith({
      name: "Kindergeld",
      art: "einnahme",
      betrag: "250",
      intervall_monate: 1,
      faelligkeitsmonat: 1,
      abbuchungstag: null,
      konto_id: GEMEINSAM,
      kategorie_id: WOHNEN,
      variabel: true,
      anteile: [
        { person_id: AARON, gewicht: 1 },
        { person_id: JESSI, gewicht: 1 },
      ],
    });
  });

  it("verlangt erst ein Konto", async () => {
    alles({ konten: [], posten: [] });

    render(<HaushaltsbuchSeite unterseite="posten" />);

    expect(await screen.findByText(/Erst ein Konto/)).toBeInTheDocument();
  });
});

describe("Stammdaten", () => {
  it("legt eine Person an und leert danach das Feld", async () => {
    alles();
    render(<HaushaltsbuchSeite unterseite="stammdaten" />);

    const abschnitt = within(await screen.findByRole("region", { name: "Personen" }));
    await userEvent.type(abschnitt.getByLabelText("Name"), "Neu");
    await userEvent.click(abschnitt.getByRole("button", { name: "Person anlegen" }));

    expect(api.legePersonAn).toHaveBeenCalledWith({ name: "Neu" });
    expect(abschnitt.getByLabelText("Name")).toHaveValue("");
  });

  it("bietet im leeren Zustand die üblichen Kategorien an", async () => {
    alles({ kategorien: [] });
    render(<HaushaltsbuchSeite unterseite="stammdaten" />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Die üblichen anlegen" }),
    );

    expect(api.legeGrundgeruestAn).toHaveBeenCalled();
  });

  it("zeigt die Meldung des Backends wörtlich", async () => {
    alles();
    vi.spyOn(api, "entfernePerson").mockRejectedValue(
      new ApiError("Diese Person hat noch Konten oder Anteile.", 409),
    );
    render(<HaushaltsbuchSeite unterseite="stammdaten" />);

    await userEvent.click(await screen.findByRole("button", { name: "Aaron entfernen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /noch Konten oder Anteile/,
    );
  });

  it("legt ein Konto mit Inhaber an", async () => {
    alles();
    render(<HaushaltsbuchSeite unterseite="stammdaten" />);

    const abschnitt = within(await screen.findByRole("region", { name: "Konten" }));
    await userEvent.type(abschnitt.getByLabelText("Name"), "CON1");
    await userEvent.selectOptions(abschnitt.getByLabelText("Art"), "verbrauch");
    await userEvent.selectOptions(abschnitt.getByLabelText("Inhaber"), AARON);
    await userEvent.click(abschnitt.getByRole("button", { name: "Konto anlegen" }));

    expect(api.legeKontoAn).toHaveBeenCalledWith({
      name: "CON1",
      art: "verbrauch",
      inhaber_id: AARON,
    });
  });

  it("legt eine Kategorie an, die als Sparen zählt", async () => {
    alles();
    render(<HaushaltsbuchSeite unterseite="stammdaten" />);

    const abschnitt = within(await screen.findByRole("region", { name: "Kategorien" }));
    await userEvent.type(abschnitt.getByLabelText("Name"), "Investments");
    await userEvent.click(abschnitt.getByLabelText(/Zählt als Sparen/));
    await userEvent.click(abschnitt.getByRole("button", { name: "Kategorie anlegen" }));

    expect(api.legeKategorieAn).toHaveBeenCalledWith({
      name: "Investments",
      zaehlt_als_sparen: true,
    });
  });

  it("entfernt Konto und Kategorie über ihre eigenen Knöpfe", async () => {
    alles();
    vi.spyOn(api, "entferneKonto").mockResolvedValue(undefined);
    vi.spyOn(api, "entferneKategorie").mockResolvedValue(undefined);
    render(<HaushaltsbuchSeite unterseite="stammdaten" />);

    await userEvent.click(await screen.findByRole("button", { name: "DKB1 entfernen" }));
    await userEvent.click(screen.getByRole("button", { name: "Wohnen entfernen" }));

    expect(api.entferneKonto).toHaveBeenCalledWith(GEMEINSAM);
    expect(api.entferneKategorie).toHaveBeenCalledWith(WOHNEN);
  });

  it("sagt, dass ein Konto ohne Inhaber ein gemeinsames ist", async () => {
    alles({ konten: [] });

    render(<HaushaltsbuchSeite unterseite="stammdaten" />);

    expect(await screen.findByText(/Ein Konto ohne Inhaber/)).toBeInTheDocument();
  });
});

describe("Geldfluss", () => {
  it("zeichnet die Bänder und sagt dasselbe als Tabelle", async () => {
    alles();

    render(<HaushaltsbuchSeite unterseite="fluss" />);

    expect(
      await screen.findByRole("img", { name: /Geldfluss eines Monats/ }),
    ).toBeInTheDocument();
    const tabelle = screen.getByRole("table", { name: "Geldfluss in Zahlen" });
    expect(within(tabelle).getByText(/Konto DKB1/)).toBeInTheDocument();
  });

  it("erklärt im leeren Zustand, was fehlt", async () => {
    alles({ flussbild: { knoten: [], fluesse: [], ebenen: 0 } });

    render(<HaushaltsbuchSeite unterseite="fluss" />);

    expect(await screen.findByText(/Noch nichts zu zeigen/)).toBeInTheDocument();
  });
});
