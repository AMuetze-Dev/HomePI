import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Einrichtung } from "./Einrichtung";
import * as api from "./api";

/**
 * Der Weg durch die Einrichtung.
 *
 * Geprüft wird nicht, wie er aussieht, sondern was er zusagt: dass der Zugang
 * wirklich ausprobiert wird, dass „Wartet" auch Warten heißt, und dass ein
 * falsches Passwort als falsches Passwort dasteht. Genau daran hängt, ob
 * jemand nach dem ersten Fehlversuch weiterkommt oder an der falschen Stelle
 * sucht.
 */

function stand(rest: Partial<api.Einrichtungsstand> = {}): api.Einrichtungsstand {
  return {
    schritt: "zugang",
    zugang: false,
    staffeln: 0,
    erledigt: false,
    schluessel_vorhanden: true,
    ...rest,
  };
}

function auftrag(rest: Partial<api.Auftrag> = {}): api.Auftrag {
  return {
    id: "a1",
    art: "anmeldeprobe",
    staffel_id: null,
    referenz: "",
    zustand: "angefordert",
    schritt: "",
    fortschritt: 0,
    gepruefte: 0,
    befunde: 0,
    meldung: "",
    gestartet_am: null,
    beendet_am: null,
    angelegt: "2026-10-24T08:00:00Z",
    protokoll: [],
    ...rest,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Die Einrichtung", () => {
  it("erklärt zuerst, worum es geht", async () => {
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(stand());

    render(<Einrichtung onFertig={vi.fn()} />);

    expect(await screen.findByRole("heading")).toHaveTextContent(/prüft er mit/);
  });

  it("nennt die Schritte, damit man weiß, wie viel kommt", async () => {
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(stand());

    render(<Einrichtung onFertig={vi.fn()} />);

    const leiste = await screen.findByRole("list", { name: /Schritte der Einrichtung/ });
    expect(leiste).toBeInTheDocument();
  });

  it("steigt beim Zugang ein, wenn der schon steht", async () => {
    // Die Erklärung zweimal zu lesen ist niemandem zuzumuten.
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(
      stand({ schritt: "staffeln", zugang: true }),
    );

    render(<Einrichtung onFertig={vi.fn()} />);

    expect(
      await screen.findByRole("heading", { name: /Deine Staffeln/ }),
    ).toBeInTheDocument();
  });

  it("legt den Zugang ab und probiert ihn aus", async () => {
    // Ein Passwort, das erst beim ersten Prüflauf auffällt, ist das Gegenteil
    // einer Einrichtung.
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(stand());
    const speichern = vi.spyOn(api, "speichereZugang").mockResolvedValue(undefined);
    const anfordern = vi.spyOn(api, "fordereAuftragAn").mockResolvedValue(auftrag());

    render(<Einrichtung onFertig={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Los geht/ }));
    await userEvent.type(screen.getByLabelText(/Benutzername/), "staffelleiter");
    await userEvent.type(screen.getByLabelText(/Passwort/), "geheim-und-lang");
    await userEvent.click(screen.getByRole("button", { name: /Speichern und anmelden/ }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith("staffelleiter", "geheim-und-lang"),
    );
    expect(anfordern).toHaveBeenCalledWith("anmeldeprobe");
  });

  it("sagt, dass gewartet wird, solange nichts läuft", async () => {
    // Ein Balken, der trotzdem kriecht, wäre eine Lüge -- und zwar genau
    // dann, wenn jemand Hilfe braucht.
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(stand());
    vi.spyOn(api, "speichereZugang").mockResolvedValue(undefined);
    vi.spyOn(api, "fordereAuftragAn").mockResolvedValue(
      auftrag({ zustand: "angefordert" }),
    );

    render(<Einrichtung onFertig={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Los geht/ }));
    await userEvent.type(screen.getByLabelText(/Benutzername/), "wer");
    await userEvent.type(screen.getByLabelText(/Passwort/), "geheim");
    await userEvent.click(screen.getByRole("button", { name: /Speichern und anmelden/ }));

    expect(await screen.findByText(/Wartet auf den Prüfdienst/)).toBeInTheDocument();
  });

  it("nennt ein falsches Passwort beim Namen", async () => {
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(stand());
    vi.spyOn(api, "speichereZugang").mockResolvedValue(undefined);
    vi.spyOn(api, "fordereAuftragAn").mockResolvedValue(
      auftrag({ zustand: "gescheitert", meldung: "DFBnet hat die Anmeldung abgelehnt" }),
    );

    render(<Einrichtung onFertig={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Los geht/ }));
    await userEvent.type(screen.getByLabelText(/Benutzername/), "wer");
    await userEvent.type(screen.getByLabelText(/Passwort/), "falsch");
    await userEvent.click(screen.getByRole("button", { name: /Speichern und anmelden/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/abgelehnt/);
  });

  it("geht nach geglückter Probe zu den Staffeln", async () => {
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(stand());
    vi.spyOn(api, "speichereZugang").mockResolvedValue(undefined);
    vi.spyOn(api, "fordereAuftragAn").mockResolvedValue(
      auftrag({ zustand: "fertig", meldung: "Die Anmeldung bei DFBnet hat geklappt" }),
    );

    render(<Einrichtung onFertig={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Los geht/ }));
    await userEvent.type(screen.getByLabelText(/Benutzername/), "wer");
    await userEvent.type(screen.getByLabelText(/Passwort/), "geheim");
    await userEvent.click(screen.getByRole("button", { name: /Speichern und anmelden/ }));

    expect(
      await screen.findByRole("button", { name: /Staffeln holen/ }),
    ).toBeInTheDocument();
  });

  it("sperrt das Speichern, wenn der Schlüssel fehlt", async () => {
    // Abgelegt wuerde dann nichts. Das soll dastehen, bevor jemand ein
    // Passwort eintippt -- und nicht danach.
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(
      stand({ schluessel_vorhanden: false }),
    );

    render(<Einrichtung onFertig={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Los geht/ }));
    await userEvent.type(screen.getByLabelText(/Benutzername/), "wer");
    await userEvent.type(screen.getByLabelText(/Passwort/), "geheim");

    expect(screen.getByRole("button", { name: /Speichern und anmelden/ })).toBeDisabled();
  });

  it("lässt sich überspringen und hakt sich dabei ab", async () => {
    // Ein Weg, der sich nicht schliessen laesst, ist eine Sackgasse.
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(stand());
    const speichern = vi
      .spyOn(api, "speichereEinstellungen")
      .mockResolvedValue({} as never);
    const fertig = vi.fn();

    render(<Einrichtung onFertig={fertig} />);
    await userEvent.click(await screen.findByRole("button", { name: /Später/ }));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith({ einrichtung_erledigt: true }),
    );
    expect(fertig).toHaveBeenCalled();
  });

  it("zählt am Ende, was wirklich dasteht", async () => {
    vi.spyOn(api, "ladeEinrichtung").mockResolvedValue(
      stand({ schritt: "staffeln", zugang: true }),
    );
    vi.spyOn(api, "fordereAuftragAn").mockResolvedValue(
      auftrag({
        art: "staffeln",
        zustand: "fertig",
        meldung: "3 angelegt, 0 aufgefrischt",
      }),
    );

    render(<Einrichtung onFertig={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Staffeln holen/ }));

    expect(await screen.findByRole("heading")).toHaveTextContent(/Fertig/);
  });
});
