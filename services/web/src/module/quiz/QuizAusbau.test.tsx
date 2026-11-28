import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Benutzer } from "../../api/anmeldung";
import * as client from "../../api/client";
import { ApiError } from "../../api/client";
import { TESTBENUTZER, mitAnmeldung } from "../../testhilfen";
import * as api from "./api";
import { Eingabe } from "./Eingabe";
import { alsEingabe, leererEntwurf, vollstaendig } from "./entwurf";
import { QuizSeite } from "./QuizSeite";
import { frage, katalog, oeffentlicheFrage, rundenstand } from "./testdaten";

const LEITUNG: Benutzer = { ...TESTBENUTZER, rechte: { quiz: "verwalter" } };
const TEAMS: api.TeamPlatz[] = [
  { id: "t1", name: "Rot", punkte: 5, rang: 1, mitglieder: 2 },
  { id: "t2", name: "Blau", punkte: 1, rang: 2, mitglieder: 1 },
];

function zeige(kind: ReactNode, adresse: string, benutzer: Benutzer | null = null) {
  return render(
    <MemoryRouter initialEntries={[adresse]}>
      {mitAnmeldung(kind, benutzer)}
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.spyOn(client, "fetchOeffentlicheUrl").mockResolvedValue(null);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ======================================================= neue Fragetypen

describe("Zuordnen", () => {
  const ZUORDNEN = oeffentlicheFrage({
    typ: "zuordnen",
    links: ["A", "B"],
    rechts: [
      { kennung: "r2", text: "2" },
      { kennung: "r1", text: "1" },
    ],
  });

  it("verlangt jede Zeile und vergibt jedes Gegenstück nur einmal", async () => {
    const aendern = vi.fn();
    const leer = leererEntwurf(ZUORDNEN);
    const { rerender } = render(
      <Eingabe
        frage={ZUORDNEN}
        entwurf={leer}
        aendern={aendern}
        bildAdresse={null}
        gesperrt={false}
      />,
    );
    expect(vollstaendig(ZUORDNEN, leer)).toBe(false);

    await userEvent.selectOptions(screen.getByLabelText("Gegenstück zu A"), "r1");
    expect(aendern).toHaveBeenLastCalledWith(
      expect.objectContaining({ zuordnung: { "0": "r1" } }),
    );

    const halb = { ...leer, zuordnung: { "0": "r1" } };
    rerender(
      <Eingabe
        frage={ZUORDNEN}
        entwurf={halb}
        aendern={aendern}
        bildAdresse={null}
        gesperrt={false}
      />,
    );
    const zweite = screen.getByLabelText("Gegenstück zu B");
    expect(within(zweite).getByRole("option", { name: "1" })).toBeDisabled();

    await userEvent.selectOptions(screen.getByLabelText("Gegenstück zu A"), "");
    expect(aendern).toHaveBeenLastCalledWith(expect.objectContaining({ zuordnung: {} }));

    const fertig = { ...leer, zuordnung: { "0": "r1", "1": "r2" } };
    expect(vollstaendig(ZUORDNEN, fertig)).toBe(true);
    expect(alsEingabe(ZUORDNEN, fertig)).toEqual({
      zuordnung: { "0": "r1", "1": "r2" },
      eingeloggt: true,
    });
  });
});

describe("Bildauswahl", () => {
  it("zeigt die Antworten als Bilder mit Alternativtext", async () => {
    const frage = oeffentlicheFrage({
      typ: "bildauswahl",
      bildoptionen: ["Karte A", ""],
    });
    const aendern = vi.fn();
    render(
      <Eingabe
        frage={frage}
        entwurf={leererEntwurf(frage)}
        aendern={aendern}
        bildAdresse={null}
        gesperrt={false}
        medienAdresse={(s) => `/medien/${s}`}
      />,
    );
    expect(screen.getByRole("img", { name: "Karte A" })).toHaveAttribute(
      "src",
      "/medien/option-0",
    );
    expect(screen.getByRole("img", { name: "Bild 2" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Bild 2" }));
    expect(aendern).toHaveBeenCalledWith(expect.objectContaining({ auswahl: [1] }));
    expect(alsEingabe(frage, { ...leererEntwurf(frage), auswahl: [1] })).toEqual({
      auswahl: [1],
      eingeloggt: true,
    });
  });
});

// ======================================================= Teams beim Spieler

describe("Teams beim Mitspielen", () => {
  it("verlangt beim Beitritt ein Team und schickt es mit", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({ ich: null, teams: TEAMS }),
    );
    const beitritt = vi.spyOn(api, "trittBei").mockResolvedValue(rundenstand());
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");

    await userEvent.type(await screen.findByLabelText("Dein Name"), "Anna");
    const knopf = screen.getByRole("button", { name: "Mitspielen" });
    expect(knopf).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: /Blau/ }));
    await userEvent.click(knopf);
    expect(beitritt).toHaveBeenCalledWith("ABC234", "Anna", undefined, "t2");
  });

  it("wechselt vor dem Start das Team", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({
        status: "lobby",
        phase: "keine",
        frage: null,
        teams: TEAMS,
        ich: { ...rundenstand().ich!, team: "Rot" },
      }),
    );
    const wechsel = vi.spyOn(api, "wechsleTeam").mockResolvedValue(rundenstand());
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");

    expect(await screen.findByText(/Anna \(Rot\)/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Rot/ })).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: /Blau/ }));
    expect(wechsel).toHaveBeenCalledWith("ABC234", "t2");
  });

  it("zeigt einen abgelehnten Teamwechsel wörtlich", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({ status: "lobby", phase: "keine", frage: null, teams: TEAMS }),
    );
    vi.spyOn(api, "wechsleTeam").mockRejectedValue(
      new ApiError("Das Team lässt sich nur vor dem Start wechseln.", 409),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");
    await userEvent.click(await screen.findByRole("radio", { name: /Blau/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("nur vor dem Start");
  });

  it("führt bei geschlossenem Beitritt direkt zum Wiederkehrcode", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({ ich: null, beitritt_offen: false }),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");
    expect(await screen.findByText(/Beitritt geschlossen/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Wiederkehrcode/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Neu beitreten" }),
    ).not.toBeInTheDocument();
  });
});

