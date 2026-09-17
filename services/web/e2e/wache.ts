import { BASIS_URL } from "./umgebung";

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
}
