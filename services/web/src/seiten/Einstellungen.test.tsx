import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as anmeldungApi from "../api/anmeldung";
import type { Benutzer } from "../api/anmeldung";
import * as client from "../api/client";
import { GRUENDE } from "../huelle/darstellung";
import { mitAnmeldung, TESTBENUTZER } from "../testhilfen";
import { Einstellungen } from "./Einstellungen";

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.removeAttribute("data-thema");
  document.documentElement.removeAttribute("data-bewegung");
  document.documentElement.removeAttribute("data-grund");
});

beforeEach(() => {
  localStorage.clear();
});

const gesund: client.Health = {
  status: "ok",
  version: "1.0.0",
  checks: { database: true },
};

function zeige(benutzer: Benutzer = TESTBENUTZER) {
  vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);
  vi.spyOn(client, "fetchModule").mockResolvedValue([
    {
      id: "geraete",
      titel: "Geräte",
      pfad: "/geraete",
      beschreibung: "",
      icon: "",
      version: "1.0.0",
      status: "bereit",
      zugang: "geschuetzt",
    },
  ]);

  render(<MemoryRouter>{mitAnmeldung(<Einstellungen />, benutzer)}</MemoryRouter>);
}

describe("Einstellungen", () => {
  it("sagt im ersten Satz, für wen sie gelten", async () => {
    // Die Frage, die jeder zuerst hat: aendere ich das fuer mich oder fuer
    // alle, die diesen Pi benutzen?
    zeige();

    expect(await screen.findByText(/nicht für die Installation/)).toBeInTheDocument();
  });

  it("schaltet das Farbschema und merkt es sich", async () => {
    zeige();

    await userEvent.click(await screen.findByRole("radio", { name: "Hell" }));

    expect(document.documentElement).toHaveAttribute("data-thema", "hell");
    expect(localStorage.getItem("homepi.thema")).toBe("hell");
  });

  it("lässt das Thema dem Gerät, solange niemand wählt", async () => {
    zeige();

    const gruppe = await screen.findByRole("radiogroup", { name: "Farbschema" });

    expect(within(gruppe).getByRole("radio", { name: "System" })).toBeChecked();
    expect(document.documentElement).not.toHaveAttribute("data-thema");
  });

  it("lässt die Grundfarbe wählen und merkt sie sich", async () => {
    zeige();

    await userEvent.click(await screen.findByRole("radio", { name: "Glut" }));

    expect(document.documentElement).toHaveAttribute("data-grund", "glut");
    expect(localStorage.getItem("homepi.grund")).toBe("glut");
  });

  it("setzt für Nocturne gar kein Attribut", async () => {
    // Es ist der Entwurf, wie er gezeichnet wurde, und steht so in
    // tokens.css. Ein Attribut dafür wäre eine Ausnahme, die nichts ändert.
    zeige();
    await userEvent.click(await screen.findByRole("radio", { name: "Glut" }));

    await userEvent.click(screen.getByRole("radio", { name: "Nocturne" }));

    expect(document.documentElement).not.toHaveAttribute("data-grund");
    expect(localStorage.getItem("homepi.grund")).toBeNull();
  });

  it("zeigt zu jeder Grundfarbe ihren Farbton", async () => {
    // "Glut" und "Moos" sagen einem nichts, bevor man sie gesehen hat. Der
    // Tupfen trägt dasselbe Attribut wie die Oberfläche und holt seine Farbe
    // damit aus derselben Quelle.
    zeige();
    const gruppe = await screen.findByRole("radiogroup", { name: "Grundfarbe" });

    expect(gruppe.querySelectorAll("[data-grund]")).toHaveLength(GRUENDE.length);
  });

  it("bestellt Bewegung ab", async () => {
    // Auf einem Pi im Wohnzimmer bedient oft jemand das Geraet, dessen
    // Systemeinstellung jemand anderem gehoert.
    zeige();

    await userEvent.click(
      await screen.findByRole("checkbox", { name: "Bewegung reduzieren" }),
    );

    expect(document.documentElement).toHaveAttribute("data-bewegung", "reduziert");
  });

  it("zeigt Anzeigename und Kennung, ohne sie zum Ändern anzubieten", async () => {
    // Beide aendert die Nutzerverwaltung. Ein Feld, das sich tippen laesst
    // und beim Verlassen nichts tut, ist ein Versprechen, das niemand haelt.
    zeige();

    expect(await screen.findByLabelText("Anzeigename")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Benutzername")).toHaveValue("pruefer");
  });

  it("nennt jedes Recht mit dem Namen des Artefakts", async () => {
    zeige();

    // "geraete" steht im Verzeichnis und wird zu "Geräte"; "messwerte"
    // nicht - dort bleibt die Kennung stehen, statt die Zeile zu
    // verschweigen. Gewartet wird auf den Titel: Bis das Verzeichnis da
    // ist, steht auch bei "geraete" noch die Kennung.
    expect(await screen.findByText("Geräte · Verwalter")).toBeInTheDocument();

    const rechte = screen.getByRole("list", { name: "Rechte" });
    expect(rechte).toHaveTextContent("messwerte · Verwalter");
  });

  it("sagt es, wenn für dieses Konto noch nichts freigeschaltet ist", async () => {
    zeige({ ...TESTBENUTZER, rechte: {} });

    expect(
      await screen.findByText(/noch kein Artefakt freigeschaltet/),
    ).toBeInTheDocument();
  });

  it("klappt den Passwortwechsel erst auf Verlangen auf", async () => {
    // Einmal im Jahr. Dauerhaft aufgeklappt waere es das Laengste auf einer
    // Seite, auf der es am wenigsten zu tun gibt.
    zeige();

    expect(screen.queryByLabelText("Neues Passwort")).not.toBeInTheDocument();

    await userEvent.click(await screen.findByRole("button", { name: "Ändern" }));

    expect(screen.getByLabelText("Neues Passwort")).toBeInTheDocument();
  });

  it("setzt das Passwort und bestätigt es", async () => {
    const aendern = vi
      .spyOn(anmeldungApi, "aenderePasswort")
      .mockResolvedValue(undefined);
    zeige();

    await userEvent.click(await screen.findByRole("button", { name: "Ändern" }));
    await userEvent.type(screen.getByLabelText("Bisheriges Passwort"), "altesgeheim");
    await userEvent.type(screen.getByLabelText("Neues Passwort"), "neuesgeheimnis");
    await userEvent.type(
      screen.getByLabelText("Neues Passwort wiederholen"),
      "neuesgeheimnis",
    );
    await userEvent.click(screen.getByRole("button", { name: "Passwort setzen" }));

    expect(aendern).toHaveBeenCalledWith("altesgeheim", "neuesgeheimnis");
    expect(await screen.findByText("Das Passwort ist gesetzt.")).toBeInTheDocument();
  });

  it("lässt nicht setzen, solange die Wiederholung abweicht", async () => {
    zeige();

    await userEvent.click(await screen.findByRole("button", { name: "Ändern" }));
    await userEvent.type(screen.getByLabelText("Bisheriges Passwort"), "altesgeheim");
    await userEvent.type(screen.getByLabelText("Neues Passwort"), "neuesgeheimnis");
    await userEvent.type(screen.getByLabelText("Neues Passwort wiederholen"), "vertippt");

    expect(screen.getByRole("button", { name: "Passwort setzen" })).toBeDisabled();
    expect(screen.getByText(/stimmen nicht überein/)).toBeInTheDocument();
  });

  it("gibt die Meldung des Backends wörtlich weiter", async () => {
    vi.spyOn(anmeldungApi, "aenderePasswort").mockRejectedValue(
      new Error("Passwort zu kurz: mindestens 12 Zeichen"),
    );
    zeige();

    await userEvent.click(await screen.findByRole("button", { name: "Ändern" }));
    await userEvent.type(screen.getByLabelText("Bisheriges Passwort"), "altesgeheim");
    await userEvent.type(screen.getByLabelText("Neues Passwort"), "kurz");
    await userEvent.type(screen.getByLabelText("Neues Passwort wiederholen"), "kurz");
    await userEvent.click(screen.getByRole("button", { name: "Passwort setzen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Passwort zu kurz: mindestens 12 Zeichen",
    );
  });
});
