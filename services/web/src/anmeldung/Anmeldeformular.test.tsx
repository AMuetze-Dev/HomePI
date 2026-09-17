import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/anmeldung";
import { ApiError } from "../api/client";
import { TESTBENUTZER, mitAnmeldung } from "../testhilfen";
import { Anmeldeformular } from "./Anmeldeformular";

afterEach(() => {
  vi.restoreAllMocks();
});

function zeige() {
  return render(mitAnmeldung(<Anmeldeformular />, null));
}

async function ausfuellen(name: string, passwort: string) {
  const benutzer = userEvent.setup();
  await benutzer.type(screen.getByLabelText("Benutzername"), name);
  await benutzer.type(screen.getByLabelText("Passwort"), passwort);
  return benutzer;
}

describe("Anmeldeformular", () => {
  it("meldet an und gibt Name und Passwort weiter", async () => {
    const anmelden = vi.spyOn(api, "anmelden").mockResolvedValue(TESTBENUTZER);
    zeige();

    const benutzer = await ausfuellen("pruefer", "korrekt-pferd-batterie");
    await benutzer.click(screen.getByRole("button", { name: "Anmelden" }));

    expect(anmelden).toHaveBeenCalledWith("pruefer", "korrekt-pferd-batterie");
  });

  it("schneidet Leerzeichen um den Namen ab", async () => {
    // Beim Tippen auf dem Handy haengt schnell eines dran.
    const anmelden = vi.spyOn(api, "anmelden").mockResolvedValue(TESTBENUTZER);
    zeige();

    const benutzer = await ausfuellen("  pruefer ", "korrekt-pferd-batterie");
    await benutzer.click(screen.getByRole("button", { name: "Anmelden" }));

    expect(anmelden).toHaveBeenCalledWith("pruefer", "korrekt-pferd-batterie");
  });

  it("zeigt die Meldung des Backends, statt sie zu verschlucken", async () => {
    vi.spyOn(api, "anmelden").mockRejectedValue(
      new ApiError("Benutzername oder Passwort stimmt nicht", 401),
    );
    zeige();

    const benutzer = await ausfuellen("pruefer", "falsch-aber-lang-genug");
    await benutzer.click(screen.getByRole("button", { name: "Anmelden" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/stimmt nicht/);
  });

  it("lässt den Namen stehen und leert nur das Passwort", async () => {
    // Bei einem Tippfehler im Passwort spart das das erneute Eintippen.
    vi.spyOn(api, "anmelden").mockRejectedValue(new ApiError("Stimmt nicht", 401));
    zeige();

    const benutzer = await ausfuellen("pruefer", "falsch-aber-lang-genug");
    await benutzer.click(screen.getByRole("button", { name: "Anmelden" }));
    await screen.findByRole("alert");

    expect(screen.getByLabelText("Benutzername")).toHaveValue("pruefer");
    expect(screen.getByLabelText("Passwort")).toHaveValue("");
  });

  it("lässt sich leer nicht absenden", async () => {
    zeige();

    expect(await screen.findByRole("button", { name: "Anmelden" })).toBeDisabled();
  });

  it("sagt, dass es keine Selbstregistrierung gibt", async () => {
    // Sonst sucht man den Knopf, den es absichtlich nicht gibt.
    zeige();

    expect(await screen.findByText(/keine Selbstregistrierung/)).toBeInTheDocument();
  });

  it("nimmt einen eigenen Titel für den Fall 'Anmeldung nötig'", async () => {
    render(mitAnmeldung(<Anmeldeformular titel="Anmeldung nötig" />, null));

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Anmeldung nötig",
    );
  });
});
