import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import { mitAnmeldung, TESTBENUTZER } from "../testhilfen";
import { Navigation } from "./Navigation";

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

/**
 * Rendert die Leiste so, als stünde sie auf der angegebenen Adresse.
 *
 * Bewusst OHNE <Routes> darum herum - genau so steht sie in der Hülle. Ein
 * Test, der sie in eine Route einpackt, prüft eine Lage, die es nicht gibt,
 * und übersieht dabei, dass useParams dort leer bliebe.
 */
function zeige(pfad = "/", module: client.ModulEintrag[] = [modul()]) {
  vi.spyOn(client, "fetchModule").mockResolvedValue(module);

  return render(
    <MemoryRouter initialEntries={[pfad]}>
      {mitAnmeldung(<Navigation />, TESTBENUTZER)}
    </MemoryRouter>,
  );
}

describe("Die Navigationsleiste", () => {
  it("führt zur Übersicht und zu jedem Artefakt", async () => {
    zeige("/", [modul(), modul({ id: "geraete", titel: "Geräte" })]);

    expect(await screen.findByRole("link", { name: /StaffelPilot/ })).toHaveAttribute(
      "href",
      "/modul/staffelpilot",
    );
    expect(screen.getByRole("link", { name: /Geräte/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Übersicht/ })).toHaveAttribute("href", "/");
  });

  it("klappt die Bereiche nur beim geöffneten Artefakt auf", async () => {
    // Alle Bereiche aller Artefakte untereinander wären eine Liste, in der
    // man sucht statt findet.
    zeige("/", [modul()]);
    await screen.findByRole("link", { name: /StaffelPilot/ });

    expect(screen.queryByRole("list", { name: /Bereiche von/ })).not.toBeInTheDocument();
  });

  it("zeigt sie, sobald das Artefakt offen ist", async () => {
    zeige("/modul/staffelpilot");

    const bereiche = await screen.findByRole("list", {
      name: "Bereiche von StaffelPilot",
    });
    expect(within(bereiche).getByRole("link", { name: "Spielprüfung" })).toHaveAttribute(
      "href",
      "/modul/staffelpilot/spiele",
    );
    // Neun Bereiche laut Register - die Leiste erfindet keine dazu.
    expect(within(bereiche).getAllByRole("link")).toHaveLength(9);
  });

  it("gibt einem Artefakt ohne Bereiche auch keine leere Liste", async () => {
    zeige("/modul/geraete", [modul({ id: "geraete", titel: "Geräte" })]);
    await screen.findByRole("link", { name: /Geräte/ });

    expect(screen.queryByRole("list", { name: /Bereiche von/ })).not.toBeInTheDocument();
  });

  it("zeigt den Symbolnamen aus dem Manifest nicht als Text", async () => {
    // Das Manifest liefert in "icon" einen NAMEN ("steckdose", "pfeife"),
    // keinen einzelnen Buchstaben. Als Text gesetzt, lief das Wort aus dem
    // 20-px-Kästchen heraus und lag über dem Titel des Artefakts. Die
    // früheren Testdaten hatten icon: "" - genau deshalb fiel es nie auf.
    zeige("/", [
      modul({ id: "geraete", titel: "Geräte", icon: "steckdose" }),
      modul({ icon: "pfeife" }),
      modul({ id: "verwaltung", titel: "Verwaltung", icon: "schluessel" }),
    ]);
    await screen.findByRole("link", { name: /StaffelPilot/ });

    for (const name of ["steckdose", "pfeife", "schluessel"]) {
      expect(screen.queryByText(name, { exact: false })).not.toBeInTheDocument();
    }
    // Der zugängliche Name bleibt der Titel - ohne Symbolwort davor.
    expect(screen.getByRole("link", { name: "Geräte" })).toBeInTheDocument();
  });

  it("benennt keine Liste so wie die Kachelliste der Startseite", async () => {
    // Die Startseite hat eine Liste "Artefakte". Trägt die Leiste denselben
    // Namen, stehen zwei gleichnamige Listen auf der Seite: Ein Screenreader
    // sagt zweimal "Artefakte, Liste" an, und jede Suche nach der Kachel
    // trifft zweimal. Die Oberflächentests sind genau daran gescheitert.
    zeige("/");
    await screen.findByRole("link", { name: /StaffelPilot/ });

    expect(screen.queryByRole("list", { name: "Artefakte" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "Artefakte" }),
    ).not.toBeInTheDocument();
  });

  it("sagt eine Störung auch dort, wo keine Farbe ankommt", async () => {
    // Der Punkt daneben ist Dekoration. Wer ihn nicht sieht - Screenreader
    // oder Farbenblindheit -, muss es trotzdem erfahren.
    zeige("/", [modul({ status: "fehler" })]);

    expect(
      await screen.findByRole("link", { name: /StaffelPilot.*Nicht erreichbar/s }),
    ).toBeInTheDocument();
  });
});
