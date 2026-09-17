import { defineConfig, devices } from "@playwright/test";

import { BASIS_URL } from "./e2e/umgebung";

/**
 * Oberflächentests gegen eine **laufende** Instanz.
 *
 * Kein `webServer`: die Tests legen Konten an, ändern Rechte und verlassen
 * sich darauf, dass die Installation frisch ist. Sie brauchen also eine eigene
 * Umgebung mit eigener Datenbank — `make e2e` fährt sie hoch, und `E2E_URL`
 * zeigt darauf. Gegen die Entwicklungsumgebung dürfen sie nicht laufen: dort
 * arbeitet jemand.
 *
 * Warum überhaupt Oberflächentests, wo es 166 Komponententests gibt: die
 * prüfen jede Ansicht für sich, mit ersetztem Backend. Was sie nicht sehen
 * können, ist der Weg — anmelden, Konto anlegen, Startpasswort weitergeben,
 * erstes Anmelden, erzwungener Wechsel. Genau dort war der Fehler.
 */
export default defineConfig({
  testDir: "./e2e",
  // Prueft vorweg, dass die Installation frisch ist. Ohne das koennte ein
  // falsch gesetztes E2E_URL die Konten treffen, mit denen jemand arbeitet.
  globalSetup: "./e2e/wache.ts",
  // Sie teilen sich eine Datenbank und bauen aufeinander auf.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: BASIS_URL,
    // Beim Fehlschlag: Spur und Bild. Ein roter Oberflächentest ohne beides
    // kostet mehr Zeit, als er spart.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "de-DE",
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
