/**
 * Wohin die Oberflächentests sprechen — an genau einer Stelle festgelegt.
 *
 * Die Voreinstellung ist **nicht** der Port der Entwicklungsumgebung. Wer
 * `npx playwright test` ohne alles startet, landet damit auf der eigenen
 * Testumgebung (`make e2e`) und nicht in der Datenbank, in der gerade jemand
 * arbeitet.
 */
export const BASIS_URL = process.env.E2E_URL ?? "http://127.0.0.1:5273";
