import { chromium } from "@playwright/test";

import { BASIS_URL } from "./umgebung";

/**
 * So lange darf die Oberfläche brauchen, bis sie das erste Mal dasteht.
 *
 * Großzügig, weil hier nichts geprüft wird: es wird nur gewartet. Die Frist
 * der Tests selbst (`expect.timeout`, 10 s) bleibt knapp, und das soll sie
 * auch — eine Ansicht, die im Betrieb zehn Sekunden braucht, ist kaputt.
 */
const KALTSTART = 120_000;

/**
 * Läuft, bevor der erste Test etwas anfasst.
 *
 * Die Oberflächentests fangen bei der Ersteinrichtung an: sie legen den ersten
 * Verwalter an, dann weitere Konten, und sie verteilen Rechte. Gegen eine
 * Installation, in der schon jemand arbeitet, ist das kein Test, sondern ein
 * Eingriff — genau so ist hier schon einmal ein Admin-Konto verschwunden.
 *
 * Deshalb die Frage vorweg: hat diese Installation noch keinen Verwalter? Nur
 * dann geht es weiter. Die Antwort gibt das Backend selbst; sie ist dieselbe,
 * nach der sich auch die Oberfläche richtet.
 */
export default async function wache(): Promise<void> {
  const adresse = `${BASIS_URL}/api/auth/einrichtung`;

  let antwort: Response;
  try {
    antwort = await fetch(adresse);
  } catch (grund) {
    throw new Error(
      `Unter ${BASIS_URL} läuft nichts (${String(grund)}).\n` +
        "Die Oberflächentests brauchen eine eigene, frische Umgebung:\n" +
        "  make e2e",
    );
  }

  if (!antwort.ok) {
    throw new Error(
      `${adresse} antwortet mit ${antwort.status} statt mit dem Einrichtungsstand.`,
    );
  }

  const stand = (await antwort.json()) as { noetig?: boolean };
  if (stand.noetig !== true) {
    throw new Error(
      `${BASIS_URL} hat bereits einen Verwalter — hier arbeitet also jemand.\n` +
        "Diese Tests legen Konten an und vergeben Rechte; sie laufen nur gegen eine\n" +
        "frische Installation mit eigener Datenbank:\n" +
        "  make e2e",
    );
  }

  await aufwaermen();
}

/**
 * Die Oberfläche einmal laden, bevor der erste Test sie misst.
 *
 * Die Prüfung oben fragt nur das Backend. Der Entwicklungsserver davor
 * übersetzt die Anwendung aber erst, wenn ein Browser sie zum ersten Mal
 * anfordert — und das dauert, je nach Maschine und Umfang des Bündels,
 * mehrere Sekunden.
 *
 * Ohne dieses Aufwärmen zahlt der allererste Test diese Zeit innerhalb seiner
 * eigenen Frist von zehn Sekunden. Genau dort ist er in der CI umgefallen:
 * `expect(page.getByRole("heading", { name: "Ersteinrichtung" }))` lief
 * 10,7 Sekunden ins Leere, während derselbe Test lokal 12,7 Sekunden braucht
 * und durchläuft. Das ist keine Aussage über die Oberfläche, sondern über die
 * Maschine — und `retries` wären die falsche Antwort darauf: sie würden einen
 * echten Fehler genauso verdecken.
 *
 * Deshalb wird die Zeit hierhin verschoben, wo sie hingehört: vor den ersten
 * Test, ohne Frist, die etwas behauptet.
 */
async function aufwaermen(): Promise<void> {
  const browser = await chromium.launch();
  try {
    const seite = await browser.newPage();
    await seite.goto(BASIS_URL, { timeout: KALTSTART });
    // Auf das Gerüst warten, nicht auf eine bestimmte Ansicht: welche Maske
    // dasteht, ist Sache der Tests. Hier geht es nur darum, dass überhaupt
    // etwas gerendert wurde.
    await seite.locator("#root > *").first().waitFor({ timeout: KALTSTART });
  } finally {
    await browser.close();
  }
}
