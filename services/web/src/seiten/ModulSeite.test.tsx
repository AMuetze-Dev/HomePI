import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import * as geraeteApi from "../module/geraete/api";
import * as register from "../module/register";
import { ModulSeite } from "./ModulSeite";

afterEach(() => {
  vi.restoreAllMocks();
});

// Bewusst ein Artefakt OHNE eingetragene Oberflaeche: genau dieser Fall soll
// die generische Ansicht bekommen. "geraete" hat inzwischen eine eigene.
const ohneOberflaeche: client.ModulEintrag = {
  id: "messwerte",
  titel: "Messwerte",
  pfad: "/messwerte",
  beschreibung: "Zahlen aus dem Haus",
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
    vi.spyOn(client, "fetchModule").mockResolvedValue([ohneOberflaeche]);
    vi.spyOn(client, "fetchEndpunkte").mockResolvedValue([
      { methode: "GET", pfad: "/messwerte/", beschreibung: "Liste" },
    ]);

    zeige("messwerte");

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Messwerte",
    );
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.getByText("/messwerte/")).toBeInTheDocument();
  });

  it("nimmt für ein eingetragenes Artefakt dessen eigene Oberfläche", async () => {
    // geraete ist in register.ts eingetragen - hier wird die echte
    // Verdrahtung geprüft, nicht ein Mock davon.
    vi.spyOn(client, "fetchModule").mockResolvedValue([
      { ...ohneOberflaeche, id: "geraete", titel: "Geräte", pfad: "/geraete" },
    ]);
    vi.spyOn(geraeteApi, "ladeGeraete").mockResolvedValue([
      {
        id: "1",
        name: "Stehlampe",
        raum: "Wohnzimmer",
        zustand: "bereit",
        eingeschaltet: false,
      },
    ]);
    vi.spyOn(geraeteApi, "ladeZusammenfassung").mockResolvedValue({
      anzahl: 1,
      eingeschaltet: 0,
      in_wartung: 0,
      raeume: { Wohnzimmer: 1 },
    });

    zeige("geraete");

    // Die Geräteseite zeigt Kennzahlen und eine Tabelle mit den Geräten -
    // die generische Ansicht zeigt eine Tabelle mit Endpunkten. Der Inhalt
    // unterscheidet sie, nicht die Struktur.
    expect(await screen.findByText("Stehlampe")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Überblick" })).toBeInTheDocument();
  });

  it("bevorzugt eine eingetragene eigene Oberfläche", async () => {
    vi.spyOn(client, "fetchModule").mockResolvedValue([ohneOberflaeche]);
    vi.spyOn(register, "oberflaecheFuer").mockReturnValue({
      id: "messwerte",
      Komponente: () => <p>Meine eigene Ansicht</p>,
    });

    zeige("messwerte");

    expect(await screen.findByText("Meine eigene Ansicht")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("meldet ein unbekanntes Artefakt verständlich", async () => {
    vi.spyOn(client, "fetchModule").mockResolvedValue([ohneOberflaeche]);

    zeige("gibtsnicht");

    // Kein Alarm, sondern ein Leerzustand: ein aufgerufener Pfad, den es
    // nicht gibt, ist kein Fehler des Systems.
    expect(await screen.findByText(/Kein Modul mit der Kennung/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Übersicht/ })).toBeInTheDocument();
  });

  it("erklärt sich, wenn ein Artefakt weder Oberfläche noch Endpunkte hat", async () => {
    vi.spyOn(client, "fetchModule").mockResolvedValue([ohneOberflaeche]);
    vi.spyOn(client, "fetchEndpunkte").mockResolvedValue([]);

    zeige("messwerte");

    expect(await screen.findByText(/Noch keine Oberfläche/)).toBeInTheDocument();
  });
});
