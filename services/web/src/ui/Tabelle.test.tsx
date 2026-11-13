import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Reihe, Tabelle, Zelle } from "./Tabelle";

function zeige(reihen: React.ReactNode) {
  return render(
    <Tabelle beschriftung="Spielberichte" raster="2fr 1fr" spalten={["Paarung", "Stand"]}>
      {reihen}
    </Tabelle>,
  );
}

describe("Tabelle", () => {
  it("ist eine benannte Liste, keine Tabelle", async () => {
    // Eine Reihe hier klappt oft auf, und ein Tabellenfeld, in dem ein ganzer
    // Bericht aufgeht, ist fuer einen Screenreader eine Zelle, die ploetzlich
    // eine Seite enthaelt.
    zeige(
      <Reihe>
        <Zelle>SG Gittersee – SV Fortschritt</Zelle>
        <Zelle rechts>fällig</Zelle>
      </Reihe>,
    );

    const liste = await screen.findByRole("list", { name: "Spielberichte" });

    expect(within(liste).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("sagt die Spaltennamen nicht an", () => {
    // Sie stehen als Orientierung fuer das Auge da. Vorgelesen waeren sie eine
    // Zeile aus Woertern ohne Tabelle dahinter - deshalb muss jede Zelle fuer
    // sich sprechen ("2 offen", nicht "2").
    zeige(
      <Reihe>
        <Zelle>SG Gittersee</Zelle>
        <Zelle>fällig</Zelle>
      </Reihe>,
    );

    expect(screen.queryByText("Paarung", { ignore: "[aria-hidden] *" })).toBeNull();
  });

  it("macht aus einer Reihe mit Ausklappung einen Knopf, der seinen Zustand nennt", async () => {
    const klick = vi.fn();
    zeige(
      <Reihe onKlick={klick} offen={false} ausklappung={<p>Der Bericht</p>}>
        <Zelle>SG Gittersee</Zelle>
        <Zelle>fällig</Zelle>
      </Reihe>,
    );

    const knopf = screen.getByRole("button", { name: /SG Gittersee/ });
    expect(knopf).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Der Bericht")).not.toBeInTheDocument();

    await userEvent.click(knopf);

    expect(klick).toHaveBeenCalled();
  });

  it("zeigt die Ausklappung, sobald sie offen ist", () => {
    zeige(
      <Reihe onKlick={() => {}} offen ausklappung={<p>Der Bericht</p>}>
        <Zelle>SG Gittersee</Zelle>
        <Zelle>fällig</Zelle>
      </Reihe>,
    );

    expect(screen.getByRole("button", { name: /SG Gittersee/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByText("Der Bericht")).toBeInTheDocument();
  });

  it("lässt eine Reihe ohne Klick eine Anzeige bleiben", () => {
    // Nicht jede Liste ist zum Aufklappen da. Ein Knopf, der nichts tut, ist
    // eine Station auf dem Weg durch die Tastatur, die nichts sagt.
    zeige(
      <Reihe>
        <Zelle>SG Gittersee</Zelle>
        <Zelle>fällig</Zelle>
      </Reihe>,
    );

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
