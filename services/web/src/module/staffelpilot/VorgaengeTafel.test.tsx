import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { VorgaengeTafel } from "./VorgaengeTafel";
import * as api from "./api";

function zeile(rest: Partial<api.VorgangZeile> = {}): api.VorgangZeile {
  return {
    id: "v1",
    befund_id: "b1",
    art: "mahnung",
    aktenzeichen: "26-27-0001",
    verein: "SG Gittersee",
    betroffener: "Max Müller",
    betreff: "Mahnung SG Gittersee – SV Fortschritt am 13.09.2026",
    zustand: "entwurf",
    ...rest,
  };
}

function vorgang(rest: Partial<api.Vorgang> = {}): api.Vorgang {
  return {
    ...zeile(),
    grund: "Tätlichkeit",
    empfaenger: "verein@example.org",
    text: "Sehr geehrte Damen und Herren,\n\nFeldverweis in Minute 71.",
    versandt_am: null,
    ...rest,
  };
}

function entwurf(rest: Partial<api.Mailentwurf> = {}): api.Mailentwurf {
  return {
    empfaenger: "verein@example.org",
    betreff: "2026/0007 | SV Loschwitz - SG Gittersee | 05.09.2026",
    text: "Sehr geehrte Damen und Herren,",
    anhang: "/staffelpilot/vorgaenge/v1/mahnung.pdf",
    fehlende_felder: [],
    ...rest,
  };
}

function mitListe(
  zeilen: api.VorgangZeile[] = [zeile()],
  offen = vorgang(),
  mail = entwurf(),
) {
  vi.spyOn(api, "ladeVorgaenge").mockResolvedValue(zeilen);
  vi.spyOn(api, "ladeVorgang").mockResolvedValue(offen);
  vi.spyOn(api, "ladeMailentwurf").mockResolvedValue(mail);
}

async function aufklappen() {
  await userEvent.click(await screen.findByRole("button", { expanded: false }));
}

/** Die Knöpfe in der Karte - die Filterleiste trägt dieselben Wörter. */
function inDerKarte() {
  return within(screen.getByRole("list", { name: "Vorgänge" }));
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Die Liste", () => {
  it("zeigt Aktenzeichen, Art und Zustand", async () => {
    mitListe();
    render(<VorgaengeTafel />);

    const liste = await screen.findByRole("list", { name: "Vorgänge" });
    expect(within(liste).getByText("26-27-0001")).toBeInTheDocument();
    expect(within(liste).getByText("Mahnung")).toBeInTheDocument();
    expect(within(liste).getByText("Entwurf")).toBeInTheDocument();
  });

  it("sagt beim leeren Stand, woher ein Vorgang kommt", async () => {
    mitListe([]);
    render(<VorgaengeTafel />);

    expect(await screen.findByText("Keine Vorgänge")).toBeInTheDocument();
    expect(screen.getByText(/Mahnung entwerfen/)).toBeInTheDocument();
  });

  it("filtert nach Zustand", async () => {
    mitListe();
    render(<VorgaengeTafel />);
    await screen.findByRole("list", { name: "Vorgänge" });

    await userEvent.click(screen.getByRole("button", { name: "Versandt" }));

    await waitFor(() =>
      expect(api.ladeVorgaenge).toHaveBeenCalledWith("versandt", expect.anything()),
    );
  });

  it("zeigt einen Ladefehler statt einer leeren Liste", async () => {
    vi.spyOn(api, "ladeVorgaenge").mockRejectedValue(new ApiError("kein Zugriff", 403));
    render(<VorgaengeTafel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });
});

