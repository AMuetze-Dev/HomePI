import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Themenwechsel } from "./Themenwechsel";

/** jsdom kennt matchMedia nicht - ohne Ersatz fällt der Hook auf "hell" zurück. */
function systemMeldet(dunkel: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: dunkel,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-thema");
  systemMeldet(false);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Themenwechsel", () => {
  it("folgt ohne eigene Wahl dem System", () => {
    render(<Themenwechsel />);

    // Kein Attribut heißt: light-dark() entscheidet allein.
    expect(document.documentElement.hasAttribute("data-thema")).toBe(false);
  });

  it("bietet bei hellem System den dunklen Modus an", () => {
    render(<Themenwechsel />);

    expect(screen.getByRole("button", { name: /dunklem/ })).toBeInTheDocument();
  });

  it("bietet bei dunklem System den hellen Modus an", () => {
    systemMeldet(true);

    render(<Themenwechsel />);

    expect(screen.getByRole("button", { name: /hellem/ })).toBeInTheDocument();
  });

  it("schreibt die Wahl an das Wurzelelement und merkt sie sich", async () => {
    render(<Themenwechsel />);

    await userEvent.click(screen.getByRole("button"));

    expect(document.documentElement.getAttribute("data-thema")).toBe("dunkel");
    expect(localStorage.getItem("homepi.thema")).toBe("dunkel");
  });

  it("schaltet wieder zurück", async () => {
    render(<Themenwechsel />);

    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(screen.getByRole("button"));

    expect(document.documentElement.getAttribute("data-thema")).toBe("hell");
  });

  it("übernimmt eine gespeicherte Wahl beim Start", () => {
    localStorage.setItem("homepi.thema", "dunkel");

    render(<Themenwechsel />);

    expect(document.documentElement.getAttribute("data-thema")).toBe("dunkel");
    expect(screen.getByRole("button", { name: /hellem/ })).toBeInTheDocument();
  });

  it("ignoriert Unsinn im Speicher", () => {
    // Ein fremder Eintrag unter demselben Schlüssel darf die Ansicht nicht
    // in einen undefinierten Zustand bringen.
    localStorage.setItem("homepi.thema", "türkis");

    render(<Themenwechsel />);

    expect(document.documentElement.hasAttribute("data-thema")).toBe(false);
  });

  it("funktioniert, wenn der Speicher gesperrt ist", async () => {
    // Privates Fenster oder blockierte Website-Daten: das Lesen und Schreiben
    // wirft. Die Oberfläche muss trotzdem umschalten.
    const kaputt = () => {
      throw new Error("Zugriff verweigert");
    };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(kaputt);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(kaputt);

    render(<Themenwechsel />);
    await userEvent.click(screen.getByRole("button"));

    expect(document.documentElement.getAttribute("data-thema")).toBe("dunkel");
  });
});
