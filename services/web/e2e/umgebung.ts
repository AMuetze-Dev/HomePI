/**
 * Wohin die Oberflächentests sprechen — an genau einer Stelle festgelegt.
 *
 * Die Voreinstellung ist **nicht** der Port der Entwicklungsumgebung. Wer
 * `npx playwright test` ohne alles startet, landet damit auf der eigenen
 * Testumgebung (`make e2e`) und nicht in der Datenbank, in der gerade jemand
 * arbeitet.
 */
export const BASIS_URL = process.env.E2E_URL ?? "http://127.0.0.1:5273";

/** Der Port, auf dem die Vorschau ausliefert - aus derselben Adresse. */
export const BASIS_PORT = Number(new URL(BASIS_URL).port || 80);

/**
 * Das Gateway, direkt und ohne den Proxy der Oberflaeche.
 *
 * Die Wache fragt hier nach dem Einrichtungsstand. Sie koennte das auch ueber
 * `/api` tun, aber dann haengt die Frage "ist diese Installation frisch?" an
 * einem Frontend-Server, der zu diesem Zeitpunkt noch nicht laufen muss - und
 * eine Wache, die am Weg scheitert statt an der Antwort, schuetzt nichts.
 */
export const API_URL = process.env.E2E_API_URL ?? `${BASIS_URL}/api`;
