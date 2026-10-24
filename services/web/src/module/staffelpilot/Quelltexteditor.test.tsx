import { render, screen } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Quelltexteditor } from "./Quelltexteditor";

/**
 * Der Editor für Regeldateien.
 *
 * Hier steht Python, und Einrückung ist dort keine Geschmacksfrage — deshalb
 * prüft diese Datei vor allem die beiden Tasten, an denen ein Textfeld sonst
 * versagt: Tabulator und Eingabetaste.
 */

/** Ein Editor, der seinen Wert behält — wie in der Tafel. */
function Gesteuert({ start = "" }: { start?: string }) {
  const [wert, setWert] = useState(start);
  return <Quelltexteditor wert={wert} onAendern={setWert} />;
}

describe("Der Editor", () => {
  it("zeigt den Quelltext", () => {
    render(<Quelltexteditor wert="melde(1)" onAendern={vi.fn()} />);

    expect(screen.getByLabelText("Quelltext")).toHaveValue("melde(1)");
  });

  it("nummeriert die Zeilen", () => {
    // Kein Schmuck: die Fehlermeldung des Laders nennt eine Zeile, und ohne
    // Nummern zählt man sie ab.
    render(<Quelltexteditor wert={"a\nb\nc"} onAendern={vi.fn()} zeilenMindestens={3} />);

    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("gibt dem Text immer mindestens die verlangten Zeilen", () => {
    render(<Quelltexteditor wert="a" onAendern={vi.fn()} zeilenMindestens={5} />);

    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("rückt mit dem Tabulator ein, statt den Fokus weiterzugeben", async () => {
    // Die eine Taste, die man in einem Feld mit Python am häufigsten braucht
    // — und die ein Textfeld von sich aus wegwirft.
    render(<Gesteuert />);
    const feld = screen.getByLabelText("Quelltext");

    await userEvent.click(feld);
    await userEvent.keyboard("{Tab}melde(1)");

    expect(feld).toHaveValue("    melde(1)");
  });

  it("nimmt mit Umschalt+Tabulator eine Stufe zurück", async () => {
    render(<Gesteuert start="    melde(1)" />);
    const feld = screen.getByLabelText("Quelltext");

    await userEvent.click(feld);
    await userEvent.keyboard("{Shift>}{Tab}{/Shift}");

    expect(feld).toHaveValue("melde(1)");
  });

  it("hält die Einrückung bei der Eingabetaste", async () => {
    render(<Gesteuert start="def f():" />);
    const feld = screen.getByLabelText("Quelltext");

    await userEvent.click(feld);
    await userEvent.keyboard("{Enter}melde(1)");

    // Nach einem Doppelpunkt eine Stufe tiefer: in Python ist das die
    // Bedeutung und keine Bequemlichkeit.
    expect(feld).toHaveValue("def f():\n    melde(1)");
  });

  it("bleibt ohne Doppelpunkt auf derselben Stufe", async () => {
    render(<Gesteuert start="    melde(1)" />);
    const feld = screen.getByLabelText("Quelltext");

    await userEvent.click(feld);
    await userEvent.keyboard("{Enter}melde(2)");

    expect(feld).toHaveValue("    melde(1)\n    melde(2)");
  });

  it("lässt nach Escape den Tabulator wieder hinaus", async () => {
    // Ein Feld, das den Tabulator einbehält, hält auch die Tastatur fest --
    // wer nicht mit der Maus arbeitet, käme nicht mehr heraus. Escape gibt
    // den nächsten Tabulator frei; das ist der übliche Ausgang.
    render(
      <>
        <Gesteuert />
        <button type="button">Speichern</button>
      </>,
    );
    const feld = screen.getByLabelText("Quelltext");

    await userEvent.click(feld);
    await userEvent.keyboard("{Escape}{Tab}");

    expect(screen.getByRole("button", { name: "Speichern" })).toHaveFocus();
    expect(feld).toHaveValue("");
  });

  it("nimmt den Ausgang bei der nächsten Taste zurück", async () => {
    // Escape gilt für den nächsten Tabulator, nicht für den übernächsten.
    render(<Gesteuert />);
    const feld = screen.getByLabelText("Quelltext");

    await userEvent.click(feld);
    await userEvent.keyboard("{Escape}a{Tab}");

    expect(feld).toHaveValue("a    ");
  });

  it("nennt den Ausgang unter dem Feld", () => {
    // Dass der Tabulator einrückt, merkt man sofort; dass Escape ihn wieder
    // freigibt, rät niemand.
    render(<Quelltexteditor wert="" onAendern={vi.fn()} />);

    expect(screen.getByText(/Esc/)).toBeInTheDocument();
  });

  it("färbt den Quelltext unter dem Feld ein", () => {
    const { container } = render(<Quelltexteditor wert="def f():" onAendern={vi.fn()} />);

    // Das `pre` liegt hinter dem Textfeld und nimmt keine Eingaben an.
    const farbe = container.querySelector("pre");
    expect(farbe?.textContent).toContain("def f():");
    expect(farbe).toHaveAttribute("aria-hidden", "true");
  });
});
