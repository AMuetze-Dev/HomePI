import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Benutzer } from "../../api/anmeldung";
import { ApiError } from "../../api/client";
import { TESTBENUTZER, mitAnmeldung } from "../../testhilfen";
import * as api from "./api";
import * as audio from "./audio";
import { KinderzimmerSeite } from "./KinderzimmerSeite";
import {
  aufnahme,
  einstellungen,
  ereignis,
  figur,
  geraet,
  notiz,
  uebersicht,
} from "./testdaten";

const ELTERN: Benutzer = { ...TESTBENUTZER, rechte: { kinderzimmer: "verwalter" } };
const OMA: Benutzer = { ...TESTBENUTZER, rechte: { kinderzimmer: "leser" } };

function zeige(unterseite: string, benutzer: Benutzer = ELTERN) {
  return render(mitAnmeldung(<KinderzimmerSeite unterseite={unterseite} />, benutzer));
}

/** Alles, was die Seite beim Öffnen holt - leer, sofern nicht anders gesagt. */
function daten(
  rest: Partial<{
    figuren: api.Figur[];
    unbekannte: api.UnbekannteFigur[];
    aufnahmen: api.Aufnahme[];
    geraete: api.Geraet[];
    protokoll: api.Ereignis[];
    tagebuch: api.Tagebucheintrag[];
    einstellungen: api.Einstellungen;
  }> = {},
) {
  vi.spyOn(api, "ladeUebersicht").mockResolvedValue(uebersicht());
  vi.spyOn(api, "ladeEinstellungen").mockResolvedValue(
    rest.einstellungen ?? einstellungen(),
  );
  vi.spyOn(api, "ladeFiguren").mockResolvedValue(rest.figuren ?? []);
  vi.spyOn(api, "ladeUnbekannte").mockResolvedValue(rest.unbekannte ?? []);
  vi.spyOn(api, "ladeAufnahmen").mockResolvedValue(rest.aufnahmen ?? []);
  vi.spyOn(api, "ladeGeraete").mockResolvedValue(rest.geraete ?? []);
  vi.spyOn(api, "ladeProtokoll").mockResolvedValue(rest.protokoll ?? []);
  vi.spyOn(api, "ladeTagebuch").mockResolvedValue(rest.tagebuch ?? []);
}

beforeEach(() => {
  daten();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Laden", () => {
  it("zeigt zuerst einen Platzhalter", () => {
    vi.spyOn(api, "ladeUebersicht").mockReturnValue(new Promise(() => {}));

    zeige("spiele");

    expect(screen.getByRole("status", { name: /wird geladen/ })).toBeInTheDocument();
  });

  it("meldet wörtlich, wenn nichts geladen werden kann", async () => {
    vi.spyOn(api, "ladeFiguren").mockRejectedValue(new ApiError("Gateway weg", 503));

    zeige("spiele");

    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway weg");
  });
});

describe("Spiele", () => {
  it("erklärt jedes Spiel: wie, was es fördert und warum", async () => {
    zeige("spiele");

    const spiel = await screen.findByRole("article", { name: /Licht und Klang/ });
    expect(within(spiel).getByText("So geht’s")).toBeInTheDocument();
    expect(within(spiel).getByText("Das fördert es")).toBeInTheDocument();
    expect(within(spiel).getByText(/Rovee-Collier/)).toBeInTheDocument();
    expect(within(spiel).getByText("eingeschaltet")).toBeInTheDocument();
  });

  it("zeigt auch die geplanten Spiele, nach Phasen geordnet", async () => {
    zeige("spiele");

    expect(
      await screen.findByRole("heading", { name: /Phase 2 · Dinge verschwinden nicht/ }),
    ).toBeInTheDocument();
    const kuckuck = screen.getByRole("article", { name: /Kuckuck/ });
    expect(within(kuckuck).getByText("geplant")).toBeInTheDocument();
    expect(within(kuckuck).getByText(/Piaget/)).toBeInTheDocument();
    expect(screen.getByText(/2 von 3 am Gerät/)).toBeInTheDocument();
  });
});

