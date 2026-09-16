import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import * as register from "../module/register";
import { ModulSeite } from "./ModulSeite";

afterEach(() => {
  vi.restoreAllMocks();
});

const geraete: client.ModulEintrag = {
  id: "geraete",
  titel: "Geräte",
  pfad: "/geraete",
  beschreibung: "Alles, was an ist",
  icon: "kachel",
  version: "1.0.0",
  status: "bereit",
};

function zeige(id: string) {
  render(
    <MemoryRouter initialEntries={[`/modul/${id}`]}>
      <Routes>
        <Route path="/modul/:id" element={<ModulSeite />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Modulseite", () => {
  it("zeigt die generische Ansicht, wenn es keine eigene Oberfläche gibt", async () => {
    vi.spyOn(client, "fetchModule").mockResolvedValue([geraete]);
    vi.spyOn(client, "fetchEndpunkte").mockResolvedValue([
      { methode: "GET", pfad: "/geraete/", beschreibung: "Liste" },
    ]);

    zeige("geraete");

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Geräte");
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.getByText("/geraete/")).toBeInTheDocument();
  });

  it("bevorzugt eine eingetragene eigene Oberfläche", async () => {
    vi.spyOn(client, "fetchModule").mockResolvedValue([geraete]);
    vi.spyOn(register, "oberflaecheFuer").mockReturnValue({
      id: "geraete",
      Komponente: () => <p>Meine eigene Ansicht</p>,
    });

    zeige("geraete");

    expect(await screen.findByText("Meine eigene Ansicht")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("meldet ein unbekanntes Artefakt verständlich", async () => {
    vi.spyOn(client, "fetchModule").mockResolvedValue([geraete]);

    zeige("gibtsnicht");

    expect(await screen.findByRole("alert")).toHaveTextContent(/kein Modul/);
    expect(screen.getByRole("link", { name: /Startseite/ })).toBeInTheDocument();
  });

  it("erklärt sich, wenn ein Artefakt weder Oberfläche noch Endpunkte hat", async () => {
    vi.spyOn(client, "fetchModule").mockResolvedValue([geraete]);
    vi.spyOn(client, "fetchEndpunkte").mockResolvedValue([]);

    zeige("geraete");

    expect(await screen.findByText(/keine eigene Oberfläche/)).toBeInTheDocument();
  });
});
