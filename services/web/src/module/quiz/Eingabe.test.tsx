import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { codeAusEingabe, restSekunden, versatzVon } from "./abruf";
import { Eingabe } from "./Eingabe";
import { alsEingabe, entwurfAus, leererEntwurf, vollstaendig } from "./entwurf";
import { oeffentlicheFrage } from "./testdaten";

const SORTIEREN = oeffentlicheFrage({
  typ: "sortieren",
  elemente: [
    { kennung: "e2", text: "Zwei" },
    { kennung: "e1", text: "Eins" },
  ],
});

function zeige(
  frage = oeffentlicheFrage(),
  aendern = vi.fn(),
  bild: string | null = null,
) {
  return render(
    <Eingabe
      frage={frage}
      entwurf={leererEntwurf(frage)}
      aendern={aendern}
      bildAdresse={bild}
      gesperrt={false}
    />,
  );
}

describe("Uhr und Code", () => {
  it("rechnet die Frist mit der Uhr des Servers", () => {
    // Das Handy geht zehn Sekunden nach.
    const versatz = versatzVon(
      "2026-11-28T20:00:10Z",
      Date.parse("2026-11-28T20:00:00Z"),
    );
    expect(versatz).toBe(10_000);
    expect(
      restSekunden("2026-11-28T20:00:40Z", versatz, Date.parse("2026-11-28T20:00:00Z")),
    ).toBe(30);
  });

  it("geht nie unter null", () => {
    expect(
      restSekunden("2026-11-28T20:00:00Z", 0, Date.parse("2026-11-28T20:05:00Z")),
    ).toBe(0);
  });

  it("nimmt den Code so, wie er getippt wird", () => {
    expect(codeAusEingabe(" abc-23 4")).toBe("ABC234");
  });
});

