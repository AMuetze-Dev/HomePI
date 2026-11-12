import { defineConfig, devices } from "@playwright/test";

import { BASIS_PORT, BASIS_URL } from "./e2e/umgebung";

/**
 * Oberflächentests gegen eine **laufende** Instanz.
 *
 * Das Backend bringt `make e2e` mit: eigene Datenbank, eigene Ports, eigener
 * Projektname. Die Tests legen Konten an und vergeben Rechte, deshalb darf das
 * niemals die Umgebung sein, in der jemand arbeitet — `wache.ts` prüft das
 * vorweg, und `E2E_URL` zeigt auf die Testumgebung, nicht auf 5173.
 *
 * Die **Oberfläche** dagegen startet Playwright selbst, als `vite preview` auf
 * dem gebauten Bundle. Das ist der Unterschied zu früher, wo auch sie aus dem
 * Compose-Projekt kam und dort der Entwicklungsserver war: der übersetzt beim
 * ersten Aufruf, und mit jedem Artefakt dauert das länger. Auf einem
 * ausgelasteten CI-Runner hat es die Tests gekippt, bevor einer von ihnen etwas
 * geprüft hatte. Ein fertiges Bundle steht sofort.
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

  /**
   * Die Oberfläche: das gebaute Bundle, ausgeliefert von `vite preview`.
   *
   * Gebaut wird **vorher**, von `make e2e`. Nicht hier: `make e2e` ruft
   * Playwright dreimal auf, und dreimal dasselbe Bundle zu bauen wäre dreimal
   * dieselbe Minute. Ein `dist/`, das nicht zum Quelltext passt, prüft die
   * falsche Fassung — darum baut das Makefile einmal, direkt davor.
   *
   * `reuseExistingServer` steht bewusst auf `false`, auch lokal: ein noch
   * laufender Vorschauserver liefert das Bundle von vorhin aus, und ein Test,
   * der die vorige Fassung prüft und grün wird, ist schlimmer als ein roter.
   * Belegter Port heißt deshalb Abbruch mit Meldung, nicht stilles Weiter.
   */
  webServer: {
    command: `npm run preview -- --port ${BASIS_PORT} --strictPort`,
    url: BASIS_URL,
    reuseExistingServer: false,
    // Statische Dateien ausliefern geht schnell; hier wird nur auf das
    // Hochkommen des Servers gewartet, nicht auf einen Build.
    timeout: 60_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
