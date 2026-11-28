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
import { QuizSeite } from "./QuizSeite";
import { frage, katalog, oeffentlicheFrage, rundenstand } from "./testdaten";

const LEITUNG: Benutzer = { ...TESTBENUTZER, rechte: { quiz: "verwalter" } };

function zeige(kind: ReactNode, adresse: string, benutzer: Benutzer | null = null) {
  return render(
    <MemoryRouter initialEntries={[adresse]}>
      {mitAnmeldung(kind, benutzer)}
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.spyOn(client, "fetchOeffentlicheUrl").mockResolvedValue("https://quiz.example");
});

beforeEach(() => {
  // jsdom rechnet kein Layout; ohne Fläche ergäbe ein Tipp aufs Bild keine Stelle.
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    left: 0,
    top: 0,
    width: 200,
    height: 100,
  } as DOMRect);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ===================================================================== Mitspielen

describe("Mitspielen ohne Konto", () => {
  it("erklärt im Erstzustand, woher der Code kommt", async () => {
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen");

    expect(screen.getByRole("heading", { name: "Mitspielen" })).toBeInTheDocument();
    expect(screen.getByText(/Code aus sechs Zeichen/)).toBeInTheDocument();
    const weiter = screen.getByRole("button", { name: "Weiter" });
    expect(weiter).toBeDisabled();

    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(rundenstand({ ich: null }));
    await userEvent.type(screen.getByLabelText("Rundencode"), "abc-234");
    await userEvent.click(weiter);
    expect(await screen.findByLabelText("Dein Name")).toBeInTheDocument();
    expect(api.ladeRundenstand).toHaveBeenCalledWith("ABC234", expect.anything());
  });

  it("zeigt beim Laden einen Platzhalter", () => {
    vi.spyOn(api, "ladeRundenstand").mockReturnValue(new Promise(() => {}));
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");
    expect(
      screen.getByRole("status", { name: "Runde wird geladen" }),
    ).toBeInTheDocument();
  });

  it("meldet einen unbekannten Code wörtlich", async () => {
    vi.spyOn(api, "ladeRundenstand").mockRejectedValue(
      new ApiError("Zu diesem Code gibt es keine Runde.", 404),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ZZZZZZ");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Zu diesem Code gibt es keine Runde.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Anderen Code eingeben" }));
    expect(screen.getByLabelText("Rundencode")).toBeInTheDocument();
  });

  it("behält den Namen, wenn er schon vergeben ist", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(rundenstand({ ich: null }));
    vi.spyOn(api, "trittBei").mockRejectedValue(
      new ApiError(
        "„Anna“ spielt in dieser Runde schon mit. Wähle einen anderen Namen.",
        409,
      ),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");

    await userEvent.type(await screen.findByLabelText("Dein Name"), "Anna");
    await userEvent.click(screen.getByRole("button", { name: "Mitspielen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("schon mit");
    expect(screen.getByLabelText("Dein Name")).toHaveValue("Anna");
  });

  it("kommt mit dem Wiederkehrcode zurück an den eigenen Namen", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(rundenstand({ ich: null }));
    const beitritt = vi.spyOn(api, "trittBei").mockResolvedValue(rundenstand());
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");

    await userEvent.click(
      await screen.findByRole("button", { name: "Ich war schon dabei" }),
    );
    await userEvent.type(screen.getByLabelText("Dein Name"), "Anna");
    await userEvent.type(screen.getByLabelText(/Wiederkehrcode/), "ABCD-EFGH");
    await userEvent.click(screen.getByRole("button", { name: "Zurück ins Spiel" }));

    expect(beitritt).toHaveBeenCalledWith("ABC234", "Anna", "ABCD-EFGH", undefined);
    expect(await screen.findByLabelText("Deine Antwort")).toBeInTheDocument();
  });

  it("gibt eine Antwort ab und zeigt sie als abgegeben", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(rundenstand());
    const antwort = vi.spyOn(api, "antworte").mockResolvedValue(
      rundenstand({
        ich: {
          ...rundenstand().ich!,
          antwort: {
            wert: { text: "Paris" },
            eingeloggt: true,
            punkte: null,
            richtig: null,
          },
        },
      }),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");

    expect(
      await screen.findByRole("heading", { name: "Hauptstadt von Frankreich?" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Anna · 4 Punkte · Platz 1/)).toBeInTheDocument();
    await userEvent.type(await screen.findByLabelText("Deine Antwort"), "Paris");
    await userEvent.click(screen.getByRole("button", { name: "Antwort abgeben" }));

    expect(antwort).toHaveBeenCalledWith("ABC234", { text: "Paris", eingeloggt: true });
    expect(await screen.findByText("Abgegeben")).toBeInTheDocument();
  });

  it("zeigt eine abgelehnte Antwort wörtlich", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(rundenstand());
    vi.spyOn(api, "antworte").mockRejectedValue(
      new ApiError("Die Zeit ist abgelaufen.", 409),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");

    await userEvent.type(await screen.findByLabelText("Deine Antwort"), "Paris");
    await userEvent.click(screen.getByRole("button", { name: "Antwort abgeben" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Die Zeit ist abgelaufen.",
    );
    expect(screen.getByLabelText("Deine Antwort")).toHaveValue("Paris");
  });

  it("wartet vor dem Zeigen und zeigt den Countdown, sobald die Frage offen ist", async () => {
    const abruf = vi
      .spyOn(api, "ladeRundenstand")
      .mockResolvedValue(
        rundenstand({ phase: "bereit", frage: oeffentlicheFrage({ text: null }) }),
      );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");
    expect(await screen.findByText("Frage 1 kommt gleich")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Rangliste" })).toBeInTheDocument();
    abruf.mockRestore();
  });

  it("zeigt den Countdown einer offenen Frage", async () => {
    const frist = new Date(Date.now() + 20_000).toISOString();
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({ frist, jetzt: new Date().toISOString() }),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");
    expect(await screen.findByRole("timer")).toHaveTextContent(/\d+ s/);
  });

  it("buzzert und zeigt den Platz in der Reihe", async () => {
    const buzzerfrage = oeffentlicheFrage({ typ: "buzzer" });
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({ frage: buzzerfrage }),
    );
    const druck = vi.spyOn(api, "buzzere").mockResolvedValue(
      rundenstand({
        frage: buzzerfrage,
        buzzer: "Ben",
        ich: { ...rundenstand().ich!, buzzer_position: 2, buzzer_urteil: "wartet" },
      }),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");

    await userEvent.click(await screen.findByRole("button", { name: "Buzzer" }));
    expect(druck).toHaveBeenCalledWith("ABC234");
    expect(
      await screen.findByText("Du bist auf Platz 2 in der Reihe."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Buzzer" })).toBeDisabled();
  });

  it("zeigt nach dem Auflösen Lösung und eigenes Ergebnis", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({
        phase: "aufgeloest",
        frage: oeffentlicheFrage({
          loesung: {
            anzeige: "Paris",
            texte: ["Paris"],
            zahl: null,
            toleranz: null,
            optionen: [],
            ziele: [],
            reihenfolge: [],
            zuordnung: {},
          },
        }),
        ich: {
          ...rundenstand().ich!,
          antwort: {
            wert: { text: "paris" },
            eingeloggt: true,
            punkte: 2,
            richtig: true,
          },
        },
      }),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");
    expect(await screen.findByText("Richtig! +2")).toBeInTheDocument();
    expect(screen.getByText("Paris")).toBeInTheDocument();
  });

  it("zeigt am Ende den Endstand", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({ status: "beendet" }),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");
    expect(await screen.findByText(/danke fürs Mitspielen/)).toBeInTheDocument();
  });

  it("lässt in eine beendete Runde niemanden mehr hinein", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({ status: "beendet", ich: null }),
    );
    zeige(<QuizSeite unterseite="spielen" />, "/modul/quiz/spielen?code=ABC234");
    expect(await screen.findByText("Diese Runde ist vorbei")).toBeInTheDocument();
    expect(screen.queryByLabelText("Dein Name")).not.toBeInTheDocument();
  });
});

// ===================================================================== Tafel

describe("Anzeigetafel", () => {
  it("fragt ohne Code nach einem", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(rundenstand());
    zeige(<QuizSeite unterseite="tafel" />, "/modul/quiz/tafel");
    await userEvent.type(screen.getByLabelText("Rundencode"), "abc234");
    await userEvent.click(screen.getByRole("button", { name: "Anzeigen" }));
    expect(
      await screen.findByRole("heading", { name: "Kneipenquiz" }),
    ).toBeInTheDocument();
  });

  it("zeigt Frage, Beitritts-QR und Rangliste", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({
        frage: oeffentlicheFrage({ typ: "auswahl", optionen: ["Rot", "Blau"] }),
      }),
    );
    zeige(<QuizSeite unterseite="tafel" />, "/modul/quiz/tafel?code=ABC234");

    expect(
      await screen.findByRole("heading", { name: "Hauptstadt von Frankreich?" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Rot")).toBeInTheDocument();
    expect(screen.getByText("1 von 2 haben geantwortet")).toBeInTheDocument();
    expect(
      await screen.findByRole("img", {
        name: "QR-Code für https://quiz.example/modul/quiz/spielen?code=ABC234",
      }),
    ).toBeInTheDocument();
  });

  it("wartet in der Lobby mit der Zahl der Mitspieler", async () => {
    vi.spyOn(api, "ladeRundenstand").mockResolvedValue(
      rundenstand({ status: "lobby", phase: "keine", frage: null }),
    );
    zeige(<QuizSeite unterseite="tafel" />, "/modul/quiz/tafel?code=ABC234");
    expect(await screen.findByLabelText("Code ABC234")).toBeInTheDocument();
    expect(screen.getByText(/Personen sind dabei/)).toHaveTextContent(
      "2 Personen sind dabei",
    );
    expect(screen.getByRole("list", { name: "Mitspieler" })).toHaveTextContent("Ben");
  });

  it("zeigt den Buzzer, die Lösung und den Endstand", async () => {
    const abruf = vi
      .spyOn(api, "ladeRundenstand")
      .mockResolvedValue(
        rundenstand({ frage: oeffentlicheFrage({ typ: "buzzer" }), buzzer: "Ben" }),
      );
    const { unmount } = zeige(
      <QuizSeite unterseite="tafel" />,
      "/modul/quiz/tafel?code=ABC234",
    );
    expect(await screen.findByText("Ben ist dran!")).toBeInTheDocument();
    unmount();

    abruf.mockResolvedValue(rundenstand({ status: "beendet" }));
    zeige(<QuizSeite unterseite="tafel" />, "/modul/quiz/tafel?code=ABC234");
    const podest = await screen.findByRole("list", { name: "Siegerpodest" });
    expect(podest).toHaveTextContent("Anna");
    expect(podest).toHaveTextContent("4 Punkte");
  });

  it("meldet einen Fehler wörtlich", async () => {
    vi.spyOn(api, "ladeRundenstand").mockRejectedValue(new ApiError("Gateway weg", 503));
    zeige(<QuizSeite unterseite="tafel" />, "/modul/quiz/tafel?code=ABC234");
    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway weg");
  });
});

// ===================================================================== Bereiche

describe("Bereiche", () => {
  it("schickt Besucher ohne Recht von den Katalogen zum Leiten", async () => {
    zeige(<QuizSeite unterseite="kataloge" />, "/modul/quiz/kataloge");
    expect(await screen.findByText(/Eine Runde leiten\s+kann jeder/)).toBeInTheDocument();
  });
});

// ===================================================================== Kataloge

describe("Kataloge", () => {
  it("erklärt im Erstzustand, wozu ein Katalog da ist", async () => {
    vi.spyOn(api, "ladeKataloge").mockResolvedValue([]);
    zeige(<QuizSeite unterseite="kataloge" />, "/modul/quiz/kataloge", LEITUNG);
    expect(await screen.findByText("Noch kein Fragenkatalog")).toBeInTheDocument();
  });

  it("legt einen Katalog an und eine Auswahlfrage hinein", async () => {
    vi.spyOn(api, "ladeKataloge").mockResolvedValue([]);
    vi.spyOn(api, "legeKatalogAn").mockResolvedValue({ ...katalog(), fragen: [] });
    vi.spyOn(api, "ladeKatalog").mockResolvedValue({
      ...katalog({ anzahl_fragen: 0 }),
      fragen: [],
    });
    const anlegen = vi.spyOn(api, "legeFrageAn").mockResolvedValue(frage());
    zeige(<QuizSeite unterseite="kataloge" />, "/modul/quiz/kataloge", LEITUNG);

    await userEvent.type(await screen.findByLabelText("Neuer Katalog"), "Kneipenquiz");
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));
    expect(await screen.findByText("Noch keine Fragen")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Frage hinzufügen" }));
    await userEvent.selectOptions(screen.getByLabelText("Fragetyp"), "auswahl");
    await userEvent.type(screen.getByLabelText("Frage"), "Welche Farbe?");
    await userEvent.type(screen.getByLabelText("Antwort 1"), "Rot");
    await userEvent.type(screen.getByLabelText("Antwort 2"), "Blau");
    await userEvent.click(screen.getByRole("button", { name: "Antwort hinzufügen" }));
    await userEvent.click(screen.getByRole("button", { name: "Frage anlegen" }));

    expect(anlegen).toHaveBeenCalledWith(
      "k1",
      expect.objectContaining({
        text: "Welche Farbe?",
        daten: {
          typ: "auswahl",
          optionen: [
            { text: "Rot", richtig: true },
            { text: "Blau", richtig: false },
          ],
        },
      }),
    );
  });

  it("behält die Frage, wenn das Backend sie ablehnt", async () => {
    vi.spyOn(api, "ladeKatalog").mockResolvedValue({ ...katalog(), fragen: [frage()] });
    vi.spyOn(api, "aendereFrage").mockRejectedValue(
      new ApiError("Mindestens eine Option muss richtig sein", 422),
    );
    zeige(
      <QuizSeite unterseite="kataloge" />,
      "/modul/quiz/kataloge?katalog=k1",
      LEITUNG,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "Frage 1 bearbeiten" }),
    );
    const text = screen.getByLabelText("Frage");
    await userEvent.clear(text);
    await userEvent.type(text, "Neu?");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Mindestens eine Option muss richtig sein",
    );
    expect(screen.getByLabelText("Frage")).toHaveValue("Neu?");
  });

  it("bietet für jeden Fragetyp eigene Felder", async () => {
    vi.spyOn(api, "ladeKatalog").mockResolvedValue({ ...katalog(), fragen: [] });
    zeige(
      <QuizSeite unterseite="kataloge" />,
      "/modul/quiz/kataloge?katalog=k1",
      LEITUNG,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Frage hinzufügen" }),
    );
    const typ = screen.getByLabelText("Fragetyp");

    const erwartet: Record<string, string> = {
      zahl: "Toleranz ±",
      schaetzung: "Maximum",
      buzzer: "Lösung (nur für dich sichtbar)",
      bild: "Richtige Antworten (leer: du bewertest von Hand)",
      hotspot: "Radius in % der Bildbreite",
      sortieren: "Elemente in der richtigen Reihenfolge",
      freitext: "Richtige Antworten",
    };
    for (const [wert, feld] of Object.entries(erwartet)) {
      await userEvent.selectOptions(typ, wert);
      expect(screen.getByLabelText(feld)).toBeInTheDocument();
    }
  });

  it("sortiert, löscht und lädt Bilder hoch", async () => {
    vi.spyOn(api, "ladeKatalog").mockResolvedValue({
      ...katalog(),
      fragen: [frage(), frage({ id: "f2", text: "Zweite?", hat_bild: true })],
    });
    const sortieren = vi
      .spyOn(api, "sortiereFragen")
      .mockResolvedValue({ ...katalog(), fragen: [] });
    const hochladen = vi.spyOn(api, "ladeBildHoch").mockResolvedValue(frage());
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const loeschen = vi.spyOn(api, "loescheFrage").mockResolvedValue();
    zeige(
      <QuizSeite unterseite="kataloge" />,
      "/modul/quiz/kataloge?katalog=k1",
      LEITUNG,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "Frage 2 nach oben" }),
    );
    expect(sortieren).toHaveBeenCalledWith("k1", ["f2", "f1"]);

    await userEvent.click(screen.getByRole("button", { name: "Frage 1 löschen" }));
    expect(loeschen).toHaveBeenCalledWith("f1");

    await userEvent.click(screen.getByRole("button", { name: "Frage 2 bearbeiten" }));
    const datei = new File(["x"], "bild.png", { type: "image/png" });
    await userEvent.upload(screen.getByLabelText(/Bild ersetzen/), datei);
    await waitFor(() => expect(hochladen).toHaveBeenCalledWith("f2", datei));
    expect(within(screen.getByRole("list")).getAllByRole("img").length).toBeGreaterThan(
      0,
    );
  });
});