describe("Figuren", () => {
  beforeEach(() => {
    vi.spyOn(api, "legeFigurAn").mockResolvedValue(figur());
    vi.spyOn(api, "aendereFigur").mockResolvedValue(figur());
    vi.spyOn(api, "entferneFigur").mockResolvedValue(undefined);
  });

  it("erklärt im Erstzustand, wie eine Figur hierherkommt", async () => {
    zeige("figuren");

    expect(await screen.findByText("Noch keine Figur")).toBeInTheDocument();
    expect(screen.getByText(/Legt eine Figur mit Tag aufs Gerät/)).toBeInTheDocument();
  });

  it("legt einen aufgelegten Tag ohne Abtippen als Figur an", async () => {
    daten({ unbekannte: [{ uid: "04FFEEDD", zuletzt: null }] });
    zeige("figuren");

    await userEvent.click(
      await screen.findByRole("button", { name: "Tag 04:FF:EE:DD als Figur anlegen" }),
    );
    expect(screen.getByLabelText("UID des Tags")).toHaveValue("04FFEEDD");
    await userEvent.type(screen.getByLabelText("Name"), "Kuh");
    await userEvent.selectOptions(screen.getByLabelText("Art"), "tier");
    await userEvent.selectOptions(screen.getByLabelText("Farbe"), "rot");
    await userEvent.click(screen.getByRole("button", { name: "Figur anlegen" }));

    expect(api.legeFigurAn).toHaveBeenCalledWith(
      expect.objectContaining({
        uid: "04FFEEDD",
        name: "Kuh",
        art: "tier",
        farbe: "rot",
      }),
    );
    await waitFor(() => expect(screen.queryByLabelText("Name")).not.toBeInTheDocument());
  });

  it("behält die Eingabe und zeigt den Grund, wenn das Anlegen scheitert", async () => {
    vi.spyOn(api, "legeFigurAn").mockRejectedValue(
      new ApiError("Diese UID gehört schon zu einer anderen Figur.", 409),
    );
    zeige("figuren");

    await userEvent.click(await screen.findByRole("button", { name: "Figur anlegen" }));
    await userEvent.type(screen.getByLabelText("Name"), "Schaf");
    await userEvent.type(screen.getByLabelText("UID des Tags"), "04A1B2C3");
    await userEvent.click(screen.getByRole("button", { name: "Figur anlegen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("gehört schon");
    expect(screen.getByLabelText("Name")).toHaveValue("Schaf");
  });

  it("ändert und entfernt über die Ausklappung", async () => {
    daten({
      figuren: [figur({ stimme: "a1" })],
      aufnahmen: [aufnahme()],
    });
    zeige("figuren");

    expect(await screen.findByText("Oma sagt Hallo")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Oma/ }));
    await userEvent.click(screen.getByRole("button", { name: "„Oma“ ändern" }));
    const name = screen.getByLabelText("Name");
    await userEvent.clear(name);
    await userEvent.type(name, "Oma Gerda");
    await userEvent.click(screen.getByRole("button", { name: "Änderung speichern" }));

    expect(api.aendereFigur).toHaveBeenCalledWith(
      "f1",
      expect.objectContaining({ name: "Oma Gerda", stimme: "a1" }),
    );
    expect(vi.mocked(api.aendereFigur).mock.calls[0]?.[1]).not.toHaveProperty("id");

    await userEvent.click(screen.getByRole("button", { name: "„Oma“ entfernen" }));
    expect(api.entferneFigur).toHaveBeenCalledWith("f1");
  });

  it("zeigt Lesern nur die Liste", async () => {
    daten({ figuren: [figur()], unbekannte: [{ uid: "04FFEEDD", zuletzt: null }] });
    zeige("figuren", OMA);

    expect(await screen.findByText("Oma")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Figur anlegen" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Aufgelegt, aber unbekannt")).not.toBeInTheDocument();
  });
});

