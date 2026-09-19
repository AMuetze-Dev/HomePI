import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { BefundeListe } from "./BefundeTafel";
import * as api from "./api";

function zeile(rest: Partial<api.BefundZeile> = {}): api.BefundZeile {
  return {
    id: "b1",
    spiel_id: "m1",
    staffel_id: "s1",
    dfbnet_id: "M-1",
    datum: "2026-09-13",
    heim: "SG Gittersee",
    gast: "SV Fortschritt",
    regel: "rote_karte",
    schwere: "kritisch",
    titel: "Feldverweis auf Dauer",
    person: "Max Müller",
    mannschaft: "SG Gittersee",
    entscheidung: "offen",
    grund: "",
    weg: "sportgericht",
    vorgang_id: null,
    ...rest,
  };
}

async function aufklappen() {
  await userEvent.click(screen.getByRole("button", { name: /Jeder Befund einzeln/ }));
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Die Befundliste unter der Auswertung", () => {
  it("lädt erst, wenn jemand hinsieht", async () => {
    // Bei dreihundert Befunden ist das eine Abfrage, die auf der
    // Ergebnisseite niemand bestellt hat.
    const laden = vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
    render(<BefundeListe />);

    expect(laden).not.toHaveBeenCalled();

    await aufklappen();

    await waitFor(() => expect(laden).toHaveBeenCalled());
  });

  it("trägt das Spiel an jeder Zeile", async () => {
    // Ohne das Spiel an der Zeile ist ein Befund nicht zuzuordnen.
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([zeile()]);
    render(<BefundeListe />);
    await aufklappen();

    const liste = await screen.findByRole("list", { name: "Befunde" });
    expect(within(liste).getByText(/SG Gittersee – SV Fortschritt/)).toBeInTheDocument();
    expect(within(liste).getByText(/13\.09\.2026/)).toBeInTheDocument();
    expect(within(liste).getByText("Feldverweis auf Dauer")).toBeInTheDocument();
  });

  it("filtert auf offene", async () => {
    const laden = vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
    render(<BefundeListe />);
    await aufklappen();
    await waitFor(() => expect(laden).toHaveBeenCalled());

    await userEvent.click(screen.getByRole("button", { name: "Nur offene" }));

    await waitFor(() =>
      expect(laden).toHaveBeenLastCalledWith(
        { staffelId: undefined, nurOffen: true },
        expect.anything(),
      ),
    );
  });

  it("reicht die Staffel der Auswertung durch", async () => {
    const laden = vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
    render(<BefundeListe staffelId="s2" />);
    await aufklappen();

    await waitFor(() =>
      expect(laden).toHaveBeenCalledWith(
        { staffelId: "s2", nurOffen: false },
        expect.anything(),
      ),
    );
  });

  it("zeigt die Entscheidung mit ihrem Grund", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([
      zeile({ entscheidung: "verworfen", grund: "Spieler war spielberechtigt" }),
    ]);
    render(<BefundeListe />);
    await aufklappen();

    const liste = await screen.findByRole("list", { name: "Befunde" });
    expect(within(liste).getByText("verworfen")).toBeInTheDocument();
    expect(within(liste).getByText("Spieler war spielberechtigt")).toBeInTheDocument();
  });

  it("markiert eine Zeile, zu der ein Vorgang gehört", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([zeile({ vorgang_id: "v1" })]);
    render(<BefundeListe />);
    await aufklappen();

    const liste = await screen.findByRole("list", { name: "Befunde" });
    expect(within(liste).getByText("Vorgang")).toBeInTheDocument();
  });

  it("sagt beim leeren Filter etwas anderes als beim leeren Stand", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockResolvedValue([]);
    render(<BefundeListe />);
    await aufklappen();

    expect(await screen.findByText("Keine Befunde.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Nur offene" }));

    expect(
      await screen.findByText("Zu jedem Befund liegt eine Entscheidung vor."),
    ).toBeInTheDocument();
  });

  it("zeigt einen Ladefehler statt einer leeren Liste", async () => {
    vi.spyOn(api, "ladeAlleBefunde").mockRejectedValue(new ApiError("kein Zugriff", 403));
    render(<BefundeListe />);
    await aufklappen();

    expect(await screen.findByRole("alert")).toHaveTextContent("kein Zugriff");
  });
});
