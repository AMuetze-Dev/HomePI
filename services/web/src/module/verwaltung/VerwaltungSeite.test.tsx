import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { TESTBENUTZER, mitAnmeldung } from "../../testhilfen";
import * as api from "./api";
import type { Artefakt, Konto, KontoAngelegt } from "./api";
import { VerwaltungSeite } from "./VerwaltungSeite";

afterEach(() => {
  vi.restoreAllMocks();
});

function konto(rest: Partial<Konto> = {}): Konto {
  return {
    id: "22222222-2222-4222-8222-222222222222",
    name: "gast",
    anzeigename: "Gast",
    aktiv: true,
    rechte: {},
    angelegt: null,
    verwalter: false,
    passwort_wechseln: false,
    ...rest,
  };
}

function angelegt(rest: Partial<KontoAngelegt> = {}): KontoAngelegt {
  return { ...konto(), startpasswort: null, ...rest };
}

const ICH = konto({
  id: TESTBENUTZER.id,
  name: "pruefer",
  anzeigename: "Prüfer",
  rechte: { verwaltung: "verwalter" },
  verwalter: true,
});

const ARTEFAKTE: Artefakt[] = [
  { id: "geraete", titel: "Geräte", zugang: "geschuetzt" },
  { id: "verwaltung", titel: "Verwaltung", zugang: "geschuetzt" },
];

function zeige(konten: Konto[] = [ICH, konto()], artefakte = ARTEFAKTE) {
  vi.spyOn(api, "ladeKonten").mockResolvedValue(konten);
  vi.spyOn(api, "ladeArtefakte").mockResolvedValue(artefakte);
  render(mitAnmeldung(<VerwaltungSeite />));
}

