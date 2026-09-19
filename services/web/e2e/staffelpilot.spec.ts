import { expect, test } from "@playwright/test";

/**
 * Der Weg eines Staffelleiters — von der leeren Installation bis zur
 * freigegebenen Übertragung.
 *
 * Was die Komponententests **nicht** sehen können: dass der Prüfdienst den
 * Auftrag wirklich übernimmt, dass eingespielte Spiele in der Warteschlange
 * ankommen und dass eine Freigabe am Ende wirklich als erledigt zurückkommt.
 * Genau dieser Weg war der, auf dem ‚0 geprueft, 0 Befunde' stand, obwohl gar
 * keine Staffel da war.
 *
 * **Die Übertragung ist simuliert**, und sie sagt das an jeder Zeile: es
 * läuft kein Browser nach DFBnet. Alles davor ist echt — echtes Gateway,
 * echte Datenbank, echter Prüfdienst-Container.
 *
 * Die Tests bauen aufeinander auf und laufen in dieser Reihenfolge
 * (`fullyParallel: false`, ein Worker).
 */

const STAFFEL = "Stadtliga C";
const VERWALTER = {
  name: "staffelleiterin",
  passwort: "korrekt-pferd-batterie-heftklammer",
};

/** So lange darf der Prüfdienst brauchen. Er fragt alle zwei Sekunden nach. */
const DIENST_WARTET = 30_000;

test.describe.configure({ mode: "serial" });

