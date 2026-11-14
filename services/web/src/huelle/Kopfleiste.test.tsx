import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import { mitAnmeldung, TESTBENUTZER } from "../testhilfen";
import { Kopfleiste } from "./Kopfleiste";

afterEach(() => {
  vi.restoreAllMocks();
});

const staffelpilot: client.ModulEintrag = {
  id: "staffelpilot",
  titel: "StaffelPilot",
  pfad: "/staffelpilot",
  beschreibung: "Spielberichte prüfen",
  icon: "",
  version: "1.2.3",
  status: "bereit",
  zugang: "geschuetzt",
};

/**
 * Bewusst OHNE <Routes> darum herum - genau so steht die Leiste in der
 * Hülle. Der Pfad kommt deshalb aus useMatch und nicht aus useParams, und
 * dieser Test prüft genau das.
 */
function zeige(pfad = "/", navigierbar = true) {
  vi.spyOn(client, "fetchModule").mockResolvedValue([staffelpilot]);

  render(
    <MemoryRouter initialEntries={[pfad]}>
      {mitAnmeldung(
        <Kopfleiste
          navigierbar={navigierbar}
          navOffen={false}
          beiNavigation={() => {}}
        />,
        TESTBENUTZER,
      )}
    </MemoryRouter>,
  );
}

describe("Kopfleiste", () => {
  it("nennt auf der Startseite die Installation statt eines Weges", async () => {
    // Dort gibt es keinen Weg zu zeigen. Eine Brotkrume mit einem einzigen
    // Glied waere ein Pfeil, der auf sich selbst zeigt.
    zeige("/");

    expect(await screen.findByText("HomePI")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Pfad" })).not.toBeInTheDocument();
  });

  it("nennt im Pfad nur das Artefakt - den Bereich zeigen die Bereiche", async () => {
    // Zweimal dasselbe Wort in einer Zeile ist eines zu viel: Welcher
    // Bereich gilt, steht an der Markierung daneben.
    zeige("/modul/staffelpilot/spiele");

    // Erst warten, bis das Verzeichnis da ist: Bis dahin steht die Kennung
    // aus der Adresse im Weg, und genau das prueft der naechste Test.
    await screen.findByText("StaffelPilot");

    expect(screen.getByRole("navigation", { name: "Pfad" })).toHaveTextContent(
      "StaffelPilot",
    );
    expect(
      within(screen.getByRole("navigation", { name: "Bereiche" })).getByRole("link", {
        name: "Spielprüfung",
      }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("nennt die Kennung, solange der Titel noch unterwegs ist", async () => {
    // Ein Platzhalter, der eine Zeile spaeter durch etwas anderes ersetzt
    // wird, ist schlechter als die Kennung, die ohnehin in der Adresse steht.
    vi.spyOn(client, "fetchModule").mockReturnValue(new Promise(() => {}));
    render(
      <MemoryRouter initialEntries={["/modul/staffelpilot/spiele"]}>
        {mitAnmeldung(
          <Kopfleiste navigierbar navOffen={false} beiNavigation={() => {}} />,
          TESTBENUTZER,
        )}
      </MemoryRouter>,
    );

    expect(await screen.findByRole("navigation", { name: "Pfad" })).toHaveTextContent(
      "staffelpilot",
    );
  });

  it("führt auch für die Einstellungen einen Weg", async () => {
    zeige("/einstellungen");

    expect(await screen.findByRole("navigation", { name: "Pfad" })).toHaveTextContent(
      "Einstellungen",
    );
  });

  it("macht aus dem Zeichen einen Verweis, wo es nichts zu navigieren gibt", async () => {
    zeige("/", false);

    expect(await screen.findByRole("link", { name: "Zur Übersicht" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(
      screen.queryByRole("button", { name: "Navigation öffnen" }),
    ).not.toBeInTheDocument();
  });

  it("sagt am Zeichen an, ob die Fläche offen ist", async () => {
    // aria-expanded ist die einzige Stelle, an der ein Screenreader den
    // Zustand erfaehrt - die vier Felder, die farbig werden, sieht er nicht.
    zeige("/");

    expect(
      await screen.findByRole("button", { name: "Navigation öffnen" }),
    ).toHaveAttribute("aria-expanded", "false");
  });
});
