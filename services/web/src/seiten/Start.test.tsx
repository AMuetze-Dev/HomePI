import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import { mitAnmeldung } from "../testhilfen";
import { Start } from "./Start";

afterEach(() => {
  vi.restoreAllMocks();
});

const gesund: client.Health = {
  status: "ok",
  version: "1.0.0",
  checks: { database: true },
};

function modul(rest: Partial<client.ModulEintrag> = {}): client.ModulEintrag {
  return {
    id: "geraete",
    titel: "Geräte",
    pfad: "/geraete",
    beschreibung: "",
    icon: "kachel",
    version: "1.0.0",
    status: "bereit",
    zugang: "geschuetzt",
    ...rest,
  };
}

function zeige(
  module: client.ModulEintrag[],
  angemeldet = true,
  oeffentlicheUrl: string | null = null,
) {
  vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);
  vi.spyOn(client, "fetchModule").mockResolvedValue(module);
  vi.spyOn(client, "fetchOeffentlicheUrl").mockResolvedValue(oeffentlicheUrl);
  render(
    <MemoryRouter>{mitAnmeldung(<Start />, angemeldet ? undefined : null)}</MemoryRouter>,
  );
}

describe("Startseite", () => {
  it("baut eine Kachel je Artefakt aus dem Manifest", async () => {
    zeige([modul(), modul({ id: "messwerte", titel: "Messwerte" })]);

    const liste = await screen.findByRole("list", { name: "Artefakte" });

    expect(within(liste).getAllByRole("listitem")).toHaveLength(2);
    // Der Verweis umschliesst die ganze Kachel; sein zugaenglicher Name ist
    // deshalb der Kachelinhalt, nicht nur die Ueberschrift.
    expect(screen.getByRole("link", { name: /Geräte/ })).toHaveAttribute(
      "href",
      "/modul/geraete",
    );
  });

  it("zeigt im Erstzustand, was als Nächstes zu tun ist", async () => {
    // Eine leere Flaeche ohne Erklaerung laesst einen ratlos zurueck.
    zeige([]);

    expect(await screen.findByText(/homepi new/)).toBeInTheDocument();
  });

  it("bietet die Anmeldung an, statt 'kein Artefakt' zu behaupten", async () => {
    // Abgemeldet ist die Liste berechtigterweise leer. Der Hinweis, man solle
    // ein Artefakt anlegen, waere hier schlicht die falsche Auskunft.
    zeige([], false);

    expect(await screen.findByRole("heading", { name: "Anmelden" })).toBeInTheDocument();
    expect(screen.queryByText(/homepi new/)).not.toBeInTheDocument();
  });

  it("zeigt oeffentliche Artefakte auch ohne Anmeldung", async () => {
    zeige([modul({ id: "start", titel: "Start", zugang: "oeffentlich" })], false);

    expect(await screen.findByRole("list", { name: "Artefakte" })).toBeInTheDocument();
  });

  it("benennt ein defektes Artefakt, statt es wegzulassen", async () => {
    zeige([
      modul({
        id: "kaputt",
        titel: "Kaputt",
        status: "fehler",
        beschreibung: "ImportError",
      }),
    ]);

    const meldung = await screen.findByRole("alert");

    expect(meldung).toHaveTextContent(/ImportError/);
    // Eine kaputte Kachel darf nicht anklickbar sein
    expect(screen.queryByRole("link", { name: /Kaputt/ })).not.toBeInTheDocument();
    expect(screen.getByText("Fehler")).toBeInTheDocument();
  });

  it("zeigt zuerst einen Ladehinweis", () => {
    vi.spyOn(client, "fetchHealth").mockReturnValue(new Promise(() => {}));
    vi.spyOn(client, "fetchModule").mockReturnValue(new Promise(() => {}));

    render(<MemoryRouter>{mitAnmeldung(<Start />)}</MemoryRouter>);

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });

  it("meldet, wenn das Manifest nicht abrufbar ist", async () => {
    vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);
    vi.spyOn(client, "fetchModule").mockRejectedValue(new Error("Gateway weg"));

    render(<MemoryRouter>{mitAnmeldung(<Start />)}</MemoryRouter>);

    expect(await screen.findByText(/Gateway weg/)).toBeInTheDocument();
  });
});

describe("Der QR-Code zum Mitnehmen", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("ist zuerst verborgen und erscheint auf Knopfdruck", async () => {
    // Im Alltag braucht ihn niemand - er ist fuer die Vorstellung, wenn die
    // Startseite an der Wand haengt.
    zeige([modul()], true, "https://homelab.example.ts.net");
    const knopf = await screen.findByRole("button", { name: "QR-Code zeigen" });
    expect(screen.queryByRole("img", { name: /QR-Code/ })).not.toBeInTheDocument();

    await userEvent.click(knopf);

    expect(
      await screen.findByRole("img", {
        name: "QR-Code für https://homelab.example.ts.net",
      }),
    ).toBeInTheDocument();
    // Die Adresse steht auch als Text da - fuer jede Kamera, die keinen
    // QR-Code liest.
    expect(screen.getByText("homelab.example.ts.net")).toBeInTheDocument();
  });

  it("zeigt die oeffentliche Adresse, nicht die, unter der die Seite gerade laeuft", async () => {
    // Im Heimnetz laeuft die Seite unter einem Namen, den nur das Pi-hole
    // kennt. Ein Handy im Mobilfunk kaeme dort nie an.
    zeige([modul()], true, "https://homelab.example.ts.net");
    await userEvent.click(await screen.findByRole("button", { name: "QR-Code zeigen" }));

    expect(
      await screen.findByRole("img", { name: /homelab\.example\.ts\.net/ }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: new RegExp(location.host) })).toBeNull();
  });

  it("nimmt die eigene Adresse, wenn keine oeffentliche eingetragen ist", async () => {
    zeige([modul()], true, null);
    await userEvent.click(await screen.findByRole("button", { name: "QR-Code zeigen" }));

    expect(
      await screen.findByRole("img", { name: `QR-Code für ${location.origin}` }),
    ).toBeInTheDocument();
  });

  it("verschwindet wieder und merkt sich, ob er zu sehen war", async () => {
    // Der Rechner bei der Vorstellung laedt die Seite vielleicht neu - der
    // Code soll dann nicht wieder fehlen.
    zeige([modul()], true, "https://homelab.example.ts.net");
    await userEvent.click(await screen.findByRole("button", { name: "QR-Code zeigen" }));
    expect(localStorage.getItem("homepi.qr-code")).toBe("an");

    await userEvent.click(screen.getByRole("button", { name: "QR-Code ausblenden" }));

    expect(screen.queryByRole("img", { name: /QR-Code/ })).not.toBeInTheDocument();
    expect(localStorage.getItem("homepi.qr-code")).toBe("aus");
  });

  it("steht beim Neuladen wieder da, wenn er zuletzt zu sehen war", async () => {
    localStorage.setItem("homepi.qr-code", "an");
    zeige([modul()], true, "https://homelab.example.ts.net");

    expect(await screen.findByRole("img", { name: /QR-Code/ })).toBeInTheDocument();
  });
});