test.describe("Ein Staffelleiter richtet ein und prüft", () => {
  test("die Installation gehört ihr, sobald sie sich einrichtet", async ({ page }) => {
    await page.goto("/");

    const token = process.env.E2E_EINRICHTUNGSTOKEN;
    expect(token, "E2E_EINRICHTUNGSTOKEN fehlt — siehe make e2e").toBeTruthy();

    await expect(page.getByRole("heading", { name: "Ersteinrichtung" })).toBeVisible();
    await page.getByLabel("Einrichtungstoken").fill(token!);
    await page.getByLabel("Benutzername").fill(VERWALTER.name);
    await page.getByLabel("Passwort", { exact: true }).fill(VERWALTER.passwort);
    await page.getByLabel("Passwort wiederholen").fill(VERWALTER.passwort);
    await page.getByRole("button", { name: /Einrichten|Anlegen|Konto/ }).click();

    await expect(
      page.getByRole("banner").getByRole("button", { name: "Abmelden" }),
    ).toBeVisible();
  });

  test("StaffelPilot sieht sie erst mit dem Recht darauf", async ({ page }) => {
    // Es gibt keinen globalen Administrator: wer die Verwaltung verwaltet,
    // hat damit kein Recht auf die Spielberichte.
    await anmelden(page);

    await expect(page.getByRole("link", { name: "StaffelPilot" })).toHaveCount(0);

    await page.getByRole("link", { name: /Verwaltung/ }).click();
    await page
      .getByRole("button", { name: new RegExp(`Rechte von ${VERWALTER.name}`) })
      .click();
    await page.getByLabel("StaffelPilot").selectOption("verwalter");

    await expect(page.getByLabel("StaffelPilot")).toHaveValue("verwalter");
  });

  test("ohne Staffel sagt die Übersicht, was zuerst zu tun ist", async ({ page }) => {
    await zuStaffelpilot(page);

    await expect(page.getByText("Keine aktive Staffel")).toBeVisible();
    await expect(page.getByRole("button", { name: "Staffeln verwalten" })).toBeVisible();
  });

  test("ein Prüflauf ohne Staffel nennt den Grund statt einer Null", async ({ page }) => {
    // Das war die verwirrende Auskunft: fertig, null geprüft, null Befunde -
    // und der Grund stand nirgends.
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "Prüflauf" }).click();
    await page.getByRole("button", { name: "Prüflauf anfordern" }).click();

    const verlauf = page.getByRole("list", { name: "Bisherige Läufe" });
    await expect(verlauf.getByText(/Keine aktive Staffel/)).toBeVisible({
      timeout: DIENST_WARTET,
    });
    await expect(verlauf.getByText(/0 geprüft/)).toHaveCount(0);
  });

  test("sie legt eine Staffel an", async ({ page }) => {
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "Staffeln" }).click();

    await page.getByRole("textbox", { name: "Name" }).fill(STAFFEL);
    await page.getByRole("textbox", { name: "Spielklasse" }).fill("3.Kreisliga (C)");
    await page.getByRole("textbox", { name: "Saison" }).fill("26/27");
    await page.getByRole("button", { name: "Anlegen" }).click();

    await expect(
      page.getByRole("list", { name: "Staffeln" }).getByText(STAFFEL),
    ).toBeVisible();
  });

  test("der DFBnet-Zugang lässt sich hinterlegen", async ({ page }) => {
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "DFBnet-Zugang" }).click();

    await page.getByLabel(/DFBnet-Benutzername/).fill("beispiel");
    await page.getByLabel(/DFBnet-Passwort/).fill("nur-ein-platzhalter");
    await page.getByRole("button", { name: "Zugang hinterlegen" }).click();

    await expect(page.getByText(/Hinterlegt für/)).toBeVisible();
  });

  test("Saisondaten holen bringt die Mannschaften", async ({ page }) => {
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "Prüflauf" }).click();
    await page.getByRole("button", { name: "Saisondaten holen" }).click();

    await expect(
      page.getByRole("list", { name: "Bisherige Läufe" }).getByText(/Mannschaften/),
    ).toBeVisible({ timeout: DIENST_WARTET });

    await page.getByRole("tab", { name: "Staffeln" }).click();
    await page.getByRole("button", { name: new RegExp(STAFFEL) }).click();

    const mannschaften = page.getByRole("list", { name: "Mannschaften" });
    await expect(mannschaften).toBeVisible();
    // Die Spielgemeinschaft muss als "prüfen" dastehen - dafür gibt es die
    // Ansicht.
    await expect(mannschaften.getByText("prüfen").first()).toBeVisible();
  });

  test("ein Prüflauf bringt Spielberichte", async ({ page }) => {
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "Prüflauf" }).click();
    await page.getByRole("button", { name: "Prüflauf anfordern" }).click();

    await expect(
      page.getByRole("list", { name: "Bisherige Läufe" }).getByText(/geprüft/),
    ).toBeVisible({ timeout: DIENST_WARTET });

    await page.getByRole("tab", { name: "Spielprüfung" }).click();
    await expect(page.getByRole("list", { name: "Spielberichte" })).toBeVisible();
  });

  test("ein Befund lässt sich nicht übergehen", async ({ page }) => {
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "Spielprüfung" }).click();

    await ersterBerichtMitBefunden(page);
    await page.getByRole("button", { name: "Abhaken" }).click();

    await expect(page.getByRole("alert")).toContainText(/Entscheidung/);
  });

  test("entschieden und abgehakt", async ({ page }) => {
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "Spielprüfung" }).click();
    await ersterBerichtMitBefunden(page);

    // Alle offenen Befunde zur Kenntnis nehmen.
    for (;;) {
      const knopf = page.getByRole("button", { name: "Zur Kenntnis genommen" }).first();
      if ((await knopf.count()) === 0) break;
      await knopf.click();
      await expect(knopf)
        .toHaveCount(0, { timeout: 5000 })
        .catch(() => undefined);
    }

    await page.getByRole("button", { name: "Abhaken" }).click();
    await expect(page.getByRole("button", { name: "Haken entfernen" })).toBeVisible();
  });

  test("das Abhaken merkt die Freigabe vor", async ({ page }) => {
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "Prüflauf" }).click();

    const zahlen = page.getByRole("list", { name: "Übertragung" });
    await expect(zahlen.getByText("vorgemerkt")).toBeVisible();
    await expect(page.getByText(/Die Übertragung ist angehalten/)).toBeVisible();
  });

  test("freigegeben wird sie simuliert erledigt", async ({ page }) => {
    // Der Prüfdienst trägt nichts in DFBnet ein - er meldet die Zeile als
    // simuliert erledigt. Genau das ist der Teil, der sich hier nicht echt
    // prüfen lässt, und er sagt es selbst.
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "Prüflauf" }).click();

    await page.getByRole("button", { name: "Übertragung freigeben" }).click();

    const zahlen = page.getByRole("list", { name: "Übertragung" });
    await expect(zahlen.getByText("eingetragen")).toBeVisible();
    await expect(async () => {
      const text = await zahlen.textContent();
      expect(text).toMatch(/1[\s\S]*eingetragen|eingetragen[\s\S]*1/);
    }).toPass({ timeout: DIENST_WARTET });
  });

  test("die Ergebnisse zählen mit", async ({ page }) => {
    await zuStaffelpilot(page);
    await page.getByRole("tab", { name: "Ergebnisse" }).click();

    const bilanz = page.getByRole("list", { name: "Bilanz" });
    await expect(bilanz.getByText("Spiele")).toBeVisible();
    await expect(page.getByRole("list", { name: "Nach Schwere" })).toBeVisible();
  });
});

// ── Helfer ────────────────────────────────────────────────────────────────

async function anmelden(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/anmelden");
  await page.getByLabel("Benutzername").fill(VERWALTER.name);
  await page.getByLabel("Passwort").fill(VERWALTER.passwort);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await expect(
    page.getByRole("banner").getByRole("button", { name: "Abmelden" }),
  ).toBeVisible();
}

async function zuStaffelpilot(page: import("@playwright/test").Page): Promise<void> {
  await anmelden(page);
  await page.getByRole("link", { name: "StaffelPilot" }).click();
  await expect(page.getByRole("tab", { name: "Übersicht" })).toBeVisible();
}

/** Klappt den ersten Bericht auf, der noch offene Befunde hat. */
async function ersterBerichtMitBefunden(
  page: import("@playwright/test").Page,
): Promise<void> {
  const liste = page.getByRole("list", { name: "Spielberichte" });
  await expect(liste).toBeVisible();

  const mitOffenen = liste.getByRole("button", { expanded: false }).filter({
    hasText: /offen/,
  });
  await mitOffenen.first().click();
  await expect(page.getByText(/Beispieldaten/).first()).toBeVisible();
}
