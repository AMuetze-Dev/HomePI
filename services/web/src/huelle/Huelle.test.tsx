import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as anmeldungApi from "../api/anmeldung";
import type { Benutzer } from "../api/anmeldung";
import * as client from "../api/client";
import { mitAnmeldung, TESTBENUTZER } from "../testhilfen";
import { Huelle } from "./Huelle";

afterEach(() => {
  vi.restoreAllMocks();
});

function modul(rest: Partial<client.ModulEintrag> = {}): client.ModulEintrag {
  return {
    id: "staffelpilot",
    titel: "StaffelPilot",
    pfad: "/staffelpilot",
    beschreibung: "Spielberichte prüfen",
    icon: "",
    version: "1.2.3",
    status: "bereit",
    zugang: "geschuetzt",
    ...rest,
  };
}

function zeige({
  schlicht = false,
  benutzer = null as Benutzer | null,
  module = [modul()],
} = {}) {
  vi.spyOn(client, "fetchModule").mockResolvedValue(module);

  render(
    <MemoryRouter>
      {mitAnmeldung(<Huelle schlicht={schlicht}>Inhalt</Huelle>, benutzer)}
    </MemoryRouter>,
  );
}

describe("Hülle", () => {
  it("rahmt den Inhalt mit einer Kopfleiste", async () => {
    zeige();

    expect(await screen.findByText("HomePI")).toBeInTheDocument();
    expect(screen.getByText("Inhalt")).toBeInTheDocument();
  });

  it("bietet abgemeldet den Weg zur Anmeldung", async () => {
    zeige();

    expect(await screen.findByRole("link", { name: "Anmelden" })).toBeInTheDocument();
  });

  it("lässt die Kopfleiste in der schlichten Fassung ganz weg", async () => {
    // Waehrend der Ersteinrichtung gibt es noch kein Konto und kein
    // Artefakt - eine Leiste mit Weg und Konto waere eine Einladung ins
    // Leere.
    zeige({ schlicht: true });

    expect(await screen.findByText("Inhalt")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Anmelden" })).not.toBeInTheDocument();
    expect(screen.queryByText("HomePI")).not.toBeInTheDocument();
  });

  it("bietet abgemeldet keine Navigation an", async () => {
    // Das Verzeichnis ist dann leer. Ein Zeichen, das eine leere Flaeche
    // aufzieht, waere ein Versprechen, das die Anwendung nicht halten kann.
    zeige();
    await screen.findByText("HomePI");

    expect(
      screen.queryByRole("button", { name: "Navigation öffnen" }),
    ).not.toBeInTheDocument();
  });

  it("öffnet und schließt die Navigation mit Escape", async () => {
    // Die Taste ist der ganze Grund, warum es keine Dauerleiste mehr gibt:
    // Ohne sie kostete jeder Wechsel des Artefakts die Suche nach einem Menü.
    zeige({ benutzer: TESTBENUTZER });
    await screen.findByRole("button", { name: "Navigation öffnen" });

    await userEvent.keyboard("{Escape}");
    expect(await screen.findByRole("dialog", { name: "Navigation" })).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "Navigation" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("öffnet sie auch über das Zeichen - für alle ohne Tastatur", async () => {
    zeige({ benutzer: TESTBENUTZER });
    const zeichen = await screen.findByRole("button", { name: "Navigation öffnen" });

    await userEvent.click(zeichen);

    expect(await screen.findByRole("dialog", { name: "Navigation" })).toBeInTheDocument();
  });

  it("schließt die Fläche, sobald es nichts mehr zu navigieren gibt", async () => {
    // „Abmelden" steht IN der Fläche. Wer es auf der Startseite anklickt,
    // wechselt die Adresse nicht - ohne diese Regel bliebe die Fläche über
    // einer Anwendung stehen, in der sie nichts mehr anzuzeigen hat.
    vi.spyOn(anmeldungApi, "abmelden").mockResolvedValue(undefined);
    zeige({ benutzer: TESTBENUTZER });

    await userEvent.click(
      await screen.findByRole("button", { name: "Navigation öffnen" }),
    );
    expect(await screen.findByRole("dialog", { name: "Navigation" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Abmelden" }));

    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "Navigation" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("lässt Escape dem Feld, in dem gerade getippt wird", async () => {
    // Wer in einem Suchfeld Escape drückt, meint das Feld - nicht die
    // Navigation. Ohne diese Unterscheidung springt bei jeder abgebrochenen
    // Eingabe eine Fläche über die halbe Anwendung.
    vi.spyOn(client, "fetchModule").mockResolvedValue([modul()]);
    render(
      <MemoryRouter>
        {mitAnmeldung(
          <Huelle>
            <input aria-label="Suche" />
          </Huelle>,
          TESTBENUTZER,
        )}
      </MemoryRouter>,
    );

    const feld = await screen.findByRole("textbox", { name: "Suche" });
    await userEvent.click(feld);
    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog", { name: "Navigation" })).not.toBeInTheDocument();
  });
});
