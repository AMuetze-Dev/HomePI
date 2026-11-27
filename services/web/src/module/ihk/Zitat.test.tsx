import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "./api";
import { Bemerkung } from "./Bewertung";
import { PdfAnsicht } from "./PdfAnsicht";
import { pruefling } from "./testdaten";
import { ZitatBereich } from "./Zitat";

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: vi.fn(() => ({
    promise: Promise.resolve({
      numPages: 2,
      getPage: () =>
        Promise.resolve({
          getViewport: ({ scale }: { scale: number }) => ({
            width: 600 * scale,
            height: 800 * scale,
          }),
          render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
        }),
    }),
    destroy: vi.fn(() => Promise.resolve()),
  })),
}));
vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({ default: "worker.js" }));

const DOKUMENT: api.Dokument = {
  id: "d1",
  art: "projekt",
  dateiname: "Projekt.pdf",
  groesse: 10,
  angelegt: "2026-06-18T09:00:00Z",
};

beforeEach(() => {
  vi.spyOn(api, "ladeDokumentDaten").mockResolvedValue(new ArrayBuffer(8));
  HTMLCanvasElement.prototype.getContext = vi.fn(
    () => ({}) as CanvasRenderingContext2D,
  ) as unknown as typeof HTMLCanvasElement.prototype.getContext;
});

afterEach(() => {
  vi.restoreAllMocks();
});

function zeige(onSpeichern = vi.fn()) {
  render(
    <ZitatBereich>
      <Bemerkung wert="" beschriftung="Bemerkung zu Form" onSpeichern={onSpeichern} />
      <PdfAnsicht pruefling={pruefling()} dokument={DOKUMENT} />
    </ZitatBereich>,
  );
  return onSpeichern;
}

describe("Seitenbezug", () => {
  it("ist erst möglich, wenn ein Bemerkungsfeld benutzt wurde", async () => {
    zeige();
    expect(
      await screen.findByRole("button", { name: "Seite 2 in die Bemerkung übernehmen" }),
    ).toBeDisabled();
  });

  it("schreibt die Seite in die zuletzt benutzte Bemerkung", async () => {
    const onSpeichern = zeige();
    const feld = screen.getByLabelText("Bemerkung zu Form");
    await userEvent.type(feld, "Gliederung unklar");

    await userEvent.click(
      await screen.findByRole("button", { name: "Seite 2 in die Bemerkung übernehmen" }),
    );

    expect(feld).toHaveValue("Gliederung unklar\nS. 2: ");
    expect(feld).toHaveFocus();
    await userEvent.tab();
    expect(onSpeichern).toHaveBeenLastCalledWith("Gliederung unklar\nS. 2: ");
  });
});