// ======================================================= Tafel

describe("Anzeigetafel, erweitert", () => {
  it("zeigt Bildauswahl, Ton, Zuordnen und Team-Rangliste", async () => {
    const abruf = vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({
        teams: TEAMS,
        frage: oeffentlicheFrage({
          typ: "bildauswahl",
          bildoptionen: ["Karte A", "Karte B"],
          hat_ton: true,
        }),
      }),
    );
    const { unmount } = zeige(
      <QuizSeite unterseite="tafel" />,
      "/modul/quiz/tafel?code=ABC234",
    );
    expect(await screen.findByRole("img", { name: "Karte B" })).toBeInTheDocument();
    expect(screen.getByLabelText("Ton zur Frage")).toBeInTheDocument();
    expect(
      within(screen.getByRole("list", { name: "Teams" })).getByText("Rot"),
    ).toBeInTheDocument();
    unmount();

    abruf.mockResolvedValue(
      rundenstand({
        frage: oeffentlicheFrage({
          typ: "zuordnen",
          links: ["A"],
          rechts: [{ kennung: "r1", text: "Eins" }],
        }),
      }),
    );
    zeige(<QuizSeite unterseite="tafel" />, "/modul/quiz/tafel?code=ABC234");
    expect(await screen.findByText("Eins")).toBeInTheDocument();
  });

  it("feiert am Ende mit Podest und bestem Team", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({
        status: "beendet",
        teams: TEAMS,
        rangliste: [
          { name: "Anna", punkte: 5, rang: 1, team: "Rot" },
          { name: "Ben", punkte: 5, rang: 1, team: "Rot" },
          { name: "Cleo", punkte: 1, rang: 3, team: "Blau" },
        ],
      }),
    );
    zeige(<QuizSeite unterseite="tafel" />, "/modul/quiz/tafel?code=ABC234");
    const podest = await screen.findByRole("list", { name: "Siegerpodest" });
    expect(podest).toHaveTextContent("Anna & Ben");
    expect(podest).toHaveTextContent("Cleo");
    expect(screen.getByText(/Bestes Team/)).toHaveTextContent("Rot");
    expect(screen.queryByRole("img", { name: /QR-Code/ })).not.toBeInTheDocument();
  });

  it("hat ohne Mitspieler nichts zu feiern", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({ status: "beendet", rangliste: [] }),
    );
    zeige(<QuizSeite unterseite="tafel" />, "/modul/quiz/tafel?code=ABC234");
    expect(await screen.findByText(/ohne Mitspieler/)).toBeInTheDocument();
  });
});

// ======================================================= Leitung

// ======================================================= Kataloge