describe("Verwaltungsseite", () => {
  it("zeigt zuerst einen Ladehinweis", () => {
    vi.spyOn(api, "ladeKonten").mockReturnValue(new Promise(() => {}));
    vi.spyOn(api, "ladeArtefakte").mockReturnValue(new Promise(() => {}));
    render(mitAnmeldung(<VerwaltungSeite />));

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });

  it("listet die Konten", async () => {
    zeige();

    const liste = await screen.findByRole("list", { name: "Konten" });

    expect(within(liste).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("pruefer")).toBeInTheDocument();
    expect(screen.getByText("gast")).toBeInTheDocument();
  });

  it("kennzeichnet ein noch nicht gewechseltes Startpasswort", async () => {
    // Bis es ersetzt ist, kommt das Konto an kein Artefakt - das soll man
    // sehen, ohne es ausprobieren zu muessen.
    zeige([ICH, konto({ passwort_wechseln: true })]);

    const liste = await screen.findByRole("list", { name: "Konten" });

    expect(within(liste).getByText("Startpasswort")).toBeInTheDocument();
    expect(within(liste).getByText(/an kein Artefakt/)).toBeInTheDocument();
  });

  it("weist Verwalter und Sperren aus", async () => {
    zeige([ICH, konto({ aktiv: false })]);

    // In der Liste, nicht in den Kennzahlen darueber - dort steht das Wort
    // ebenfalls, meint aber etwas anderes.
    const liste = await screen.findByRole("list", { name: "Konten" });

    expect(within(liste).getByText("Verwalter")).toBeInTheDocument();
    expect(within(liste).getByText("Gesperrt")).toBeInTheDocument();
  });

  it("markiert das eigene Konto", async () => {
    // Damit beim Sperren klar ist, warum der Knopf nicht geht.
    zeige();

    expect(await screen.findByText("Du")).toBeInTheDocument();
  });

  it("schaltet Sperren und Löschen am eigenen Konto ab", async () => {
    // Ein Fehlgriff am eigenen Konto ließe sich nicht zurücknehmen.
    zeige();

    expect(await screen.findByRole("button", { name: /pruefer sperren/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /pruefer löschen/ })).toBeDisabled();
  });

  it("sperrt ein fremdes Konto", async () => {
    const setzen = vi.spyOn(api, "setzeAktiv").mockResolvedValue(konto({ aktiv: false }));
    zeige();

    await userEvent.click(await screen.findByRole("button", { name: /gast sperren/ }));

    expect(setzen).toHaveBeenCalledWith(konto().id, false);
  });

  it("löscht ein fremdes Konto", async () => {
    const loeschen = vi.spyOn(api, "loescheKonto").mockResolvedValue(undefined);
    zeige();

    await userEvent.click(await screen.findByRole("button", { name: /gast löschen/ }));

    expect(loeschen).toHaveBeenCalledWith(konto().id);
  });

  it("zeigt die Meldung des Backends, statt sie zu verschlucken", async () => {
    vi.spyOn(api, "loescheKonto").mockRejectedValue(
      new ApiError("Löschen geht nicht am eigenen Konto.", 409),
    );
    zeige();

    await userEvent.click(await screen.findByRole("button", { name: /gast löschen/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/eigenen Konto/);
  });

  it("meldet, wenn die Konten nicht abrufbar sind", async () => {
    vi.spyOn(api, "ladeKonten").mockRejectedValue(new ApiError("Gateway weg", 503));
    vi.spyOn(api, "ladeArtefakte").mockResolvedValue(ARTEFAKTE);
    render(mitAnmeldung(<VerwaltungSeite />));

    expect(await screen.findByText(/Gateway weg/)).toBeInTheDocument();
  });

  it("zeigt im Erstzustand, was als Nächstes zu tun ist", async () => {
    zeige([]);

    expect(await screen.findByText(/erste an/)).toBeInTheDocument();
  });

  describe("Rechte", () => {
    async function oeffneRechte(name = "gast") {
      zeige();
      await userEvent.click(
        await screen.findByRole("button", { name: new RegExp(`Rechte von ${name}`) }),
      );
    }

    it("bietet je Artefakt eine Rolle an", async () => {
      await oeffneRechte();

      const feld = screen.getByLabelText("Geräte");
      expect(feld).toHaveValue("-");
      expect(within(feld as HTMLSelectElement).getAllByRole("option")).toHaveLength(4);
    });

    it("setzt ein Recht", async () => {
      const setzen = vi.spyOn(api, "setzeRecht").mockResolvedValue(konto());
      await oeffneRechte();

      await userEvent.selectOptions(screen.getByLabelText("Geräte"), "nutzer");

      expect(setzen).toHaveBeenCalledWith(konto().id, "geraete", "nutzer");
    });

    it("entzieht ein Recht", async () => {
      const entziehen = vi.spyOn(api, "entzieheRecht").mockResolvedValue(konto());
      vi.spyOn(api, "ladeKonten").mockResolvedValue([
        ICH,
        konto({ rechte: { geraete: "nutzer" } }),
      ]);
      vi.spyOn(api, "ladeArtefakte").mockResolvedValue(ARTEFAKTE);
      render(mitAnmeldung(<VerwaltungSeite />));
      await userEvent.click(
        await screen.findByRole("button", { name: /Rechte von gast/ }),
      );

      await userEvent.selectOptions(screen.getByLabelText("Geräte"), "-");

      expect(entziehen).toHaveBeenCalledWith(konto().id, "geraete");
    });

    it("sperrt die eigene Verwaltung im Auswahlfeld", async () => {
      // Das Backend lehnt es ohnehin ab - hier steht es gar nicht erst als
      // anklickbare Falle da.
      await oeffneRechte("pruefer");

      expect(screen.getByLabelText("Verwaltung")).toBeDisabled();
    });
  });

  describe("Anlegen", () => {
    it("legt ein Konto an", async () => {
      const anlegen = vi.spyOn(api, "legeKontoAn").mockResolvedValue(angelegt());
      zeige();
      await screen.findByRole("list", { name: "Konten" });

      await userEvent.type(screen.getByLabelText("Benutzername"), "neuling");
      await userEvent.type(screen.getByLabelText("Passwort"), "korrekt-pferd-batterie");
      await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

      expect(anlegen).toHaveBeenCalledWith({
        name: "neuling",
        passwort: "korrekt-pferd-batterie",
      });
    });

    it("lässt sich leer nicht absenden", async () => {
      zeige();

      expect(await screen.findByRole("button", { name: "Anlegen" })).toBeDisabled();
    });

    it("behält die Eingabe, wenn es schiefgeht", async () => {
      // Sonst tippt man nach einem vergebenen Namen alles neu.
      vi.spyOn(api, "legeKontoAn").mockRejectedValue(new ApiError("schon vergeben", 409));
      zeige();
      await screen.findByRole("list", { name: "Konten" });

      await userEvent.type(screen.getByLabelText("Benutzername"), "gast");
      await userEvent.type(screen.getByLabelText("Passwort"), "korrekt-pferd-batterie");
      await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

      await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
      expect(screen.getByLabelText("Benutzername")).toHaveValue("gast");
    });

    it("sagt, dass ein neues Konto keine Rechte hat", async () => {
      zeige();

      expect(await screen.findByText(/Rechte hat ein neues Konto/)).toBeInTheDocument();
    });

    it("braucht kein Passwort", async () => {
      // Der Name genuegt - den Rest erzeugt der Dienst.
      const anlegen = vi.spyOn(api, "legeKontoAn").mockResolvedValue(angelegt());
      zeige();
      await screen.findByRole("list", { name: "Konten" });

      await userEvent.type(screen.getByLabelText("Benutzername"), "neuling");
      await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

      expect(anlegen).toHaveBeenCalledWith({ name: "neuling" });
    });

    it("zeigt das Startpasswort genau einmal", async () => {
      vi.spyOn(api, "legeKontoAn").mockResolvedValue(
        angelegt({ name: "neuling", startpasswort: "abcd-efgh-ijkl-mnop" }),
      );
      zeige();
      await screen.findByRole("list", { name: "Konten" });

      await userEvent.type(screen.getByLabelText("Benutzername"), "neuling");
      await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

      expect(await screen.findByText("abcd-efgh-ijkl-mnop")).toBeInTheDocument();
      expect(screen.getByText(/nicht mehr abrufbar/)).toBeInTheDocument();
    });

    it("blendet es erst auf ausdrückliches Wegklicken aus", async () => {
      // Wer es wegklickt, ohne es weiterzugeben, muss ein neues erzeugen.
      vi.spyOn(api, "legeKontoAn").mockResolvedValue(
        angelegt({ startpasswort: "abcd-efgh-ijkl-mnop" }),
      );
      zeige();
      await screen.findByRole("list", { name: "Konten" });
      await userEvent.type(screen.getByLabelText("Benutzername"), "neuling");
      await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));
      await screen.findByText("abcd-efgh-ijkl-mnop");

      await userEvent.click(screen.getByRole("button", { name: /ausblenden/ }));

      expect(screen.queryByText("abcd-efgh-ijkl-mnop")).not.toBeInTheDocument();
    });
  });
});
