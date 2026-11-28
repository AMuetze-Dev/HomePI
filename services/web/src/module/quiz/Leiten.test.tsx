import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Benutzer } from "../../api/anmeldung";
import * as client from "../../api/client";
import { ApiError } from "../../api/client";
import { TESTBENUTZER, mitAnmeldung } from "../../testhilfen";
import * as api from "./api";
import { QuizSeite } from "./QuizSeite";
import { frage, katalog, runde, steuerung } from "./testdaten";

const LEITUNG: Benutzer = { ...TESTBENUTZER, rechte: { quiz: "verwalter" } };
const TEAMS: api.TeamPlatz[] = [
  { id: "t1", name: "Rot", punkte: 5, rang: 1, mitglieder: 2 },
  { id: "t2", name: "Blau", punkte: 1, rang: 2, mitglieder: 1 },
];
const GESTARTET: api.RundeGestartet = {
  runde: runde(),
  moderatorcode: "ABCD-EFGH-JKLM-NPQR",
  hinweise: [],
};

/** Zeigt, wo der Router gerade steht - die Leitung lebt in der Adresse. */
function Adresse() {
  const ort = useLocation();
  return <output aria-label="Adresse">{ort.pathname + ort.search}</output>;
}

function zeige(adresse: string, benutzer: Benutzer | null = null) {
  return render(
    <MemoryRouter initialEntries={[adresse]}>
      {mitAnmeldung(
        <>
          <QuizSeite unterseite="leiten" />
          <Adresse />
        </>,
        benutzer,
      )}
    </MemoryRouter>,
  );
}

function dashboard(benutzer: Benutzer | null = null) {
  return zeige("/modul/quiz/leiten?runde=r1", benutzer);
}

async function dialog(knopf: string, titel: string): Promise<HTMLElement> {
  await userEvent.click(await screen.findByRole("button", { name: knopf }));
  return screen.findByRole("dialog", { name: titel });
}

