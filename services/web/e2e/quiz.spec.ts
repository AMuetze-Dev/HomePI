import { expect, test, type Browser, type Page } from "@playwright/test";

/**
 * Der Weg eines Quizabends - von der leeren Installation bis zur Wertung.
 *
 * Was die Komponententests nicht sehen können: dass ein Spieler **ohne
 * Konto** wirklich hineinkommt (das Artefakt ist öffentlich), dass sein Name
 * an seinem Cookie hängt und ein zweites Gerät ihn nicht bekommt, und dass
 * die Antwort vom Handy über das Gateway bis in die Wertung der Leitung
 * läuft. Drei Browser-Kontexte: Leitung, Anna, ein Fremder.
 *
 * Die Tests bauen aufeinander auf (`mode: serial`).
 */

const LEITUNG = { name: "quizleitung", passwort: "korrekt-pferd-batterie-heftklammer" };

/** Ein Quiz, wie Battle.Net es speichert - als nacktes quiz.json. */
const BATTLENET = {
  title: "Kneipenquiz",
  description: "aus Battle.Net",
  questions: [
    {
      type: "text",
      question: "Hauptstadt von Frankreich?",
      correctAnswerText: "Paris",
      points: 2,
    },
    { type: "tanzen", question: "Gibt es hier nicht" },
  ],
};

let code = "";

function artefakt(page: Page, name: string | RegExp) {
  return page.getByRole("list", { name: "Artefakte" }).getByRole("link", { name });
}

function bereich(page: Page, name: string) {
  return page
    .getByRole("navigation", { name: "Bereiche" })
    .getByRole("link", { name, exact: true });
}

function konto(page: Page) {
  return page.getByRole("banner").getByRole("link", { name: /^Einstellungen für / });
}

async function anmelden(page: Page): Promise<void> {
  await page.goto("/anmelden");
  await page.getByLabel("Benutzername").fill(LEITUNG.name);
  await page.getByLabel("Passwort").fill(LEITUNG.passwort);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await expect(konto(page)).toBeVisible();
}

/** Ein Handy: eigener Kontext, eigene Cookies, kein Konto. */
async function handy(browser: Browser): Promise<Page> {
  const kontext = await browser.newContext({ viewport: { width: 375, height: 812 } });
  return kontext.newPage();
}

test.describe.configure({ mode: "serial" });

