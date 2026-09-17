import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/anmeldung";
import { ApiError } from "../api/client";
import { TESTBENUTZER, mitAnmeldung } from "../testhilfen";
import { Passwortwechsel } from "./Passwortwechsel";
import { Passwortwechseltor } from "./Passwortwechseltor";

afterEach(() => {
  vi.restoreAllMocks();
});

const START = "abcd-efgh-ijkl-mnop";
const EIGENES = "mein-eigenes-langes-passwort";

const MIT_WECHSEL = { ...TESTBENUTZER, passwort_wechseln: true };

function zeige() {
  render(mitAnmeldung(<Passwortwechsel />, MIT_WECHSEL));
}

async function ausfuellen(neues = EIGENES, wiederholung = neues) {
  const benutzer = userEvent.setup();
  await benutzer.type(screen.getByLabelText("Startpasswort"), START);
  await benutzer.type(screen.getByLabelText("Neues Passwort"), neues);
  await benutzer.type(screen.getByLabelText("Neues Passwort wiederholen"), wiederholung);
  return benutzer;
}

describe("Passwortwechseltor", () => {
  it("lässt durch, wenn kein Wechsel aussteht", async () => {
    render(mitAnmeldung(<Passwortwechseltor>Die Anwendung</Passwortwechseltor>));

    expect(await screen.findByText("Die Anwendung")).toBeInTheDocument();
  });

  it("führt sonst zum Wechsel", async () => {
    render(
      mitAnmeldung(<Passwortwechseltor>Die Anwendung</Passwortwechseltor>, MIT_WECHSEL),
    );

    expect(
      await screen.findByRole("heading", { name: "Eigenes Passwort wählen" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Die Anwendung")).not.toBeInTheDocument();
  });
});

describe("Passwortwechsel", () => {
  it("schickt altes und neues Passwort", async () => {
    const aendern = vi.spyOn(api, "aenderePasswort").mockResolvedValue(undefined);
    vi.spyOn(api, "holeIch").mockResolvedValue({
      ...TESTBENUTZER,
      passwort_wechseln: false,
    });
    zeige();

    const benutzer = await ausfuellen();
    await benutzer.click(screen.getByRole("button", { name: "Passwort setzen" }));

    expect(aendern).toHaveBeenCalledWith(START, EIGENES);
  });

  it("fragt danach nach, ob der Wechsel erledigt ist", async () => {
    // Nicht raten: das Backend entscheidet, ob das Konto jetzt frei ist.
    vi.spyOn(api, "aenderePasswort").mockResolvedValue(undefined);
    zeige();
    await screen.findByRole("heading", { name: "Eigenes Passwort wählen" });

    // Nach dem Rendern ersetzen: mitAnmeldung setzt selbst eine Vorgabe fuer
    // holeIch, und der Aufruf beim Start soll hier nicht mitzaehlen.
    const ich = vi
      .spyOn(api, "holeIch")
      .mockResolvedValue({ ...TESTBENUTZER, passwort_wechseln: false });
    ich.mockClear();

    const benutzer = await ausfuellen();
    await benutzer.click(screen.getByRole("button", { name: "Passwort setzen" }));

    expect(ich).toHaveBeenCalled();
  });

  it("lässt sich mit ungleichen Passwörtern nicht absenden", async () => {
    zeige();

    await ausfuellen(EIGENES, "etwas-ganz-anderes");

    expect(screen.getByRole("button", { name: "Passwort setzen" })).toBeDisabled();
    expect(screen.getByText(/nicht überein/)).toBeInTheDocument();
  });

  it("lässt sich leer nicht absenden", async () => {
    zeige();

    expect(await screen.findByRole("button", { name: "Passwort setzen" })).toBeDisabled();
  });

  it("zeigt die Meldung des Backends, statt sie zu verschlucken", async () => {
    vi.spyOn(api, "aenderePasswort").mockRejectedValue(
      new ApiError("Das alte Passwort stimmt nicht", 401),
    );
    zeige();

    const benutzer = await ausfuellen();
    await benutzer.click(screen.getByRole("button", { name: "Passwort setzen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/stimmt nicht/);
  });

  it("nennt das angemeldete Konto und einen Weg hinaus", async () => {
    // Falls jemand mit dem falschen Startpasswort gelandet ist.
    zeige();

    expect(await screen.findByText("pruefer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abmelden" })).toBeInTheDocument();
  });

  it("meldet ab, wenn man will", async () => {
    const abmelden = vi.spyOn(api, "abmelden").mockResolvedValue(undefined);
    zeige();

    await userEvent.click(await screen.findByRole("button", { name: "Abmelden" }));

    expect(abmelden).toHaveBeenCalled();
  });
});
