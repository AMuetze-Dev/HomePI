import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import * as api from "./api";
import { IhkSeite } from "./IhkSeite";
import { KATALOG, kurz, pruefling, tag } from "./testdaten";

// Die PDF-Ansicht zeichnet mit pdf.js auf ein Canvas - das gibt es in jsdom
// nicht. Sie hat ihren eigenen Test; hier steht sie nur für sich selbst.
vi.mock("./PdfAnsicht", () => ({
  PdfAnsicht: ({ dokument }: { dokument: api.Dokument }) => (
    <p>PDF-Ansicht {dokument.dateiname}</p>
  ),
}));

function zeige(suche = "") {
  return render(
    <MemoryRouter initialEntries={[`/modul/ihk${suche}`]}>
      <IhkSeite />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.spyOn(api, "ladeKatalog").mockResolvedValue(KATALOG);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Prüfungstage ─────────────────────────────────────────────────────────────

describe("Prüfungstage", () => {
  it("zeigt zuerst einen Ladehinweis", () => {
    vi.spyOn(api, "ladeTage").mockReturnValue(new Promise(() => {}));
    zeige();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("sagt im Erstzustand, was zu tun ist", async () => {
    vi.spyOn(api, "ladeTage").mockResolvedValue([]);
    zeige();
    expect(await screen.findByText(/Noch kein Prüfungstag/)).toBeInTheDocument();
  });

  it("listet die Tage mit Zahl der Prüflinge", async () => {
    vi.spyOn(api, "ladeTage").mockResolvedValue([tag({ anzahl_prueflinge: 3 })]);
    zeige();
    const verweis = await screen.findByRole("link", { name: /18\.06\.2026/ });
    expect(verweis).toHaveAttribute("href", "/modul/ihk?tag=t1");
    expect(verweis).toHaveTextContent("3 Prüflinge");
  });

  it("legt einen Tag an und leert das Formular", async () => {
    vi.spyOn(api, "ladeTage").mockResolvedValue([]);
    vi.spyOn(api, "legeTagAn").mockResolvedValue(tag());
    zeige();

    await userEvent.type(await screen.findByLabelText("Ort"), "Köln");
    await userEvent.click(screen.getByRole("button", { name: "Tag anlegen" }));

    expect(api.legeTagAn).toHaveBeenCalledWith(
      expect.objectContaining({ ort: "Köln", korrektor: "" }),
    );
    expect(screen.getByLabelText("Ort")).toHaveValue("");
  });

  it("behält die Eingabe, wenn das Anlegen fehlschlägt", async () => {
    vi.spyOn(api, "ladeTage").mockResolvedValue([]);
    vi.spyOn(api, "legeTagAn").mockRejectedValue(
      new ApiError("Datum fehlt (datum)", 422),
    );
    zeige();

    await userEvent.type(await screen.findByLabelText("Ort"), "Köln");
    await userEvent.click(screen.getByRole("button", { name: "Tag anlegen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Datum fehlt (datum)");
    expect(screen.getByLabelText("Ort")).toHaveValue("Köln");
  });

  it("meldet, wenn die Liste nicht geladen werden kann", async () => {
    vi.spyOn(api, "ladeTage").mockRejectedValue(new ApiError("Gateway weg", 503));
    zeige();
    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway weg");
  });
});

// ── Ein Prüfungstag ──────────────────────────────────────────────────────────

describe("Prüfungstag", () => {
  it("listet die Prüflinge mit Punkten und Note", async () => {
    vi.spyOn(api, "ladeTag").mockResolvedValue({
      tag: tag({ anzahl_prueflinge: 1 }),
      prueflinge: [kurz({ doku_punkte: 81, doku_note: 2.4 })],
    });
    zeige("?tag=t1");

    expect(
      await screen.findByRole("heading", { name: /18\.06\.2026/ }),
    ).toBeInTheDocument();
    const verweis = screen.getByRole("link", { name: /Muster, Max/ });
    expect(verweis).toHaveAttribute("href", "/modul/ihk?pruefling=p1");
    expect(verweis).toHaveTextContent("81 P");
    expect(verweis).toHaveTextContent("2,4");
  });

  it("sagt, wie der erste Prüfling hinzukommt", async () => {
    vi.spyOn(api, "ladeTag").mockResolvedValue({ tag: tag(), prueflinge: [] });
    zeige("?tag=t1");
    expect(await screen.findByText(/Noch keine Prüflinge/)).toBeInTheDocument();
  });

  it("legt einen Prüfling an", async () => {
    vi.spyOn(api, "ladeTag").mockResolvedValue({ tag: tag(), prueflinge: [] });
    vi.spyOn(api, "legePrueflingAn").mockResolvedValue(pruefling());
    zeige("?tag=t1");

    await userEvent.type(await screen.findByLabelText("Name"), "Muster, Max");
    await userEvent.click(screen.getByRole("button", { name: "Prüfling anlegen" }));

    expect(api.legePrueflingAn).toHaveBeenCalledWith("t1", "Muster, Max");
    expect(screen.getByLabelText("Name")).toHaveValue("");
  });

  it("entfernt den Tag erst nach Rückfrage", async () => {
    vi.spyOn(api, "ladeTag").mockResolvedValue({ tag: tag(), prueflinge: [] });
    vi.spyOn(api, "ladeTage").mockResolvedValue([]);
    vi.spyOn(api, "entferneTag").mockResolvedValue(undefined);
    const frage = vi
      .spyOn(window, "confirm")
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    zeige("?tag=t1");

    const knopf = await screen.findByRole("button", { name: "Tag entfernen" });
    await userEvent.click(knopf);
    expect(api.entferneTag).not.toHaveBeenCalled();

    await userEvent.click(knopf);
    expect(frage).toHaveBeenCalledTimes(2);
    expect(api.entferneTag).toHaveBeenCalledWith("t1");
    expect(await screen.findByText(/Noch kein Prüfungstag/)).toBeInTheDocument();
  });

  it("meldet einen unbekannten Tag wörtlich", async () => {
    vi.spyOn(api, "ladeTag").mockRejectedValue(
      new ApiError("Es gibt keinen Prüfungstag", 404),
    );
    zeige("?tag=weg");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Es gibt keinen Prüfungstag",
    );
  });
});

// ── Ein Prüfling ─────────────────────────────────────────────────────────────

describe("Prüfling", () => {
  it("zeigt Name, Bogen-Verweis und das Raster der Dokumentation", async () => {
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    zeige("?pruefling=p1");

    expect(
      await screen.findByRole("heading", { name: "Muster, Max" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Korrekturbogen/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/ihk/prueflinge/p1/korrekturbogen"),
    );
    expect(screen.getByRole("heading", { name: /1\. Form/ })).toBeInTheDocument();
    expect(screen.getByText(/4 von 4 Kriterien offen/)).toBeInTheDocument();
  });

  it("setzt Punkte über das Backend und zeigt die neue Summe", async () => {
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    const neu = pruefling();
    neu.bewertung.doku = { "doku.1.1": 1 };
    neu.auswertung.doku.sektionen[0] = { ...neu.auswertung.doku.sektionen[0]!, wert: 1 };
    vi.spyOn(api, "aendereBewertung").mockResolvedValue(neu);
    zeige("?pruefling=p1");

    const gruppe = await screen.findByRole("group", { name: /Umfang/ });
    await userEvent.click(within(gruppe).getByRole("button", { name: "1" }));

    expect(api.aendereBewertung).toHaveBeenCalledWith("p1", { doku: { "doku.1.1": 1 } });
    expect(within(gruppe).getByRole("button", { name: "1" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("1 / 2 P")).toBeInTheDocument();
  });

  it("nimmt einen gesetzten Punkt beim zweiten Antippen zurück", async () => {
    const p = pruefling();
    p.bewertung.doku = { "doku.1.1": 1 };
    vi.spyOn(api, "ladePruefling").mockResolvedValue(p);
    vi.spyOn(api, "aendereBewertung").mockResolvedValue(pruefling());
    zeige("?pruefling=p1");

    const gruppe = await screen.findByRole("group", { name: /Umfang/ });
    await userEvent.click(within(gruppe).getByRole("button", { name: "1" }));

    expect(api.aendereBewertung).toHaveBeenCalledWith("p1", {
      doku: { "doku.1.1": null },
    });
  });

  it("bietet bei den Mängeln nur -2 bis 0 an", async () => {
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    zeige("?pruefling=p1");

    const gruppe = await screen.findByRole("group", { name: /Mängel/ });
    expect(
      within(gruppe)
        .getAllByRole("button")
        .map((k) => k.textContent),
    ).toEqual(["-2", "-1", "0"]);
  });

  it("zeigt eine Ablehnung des Backends wörtlich und behält den Stand", async () => {
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    vi.spyOn(api, "aendereBewertung").mockRejectedValue(
      new ApiError("„Umfang“ erlaubt 0 bis 1 Punkte, nicht 2", 422),
    );
    zeige("?pruefling=p1");

    const gruppe = await screen.findByRole("group", { name: /Umfang/ });
    await userEvent.click(within(gruppe).getByRole("button", { name: "1" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("erlaubt 0 bis 1 Punkte");
    expect(within(gruppe).getByRole("button", { name: "1" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("speichert eine Bemerkung, wenn das Feld verlassen wird", async () => {
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    vi.spyOn(api, "aendereBewertung").mockResolvedValue(pruefling());
    zeige("?pruefling=p1");

    await userEvent.type(await screen.findByLabelText("Bemerkung zu Form"), "sauber");
    await userEvent.tab();

    expect(api.aendereBewertung).toHaveBeenCalledWith("p1", {
      doku_bemerkungen: { "doku.1": "sauber" },
    });
  });

  it("ändert den Status mit einem Schalter", async () => {
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    vi.spyOn(api, "aenderePruefling").mockResolvedValue(pruefling());
    zeige("?pruefling=p1");

    await userEvent.click(await screen.findByRole("checkbox", { name: "Kontrolliert" }));

    expect(api.aenderePruefling).toHaveBeenCalledWith("p1", {
      status: { kontrolliert: true },
    });
  });

  it("bewertet die Präsentation auf der Skala und übernimmt den Vorschlag", async () => {
    const p = pruefling();
    p.auswertung.praesentation.sektionen[0] = {
      ...p.auswertung.praesentation.sektionen[0]!,
      vorschlag: 8,
    };
    vi.spyOn(api, "ladePruefling").mockResolvedValue(p);
    vi.spyOn(api, "aendereBewertung").mockResolvedValue(p);
    zeige("?pruefling=p1");

    await userEvent.click(await screen.findByRole("radio", { name: "Präsentation" }));
    const ziel = screen.getByRole("group", { name: /Projektziel/ });
    await userEvent.click(within(ziel).getByRole("button", { name: "¾" }));
    expect(api.aendereBewertung).toHaveBeenCalledWith("p1", {
      praesi_skala: { "praesi.1.1": 0.75 },
    });

    await userEvent.click(screen.getByRole("button", { name: "Vorschlag 8 übernehmen" }));
    expect(api.aendereBewertung).toHaveBeenCalledWith("p1", {
      praesi_punkte: { "praesi.1": 8 },
    });
  });

  it("startet die Zeitmessung", async () => {
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    vi.spyOn(api, "schalteZeit").mockResolvedValue(
      pruefling({
        zeiten: {
          praesi_start: "2026-06-18T09:00:00Z",
          praesi_ende: null,
          fg_start: null,
          fg_ende: null,
        },
      }),
    );
    zeige("?pruefling=p1");

    await userEvent.click(await screen.findByRole("radio", { name: "Präsentation" }));
    await userEvent.click(screen.getByRole("button", { name: "Präsentation starten" }));

    expect(api.schalteZeit).toHaveBeenCalledWith("p1", "praesentation_starten");
    expect(
      await screen.findByRole("button", { name: "Fachgespräch starten" }),
    ).toBeVisible();
  });

  it("trägt Teilnoten und eine Ergänzungsprüfung ein", async () => {
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    vi.spyOn(api, "setzeTeilnoten").mockResolvedValue(pruefling());
    zeige("?pruefling=p1");

    await userEvent.click(await screen.findByRole("radio", { name: "Gesamt" }));
    await userEvent.type(screen.getByLabelText(KATALOG.teil1_label), "80");
    await userEvent.selectOptions(
      screen.getByLabelText("Bereich der Ergänzungsprüfung"),
      "wiso",
    );
    await userEvent.type(screen.getByLabelText("Punkte mündlich"), "40");
    await userEvent.click(screen.getByRole("button", { name: "Teilnoten speichern" }));

    expect(api.setzeTeilnoten).toHaveBeenCalledWith("p1", {
      teil1: 80,
      planen_softwareprodukt: null,
      algorithmen: null,
      wiso: null,
      mep: { bereich: "wiso", punkte: 40 },
    });
  });

  it("lädt ein PDF hoch und zeigt es an", async () => {
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    const dokument: api.Dokument = {
      id: "d1",
      art: "projekt",
      dateiname: "Projekt.pdf",
      groesse: 10,
      angelegt: "2026-06-18T09:00:00Z",
    };
    vi.spyOn(api, "ladeDokumentHoch").mockResolvedValue(dokument);
    vi.spyOn(api, "ladePruefling")
      .mockResolvedValueOnce(pruefling())
      .mockResolvedValueOnce(pruefling({ dokumente: [dokument] }));
    zeige("?pruefling=p1");

    const datei = new File(["%PDF-1.4"], "Projekt.pdf", { type: "application/pdf" });
    await userEvent.upload(
      await screen.findByLabelText("Projektdokumentation hochladen"),
      datei,
    );

    expect(api.ladeDokumentHoch).toHaveBeenCalledWith("p1", "projekt", datei);
    expect(await screen.findByText("PDF-Ansicht Projekt.pdf")).toBeInTheDocument();
  });

  it("blendet das Dokument auf dem Telefon zuerst aus", async () => {
    vi.spyOn(window, "matchMedia").mockReturnValue({ matches: false } as MediaQueryList);
    vi.spyOn(api, "ladePruefling").mockResolvedValue(pruefling());
    zeige("?pruefling=p1");

    const knopf = await screen.findByRole("button", { name: "Dokument zeigen" });
    expect(screen.queryByText("Noch keine Dokumentation")).not.toBeInTheDocument();

    await userEvent.click(knopf);
    expect(screen.getByText("Noch keine Dokumentation")).toBeInTheDocument();
  });

  it("meldet einen unbekannten Prüfling wörtlich", async () => {
    vi.spyOn(api, "ladePruefling").mockRejectedValue(
      new ApiError("Es gibt keinen Prüfling", 404),
    );
    zeige("?pruefling=weg");
    expect(await screen.findByRole("alert")).toHaveTextContent("Es gibt keinen Prüfling");
  });
});
