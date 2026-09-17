import { expect, test } from "@playwright/test";

/**
 * Der Weg, den eine frische Installation nimmt.
 *
 * Ein einziger Ablauf in Schritten statt vieler unabhängiger Tests: die
 * Schritte bauen aufeinander auf, und genau ihr Zusammenhang ist das, was
 * Komponententests nicht sehen können.
 *
 * Er läuft gegen eine eigene Umgebung mit eigener Datenbank (`make e2e`) —
 * niemals gegen die, in der jemand arbeitet.
 */

const VERWALTERIN = {
  name: "leitung",
  anzeige: "Die Leitung",
  passwort: "ein-hinreichend-langes-passwort",
};

const NEULING = {
  name: "neuling",
  anzeige: "Der Neue",
  eigenes: "mein-eigenes-langes-passwort",
};

/** Wird im ersten Schritt gefüllt und danach gebraucht. */
let startpasswort = "";

test.describe.configure({ mode: "serial" });

test.describe("Der Weg einer frischen Installation", () => {
  test("die Ersteinrichtung verlangt das Token aus dem Log", async ({
    page,
    request,
  }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Ersteinrichtung" })).toBeVisible();

    // Ohne Anmeldung und ohne Token ist hier nichts zu holen - geprüft wird
    // das im Backend, nicht daran, dass die Maske erscheint.
    const abgelehnt = await request.post("/api/auth/einrichtung", {
      data: {
        token: "stimmt-nicht",
        name: "eindringling",
        passwort: "auch-nicht-4711-lang",
      },
      failOnStatusCode: false,
    });
    expect(abgelehnt.status()).toBe(401);

    // Und die Einrichtung steht danach noch offen.
    await page.reload();
    await expect(page.getByRole("heading", { name: "Ersteinrichtung" })).toBeVisible();
  });

  test("mit dem Token entsteht die erste Verwalterin", async ({ page }) => {
    const token = process.env.E2E_EINRICHTUNGSTOKEN;
    expect(token, "E2E_EINRICHTUNGSTOKEN muss gesetzt sein").toBeTruthy();

    await page.goto("/");
    await page.getByLabel("Einrichtungstoken").fill(token!);
    await page.getByLabel("Benutzername").fill(VERWALTERIN.name);
    await page.getByLabel("Anzeigename").fill(VERWALTERIN.anzeige);
    await page.getByLabel("Passwort", { exact: true }).fill(VERWALTERIN.passwort);
    await page.getByLabel("Passwort wiederholen").fill(VERWALTERIN.passwort);
    await page.getByRole("button", { name: "Einrichten" }).click();

    // Sie ist damit angemeldet - ohne zweiten Schritt.
    await expect(page.getByRole("heading", { name: "Übersicht" })).toBeVisible();
    await expect(page.getByText(VERWALTERIN.anzeige)).toBeVisible();
  });

  test("sie sieht die Verwaltung und sonst nichts", async ({ page }) => {
    await anmelden(page, VERWALTERIN.name, VERWALTERIN.passwort);

    const kacheln = page.getByRole("list", { name: "Artefakte" });
    await expect(kacheln.getByRole("link", { name: /Verwaltung/ })).toBeVisible();
    // Auf "geraete" hat sie kein Recht - das Artefakt existiert für sie nicht.
    await expect(kacheln.getByRole("link", { name: /Geräte/ })).toHaveCount(0);
  });

  test("ein neues Konto braucht nur einen Namen", async ({ page }) => {
    await anmelden(page, VERWALTERIN.name, VERWALTERIN.passwort);
    await page.getByRole("link", { name: /Verwaltung/ }).click();

    await page.getByLabel("Benutzername").fill(NEULING.name);
    await page.getByLabel("Anzeigename").fill(NEULING.anzeige);
    await page.getByRole("button", { name: "Anlegen" }).click();

    const karte = page.getByRole("heading", {
      name: `Startpasswort für ${NEULING.name}`,
    });
    await expect(karte).toBeVisible();

    startpasswort = (await page.locator("code").first().innerText()).trim();
    expect(startpasswort).toMatch(/^[a-z2-9]{4}(-[a-z2-9]{4}){3}$/);
  });

  test("sie gibt dem Konto ein Recht", async ({ page }) => {
    await anmelden(page, VERWALTERIN.name, VERWALTERIN.passwort);
    await page.getByRole("link", { name: /Verwaltung/ }).click();

    await page
      .getByRole("button", { name: new RegExp(`Rechte von ${NEULING.name}`) })
      .click();
    await page.getByLabel("Geräte").selectOption("nutzer");

    await expect(page.getByLabel("Geräte")).toHaveValue("nutzer");
  });

  test("der Neue kommt mit dem Startpasswort hinein, aber an kein Artefakt", async ({
    page,
  }) => {
    expect(startpasswort, "Startpasswort aus dem vorigen Schritt").toBeTruthy();

    await anmelden(page, NEULING.name, startpasswort);

    // Statt der Übersicht: der erzwungene Wechsel.
    await expect(
      page.getByRole("heading", { name: "Eigenes Passwort wählen" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Übersicht" })).toHaveCount(0);
  });

  test("auch nicht, wenn er die Adresse von Hand eintippt", async ({ page }) => {
    await anmelden(page, NEULING.name, startpasswort);

    await page.goto("/modul/geraete");

    await expect(
      page.getByRole("heading", { name: "Eigenes Passwort wählen" }),
    ).toBeVisible();
  });

  test("nach dem Wechsel ist der Weg frei", async ({ page }) => {
    await anmelden(page, NEULING.name, startpasswort);

    await page.getByLabel("Startpasswort").fill(startpasswort);
    await page.getByLabel("Neues Passwort", { exact: true }).fill(NEULING.eigenes);
    await page.getByLabel("Neues Passwort wiederholen").fill(NEULING.eigenes);
    await page.getByRole("button", { name: "Passwort setzen" }).click();

    // Ohne erneutes Anmelden: die laufende Sitzung bleibt.
    await expect(page.getByRole("heading", { name: "Übersicht" })).toBeVisible();

    const kacheln = page.getByRole("list", { name: "Artefakte" });
    await expect(kacheln.getByRole("link", { name: /Geräte/ })).toBeVisible();
    // Die Verwaltung darf er nicht - sie steht nicht da.
    await expect(kacheln.getByRole("link", { name: /Verwaltung/ })).toHaveCount(0);
  });

  test("das Startpasswort gilt danach nicht mehr", async ({ page }) => {
    await page.goto("/anmelden");
    await page.getByLabel("Benutzername").fill(NEULING.name);
    await page.getByLabel("Passwort").fill(startpasswort);
    await page.getByRole("button", { name: "Anmelden" }).click();

    await expect(page.getByRole("alert")).toContainText(/stimmt nicht/);
  });

  test("mit dem eigenen Passwort kommt er an sein Artefakt", async ({ page }) => {
    await anmelden(page, NEULING.name, NEULING.eigenes);

    await page.getByRole("link", { name: /Geräte/ }).click();

    await expect(page.getByRole("heading", { name: "Geräte" })).toBeVisible();
  });

  test("abmelden schließt alles wieder", async ({ page }) => {
    await anmelden(page, NEULING.name, NEULING.eigenes);

    await page.getByRole("banner").getByRole("button", { name: "Abmelden" }).click();

    await expect(page.getByRole("heading", { name: "Anmelden" })).toBeVisible();
    await expect(page.getByRole("list", { name: "Artefakte" })).toHaveCount(0);
  });
});

/**
 * Meldet sich an und wartet, bis die Sitzung wirklich steht.
 *
 * Gewartet wird auf "Abmelden" in der Kopfzeile - das erscheint nur bei einer
 * bestehenden Sitzung. Auf die Marke zu warten wäre wertlos: die steht auch
 * da, während die Anmeldung noch läuft, und der nächste `goto` fände dann
 * einen abgemeldeten Zustand vor.
 */
async function anmelden(
  page: import("@playwright/test").Page,
  name: string,
  passwort: string,
): Promise<void> {
  await page.goto("/anmelden");
  await page.getByLabel("Benutzername").fill(name);
  await page.getByLabel("Passwort").fill(passwort);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await expect(
    page.getByRole("banner").getByRole("button", { name: "Abmelden" }),
  ).toBeVisible();
}
