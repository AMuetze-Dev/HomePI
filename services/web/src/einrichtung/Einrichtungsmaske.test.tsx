import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import * as api from "../api/einrichtung";
import { TESTBENUTZER, mitAnmeldung } from "../testhilfen";
import { Einrichtungsmaske } from "./Einrichtungsmaske";

afterEach(() => {
  vi.restoreAllMocks();
});

const TOKEN = "xYz-ein-langes-einrichtungstoken-aus-dem-log";
const PASSWORT = "korrekt-pferd-batterie";

function zeige(onFertig = vi.fn()) {
  render(mitAnmeldung(<Einrichtungsmaske onFertig={onFertig} />, null));
  return onFertig;
}

async function ausfuellen(
  felder: {
    token?: string;
    name?: string;
    passwort?: string;
    wiederholung?: string;
  } = {},
) {
  const benutzer = userEvent.setup();
  await benutzer.type(screen.getByLabelText("Einrichtungstoken"), felder.token ?? TOKEN);
  await benutzer.type(screen.getByLabelText("Benutzername"), felder.name ?? "aaron");
  await benutzer.type(screen.getByLabelText("Passwort"), felder.passwort ?? PASSWORT);
  await benutzer.type(
    screen.getByLabelText("Passwort wiederholen"),
    felder.wiederholung ?? felder.passwort ?? PASSWORT,
  );
  return benutzer;
}

describe("Einrichtungsmaske", () => {
  it("schickt Token, Name und Passwort", async () => {
    const einrichten = vi.spyOn(api, "einrichten").mockResolvedValue(TESTBENUTZER);
    zeige();

    const benutzer = await ausfuellen();
    await benutzer.click(screen.getByRole("button", { name: "Einrichten" }));

    expect(einrichten).toHaveBeenCalledWith({
      token: TOKEN,
      name: "aaron",
      passwort: PASSWORT,
    });
  });

  it("nimmt den Anzeigenamen mit, wenn einer dasteht", async () => {
    const einrichten = vi.spyOn(api, "einrichten").mockResolvedValue(TESTBENUTZER);
    zeige();

    const benutzer = await ausfuellen();
    await benutzer.type(screen.getByLabelText("Anzeigename"), "Aaron M.");
    await benutzer.click(screen.getByRole("button", { name: "Einrichten" }));

    expect(einrichten).toHaveBeenCalledWith(
      expect.objectContaining({ anzeigename: "Aaron M." }),
    );
  });

  it("meldet oben, dass es fertig ist", async () => {
    vi.spyOn(api, "einrichten").mockResolvedValue(TESTBENUTZER);
    const onFertig = zeige();

    const benutzer = await ausfuellen();
    await benutzer.click(screen.getByRole("button", { name: "Einrichten" }));

    expect(onFertig).toHaveBeenCalled();
  });

  it("verlangt das Einrichtungstoken", async () => {
    // Der Kern: 'es gibt noch keinen Verwalter' allein genügt nicht.
    zeige();

    await ausfuellen({ token: " " });

    expect(screen.getByRole("button", { name: "Einrichten" })).toBeDisabled();
  });

  it("lässt sich mit ungleichen Passwörtern nicht absenden", async () => {
    zeige();

    await ausfuellen({ passwort: PASSWORT, wiederholung: "etwas-anderes-langes" });

    expect(screen.getByRole("button", { name: "Einrichten" })).toBeDisabled();
    expect(screen.getByText(/nicht überein/)).toBeInTheDocument();
  });

  it("zeigt die Meldung des Backends, statt sie zu verschlucken", async () => {
    vi.spyOn(api, "einrichten").mockRejectedValue(
      new ApiError("Das Einrichtungstoken stimmt nicht", 401),
    );
    zeige();

    const benutzer = await ausfuellen();
    await benutzer.click(screen.getByRole("button", { name: "Einrichten" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/stimmt nicht/);
  });

  it("lässt Token und Name stehen und leert nur die Passwörter", async () => {
    // Ein 43-Zeichen-Token nach einem Tippfehler erneut abzutippen wäre eine
    // Zumutung.
    vi.spyOn(api, "einrichten").mockRejectedValue(new ApiError("Stimmt nicht", 401));
    zeige();

    const benutzer = await ausfuellen();
    await benutzer.click(screen.getByRole("button", { name: "Einrichten" }));
    await screen.findByRole("alert");

    expect(screen.getByLabelText("Einrichtungstoken")).toHaveValue(TOKEN);
    expect(screen.getByLabelText("Benutzername")).toHaveValue("aaron");
    expect(screen.getByLabelText("Passwort")).toHaveValue("");
  });

  it("sagt, wo das Token steht", async () => {
    zeige();

    expect(await screen.findByText(/docker compose logs gateway/)).toBeInTheDocument();
  });

  it("nennt den Weg über die Kommandozeile", async () => {
    zeige();

    expect(await screen.findByText(/homepi benutzer anlegen/)).toBeInTheDocument();
  });
});
