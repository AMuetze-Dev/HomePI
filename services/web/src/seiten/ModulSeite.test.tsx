import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import * as verwaltungApi from "../module/verwaltung/api";
import * as register from "../module/register";
import { mitAnmeldung } from "../testhilfen";
import { ModulSeite } from "./ModulSeite";

afterEach(() => {
  vi.restoreAllMocks();
});

// Bewusst ein Artefakt OHNE eingetragene Oberflaeche: genau dieser Fall soll
// die generische Ansicht bekommen. "verwaltung" hat eine eigene.
const ohneOberflaeche: client.ModulEintrag = {
  id: "messwerte",
  titel: "Messwerte",
  pfad: "/messwerte",
  beschreibung: "Zahlen aus dem Haus",
  icon: "kachel",
  version: "1.0.0",
  status: "bereit",
  zugang: "geschuetzt",
};

function zeige(id: string, angemeldet = true) {
  render(
    <MemoryRouter initialEntries={[`/modul/${id}`]}>
      {mitAnmeldung(
        <Routes>
          <Route path="/modul/:id" element={<ModulSeite />} />
        </Routes>,
        angemeldet ? undefined : null,
      )}
    </MemoryRouter>,
  );
}

/** Dasselbe, aber auf einem Bereich - dort entscheidet sich, wer die
 *  Überschrift setzt. */
function zeigeBereich(id: string, unterseite: string) {
  render(
    <MemoryRouter initialEntries={[`/modul/${id}/${unterseite}`]}>
      {mitAnmeldung(
        <Routes>
          <Route path="/modul/:id/:unterseite" element={<ModulSeite />} />
        </Routes>,
      )}
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

  it("setzt keine Überschrift über ein Artefakt, das seine eigene trägt", async () => {
    /* Die Verwaltung baut ihren Kopf selbst - mit den Zahlen daneben, die
       nur sie kennt. Eine zweite Überschrift darüber waere dasselbe Wort
       zweimal untereinander. */
    vi.spyOn(client, "fetchModule").mockResolvedValue([
      { ...ohneOberflaeche, id: "verwaltung", titel: "Verwaltung", pfad: "/verwaltung" },
    ]);
    vi.spyOn(verwaltungApi, "ladeKonten").mockResolvedValue([]);
    vi.spyOn(verwaltungApi, "ladeArtefakte").mockResolvedValue([]);

    zeige("verwaltung");

    await screen.findByRole("heading", { level: 1 });
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("nimmt für ein eingetragenes Artefakt dessen eigene Oberfläche", async () => {
    // verwaltung ist in register.ts eingetragen - hier wird die echte
    // Verdrahtung geprüft, nicht ein Mock davon.
    vi.spyOn(client, "fetchModule").mockResolvedValue([
      { ...ohneOberflaeche, id: "verwaltung", titel: "Verwaltung", pfad: "/verwaltung" },
    ]);
    vi.spyOn(verwaltungApi, "ladeKonten").mockResolvedValue([
      {
        id: "22222222-2222-4222-8222-222222222222",
        name: "gast",
        anzeigename: "Gast",
        aktiv: true,
        rechte: {},
        angelegt: null,
        verwalter: false,
        passwort_wechseln: false,
      },
    ]);
    vi.spyOn(verwaltungApi, "ladeArtefakte").mockResolvedValue([
      { id: "verwaltung", titel: "Verwaltung", zugang: "geschuetzt" },
    ]);

    zeige("verwaltung");

    // Die Verwaltung zeigt die Konten - die generische Ansicht zeigt eine
    // Tabelle mit Endpunkten. Der Inhalt unterscheidet sie, nicht die
    // Struktur.
    expect(await screen.findByText("Gast")).toBeInTheDocument();
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
    // Einen Zurück-Verweis gibt es hier nicht mehr: Die Navigationsleiste
    // steht dauerhaft daneben und führt zur Übersicht wie zu jedem anderen
    // Artefakt. Ein zweiter Weg an derselben Stelle wäre einer zu viel.
  });

  it("bietet abgemeldet die Anmeldung an, statt 'gibt es nicht' zu behaupten", async () => {
    // Ein Artefakt ohne Recht steht gar nicht erst im Manifest - von hier aus
    // ist es von einem nicht vorhandenen nicht zu unterscheiden.
    vi.spyOn(client, "fetchModule").mockResolvedValue([]);

    zeige("staffelpilot", false);

    expect(
      await screen.findByRole("heading", { name: "Anmeldung nötig" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Kein Modul mit der Kennung/)).not.toBeInTheDocument();
  });

  it("erklärt sich, wenn ein Artefakt weder Oberfläche noch Endpunkte hat", async () => {
    vi.spyOn(client, "fetchModule").mockResolvedValue([ohneOberflaeche]);
    vi.spyOn(client, "fetchEndpunkte").mockResolvedValue([]);

    zeige("messwerte");

    expect(await screen.findByText(/Noch keine Oberfläche/)).toBeInTheDocument();
  });

  it("setzt den Bereichsnamen als Überschrift über den Inhalt", async () => {
    vi.spyOn(client, "fetchModule").mockResolvedValue([ohneOberflaeche]);
    vi.spyOn(register, "oberflaecheFuer").mockReturnValue({
      id: "messwerte",
      Komponente: () => <p>Meine eigene Ansicht</p>,
      unterseiten: [{ id: "tag", wort: "Heute" }],
    });

    zeigeBereich("messwerte", "tag");

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Heute");
  });

  it("hält sich heraus, wo der Bereich seinen Titel selbst mitbringt", async () => {
    // Sonst stünde dasselbe Wort zweimal untereinander: einmal von hier,
    // einmal aus der Tafel, die daneben noch eine Zahl und einen Filter
    // trägt - beides kennt diese Seite nicht.
    vi.spyOn(client, "fetchModule").mockResolvedValue([ohneOberflaeche]);
    vi.spyOn(register, "oberflaecheFuer").mockReturnValue({
      id: "messwerte",
      Komponente: () => <h1>Heute</h1>,
      unterseiten: [{ id: "tag", wort: "Heute", eigenerTitel: true }],
    });

    zeigeBereich("messwerte", "tag");

    expect(await screen.findAllByRole("heading", { name: "Heute" })).toHaveLength(1);
  });
});
