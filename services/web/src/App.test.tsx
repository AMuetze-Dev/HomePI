import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "./api/client";
import { App } from "./App";
import { mitAnmeldung } from "./testhilfen";

afterEach(() => {
  vi.restoreAllMocks();
});

const geraete: client.ModulEintrag = {
  id: "geraete",
  titel: "Geräte",
  pfad: "/geraete",
  beschreibung: "",
  icon: "kachel",
  version: "1.0.0",
  status: "bereit",
  zugang: "geschuetzt",
};

function zeige(pfad: string) {
  vi.spyOn(client, "fetchHealth").mockResolvedValue({
    status: "ok",
    version: "1.0.0",
    checks: { database: true },
  });
  vi.spyOn(client, "fetchModule").mockResolvedValue([geraete]);
  vi.spyOn(client, "fetchEndpunkte").mockResolvedValue([]);

  render(<MemoryRouter initialEntries={[pfad]}>{mitAnmeldung(<App />)}</MemoryRouter>);
}

describe("App", () => {
  it("zeigt unter / die Startseite", async () => {
    zeige("/");

    // Die Ueberschrift der Startseite ist die Begruessung, nicht das Wort
    // "Uebersicht": Wer seinen eigenen Pi aufruft, braucht keine Ueberschrift,
    // die ihm sagt, dass er auf der Uebersicht ist.
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      /Gut(en|e) \w+, Prüfer\./,
    );
  });

  it("rahmt jede Ansicht mit der Kopfleiste", async () => {
    zeige("/");

    expect(await screen.findByText("HomePI")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Navigation öffnen" })).toBeInTheDocument();
  });

  it("zeigt unter /einstellungen die Einstellungen", async () => {
    zeige("/einstellungen");

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Einstellungen",
    );
  });

  it("zeigt unter /modul/:id die Modulseite", async () => {
    zeige("/modul/geraete");

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Geräte");
  });

  it("führt einen unbekannten Pfad zur Startseite statt ins Leere", async () => {
    zeige("/voellig/woanders");

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      /Gut(en|e) \w+, Prüfer\./,
    );
  });
});
