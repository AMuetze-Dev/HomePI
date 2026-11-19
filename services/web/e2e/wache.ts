import { API_URL, BASIS_URL } from "./umgebung";

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
 *
 * **Sie fragt das Gateway direkt**, nicht über `/api` und damit nicht über die
 * Oberfläche. Die kommt inzwischen von `vite preview`, gestartet von Playwright
 * selbst — und ob das vor oder nach dieser Datei geschieht, ist eine Zusage,
 * auf die sich eine Wache nicht stützen sollte. Gefragt ist der
 * Einrichtungsstand des Backends; wer dafür den Weg über den Frontend-Proxy
 * nimmt, scheitert irgendwann am Weg statt an der Antwort und schützt dann
 * nichts mehr.
 */
export default async function wache(): Promise<void> {
  const adresse = `${API_URL}/auth/einrichtung`;

  let antwort: Response;
  try {
    antwort = await fetch(adresse);
  } catch (grund) {
    throw new Error(
      `Unter ${API_URL} antwortet kein Gateway (${String(grund)}).\n` +
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
}