describe("Antwort-Entwurf", () => {
  it("schickt je Typ nur das passende Feld", () => {
    const schaetzung = oeffentlicheFrage({ typ: "schaetzung", minimum: 0, maximum: 10 });
    expect(leererEntwurf(schaetzung).zahl).toBe("5");
    expect(alsEingabe(schaetzung, { ...leererEntwurf(schaetzung), zahl: "3,5" })).toEqual(
      {
        zahl: 3.5,
        eingeloggt: true,
      },
    );
    const auswahl = oeffentlicheFrage({ typ: "auswahl", optionen: ["a", "b"] });
    expect(alsEingabe(auswahl, { ...leererEntwurf(auswahl), auswahl: [1] })).toEqual({
      auswahl: [1],
      eingeloggt: true,
    });
    const hotspot = oeffentlicheFrage({ typ: "hotspot" });
    expect(alsEingabe(hotspot, leererEntwurf(hotspot))).toEqual({ eingeloggt: true });
    expect(alsEingabe(hotspot, { ...leererEntwurf(hotspot), x: 1, y: 2 })).toEqual({
      x: 1,
      y: 2,
      eingeloggt: true,
    });
    expect(alsEingabe(SORTIEREN, leererEntwurf(SORTIEREN))).toEqual({
      reihenfolge: ["e2", "e1"],
      eingeloggt: true,
    });
    expect(
      alsEingabe(oeffentlicheFrage(), {
        ...leererEntwurf(oeffentlicheFrage()),
        text: "x",
      }),
    ).toEqual({
      text: "x",
      eingeloggt: true,
    });
  });

  it("weiß, wann sich abschicken lässt", () => {
    const frei = oeffentlicheFrage();
    const leer = leererEntwurf(frei);
    expect(vollstaendig(frei, leer)).toBe(false);
    expect(vollstaendig(frei, { ...leer, text: "Paris" })).toBe(true);
    const zahl = oeffentlicheFrage({ typ: "zahl" });
    expect(vollstaendig(zahl, { ...leer, zahl: "abc" })).toBe(false);
    expect(vollstaendig(zahl, { ...leer, zahl: "16" })).toBe(true);
    expect(vollstaendig(oeffentlicheFrage({ typ: "auswahl" }), leer)).toBe(false);
    expect(vollstaendig(oeffentlicheFrage({ typ: "hotspot" }), leer)).toBe(false);
    expect(vollstaendig(SORTIEREN, leererEntwurf(SORTIEREN))).toBe(true);
  });

  it("stellt nach dem Neuladen die abgegebene Antwort wieder her", () => {
    expect(entwurfAus(oeffentlicheFrage({ typ: "zahl" }), { zahl: 16 }).zahl).toBe("16");
    expect(entwurfAus(SORTIEREN, { reihenfolge: ["e1", "e2"] }).reihenfolge).toEqual([
      "e1",
      "e2",
    ]);
    expect(
      entwurfAus(oeffentlicheFrage({ typ: "hotspot" }), { x: 3, y: 4 }),
    ).toMatchObject({
      x: 3,
      y: 4,
    });
    expect(entwurfAus(oeffentlicheFrage(), { text: "Paris" }).text).toBe("Paris");
    expect(
      entwurfAus(oeffentlicheFrage({ typ: "auswahl" }), { auswahl: [0] }).auswahl,
    ).toEqual([0]);
  });

  it("sortiert mit Knöpfen statt Ziehen", async () => {
    const aendern = vi.fn();
    zeige(SORTIEREN, aendern);
    expect(screen.getByRole("button", { name: "Zwei nach oben" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Zwei nach unten" }));
    expect(aendern).toHaveBeenCalledWith(
      expect.objectContaining({ reihenfolge: ["e1", "e2"] }),
    );
  });

  it("wählt bei Mehrfachauswahl an und wieder ab", async () => {
    const frage = oeffentlicheFrage({
      typ: "auswahl",
      optionen: ["Rot", "Blau"],
      mehrfach: true,
    });
    const aendern = vi.fn();
    const { rerender } = zeige(frage, aendern);
    expect(screen.getByText("Mehrere Antworten sind richtig")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Blau" }));
    expect(aendern).toHaveBeenLastCalledWith(expect.objectContaining({ auswahl: [1] }));
    rerender(
      <Eingabe
        frage={frage}
        entwurf={{ ...leererEntwurf(frage), auswahl: [1] }}
        aendern={aendern}
        bildAdresse={null}
        gesperrt={false}
      />,
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "Blau" }));
    expect(aendern).toHaveBeenLastCalledWith(expect.objectContaining({ auswahl: [] }));
  });

  it("wählt bei Einfachauswahl genau eine", async () => {
    const aendern = vi.fn();
    zeige(oeffentlicheFrage({ typ: "auswahl", optionen: ["Rot", "Blau"] }), aendern);
    expect(screen.getByText("Eine Antwort ist richtig")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Rot" }));
    expect(aendern).toHaveBeenLastCalledWith(expect.objectContaining({ auswahl: [0] }));
  });

  it("setzt beim Hotspot einen Punkt in Prozent", async () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      left: 0,
      top: 0,
      width: 200,
      height: 100,
    } as DOMRect);
    const aendern = vi.fn();
    zeige(oeffentlicheFrage({ typ: "hotspot", hat_bild: true }), aendern, "/bild");
    await userEvent.click(
      screen.getByRole("button", { name: "Auf die Stelle im Bild tippen" }),
    );
    expect(aendern).toHaveBeenCalledWith(
      expect.objectContaining({ x: expect.any(Number) as number }),
    );
  });

  it("wartet beim Hotspot auf das Bild", () => {
    zeige(oeffentlicheFrage({ typ: "hotspot" }));
    expect(screen.getByText(/Das Bild erscheint/)).toBeInTheDocument();
  });

  it("zeigt Zahl, Schätzung und Freitext", async () => {
    const aendern = vi.fn();
    const { unmount } = zeige(oeffentlicheFrage({ typ: "zahl", einheit: "m" }), aendern);
    await userEvent.type(screen.getByLabelText("Deine Zahl (m)"), "7");
    expect(aendern).toHaveBeenCalledWith(expect.objectContaining({ zahl: "7" }));
    unmount();

    const zweite = zeige(
      oeffentlicheFrage({
        typ: "schaetzung",
        minimum: 0,
        maximum: 10,
        schritt: 1,
        einheit: "kg",
      }),
    );
    expect(screen.getByRole("slider")).toHaveValue("5");
    zweite.unmount();

    zeige(oeffentlicheFrage(), aendern);
    await userEvent.type(screen.getByLabelText("Deine Antwort"), "P");
    expect(aendern).toHaveBeenCalledWith(expect.objectContaining({ text: "P" }));
  });
});