describe("Ein Vorgang", () => {
  it("zeigt Text und Empfänger beim Aufklappen", async () => {
    mitListe();
    render(<VorgaengeTafel />);
    await aufklappen();

    expect(
      await screen.findByDisplayValue(/Feldverweis in Minute 71/),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("verein@example.org")).toBeInTheDocument();
  });

  it("sagt ausdrücklich, dass nichts verschickt wird", async () => {
    // Die eine Zusage, die ein Staffelleiter hier braucht: kein Klick loest
    // eine Mail aus.
    mitListe();
    render(<VorgaengeTafel />);
    await aufklappen();

    expect(
      await screen.findByText(/Dieses Programm verschickt nichts/),
    ).toBeInTheDocument();
  });

  it("speichert den geänderten Text", async () => {
    mitListe();
    const aendern = vi
      .spyOn(api, "aendereVorgang")
      .mockResolvedValue(vorgang({ text: "Eigene Fassung." }));
    render(<VorgaengeTafel />);
    await aufklappen();

    const feld = await screen.findByLabelText("Text");
    await userEvent.clear(feld);
    await userEvent.type(feld, "Eigene Fassung.");
    await userEvent.click(inDerKarte().getByRole("button", { name: "Speichern" }));

    await waitFor(() =>
      expect(aendern).toHaveBeenCalledWith(
        "v1",
        expect.objectContaining({ text: "Eigene Fassung." }),
      ),
    );
  });

  it("bietet aus dem Entwurf nur den Schritt an, den das Backend erlaubt", async () => {
    mitListe();
    render(<VorgaengeTafel />);
    await aufklappen();

    expect(
      await inDerKarte().findByRole("button", { name: /Versandt/ }),
    ).toBeInTheDocument();
    expect(
      inDerKarte().queryByRole("button", { name: /Erledigt/ }),
    ).not.toBeInTheDocument();
  });

  it("bietet aus dem versandten Zustand beide Richtungen an", async () => {
    mitListe([zeile({ zustand: "versandt" })], vorgang({ zustand: "versandt" }));
    render(<VorgaengeTafel />);
    await aufklappen();

    expect(
      await inDerKarte().findByRole("button", { name: /Erledigt/ }),
    ).toBeInTheDocument();
    expect(
      inDerKarte().getByRole("button", { name: /Zurück in den Entwurf/ }),
    ).toBeInTheDocument();
  });

  it("stellt weiter", async () => {
    mitListe();
    const setzen = vi
      .spyOn(api, "setzeVorgangZustand")
      .mockResolvedValue(
        vorgang({ zustand: "versandt", versandt_am: "2026-09-17T10:00:00Z" }),
      );
    render(<VorgaengeTafel />);
    await aufklappen();

    await userEvent.click(await inDerKarte().findByRole("button", { name: /Versandt/ }));

    await waitFor(() => expect(setzen).toHaveBeenCalledWith("v1", "versandt"));
  });

  it("nennt den Versandtag, sobald einer feststeht", async () => {
    mitListe(
      [zeile({ zustand: "versandt" })],
      vorgang({ zustand: "versandt", versandt_am: "2026-09-17T10:00:00Z" }),
    );
    render(<VorgaengeTafel />);
    await aufklappen();

    expect(await screen.findByText(/Versandt am 17\.9\.2026/)).toBeInTheDocument();
  });

  it("zeigt die Meldung des Backends bei einem unmöglichen Schritt", async () => {
    mitListe();
    vi.spyOn(api, "setzeVorgangZustand").mockRejectedValue(
      new ApiError("Von 'entwurf' aus geht nur: versandt", 409),
    );
    render(<VorgaengeTafel />);
    await aufklappen();

    await userEvent.click(await inDerKarte().findByRole("button", { name: /Versandt/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/geht nur: versandt/);
  });

  it("verwirft", async () => {
    mitListe();
    const verwerfen = vi.spyOn(api, "verwerfeVorgang").mockResolvedValue(undefined);
    render(<VorgaengeTafel />);
    await aufklappen();

    await userEvent.click(await inDerKarte().findByRole("button", { name: "Verwerfen" }));

    await waitFor(() => expect(verwerfen).toHaveBeenCalledWith("v1"));
  });

  describe("Mahnung und Mail", () => {
    it("bietet das ausgefüllte Formular an", async () => {
      mitListe();
      render(<VorgaengeTafel />);
      await aufklappen();

      const verweis = await screen.findByRole("link", { name: /Mahnung \(PDF\)/ });
      expect(verweis).toHaveAttribute("href", expect.stringContaining("/mahnung.pdf"));
    });

    it("nennt die Felder, die im Formular fehlen", async () => {
      // Ein Vordruck mit Lücken ist besser als einer mit erfundenen Angaben —
      // aber nur, wenn die Lücken auffallen.
      mitListe(
        [zeile()],
        vorgang(),
        entwurf({ fehlende_felder: ["Spielort", "Spieltag"] }),
      );
      render(<VorgaengeTafel />);
      await aufklappen();

      expect(await screen.findByText(/Spielort, Spieltag/)).toBeInTheDocument();
    });

    it("hat einen Knopf, der das Mailprogramm öffnet", async () => {
      mitListe();
      render(<VorgaengeTafel />);
      await aufklappen();

      expect(
        await inDerKarte().findByRole("button", { name: "E-Mail öffnen" }),
      ).toBeInTheDocument();
    });

    it("bietet bei einem Sportgerichtsfall kein Formular an", async () => {
      // Der läuft über das Verbandspostfach, nicht über den Vordruck für
      // Bagatellsachen.
      mitListe(
        [zeile({ art: "sportgericht" })],
        vorgang({ art: "sportgericht" }),
        entwurf({ anhang: "" }),
      );
      render(<VorgaengeTafel />);
      await aufklappen();

      await screen.findByRole("button", { name: "Speichern" });
      expect(screen.queryByRole("link", { name: /Mahnung/ })).toBeNull();
    });
  });
});