beforeEach(() => {
  vi.spyOn(client, "fetchOeffentlicheUrl").mockResolvedValue("https://quiz.example");
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ======================================================= Start

describe("Leiten - Start", () => {
  it("zeigt ohne Konto nur die freigegebenen Kataloge und startet eine Runde", async () => {
    const frei = vi.spyOn(api, "ladeFreieKataloge").mockResolvedValue([
      { id: "k1", titel: "Kneipenquiz", beschreibung: "Für alle", anzahl_fragen: 2 },
      { id: "k2", titel: "Filmquiz", beschreibung: "", anzahl_fragen: 5 },
    ]);
    const alle = vi.spyOn(api, "ladeKataloge");
    const starten = vi.spyOn(api, "starteRunde").mockResolvedValue(GESTARTET);
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    zeige("/modul/quiz/leiten");

    expect(await screen.findByText("Kneipenquiz")).toBeInTheDocument();
    expect(frei).toHaveBeenCalled();
    expect(alle).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("radio", { name: /Filmquiz/ }));
    await userEvent.click(screen.getByRole("button", { name: "Runde starten" }));
    expect(starten).toHaveBeenCalledWith("k2");

    const code = await screen.findByRole("dialog", { name: "Dein Moderatorcode" });
    expect(within(code).getByText("ABCD-EFGH-JKLM-NPQR")).toBeInTheDocument();
    expect(
      within(code).getByRole("img", {
        name: "QR-Code für https://quiz.example/modul/quiz/leiten?zugang=ABCD-EFGH-JKLM-NPQR",
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Adresse")).toHaveTextContent("?runde=r1");

    await userEvent.click(
      within(code).getByRole("button", { name: "Verstanden - zur Runde" }),
    );
    expect(
      screen.queryByRole("dialog", { name: "Dein Moderatorcode" }),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Kneipenquiz" }),
    ).toBeInTheDocument();
  });

  it("nennt nach dem Start, was beim eigenen Quiz nicht übernommen wurde", async () => {
    vi.spyOn(api, "ladeFreieKataloge").mockResolvedValue([]);
    const eigenes = vi.spyOn(api, "starteEigenes").mockResolvedValue({
      ...GESTARTET,
      hinweise: ["Frage 1: Bild nicht geholt"],
    });
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    zeige("/modul/quiz/leiten");

    expect(await screen.findByText("Noch kein Quiz freigegeben")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Runde starten" }),
    ).not.toBeInTheDocument();

    const datei = new File(["PK"], "quiz.zip", { type: "application/zip" });
    await userEvent.upload(
      screen.getByLabelText("Eigenes Quiz hochladen und starten"),
      datei,
    );
    expect(eigenes).toHaveBeenCalledWith(datei);
    const code = await screen.findByRole("dialog", { name: "Dein Moderatorcode" });
    expect(within(code).getByText("Frage 1: Bild nicht geholt")).toBeInTheDocument();
  });

  it("meldet einen abgelehnten Start wörtlich", async () => {
    vi.spyOn(api, "ladeFreieKataloge").mockResolvedValue([]);
    vi.spyOn(api, "starteEigenes").mockRejectedValue(
      new ApiError("Gerade laufen zu viele Runden ohne Konto.", 429),
    );
    zeige("/modul/quiz/leiten");
    await userEvent.upload(
      await screen.findByLabelText("Eigenes Quiz hochladen und starten"),
      new File(["x"], "quiz.zip", { type: "application/zip" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Gerade laufen zu viele Runden ohne Konto.",
    );
  });

  it("zeigt mit Recht alle Kataloge mit Fragen und die laufenden Runden", async () => {
    vi.spyOn(api, "ladeKataloge").mockResolvedValue([
      katalog(),
      katalog({ id: "leer", titel: "Leerer Katalog", anzahl_fragen: 0 }),
    ]);
    vi.spyOn(api, "ladeRunden").mockResolvedValue([
      runde(),
      runde({ id: "r2", code: "ZZZ999", status: "beendet" }),
    ]);
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    zeige("/modul/quiz/leiten", LEITUNG);

    expect(await screen.findByRole("radio", { name: /Kneipenquiz/ })).toBeChecked();
    expect(screen.queryByText("Leerer Katalog")).not.toBeInTheDocument();
    expect(screen.queryByText("ZZZ999")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /ABC234/ }));
    expect(await screen.findByLabelText("Adresse")).toHaveTextContent("?runde=r1");
  });

  it("meldet, wenn die Kataloge nicht laden", async () => {
    vi.spyOn(api, "ladeFreieKataloge").mockRejectedValue(
      new ApiError("Gateway weg", 503),
    );
    zeige("/modul/quiz/leiten");
    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway weg");
  });

  it("übernimmt eine Runde mit dem Moderatorcode", async () => {
    vi.spyOn(api, "ladeFreieKataloge").mockResolvedValue([]);
    const uebernehmen = vi
      .spyOn(api, "uebernimmLeitung")
      .mockRejectedValueOnce(
        new ApiError("Dieser Moderatorcode passt zu keiner Runde.", 404),
      )
      .mockResolvedValue(runde());
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    zeige("/modul/quiz/leiten");

    const feld = await screen.findByLabelText(/Moderatorcode/);
    const knopf = screen.getByRole("button", { name: "Übernehmen" });
    expect(knopf).toBeDisabled();
    await userEvent.type(feld, "abcd-efgh-jklm-npqr");
    await userEvent.click(knopf);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Dieser Moderatorcode passt zu keiner Runde.",
    );
    expect(feld).toHaveValue("abcd-efgh-jklm-npqr");

    await userEvent.click(knopf);
    expect(uebernehmen).toHaveBeenLastCalledWith("abcd-efgh-jklm-npqr");
    expect(await screen.findByLabelText("Adresse")).toHaveTextContent("?runde=r1");
  });
});

// ======================================================= Zugang per QR

describe("Leiten - Zugang über den QR-Code", () => {
  it("übernimmt die Runde und ersetzt den Code in der Adresse", async () => {
    const uebernehmen = vi.spyOn(api, "uebernimmLeitung").mockResolvedValue(runde());
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    zeige("/modul/quiz/leiten?zugang=ABCD-EFGH-JKLM-NPQR");

    expect(
      screen.getByRole("status", { name: "Runde wird übernommen" }),
    ).toBeInTheDocument();
    expect(uebernehmen).toHaveBeenCalledWith("ABCD-EFGH-JKLM-NPQR");
    await waitFor(() =>
      expect(screen.getByLabelText("Adresse")).toHaveTextContent(
        "/modul/quiz/leiten?runde=r1",
      ),
    );
    expect(screen.getByLabelText("Adresse")).not.toHaveTextContent("zugang");
  });

  it("meldet einen ungültigen Code wörtlich", async () => {
    vi.spyOn(api, "uebernimmLeitung").mockRejectedValue(
      new ApiError("Dieser Moderatorcode passt zu keiner Runde.", 404),
    );
    zeige("/modul/quiz/leiten?zugang=FALSCH");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Dieser Moderatorcode passt zu keiner Runde.",
    );
  });
});

// ======================================================= Dashboard

describe("Dashboard", () => {
  it("zeigt beim Laden einen Platzhalter und dann die drei Spalten", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    dashboard();
    expect(
      screen.getByRole("status", { name: "Runde wird geladen" }),
    ).toBeInTheDocument();

    expect(await screen.findByRole("region", { name: "Fragen" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Aktuelle Frage" })).toHaveTextContent(
      "Hauptstadt von Frankreich?",
    );
    const spieler = screen.getByRole("region", { name: "Spieler" });
    expect(spieler).toHaveTextContent("1 verbunden");
    expect(screen.getByLabelText("Rundencode ABC234")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Anzeigetafel öffnen" })).toHaveAttribute(
      "href",
      "/modul/quiz/tafel?code=ABC234",
    );
  });

  it("meldet, wenn die Runde nicht lädt, und führt zurück", async () => {
    vi.spyOn(api, "ladeSteuerung").mockRejectedValue(
      new ApiError("Diese Runde leitest du nicht.", 401),
    );
    vi.spyOn(api, "ladeFreieKataloge").mockResolvedValue([]);
    dashboard();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Diese Runde leitest du nicht.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Zurück" }));
    expect(
      await screen.findByRole("heading", { name: /Neue Runde/ }),
    ).toBeInTheDocument();
  });

  it("beginnt aus der Lobby mit der ersten Frage", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(
      steuerung({ frage: null, phase: "keine", runde: runde({ status: "lobby" }) }),
    );
    const steuern = vi.spyOn(api, "steuere").mockResolvedValue(steuerung());
    dashboard();
    expect(await screen.findByText("Mitspielen mit dem Code")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mit Frage 1 beginnen" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "frage", frage_id: "f1" });
  });

  it("zeigt ohne Timer, sperrt, öffnet wieder und löst auf", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung({ phase: "bereit" }));
    const steuern = vi
      .spyOn(api, "steuere")
      .mockResolvedValue(steuerung({ phase: "offen" }));
    dashboard();

    await userEvent.click(
      await screen.findByRole("button", { name: "Ohne Timer zeigen (sonst 30 s)" }),
    );
    expect(
      screen.getByRole("button", { name: "Mit Timer 30 s zeigen" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Frage zeigen" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "zeigen", timer: false });

    steuern.mockResolvedValue(steuerung({ phase: "gesperrt" }));
    await userEvent.click(await screen.findByRole("button", { name: "Eingabe sperren" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "sperren" });

    steuern.mockResolvedValue(steuerung({ phase: "offen" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Eingabe wieder öffnen" }),
    );
    expect(steuern).toHaveBeenCalledWith("r1", { art: "oeffnen" });

    steuern.mockResolvedValue(steuerung({ phase: "gesperrt" }));
    await userEvent.click(await screen.findByRole("button", { name: "Eingabe sperren" }));
    await userEvent.click(await screen.findByRole("button", { name: "Auflösen" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "aufloesen" });
  });

  it("löst sofort auf - als Hauptaktion, sobald alle geantwortet haben", async () => {
    const laden = vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    const steuern = vi.spyOn(api, "steuere").mockResolvedValue(steuerung());
    const { unmount } = dashboard();

    expect(
      await screen.findByRole("button", { name: "Eingabe sperren" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sofort auflösen" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "aufloesen" });
    unmount();

    const alle = steuerung();
    laden.mockResolvedValue({ ...alle, spieler: alle.spieler.slice(0, 1) });
    dashboard();
    const aufloesen = await screen.findByRole("button", { name: "Auflösen" });
    expect(
      screen.queryByRole("button", { name: "Eingabe sperren" }),
    ).not.toBeInTheDocument();
    await userEvent.click(aufloesen);
    expect(steuern).toHaveBeenCalledTimes(2);
  });

  it("vergibt nach dem Auflösen Punkte von Hand und geht zur nächsten Frage", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(
      steuerung({ phase: "aufgeloest", beantwortet: ["f1"] }),
    );
    const steuern = vi
      .spyOn(api, "steuere")
      .mockResolvedValue(steuerung({ phase: "bereit" }));
    const bewerten = vi
      .spyOn(api, "bewerteAntwort")
      .mockResolvedValue(steuerung({ phase: "aufgeloest", beantwortet: ["f1"] }));
    dashboard();

    expect(await screen.findByText("1 / 2 Antworten")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Punkte für Anna"), "2");
    await userEvent.click(
      screen.getByRole("button", { name: "Punkte für Anna speichern" }),
    );
    expect(bewerten).toHaveBeenCalledWith("r1", "a1", 2);

    await userEvent.click(screen.getByRole("button", { name: "Nächste Frage" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "frage", frage_id: "f2" });
  });

  it("urteilt über den Buzzer und gibt ihn frei", async () => {
    const buzzerfrage = steuerung().fragen[1]!;
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(
      steuerung({
        frage: buzzerfrage,
        antworten: [],
        buzzer: [
          { spieler_id: "s2", spieler: "Ben", position: 1, urteil: "falsch" },
          { spieler_id: "s1", spieler: "Anna", position: 2, urteil: "wartet" },
        ],
      }),
    );
    const steuern = vi
      .spyOn(api, "steuere")
      .mockImplementation(() => api.ladeSteuerung("r1"));
    dashboard();

    expect(await screen.findByText(/ist dran/)).toHaveTextContent("Anna ist dran");
    await userEvent.click(screen.getByRole("button", { name: "Falsch - nächster" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "buzzer", richtig: false });
    await userEvent.click(screen.getByRole("button", { name: "Richtig" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "buzzer", richtig: true });
    await userEvent.click(screen.getByRole("button", { name: "Buzzer freigeben" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "buzzer/zuruecksetzen" });
  });

  it("wartet beim Buzzer auf den ersten Druck", async () => {
    const buzzerfrage = steuerung().fragen[1]!;
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(
      steuerung({ frage: buzzerfrage, antworten: [] }),
    );
    dashboard();
    expect(await screen.findByText("Warte auf den ersten Druck …")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Richtig" })).toBeDisabled();
  });

  it("wählt eine andere Frage aus der Leiste", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung({ beantwortet: ["f1"] }));
    const steuern = vi.spyOn(api, "steuere").mockResolvedValue(steuerung());
    dashboard();
    expect(await screen.findByRole("button", { name: /Frage 1 wählen/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /Frage 2 wählen/ }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "frage", frage_id: "f2" });
  });

  it("schaltet das Bild und spielt den Ton der aktuellen Frage", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(
      steuerung({
        frage: frage({ hat_bild: true, medien: ["ton"] }),
        bild_sichtbar: true,
      }),
    );
    const steuern = vi.spyOn(api, "steuere").mockResolvedValue(steuerung());
    dashboard();

    expect(await screen.findByLabelText("Ton zur Frage")).toHaveAttribute(
      "src",
      "/quiz/leitung/r1/medien/ton?stand=f1",
    );
    await userEvent.click(screen.getByRole("button", { name: "Bild verbergen" }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "bild", sichtbar: false });
  });

  it("schließt und öffnet den Beitritt mit einem Knopf", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    const steuern = vi
      .spyOn(api, "steuere")
      .mockResolvedValue(steuerung({ runde: runde({ beitritt_offen: false }) }));
    dashboard();

    await userEvent.click(
      await screen.findByRole("button", { name: "Beitritt schließen" }),
    );
    expect(steuern).toHaveBeenCalledWith("r1", { art: "beitritt", offen: false });
    expect(
      await screen.findByRole("button", { name: "Beitritt öffnen" }),
    ).toBeInTheDocument();
  });

  it("meldet eine abgelehnte Aktion wörtlich und behält die Steuerung", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    vi.spyOn(api, "steuere").mockRejectedValue(
      new ApiError("Die Frage ist nicht offen.", 409),
    );
    dashboard();
    await userEvent.click(await screen.findByRole("button", { name: "Eingabe sperren" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Die Frage ist nicht offen.",
    );
    expect(screen.getByRole("region", { name: "Aktuelle Frage" })).toBeInTheDocument();
  });
});

// ======================================================= Dialoge

describe("Dashboard - Dialoge", () => {
  it("zeigt den QR-Code nur auf Knopfdruck", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(
      steuerung({ runde: runde({ beitritt_offen: false }) }),
    );
    dashboard();
    await screen.findByRole("region", { name: "Spieler" });
    expect(screen.queryByRole("img", { name: /QR-Code/ })).not.toBeInTheDocument();

    const qr = await dialog("QR-Code zum Mitspielen", "Mitspielen");
    expect(
      within(qr).getByRole("img", {
        name: "QR-Code für https://quiz.example/modul/quiz/spielen?code=ABC234",
      }),
    ).toBeInTheDocument();
    expect(within(qr).getByText(/Der Beitritt ist geschlossen/)).toBeInTheDocument();

    await userEvent.click(within(qr).getByRole("button", { name: "Schließen" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("schließt einen Dialog mit Escape und mit einem Klick daneben", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    dashboard();
    const qr = await dialog("QR-Code zum Mitspielen", "Mitspielen");
    act(() => {
      qr.dispatchEvent(new Event("cancel", { cancelable: true }));
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    const wieder = await dialog("QR-Code zum Mitspielen", "Mitspielen");
    await userEvent.click(wieder);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("legt Teams an, ordnet Spieler zu und löst ein Team auf", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung({ teams: TEAMS }));
    const anlegen = vi
      .spyOn(api, "legeTeamAn")
      .mockResolvedValue(steuerung({ teams: TEAMS }));
    const zuordnen = vi
      .spyOn(api, "weiseTeamZu")
      .mockResolvedValue(steuerung({ teams: TEAMS }));
    const aufloesen = vi.spyOn(api, "loescheTeam").mockResolvedValue(steuerung());
    dashboard();

    expect(await screen.findByRole("list", { name: "Teams" })).toHaveTextContent("Rot");
    const teams = await dialog("Teams einteilen", "Teams");
    await userEvent.type(within(teams).getByLabelText("Neues Team"), "Grün");
    await userEvent.click(within(teams).getByRole("button", { name: "Team anlegen" }));
    expect(anlegen).toHaveBeenCalledWith("r1", "Grün");
    await waitFor(() =>
      expect(within(teams).getByLabelText("Neues Team")).toHaveValue(""),
    );

    await userEvent.selectOptions(within(teams).getByLabelText("Team von Ben"), "t1");
    expect(zuordnen).toHaveBeenCalledWith("r1", "s2", "t1");
    await userEvent.selectOptions(within(teams).getByLabelText("Team von Anna"), "");
    expect(zuordnen).toHaveBeenCalledWith("r1", "s1", null);

    await userEvent.click(
      within(teams).getByRole("button", { name: "Team Blau auflösen" }),
    );
    expect(aufloesen).toHaveBeenCalledWith("r1", "t2");
  });

  it("zeigt die Auswertung im Dialog und bietet die CSV an", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung({ beantwortet: ["f1"] }));
    const laden = vi.spyOn(api, "ladeAuswertung").mockResolvedValue([
      {
        frage_id: "f1",
        nummer: 1,
        text: "Hauptstadt?",
        typ: "freitext",
        loesung: "Paris",
        richtig: 1,
        gesamt: 2,
        antworten: [
          { spieler: "Anna", anzeige: "Paris", punkte: 2, richtig: true },
          { spieler: "Ben", anzeige: "Bonn", punkte: null, richtig: null },
        ],
      },
    ]);
    dashboard();

    const auswertung = await dialog("Auswertung", "Auswertung");
    expect(laden).toHaveBeenCalledWith("r1", expect.any(AbortSignal));
    expect(await within(auswertung).findByText("1 von 2 richtig")).toBeInTheDocument();
    expect(within(auswertung).getByText("Bonn")).toBeInTheDocument();
    expect(within(auswertung).getByText("? P.")).toBeInTheDocument();
    expect(
      within(auswertung).getByRole("link", { name: "Ergebnis als CSV herunterladen" }),
    ).toHaveAttribute("href", "/quiz/leitung/r1/ergebnis.csv");
  });

  it("meldet eine fehlgeschlagene und eine leere Auswertung", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    const laden = vi
      .spyOn(api, "ladeAuswertung")
      .mockRejectedValue(new ApiError("Gateway weg", 503));
    dashboard();

    const auswertung = await dialog("Auswertung", "Auswertung");
    expect(await within(auswertung).findByRole("alert")).toHaveTextContent("Gateway weg");
    await userEvent.click(within(auswertung).getByRole("button", { name: "Schließen" }));

    laden.mockResolvedValue([]);
    const leer = await dialog("Auswertung", "Auswertung");
    expect(
      await within(leer).findByText("Noch keine Frage aufgelöst."),
    ).toBeInTheDocument();
  });

  it("stellt einen neuen Moderatorcode aus und zeigt ihn mit QR-Code", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    const neu = vi.spyOn(api, "neuerModeratorcode").mockResolvedValue(GESTARTET);
    dashboard();

    const code = await dialog("Moderatorcode", "Moderatorcode");
    expect(within(code).queryByText("ABCD-EFGH-JKLM-NPQR")).not.toBeInTheDocument();
    await userEvent.click(
      within(code).getByRole("button", { name: "Neuen Moderatorcode ausstellen" }),
    );
    expect(neu).toHaveBeenCalledWith("r1");
    expect(await within(code).findByText("ABCD-EFGH-JKLM-NPQR")).toBeInTheDocument();
    expect(
      within(code).getByRole("img", {
        name: "QR-Code für https://quiz.example/modul/quiz/leiten?zugang=ABCD-EFGH-JKLM-NPQR",
      }),
    ).toBeInTheDocument();

    // Wer den Dialog schließt, sieht den Code nicht noch einmal.
    await userEvent.click(within(code).getByRole("button", { name: "Schließen" }));
    const wieder = await dialog("Moderatorcode", "Moderatorcode");
    expect(within(wieder).queryByText("ABCD-EFGH-JKLM-NPQR")).not.toBeInTheDocument();
  });

  it("beendet die Runde und löscht sie", async () => {
    const beendet = steuerung({ runde: runde({ status: "beendet" }) });
    const laden = vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    const steuern = vi.spyOn(api, "steuere").mockImplementation(() => {
      laden.mockResolvedValue(beendet);
      return Promise.resolve(beendet);
    });
    const loeschen = vi.spyOn(api, "loescheRunde").mockResolvedValue();
    vi.spyOn(api, "ladeFreieKataloge").mockResolvedValue([]);
    dashboard();

    const ende = await dialog("Runde beenden oder löschen", "Runde");
    await userEvent.click(within(ende).getByRole("button", { name: /Runde beenden/ }));
    expect(steuern).toHaveBeenCalledWith("r1", { art: "beenden" });
    expect(await screen.findByText("Beendet")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Beitritt schließen" }),
    ).not.toBeInTheDocument();

    const nochmal = await dialog("Runde beenden oder löschen", "Runde");
    expect(
      within(nochmal).queryByRole("button", { name: /Runde beenden/ }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      within(nochmal).getByRole("button", { name: "Runde mit allen Punkten löschen" }),
    );
    expect(loeschen).toHaveBeenCalledWith("r1");
    expect(
      await screen.findByRole("heading", { name: /Neue Runde/ }),
    ).toBeInTheDocument();
  });

  it("korrigiert Punkte, stellt einen Wiederkehrcode aus und entfernt einen Spieler", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung());
    const korrektur = vi.spyOn(api, "korrigiere").mockResolvedValue(steuerung());
    vi.spyOn(api, "stelleWiederkehrAus").mockResolvedValue({
      code: "WXYZ-2345",
      gueltig_bis: "x",
    });
    const entfernen = vi.spyOn(api, "entferneSpieler").mockResolvedValue();
    dashboard();

    const ben = await dialog("Ben, Platz 2, 1 Punkte - Aktionen", "Ben");
    expect(within(ben).getByText(/Platz 2/)).toBeInTheDocument();
    await userEvent.click(
      within(ben).getByRole("button", { name: "Ben einen Punkt geben" }),
    );
    expect(korrektur).toHaveBeenCalledWith("r1", "s2", 1);
    await userEvent.click(
      within(ben).getByRole("button", { name: "Ben einen Punkt abziehen" }),
    );
    expect(korrektur).toHaveBeenCalledWith("r1", "s2", -1);

    await userEvent.click(
      within(ben).getByRole("button", { name: /Wiederkehrcode für ein neues Gerät/ }),
    );
    expect(await within(ben).findByText("WXYZ-2345")).toBeInTheDocument();

    await userEvent.click(
      within(ben).getByRole("button", { name: /Ben aus der Runde entfernen/ }),
    );
    expect(entfernen).toHaveBeenCalledWith("r1", "s2");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("bittet ohne Spieler um den QR-Code", async () => {
    vi.spyOn(api, "ladeSteuerung").mockResolvedValue(steuerung({ spieler: [] }));
    dashboard();
    expect(await screen.findByText(/Noch niemand da/)).toBeInTheDocument();
  });
});