describe("Aufnahmen", () => {
  beforeEach(() => {
    vi.spyOn(api, "ladeAufnahmeHoch").mockResolvedValue(aufnahme());
    vi.spyOn(api, "aendereAufnahme").mockResolvedValue(aufnahme());
    vi.spyOn(api, "entferneAufnahme").mockResolvedValue(undefined);
    URL.createObjectURL = vi.fn(() => "blob:vorschau");
    URL.revokeObjectURL = vi.fn();
  });

  it("erklärt im Erstzustand, womit man anfängt", async () => {
    zeige("aufnahmen");

    expect(await screen.findByText("Noch keine Aufnahme")).toBeInTheDocument();
  });

  it("nennt, wofür eine Aufnahme benutzt wird", async () => {
    daten({
      aufnahmen: [aufnahme(), aufnahme({ id: "a2", titel: "Glocke", art: "klang" })],
      figuren: [figur({ stimme: "a1" })],
      einstellungen: einstellungen({
        knoepfe: [{ nummer: 1, farbe: "#FFB000", klang: "a2" }],
      }),
    });
    zeige("aufnahmen");

    expect(await screen.findByText("Oma")).toBeInTheDocument();
    expect(screen.getByText("Knopf 1")).toBeInTheDocument();
    expect(screen.getAllByText("2,0 s")).toHaveLength(2);
  });

  it("bereitet eine Datei auf und lädt sie hoch", async () => {
    const wav = new Blob([new Uint8Array(44 + 22050 * 2)], { type: "audio/wav" });
    vi.spyOn(audio, "bereiteAuf").mockResolvedValue(wav);
    zeige("aufnahmen");

    await userEvent.click(await screen.findByRole("button", { name: "Neue Aufnahme" }));
    await userEvent.type(screen.getByLabelText("Titel"), "Muh");
    await userEvent.click(screen.getByRole("radio", { name: "Klang" }));
    const datei = new File(["roh"], "kuh.mp3", { type: "audio/mpeg" });
    await userEvent.upload(screen.getByLabelText("Oder eine Tondatei wählen"), datei);

    expect(await screen.findByText(/1,0 s, Stille abgeschnitten/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Aufnahme speichern" }));

    expect(api.ladeAufnahmeHoch).toHaveBeenCalledWith("Muh", "klang", wav);
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Aufnahme speichern" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("sagt, wenn in der Datei nichts zu hören ist", async () => {
    vi.spyOn(audio, "bereiteAuf").mockRejectedValue(
      new Error("In der Aufnahme ist nichts zu hören."),
    );
    zeige("aufnahmen");

    await userEvent.click(await screen.findByRole("button", { name: "Neue Aufnahme" }));
    await userEvent.upload(
      screen.getByLabelText("Oder eine Tondatei wählen"),
      new File(["x"], "leer.wav", { type: "audio/wav" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("nichts zu hören");
    expect(screen.getByRole("button", { name: "Aufnahme speichern" })).toBeDisabled();
  });

  it("benennt um und meldet wörtlich, warum Löschen nicht geht", async () => {
    daten({ aufnahmen: [aufnahme()] });
    vi.spyOn(api, "entferneAufnahme").mockRejectedValue(
      new ApiError("Die Aufnahme gehört noch zu Figur „Oma“.", 409),
    );
    zeige("aufnahmen");

    await userEvent.click(await screen.findByRole("button", { name: /Oma sagt Hallo/ }));
    expect(screen.getByLabelText("Oma sagt Hallo anhören")).toHaveAttribute(
      "src",
      expect.stringContaining("/kinderzimmer/aufnahmen/a1/datei"),
    );
    const titel = screen.getByLabelText("Titel");
    await userEvent.clear(titel);
    await userEvent.type(titel, "Oma");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));
    expect(api.aendereAufnahme).toHaveBeenCalledWith("a1", {
      titel: "Oma",
      art: "stimme",
    });

    await userEvent.click(
      screen.getByRole("button", { name: "„Oma sagt Hallo“ löschen" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "gehört noch zu Figur „Oma“",
    );
  });
});

describe("Einstellungen", () => {
  beforeEach(() => {
    vi.spyOn(api, "speichereEinstellungen").mockImplementation((w) => Promise.resolve(w));
  });

  it("speichert Grenzen, Spiele und Knöpfe", async () => {
    daten({ aufnahmen: [aufnahme({ id: "a2", titel: "Glocke", art: "klang" })] });
    zeige("einstellungen");

    fireEvent.change(await screen.findByLabelText("Höchste Lautstärke"), {
      target: { value: "25" },
    });
    expect(screen.getByText("25 %")).toBeInTheDocument();
    // Das Startspiel auszuschalten schiebt das nächste nach vorn.
    await userEvent.click(screen.getByRole("checkbox", { name: "Licht und Klang" }));
    await userEvent.click(screen.getByRole("button", { name: "Knopf hinzufügen" }));
    await userEvent.selectOptions(screen.getByLabelText("Klang für Knopf 2"), "a2");
    // Nach dem Speichern meldet das Backend einen neuen Stand - genau dann
    // darf die Rückmeldung nicht mit dem Formular verschwinden.
    vi.spyOn(api, "ladeUebersicht").mockResolvedValue(
      uebersicht({ stand: "neuerstand000000" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Einstellungen speichern" }),
    );

    expect(api.speichereEinstellungen).toHaveBeenCalledWith(
      expect.objectContaining({
        lautstaerke_max: 25,
        spiele_aktiv: ["stimmen"],
        startspiel: "stimmen",
        knoepfe: [
          { nummer: 1, farbe: "#FFB000", klang: null },
          expect.objectContaining({ nummer: 2, klang: "a2" }),
        ],
      }),
    );
    expect(
      await screen.findByText(/Gespeichert\. Das Gerät übernimmt es/),
    ).toBeInTheDocument();
  });

  it("entfernt einen Knopf, aber nie den letzten", async () => {
    daten({
      einstellungen: einstellungen({
        knoepfe: [
          { nummer: 1, farbe: "#FFB000", klang: null },
          { nummer: 2, farbe: "#2F80ED", klang: null },
        ],
      }),
    });
    zeige("einstellungen");

    await userEvent.click(
      await screen.findByRole("button", { name: "Knopf 2 entfernen" }),
    );

    expect(screen.queryByText("Knopf 2")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Knopf 1 entfernen" }),
    ).not.toBeInTheDocument();
  });

  it("zeigt Lesern die Werte ohne Speichern", async () => {
    zeige("einstellungen", OMA);

    expect(await screen.findByText(/Ansehen geht/)).toBeInTheDocument();
    expect(screen.getByLabelText("Höchste Lautstärke")).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Einstellungen speichern" }),
    ).not.toBeInTheDocument();
  });

  it("meldet den Grund, wenn das Backend ablehnt", async () => {
    vi.spyOn(api, "speichereEinstellungen").mockRejectedValue(
      new ApiError("„Kuckuck“ ist geplant, das Gerät kann es noch nicht.", 422),
    );
    zeige("einstellungen");

    await userEvent.click(
      await screen.findByRole("button", { name: "Einstellungen speichern" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Kuckuck");
  });
});

describe("Geräte", () => {
  const MIT_TOKEN = { ...geraet(), token: "geheim-123" };

  beforeEach(() => {
    vi.spyOn(api, "legeGeraetAn").mockResolvedValue(MIT_TOKEN);
    vi.spyOn(api, "stelleTokenAus").mockResolvedValue(MIT_TOKEN);
    vi.spyOn(api, "entferneGeraet").mockResolvedValue(undefined);
  });

  it("zeigt das Token genau einmal nach dem Anlegen", async () => {
    zeige("geraete");

    await userEvent.click(await screen.findByRole("button", { name: "Gerät anlegen" }));
    await userEvent.type(screen.getByLabelText("Name des Geräts"), "Spielkiste");
    await userEvent.click(screen.getByRole("button", { name: "Gerät anlegen" }));

    expect(api.legeGeraetAn).toHaveBeenCalledWith("Spielkiste");
    expect(await screen.findByLabelText("Token")).toHaveValue("geheim-123");
    expect(screen.getByLabelText("Adresse für das Gerät")).toHaveDisplayValue(
      /\/kinderzimmer$/,
    );
    await userEvent.click(screen.getByRole("button", { name: "Eingetragen" }));
    expect(screen.queryByLabelText("Token")).not.toBeInTheDocument();
  });

  it("zeigt Stand und stellt ein neues Token aus", async () => {
    daten({
      geraete: [
        geraet({
          zuletzt_gesehen: "2026-11-20T08:00:00Z",
          firmware: "0.1.0",
          stand_aktuell: false,
        }),
      ],
    });
    zeige("geraete");

    expect(
      await screen.findByText("übernimmt beim nächsten Abgleich"),
    ).toBeInTheDocument();
    expect(screen.getByText("0.1.0")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Spielkiste/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Neues Token für „Spielkiste“" }),
    );

    expect(api.stelleTokenAus).toHaveBeenCalledWith("g1");
    expect(await screen.findByLabelText("Token")).toHaveValue("geheim-123");

    await userEvent.click(screen.getByRole("button", { name: "„Spielkiste“ entfernen" }));
    expect(api.entferneGeraet).toHaveBeenCalledWith("g1");
  });

  it("lässt nur Verwalter Geräte anlegen", async () => {
    daten({ geraete: [geraet({ stand_aktuell: true })] });
    zeige("geraete", OMA);

    expect(await screen.findByText("aktuell")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Gerät anlegen" }),
    ).not.toBeInTheDocument();
  });
});

describe("Tagebuch", () => {
  beforeEach(() => {
    vi.spyOn(api, "schreibeTagebuch").mockResolvedValue(notiz());
    vi.spyOn(api, "entferneTagebuch").mockResolvedValue(undefined);
  });

  it("erklärt beide leeren Hälften", async () => {
    zeige("tagebuch");

    expect(await screen.findByText("Noch nichts notiert")).toBeInTheDocument();
    expect(screen.getByText("Noch nichts gemeldet")).toBeInTheDocument();
  });

  it("schreibt eine Notiz", async () => {
    zeige("tagebuch");

    await userEvent.click(await screen.findByRole("button", { name: "Notiz schreiben" }));
    await userEvent.type(screen.getByLabelText("Was ist passiert?"), "Erstes Lachen");
    await userEvent.click(screen.getByRole("button", { name: "Notiz speichern" }));

    expect(api.schreibeTagebuch).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Erstes Lachen" }),
    );
  });

  it("zeigt Notizen und Protokoll und löscht erst nach Rückfrage", async () => {
    daten({
      tagebuch: [notiz()],
      protokoll: [
        ereignis(),
        ereignis({ id: 2, text: "„Oma“ aufgelegt", zeitpunkt: null }),
      ],
    });
    zeige("tagebuch");

    expect(
      await screen.findByText("Hat gelacht, als Omas Stimme kam."),
    ).toBeInTheDocument();
    expect(screen.getByText("„Oma“ aufgelegt")).toBeInTheDocument();
    expect(screen.getByText("Zeit unbekannt")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Notiz vom .* löschen/ }));
    expect(api.entferneTagebuch).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Notiz löschen" }));
    expect(api.entferneTagebuch).toHaveBeenCalledWith("t1");
  });
});
