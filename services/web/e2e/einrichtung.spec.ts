import { expect, test, type Page } from "@playwright/test";

/**
 * Der Weg durch die Einrichtung — von der leeren Installation bis zur
 * Spielprüfung.
 *
 * **Warum als Oberflächentest.** Die Komponententests prüfen jede Seite des
 * Weges für sich, mit ersetztem Backend. Was sie nicht sehen können, ist
 * genau das, worum es hier geht: dass die Übersicht einer frischen Anlage
 * wirklich hierher führt, dass die Anmeldeprobe wirklich bei einem Dienst
 * ankommt und von dort eine Antwort zurückbringt, und dass der Weg sich
 * danach schließt und nicht beim nächsten Aufruf wieder dasteht.
 *
 * **Hier gibt es kein DFBnet.** Der Prüfdienst dieser Umgebung ist eine
 * Attrappe: die Anmeldung gelingt immer, und „Eigene Staffeln" liefert
 * nichts, weil er sich keine erfindet — eine erfundene Staffel wäre
 * schlimmer als keine, denn aus ihr entstünden Spiele, die es nie gab. Also
 * prüft dieser Weg beides: die geglückte Probe und das ehrliche Scheitern am
 * Staffelholen samt Ausweg.
 *
 * Er braucht eine eigene, frische Umgebung mit eigener Datenbank
 * (`make e2e`) — niemals die, in der jemand arbeitet.
 */

const VERWALTERIN = {
  name: "staffelleitung",
  passwort: "ein-hinreichend-langes-passwort",
};

const STAFFEL = "Stadtliga C";

/**
 * So lange darf der Prüfdienst brauchen.
 *
 * Er fragt nicht im Sekundentakt: nach ein paar leeren Runden wartet er bis
 * zu dreißig Sekunden, bevor er wieder nachsieht (`dienst.wartezeit`). Das
 * ist Absicht — ein Dienst, der ständig fragt, hält den Pi wach. Für einen
 * Test heißt es: eine frisch angeforderte Probe kann eine halbe Minute
 * liegenbleiben, bevor überhaupt jemand sie ansieht.
 */
const DIENST_WARTET = 45_000;

/** Ein Artefakt in der Liste der Startseite. */
function artefakt(page: Page, name: string | RegExp) {
  return page.getByRole("list", { name: "Artefakte" }).getByRole("link", { name });
}

/** Ein Bereich innerhalb des geöffneten Artefakts - die Leiste über dem Inhalt. */
function bereich(page: Page, name: string) {
  return page
    .getByRole("navigation", { name: "Bereiche" })
    .getByRole("link", { name, exact: true });
}

/** Das Kürzel in der Kopfzeile - es erscheint nur bei bestehender Sitzung. */
function konto(page: Page) {
  return page.getByRole("banner").getByRole("link", { name: /^Einstellungen für / });
}

/** Die Schrittleiste des Weges. Sie ist das Versprechen "so viel kommt noch". */
function schritte(page: Page) {
  return page.getByRole("list", { name: "Schritte der Einrichtung" });
}

test.describe.configure({ mode: "serial" });