describe("Kataloge, erweitert", () => {
  it("übernimmt ein Battle.Net-Quiz und nennt, was nicht ging", async () => {
    vi.spyOn(api, "ladeKataloge").mockResolvedValue([katalog()]);
    const importieren = vi.spyOn(api, "importiereKatalog").mockResolvedValue({
      katalog: { ...katalog({ id: "neu", titel: "Allgemeinwissen" }), fragen: [frage()] },
      hinweise: ["Frage 1: Bild von images.pexels.com nicht geholt"],
    });
    vi.spyOn(api, "ladeKatalog").mockResolvedValue({
      ...katalog({ id: "neu", titel: "Allgemeinwissen" }),
      fragen: [frage()],
    });
    zeige(<QuizSeite unterseite="kataloge" />, "/modul/quiz/kataloge", LEITUNG);

    const datei = new File(["PK"], "quiz.zip", { type: "application/zip" });
    await userEvent.upload(await screen.findByLabelText(/Quiz übernehmen/), datei);
    expect(importieren).toHaveBeenCalledWith(datei);
    expect(
      await screen.findByRole("heading", { name: "Allgemeinwissen" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/pexels/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Als ZIP sichern" })).toHaveAttribute(
      "href",
      "/quiz/kataloge/neu/export",
    );
  });

  it("meldet eine abgelehnte Datei wörtlich", async () => {
    vi.spyOn(api, "ladeKataloge").mockResolvedValue([]);
    vi.spyOn(api, "importiereKatalog").mockRejectedValue(
      new ApiError("Das ist weder ein ZIP noch eine JSON-Datei.", 422),
    );
    zeige(<QuizSeite unterseite="kataloge" />, "/modul/quiz/kataloge", LEITUNG);
    await userEvent.upload(
      await screen.findByLabelText(/Quiz übernehmen/),
      new File(["x"], "kaputt.zip", { type: "application/zip" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("weder ein ZIP");
  });

  it("pflegt Paare, Bildantworten und Medien", async () => {
    const bildfrage = frage({
      id: "f9",
      medien: ["option-0", "ton"],
      daten: {
        typ: "bildauswahl",
        optionen: [
          { text: "Karte A", richtig: true },
          { text: "", richtig: false },
        ],
      },
    });
    vi.spyOn(api, "ladeKatalog").mockResolvedValue({ ...katalog(), fragen: [bildfrage] });
    const hochladen = vi.spyOn(api, "ladeMediumHoch").mockResolvedValue(bildfrage);
    const entfernen = vi.spyOn(api, "entferneMedium").mockResolvedValue();
    const anlegen = vi.spyOn(api, "legeFrageAn").mockResolvedValue(frage());
    zeige(
      <QuizSeite unterseite="kataloge" />,
      "/modul/quiz/kataloge?katalog=k1",
      LEITUNG,
    );

    expect(await screen.findByText("Ton")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Frage 1 bearbeiten" }));
    expect(
      screen.getByRole("img", { name: /Bild zu Antwort 1 \(Karte A\)/ }),
    ).toBeInTheDocument();
    const datei = new File(["x"], "b.png", { type: "image/png" });
    await userEvent.upload(screen.getByLabelText("Bild zu Antwort 2"), datei);
    await waitFor(() => expect(hochladen).toHaveBeenCalledWith("f9", "option-1", datei));
    await userEvent.click(
      screen.getByRole("button", { name: /Ton zur Frage.*entfernen/ }),
    );
    expect(entfernen).toHaveBeenCalledWith("f9", "ton");

    await userEvent.click(screen.getByRole("button", { name: "Bild hinzufügen" }));
    await userEvent.type(screen.getByLabelText("Beschreibung Bild 3"), "Karte C");
    await userEvent.click(screen.getByRole("button", { name: "Bild 3 entfernen" }));
    expect(screen.queryByLabelText("Beschreibung Bild 3")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Abbrechen" }));

    await userEvent.click(screen.getByRole("button", { name: "Frage hinzufügen" }));
    await userEvent.selectOptions(screen.getByLabelText("Fragetyp"), "zuordnen");
    await userEvent.type(screen.getByLabelText("Frage"), "Ordne zu");
    await userEvent.type(screen.getByLabelText("Paar 1 links"), "A");
    await userEvent.type(screen.getByLabelText("Paar 1 rechts"), "1");
    await userEvent.type(screen.getByLabelText("Paar 2 links"), "B");
    await userEvent.type(screen.getByLabelText("Paar 2 rechts"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Paar hinzufügen" }));
    await userEvent.click(screen.getByRole("button", { name: "Paar 3 entfernen" }));
    await userEvent.click(screen.getByRole("button", { name: "Frage anlegen" }));
    expect(anlegen).toHaveBeenCalledWith(
      "k1",
      expect.objectContaining({
        daten: {
          typ: "zuordnen",
          paare: [
            { links: "A", rechts: "1" },
            { links: "B", rechts: "2" },
          ],
        },
      }),
    );
  });
});

describe("API, erweitert", () => {
  it("baut die neuen Adressen", () => {
    expect(api.rundenmediumAdresse("ABC234", "option-1", 2)).toBe(
      "/quiz/runden/ABC234/medien/option-1?frage=2",
    );
    expect(api.exportAdresse("k1")).toBe("/quiz/kataloge/k1/export");
    expect(api.ergebnisAdresse("r1")).toBe("/quiz/leitung/r1/ergebnis.csv");
    expect(api.mediumAdresse("f1", "ton", "3")).toBe(
      "/quiz/fragen/f1/medien/ton?stand=3",
    );
  });

  it("schickt die neuen Anfragen an die richtigen Pfade", async () => {
    const aufrufe: { url: string; init: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init: RequestInit) => {
        aufrufe.push({ url, init });
        return Promise.resolve(new Response("{}", { status: 200 }));
      }),
    );
    await api.wechsleTeam("ABC234", "t1");
    await api.trittBei("ABC234", "Anna", undefined, "t1");
    await api.importiereKatalog(new Blob(["x"], { type: "application/zip" }));
    await api.ladeMediumHoch("f1", "ton", new Blob(["x"], { type: "audio/mpeg" }));
    await api.entferneMedium("f1", "ton");
    await api.legeTeamAn("r1", "Rot");
    await api.loescheTeam("r1", "t1");
    await api.weiseTeamZu("r1", "s1", null);
    await api.ladeAuswertung("r1");
    await api.steuere("r1", { art: "beitritt", offen: false });
    vi.unstubAllGlobals();

    expect(aufrufe.map((a) => `${a.init.method ?? "GET"} ${a.url}`)).toEqual([
      "PUT /quiz/runden/ABC234/team",
      "POST /quiz/runden/ABC234/beitreten",
      "POST /quiz/kataloge/import",
      "PUT /quiz/fragen/f1/medien/ton",
      "DELETE /quiz/fragen/f1/medien/ton",
      "POST /quiz/leitung/r1/teams",
      "DELETE /quiz/leitung/r1/teams/t1",
      "PUT /quiz/leitung/r1/spieler/s1/team",
      "GET /quiz/leitung/r1/auswertung",
      "POST /quiz/leitung/r1/beitritt",
    ]);
    expect(JSON.parse(aufrufe[1]!.init.body as string)).toEqual({
      name: "Anna",
      team_id: "t1",
    });
  });

  it("startet, übernimmt und gibt frei - auf den Pfaden ohne Konto", async () => {
    const aufrufe: { url: string; init: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init: RequestInit) => {
        aufrufe.push({ url, init });
        return Promise.resolve(new Response("[]", { status: 200 }));
      }),
    );
    await api.ladeFreieKataloge();
    await api.starteRunde("k1");
    await api.starteEigenes(new Blob(["x"]));
    await api.uebernimmLeitung("ABCD-EFGH-JKLM-NPQR");
    await api.neuerModeratorcode("r1");
    await api.gibFrei("k1", true);
    vi.unstubAllGlobals();

    expect(aufrufe.map((a) => `${a.init.method ?? "GET"} ${a.url}`)).toEqual([
      "GET /quiz/kataloge/frei",
      "POST /quiz/starten",
      "POST /quiz/starten/eigenes",
      "POST /quiz/leitung/zugang",
      "POST /quiz/leitung/r1/moderatorcode",
      "PUT /quiz/kataloge/k1/freigabe",
    ]);
    expect(JSON.parse(aufrufe[1]!.init.body as string)).toEqual({ katalog_id: "k1" });
    expect(new Headers(aufrufe[2]!.init.headers).get("Content-Type")).toBe(
      "application/zip",
    );
    expect(JSON.parse(aufrufe[3]!.init.body as string)).toEqual({
      code: "ABCD-EFGH-JKLM-NPQR",
    });
    expect(JSON.parse(aufrufe[5]!.init.body as string)).toEqual({ frei: true });
    expect(api.leitungsmediumAdresse("r1", "bild", "f 1")).toBe(
      "/quiz/leitung/r1/medien/bild?stand=f%201",
    );
  });
});