test.describe("Ein Quizabend", () => {
  test("die Leitung richtet die Installation ein", async ({ page }) => {
    await page.goto("/");
    const token = process.env.E2E_EINRICHTUNGSTOKEN;
    expect(token, "E2E_EINRICHTUNGSTOKEN fehlt — siehe make e2e").toBeTruthy();

    await expect(page.getByRole("heading", { name: "Ersteinrichtung" })).toBeVisible();
    await page.getByLabel("Einrichtungstoken").fill(token!);
    await page.getByLabel("Benutzername").fill(LEITUNG.name);
    await page.getByLabel("Passwort", { exact: true }).fill(LEITUNG.passwort);
    await page.getByLabel("Passwort wiederholen").fill(LEITUNG.passwort);
    await page.getByRole("button", { name: /Einrichten|Anlegen|Konto/ }).click();
    await expect(konto(page)).toBeVisible();
  });

  test("das Quiz ist ohne Konto sichtbar, Leiten braucht das Recht", async ({
    browser,
    page,
  }) => {
    const besucher = await handy(browser);
    await besucher.goto("/");
    await expect(artefakt(besucher, "Quiz")).toBeVisible();
    await besucher.close();

    await anmelden(page);
    await artefakt(page, /Verwaltung/).click();
    await page.getByRole("button", { name: new RegExp(`^${LEITUNG.name}`) }).click();
    await page.getByRole("combobox", { name: /^Quiz —/ }).selectOption("verwalter");
    await expect(page.getByRole("combobox", { name: /^Quiz —/ })).toHaveValue(
      "verwalter",
    );
  });

  test("sie übernimmt ein Battle.Net-Quiz und eröffnet eine Runde", async ({ page }) => {
    await anmelden(page);
    await artefakt(page, "Quiz").click();
    await bereich(page, "Kataloge").click();

    await page.getByLabel(/Quiz übernehmen/).setInputFiles({
      name: "quiz.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(BATTLENET)),
    });
    await expect(page.getByRole("heading", { name: "Kneipenquiz" })).toBeVisible();
    await expect(page.getByText(/tanzen/)).toBeVisible();

    await bereich(page, "Runden").click();
    await page.getByRole("button", { name: "Runde eröffnen" }).click();
    await expect(page.getByText("Lösung: Paris")).toBeHidden();
    await expect(page.getByText(/Wähle unten die erste Frage/)).toBeVisible();

    const beiwort = await page
      .getByRole("heading", { name: "Kneipenquiz" })
      .locator("..")
      .innerText();
    code = /[A-Z0-9]{6}/.exec(beiwort)?.[0] ?? "";
    expect(code).toHaveLength(6);
  });

  test("Anna spielt ohne Konto, ihr Name gehört ihr", async ({ browser, page }) => {
    const anna = await handy(browser);
    await anna.goto("/modul/quiz/spielen");
    await anna.getByLabel("Rundencode").fill(code.toLowerCase());
    await anna.getByRole("button", { name: "Weiter" }).click();
    await anna.getByLabel("Dein Name").fill("Anna");
    await anna.getByRole("button", { name: "Mitspielen" }).click();
    await expect(anna.getByText("Gleich geht es los")).toBeVisible();

    // Ein zweites Gerät bekommt den Namen nicht - auch nicht in anderer
    // Schreibweise.
    const fremder = await handy(browser);
    await fremder.goto(`/modul/quiz/spielen?code=${code}`);
    await fremder.getByLabel("Dein Name").fill("ANNA");
    await fremder.getByRole("button", { name: "Mitspielen" }).click();
    await expect(fremder.getByRole("alert")).toContainText(
      "spielt in dieser Runde schon mit",
    );
    await expect(fremder.getByLabel("Dein Name")).toHaveValue("ANNA");
    await fremder.close();

    // Die Leitung stellt die Frage.
    await anmelden(page);
    await artefakt(page, "Quiz").click();
    await bereich(page, "Runden").click();
    await page.getByRole("button", { name: new RegExp(code) }).click();
    await page.getByRole("button", { name: "Frage 1 wählen" }).click();
    await page.getByRole("button", { name: "Frage zeigen" }).click();

    await expect(
      anna.getByRole("heading", { name: "Hauptstadt von Frankreich?" }),
    ).toBeVisible();
    await anna.getByLabel("Deine Antwort").fill("paris");
    await anna.getByRole("button", { name: "Antwort abgeben" }).click();
    await expect(anna.getByText("Abgegeben")).toBeVisible();

    await expect(page.getByText("paris")).toBeVisible();
    await page.getByRole("button", { name: "Auflösen" }).click();

    await expect(anna.getByText("Richtig! +2")).toBeVisible();
    await expect(anna.getByText(/Anna · 2 Punkte · Platz 1/)).toBeVisible();

    // Nichts davon darf bei 375 px quer scrollen.
    const breite = await anna.evaluate(() => [
      document.documentElement.scrollWidth,
      document.documentElement.clientWidth,
    ]);
    expect(breite[0]).toBeLessThanOrEqual(breite[1]!);
    await anna.close();
  });

  test("am Ende steht Anna auf dem Podest", async ({ browser, page }) => {
    await anmelden(page);
    await artefakt(page, "Quiz").click();
    await bereich(page, "Runden").click();
    await page.getByRole("button", { name: new RegExp(code) }).click();
    page.once("dialog", (dialog) => void dialog.accept());
    await page.getByRole("button", { name: "Runde beenden" }).click();

    const tafel = await handy(browser);
    await tafel.goto(`/modul/quiz/tafel?code=${code}`);
    await expect(tafel.getByRole("list", { name: "Siegerpodest" })).toContainText("Anna");
    await tafel.close();
  });
});
