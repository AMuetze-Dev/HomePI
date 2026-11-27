import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { PdfAnsicht } from "./PdfAnsicht";
import { pruefling } from "./testdaten";

// pdf.js selbst braucht ein echtes Canvas und einen Worker - beides fehlt in
// jsdom. Geprüft wird hier, was die Ansicht daraus macht.
const render_ = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }));
const getPage = vi.fn(() =>
  Promise.resolve({
    getViewport: ({ scale }: { scale: number }) => ({
      width: 600 * scale,
      height: 800 * scale,
    }),
    render: render_,
  }),
);
vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: vi.fn(() => ({
    promise: Promise.resolve({ numPages: 3, getPage }),
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
  HTMLCanvasElement.prototype.getContext = vi.fn(
    () => ({}) as CanvasRenderingContext2D,
  ) as unknown as typeof HTMLCanvasElement.prototype.getContext;
});

afterEach(() => {
  vi.restoreAllMocks();
  render_.mockClear();
  getPage.mockClear();
});

describe("PDF-Ansicht", () => {
  it("zeigt alle Seiten untereinander zum Durchscrollen", async () => {
    vi.spyOn(api, "ladeDokumentDaten").mockResolvedValue(new ArrayBuffer(8));
    render(<PdfAnsicht pruefling={pruefling()} dokument={DOKUMENT} />);

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByText("3 Seiten")).toBeInTheDocument();
    for (const nummer of [1, 2, 3]) {
      expect(
        await screen.findByRole("img", { name: `Projekt.pdf, Seite ${nummer} von 3` }),
      ).toBeInTheDocument();
    }
    // Kein Blättern mehr: gescrollt wird in der Fläche selbst.
    expect(
      screen.queryByRole("button", { name: "Nächste Seite" }),
    ).not.toBeInTheDocument();
    expect(getPage).toHaveBeenCalledWith(3);

    await userEvent.click(screen.getByRole("button", { name: "Vergrößern" }));
    await userEvent.click(screen.getByRole("button", { name: "Verkleinern" }));
    expect(render_).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Im neuen Tab öffnen" })).toHaveAttribute(
      "href",
      expect.stringContaining("/ihk/prueflinge/p1/dokumente/d1"),
    );
  });

  it("meldet, wenn das Dokument nicht geladen werden kann", async () => {
    vi.spyOn(api, "ladeDokumentDaten").mockRejectedValue(
      new ApiError("Das Dokument ließ sich nicht laden", 404),
    );
    render(<PdfAnsicht pruefling={pruefling()} dokument={DOKUMENT} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("ließ sich nicht laden");
  });
});
