import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as anmeldungApi from "../api/anmeldung";
import { mitAnmeldung } from "../testhilfen";
import { useKontoDarstellung } from "./kontoDarstellung";

function Probe() {
  useKontoDarstellung();
  return null;
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.removeAttribute("data-thema");
  document.documentElement.removeAttribute("data-grund");
  document.documentElement.removeAttribute("data-bewegung");
});

describe("Die Darstellung des Kontos", () => {
  it("gilt nach dem Anmelden auch auf diesem Gerät", async () => {
    // Am Rechner dunkel gestellt, am Handy angemeldet: dann ist es dort
    // auch dunkel, ohne dass man es ein zweites Mal sucht.
    vi.spyOn(anmeldungApi, "holeDarstellung").mockResolvedValue({
      thema: "dunkel",
      grund: "moos",
      bewegung_reduziert: true,
    });
    const speichern = vi.spyOn(anmeldungApi, "speichereDarstellung");

    render(mitAnmeldung(<Probe />));

    await waitFor(() =>
      expect(document.documentElement).toHaveAttribute("data-thema", "dunkel"),
    );
    expect(document.documentElement).toHaveAttribute("data-grund", "moos");
    expect(document.documentElement).toHaveAttribute("data-bewegung", "reduziert");
    // Im Browser vermerkt: Beim nächsten Laden steht die Seite gleich
    // richtig da, ohne erst hell aufzublitzen.
    expect(localStorage.getItem("homepi.thema")).toBe("dunkel");
    expect(speichern).not.toHaveBeenCalled();
  });

  it("bringt beim ersten Anmelden die Wahl aus dem Browser ins Konto", async () => {
    // Wer vor dem Konto schon den Dunkelmodus gewählt hat, soll ihn nicht
    // durch das Anmelden verlieren.
    localStorage.setItem("homepi.thema", "hell");
    vi.spyOn(anmeldungApi, "holeDarstellung").mockResolvedValue(null);
    const speichern = vi
      .spyOn(anmeldungApi, "speichereDarstellung")
      .mockResolvedValue({ thema: "hell", grund: "nocturne", bewegung_reduziert: false });

    render(mitAnmeldung(<Probe />));

    await waitFor(() =>
      expect(speichern).toHaveBeenCalledWith({
        thema: "hell",
        grund: "nocturne",
        bewegung_reduziert: false,
      }),
    );
  });

  it("fragt ohne Anmeldung nicht nach", async () => {
    const holen = vi.spyOn(anmeldungApi, "holeDarstellung");

    render(mitAnmeldung(<Probe />, null));

    // Einen Takt warten, bis die Anmeldung geklärt ist.
    await waitFor(() => expect(anmeldungApi.holeIch).toHaveBeenCalled());
    expect(holen).not.toHaveBeenCalled();
  });
});