describe("Seltene Handgriffe", () => {
  it("löscht einen Katalog und ein Bild, setzt das Ziel eines Hotspots", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const hotspot = frage({
      id: "f3",
      hat_bild: true,
      daten: { typ: "hotspot", ziele: [{ x: 50, y: 50, radius: 10 }] },
    });
    vi.spyOn(api, "ladeKatalog").mockResolvedValue({ ...katalog(), fragen: [hotspot] });
    vi.spyOn(api, "ladeKataloge").mockResolvedValue([katalog()]);
    const bildWeg = vi.spyOn(api, "entferneBild").mockResolvedValue();
    const aendern = vi.spyOn(api, "aendereFrage").mockResolvedValue(hotspot);
    const katalogWeg = vi.spyOn(api, "loescheKatalog").mockResolvedValue();
    zeige(
      <QuizSeite unterseite="kataloge" />,
      "/modul/quiz/kataloge?katalog=k1",
      LEITUNG,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "Frage 1 bearbeiten" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Richtige Stelle setzen" }));
    const radius = screen.getByLabelText("Radius in % der Bildbreite");
    await userEvent.clear(radius);
    await userEvent.type(radius, "5");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));
    expect(aendern).toHaveBeenCalledWith(
      "f3",
      expect.objectContaining({
        daten: { typ: "hotspot", ziele: [expect.objectContaining({ radius: 5 })] },
      }),
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "Frage 1 bearbeiten" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Bild entfernen" }));
    expect(bildWeg).toHaveBeenCalledWith("f3");
    await userEvent.click(screen.getByRole("button", { name: "Abbrechen" }));

    await userEvent.click(screen.getByRole("button", { name: "Katalog löschen" }));
    expect(katalogWeg).toHaveBeenCalledWith("k1");
    expect(
      await screen.findByRole("heading", { name: "Fragenkataloge" }),
    ).toBeInTheDocument();
  });

  it("pflegt Zahlen und Optionen im Formular", async () => {
    vi.spyOn(api, "ladeKatalog").mockResolvedValue({ ...katalog(), fragen: [] });
    const anlegen = vi.spyOn(api, "legeFrageAn").mockResolvedValue(frage());
    zeige(
      <QuizSeite unterseite="kataloge" />,
      "/modul/quiz/kataloge?katalog=k1",
      LEITUNG,
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "Frage hinzufügen" }),
    );
    await userEvent.selectOptions(screen.getByLabelText("Fragetyp"), "auswahl");
    await userEvent.click(screen.getByRole("button", { name: "Antwort hinzufügen" }));
    await userEvent.click(screen.getByRole("button", { name: "Antwort 3 entfernen" }));
    expect(screen.queryByLabelText("Antwort 3")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Antwort 2 ist richtig" }),
    );

    await userEvent.selectOptions(screen.getByLabelText("Fragetyp"), "zahl");
    await userEvent.type(screen.getByLabelText("Frage"), "Wie viele?");
    const loesung = screen.getByLabelText("Lösung");
    await userEvent.clear(loesung);
    await userEvent.type(loesung, "16,5");
    await userEvent.type(screen.getByLabelText("Punkte"), "0");
    await userEvent.clear(screen.getByLabelText(/Zeitlimit/));
    await userEvent.click(screen.getByRole("button", { name: "Frage anlegen" }));
    expect(anlegen).toHaveBeenCalledWith(
      "k1",
      expect.objectContaining({
        zeitlimit: null,
        daten: expect.objectContaining({ typ: "zahl", loesung: 16.5 }) as unknown,
      }),
    );
  });
});
