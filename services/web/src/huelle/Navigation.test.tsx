import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/anmeldung";
import * as client from "../api/client";
import { sichtbareUnterseiten } from "../module/register";
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
 * Rendert die Fläche so, als stünde sie auf der angegebenen Adresse.
 *
 * Bewusst OHNE <Routes> darum herum - genau so steht sie in der Hülle. Ein
 * Test, der sie in eine Route einpackt, prüft eine Lage, die es nicht gibt,
 * und übersieht dabei, dass useParams dort leer bliebe.
 */
function zeige(
  pfad = "/",
  module: client.ModulEintrag[] = [modul()],
  beiSchliessen = () => {},
) {
  vi.spyOn(client, "fetchModule").mockResolvedValue(module);

  return render(
    <MemoryRouter initialEntries={[pfad]}>
      {mitAnmeldung(<Navigation beiSchliessen={beiSchliessen} />, TESTBENUTZER)}
    </MemoryRouter>,
  );
}

describe("Die Navigationsfläche", () => {
  it("ist ein Dialog über der Seite und nicht Teil von ihr", async () => {
    // aria-modal sagt dem Screenreader, dass die Seite dahinter gerade
    // nicht gemeint ist. Ohne das liest er munter weiter, was unter der
    // Flaeche liegt.
    zeige("/");

    const dialog = await screen.findByRole("dialog", { name: "Navigation" });

    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("führt zur Übersicht und zu jedem Artefakt", async () => {
    zeige("/", [modul(), modul({ id: "geraete", titel: "Geräte" })]);

    expect(await screen.findByRole("link", { name: /StaffelPilot/ })).toHaveAttribute(
      "href",
      "/modul/staffelpilot",
    );
    expect(screen.getByRole("link", { name: /Geräte/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Übersicht/ })).toHaveAttribute("href", "/");
  });

  it("zeigt die Bereiche nur beim geöffneten Artefakt", async () => {
    // Alle Bereiche aller Artefakte nebeneinander wären eine Liste, in der
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
    // So viele Bereiche, wie im Register stehen -- die Flaeche erfindet
    // keine dazu und laesst keinen weg. Die Zahl kommt aus dem Register und
    // nicht aus dieser Datei: sonst scheitert dieser Test bei jedem neuen
    // Bereich, ohne dass an der Flaeche etwas falsch waere.
    expect(within(bereiche).getAllByRole("link")).toHaveLength(
      sichtbareUnterseiten("staffelpilot").length,
    );
  });

  it("gibt einem Artefakt ohne Bereiche auch keine leere Liste", async () => {
    zeige("/modul/geraete", [modul({ id: "geraete", titel: "Geräte" })]);
    await screen.findByRole("link", { name: /Geräte/ });

    expect(screen.queryByRole("list", { name: /Bereiche von/ })).not.toBeInTheDocument();
  });

  it("zeigt den Symbolnamen aus dem Manifest nicht als Text", async () => {
    // Das Manifest liefert in "icon" einen NAMEN ("steckdose", "pfeife"),
    // keinen einzelnen Buchstaben. Als Text gesetzt, lief das Wort aus dem
    // Kästchen heraus und lag über dem Titel des Artefakts.
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

  it("benennt keine Liste so wie die Artefaktliste der Startseite", async () => {
    // Die Startseite hat eine Liste "Artefakte" - und sie liegt UNTER
    // dieser Flaeche, nicht hinter einer geschlossenen Tuer. Traegt die
    // Flaeche denselben Namen, stehen zwei gleichnamige Listen im Dokument:
    // Ein Screenreader sagt zweimal "Artefakte, Liste" an, und jede Suche
    // trifft doppelt.
    zeige("/");
    await screen.findByRole("link", { name: /StaffelPilot/ });

    expect(screen.queryByRole("list", { name: "Artefakte" })).not.toBeInTheDocument();
  });

  it("sagt eine Störung auch dort, wo keine Farbe ankommt", async () => {
    // Der Punkt daneben ist Dekoration. Wer ihn nicht sieht - Screenreader
    // oder Farbenblindheit -, muss es trotzdem erfahren.
    zeige("/", [modul({ status: "fehler" })]);

    expect(
      await screen.findByRole("link", { name: /StaffelPilot.*Nicht erreichbar/s }),
    ).toBeInTheDocument();
  });

  it("trägt Einstellungen und Abmelden", async () => {
    // Beides stand vorher in der Kopfzeile und war dort dauerhaft im Bild,
    // obwohl man es selten braucht.
    zeige("/");

    expect(await screen.findByRole("link", { name: "Einstellungen" })).toHaveAttribute(
      "href",
      "/einstellungen",
    );
    expect(screen.getByRole("button", { name: "Abmelden" })).toBeInTheDocument();
  });

  it("meldet ab", async () => {
    const abmelden = vi.spyOn(api, "abmelden").mockResolvedValue(undefined);
    zeige("/");

    await userEvent.click(await screen.findByRole("button", { name: "Abmelden" }));

    expect(abmelden).toHaveBeenCalled();
  });

  it("lässt sich über den Knopf schließen", async () => {
    const beiSchliessen = vi.fn();
    zeige("/", [modul()], beiSchliessen);

    // Der zugängliche Name ist "Navigation schließen" und nicht das, was
    // sichtbar dasteht: Sichtbar steht auf einer Tastatur "Esc schließt"
    // und auf einem Telefon "Schließen".
    await userEvent.click(
      await screen.findByRole("button", { name: "Navigation schließen" }),
    );

    expect(beiSchliessen).toHaveBeenCalled();
  });
});

describe("Die Bereiche beim Zeigen", () => {
  it("schlägt rechts das Artefakt auf, auf das man zeigt", async () => {
    // Vorher führte der Weg zu "Haushaltsbuch · Posten" über drei Schritte:
    // Artefakt anklicken, warten, Fläche noch einmal aufziehen, Bereich
    // anklicken. Dabei stand die Liste der Bereiche die ganze Zeit daneben.
    zeige("/", [modul(), modul({ id: "haushaltsbuch", titel: "Haushaltsbuch" })]);
    const haushalt = await screen.findByRole("link", { name: /Haushaltsbuch/ });

    await userEvent.hover(haushalt);

    const bereiche = await screen.findByRole("list", {
      name: "Bereiche von Haushaltsbuch",
    });
    expect(within(bereiche).getByRole("link", { name: "Monatsplan" })).toHaveAttribute(
      "href",
      "/modul/haushaltsbuch/uebersicht",
    );
  });

  it("tut dasselbe mit der Tastatur", async () => {
    zeige("/", [modul(), modul({ id: "haushaltsbuch", titel: "Haushaltsbuch" })]);
    const haushalt = await screen.findByRole("link", { name: /Haushaltsbuch/ });

    haushalt.focus();

    expect(
      await screen.findByRole("list", { name: "Bereiche von Haushaltsbuch" }),
    ).toBeInTheDocument();
  });

  it("fällt auf das geöffnete Artefakt zurück, sobald der Zeiger die Liste verlässt", async () => {
    zeige("/modul/staffelpilot/spiele", [
      modul(),
      modul({ id: "haushaltsbuch", titel: "Haushaltsbuch" }),
    ]);
    const haushalt = await screen.findByRole("link", { name: /Haushaltsbuch/ });

    await userEvent.hover(haushalt);
    await screen.findByRole("list", { name: "Bereiche von Haushaltsbuch" });
    await userEvent.unhover(haushalt);

    expect(
      await screen.findByRole("list", { name: "Bereiche von StaffelPilot" }),
    ).toBeInTheDocument();
  });
});