test.describe("Eine Staffelleiterin richtet ein", () => {
  test("die Installation gehört ihr, sobald sie sich einrichtet", async ({ page }) => {
    await page.goto("/");

    const token = process.env.E2E_EINRICHTUNGSTOKEN;
    expect(token, "E2E_EINRICHTUNGSTOKEN fehlt — siehe make e2e").toBeTruthy();

    await expect(page.getByRole("heading", { name: "Ersteinrichtung" })).toBeVisible();
    await page.getByLabel("Einrichtungstoken").fill(token!);
    await page.getByLabel("Benutzername").fill(VERWALTERIN.name);
    await page.getByLabel("Passwort", { exact: true }).fill(VERWALTERIN.passwort);
    await page.getByLabel("Passwort wiederholen").fill(VERWALTERIN.passwort);
    await page.getByRole("button", { name: /Einrichten|Anlegen|Konto/ }).click();

    await expect(konto(page)).toBeVisible();
  });

  test("sie gibt sich selbst das Recht auf StaffelPilot", async ({ page }) => {
    // Es gibt keinen globalen Administrator: wer die Verwaltung verwaltet,
    // hat damit kein Recht auf die Spielberichte.
    await anmelden(page);

    await artefakt(page, /Verwaltung/).click();
    await page
      .getByRole("button", { name: new RegExp(`Rechte von ${VERWALTERIN.name}`) })
      .click();
    await page.getByLabel("StaffelPilot").selectOption("verwalter");

    await expect(page.getByLabel("StaffelPilot")).toHaveValue("verwalter");
  });

  test("die Übersicht führt in die Einrichtung, statt eine leere Liste zu zeigen", async ({
    page,
  }) => {
    // Vorher stand dort "keine Spielberichte" und gemeint war "nicht
    // eingerichtet". Das ist der Unterschied zwischen einer Anwendung, die
    // nichts zu tun hat, und einer, die noch nichts tun kann.
    await anmelden(page);
    await artefakt(page, "StaffelPilot").click();

    await expect(page).toHaveURL(/\/modul\/staffelpilot\/einrichten$/);
    await expect(schritte(page)).toBeVisible();
    await expect(page.getByRole("heading", { name: /prüft er mit/ })).toBeVisible();
  });

  test("der Weg sagt vorher, was kommt", async ({ page }) => {
    // Die eine Frage, die ein Formular nie beantwortet: wie viel kommt noch.
    await zurEinrichtung(page);

    await expect(schritte(page).getByRole("listitem")).toHaveCount(4);
    await expect(schritte(page)).toContainText("Zugang");
    await expect(schritte(page)).toContainText("Staffeln");
  });

  test("der Zugang wird nicht nur abgelegt, sondern ausprobiert", async ({ page }) => {
    // Dreifache Zeit: hier wartet der Test auf einen anderen Prozess, und
    // dessen Takt gehört ihm.
    test.slow();
    // Ein Passwort, das erst beim ersten Prüflauf auffällt, ist das Gegenteil
    // einer Einrichtung. Der Dienst dieser Umgebung lässt jede Anmeldung
    // gelingen -- geprüft wird hier, dass die Probe wirklich bis zu ihm und
    // wieder zurück kommt.
    await zurEinrichtung(page);
    await page.getByRole("button", { name: /Los geht/ }).click();

    await expect(page.getByRole("heading", { name: "Dein DFBnet-Zugang" })).toBeVisible();
    await page.getByLabel("DFBnet-Benutzername").fill("beispiel");
    await page.getByLabel("Passwort").fill("nur-ein-platzhalter");
    await page.getByRole("button", { name: "Speichern und anmelden" }).click();

    // Zuerst wartet er -- und sagt das, statt einen Fortschritt
    // vorzutäuschen. Dann kommt die Antwort des Dienstes.
    await expect(page.getByRole("heading", { name: "Deine Staffeln" })).toBeVisible({
      timeout: DIENST_WARTET,
    });
  });

  test("ohne DFBnet scheitert das Staffelholen — und sagt warum", async ({ page }) => {
    test.slow();
    // Hier ist keine Verbandsmaske: der Dienst erfindet sich keine Staffel,
    // denn aus einer erfundenen entstünden Spiele, die es nie gab. Dass das
    // Scheitern den Grund nennt, ist der eigentliche Prüfpunkt -- eine Null
    // ohne Begründung war genau der Fehler, den dieser Weg beheben soll.
    await zurEinrichtung(page);

    await expect(page.getByRole("heading", { name: "Deine Staffeln" })).toBeVisible();
    await page.getByRole("button", { name: "Staffeln holen" }).click();

    await expect(page.getByRole("alert")).toContainText(/Eigene Staffeln|keine einzige/, {
      timeout: DIENST_WARTET,
    });
  });

  test("überspringen führt trotzdem ans Ende", async ({ page }) => {
    // Ein Weg, der nur bei gutem Wetter zu Ende geht, ist eine Sackgasse.
    await zurEinrichtung(page);
    await page.getByRole("button", { name: "Überspringen" }).click();

    await expect(page.getByRole("heading", { name: "Fertig." })).toBeVisible();
    // Ehrlich gezählt: hier steht wirklich noch keine Staffel.
    await expect(page.getByText(/noch keine Staffel/)).toBeVisible();
  });

  test("am Ende steht die Spielprüfung", async ({ page }) => {
    await zurEinrichtung(page);
    await page.getByRole("button", { name: "Überspringen" }).click();
    await page.getByRole("button", { name: "Zur Spielprüfung" }).click();

    await expect(page).toHaveURL(/\/modul\/staffelpilot\/spiele$/);
  });

  test("und wird danach nicht wieder vorgesetzt", async ({ page }) => {
    // Abgehakt heißt abgehakt. Ein Weg, der bei jedem Aufruf wieder dasteht,
    // ist eine Falle -- auch dann, wenn noch etwas fehlt.
    await anmelden(page);
    await artefakt(page, "StaffelPilot").click();

    // Nicht auf den nackten Modulpfad pruefen: die Huelle leitet sofort auf
    // die erste Unterseite weiter. Wer diesen Zwischenzustand zusichert,
    // prueft die Geschwindigkeit der Maschine -- auf einer langsamen
    // erwischt man ihn, auf einer schnellen nicht mehr. Welche Unterseite
    // die erste ist, entscheidet ausserdem das Register und nicht dieser Test.
    await expect(page).toHaveURL(/\/modul\/staffelpilot(\/|$)/);
    // Das hier ist die Aussage des Tests: nicht wieder der Weg.
    await expect(page).not.toHaveURL(/\/einrichten$/);
    await expect(schritte(page)).toHaveCount(0);
    // Stattdessen der ehrliche Erstzustand: es fehlt eine Staffel.
    await expect(page.getByText("Keine aktive Staffel")).toBeVisible();
  });

  test("aus den Einstellungen heraus geht sie wieder auf", async ({ page }) => {
    // Sie steht in keiner Navigationsleiste -- ohne diesen Knopf wäre sie
    // danach unerreichbar, und wer seinen Zugang wechselt, stünde wieder vor
    // zwei Formularen ohne Reihenfolge.
    await anmelden(page);
    await artefakt(page, "StaffelPilot").click();
    await bereich(page, "Einstellungen").click();

    await page
      .getByRole("button", { name: /Einrichtung noch einmal durchlaufen/ })
      .click();

    await expect(page).toHaveURL(/\/modul\/staffelpilot\/einrichten$/);
    await expect(schritte(page)).toBeVisible();
  });

  test("der eingetragene Zugang steht noch", async ({ page }) => {
    // Die Einrichtung noch einmal zu öffnen darf nichts wegwerfen: aufmachen
    // ist kein Zurücksetzen.
    await anmelden(page);
    await artefakt(page, "StaffelPilot").click();
    await bereich(page, "DFBnet-Zugang").click();

    await expect(page.getByText(/Hinterlegt für/)).toContainText("beispiel");
  });

  test("von Hand angelegt zählt sie auch", async ({ page }) => {
    // Der Weg ist ein Angebot und keine Pflicht. Wer seine Staffel selbst
    // einträgt, ist genauso eingerichtet -- die Prüfung fragt nach einer
    // Staffel, nicht danach, woher sie kam.
    await anmelden(page);
    await artefakt(page, "StaffelPilot").click();
    await bereich(page, "Staffeln").click();

    await page.getByRole("textbox", { name: "Name" }).fill(STAFFEL);
    await page.getByRole("textbox", { name: "Spielklasse" }).fill("3.Kreisliga (C)");
    await page.getByRole("textbox", { name: "Saison" }).fill("26/27");
    await page.getByRole("button", { name: "Anlegen" }).click();

    await expect(
      page.getByRole("list", { name: "Staffeln" }).getByText(STAFFEL),
    ).toBeVisible();
  });
});

// ── Helfer ────────────────────────────────────────────────────────────────

async function anmelden(page: Page): Promise<void> {
  await page.goto("/anmelden");
  await page.getByLabel("Benutzername").fill(VERWALTERIN.name);
  await page.getByLabel("Passwort").fill(VERWALTERIN.passwort);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await expect(konto(page)).toBeVisible();
}

/**
 * Direkt auf den Weg, ohne ihn von vorn zu durchlaufen.
 *
 * Er merkt sich seinen Schritt nicht im Browser, sondern leitet ihn aus dem
 * Stand im Artefakt ab: ohne Zugang beim Willkommen, mit Zugang und ohne
 * Staffel bei den Staffeln. Genau das macht ihn fortsetzbar -- auch nach
 * einem Neuladen.
 */
async function zurEinrichtung(page: Page): Promise<void> {
  await anmelden(page);
  await page.goto("/modul/staffelpilot/einrichten");
  await expect(schritte(page)).toBeVisible();
}
