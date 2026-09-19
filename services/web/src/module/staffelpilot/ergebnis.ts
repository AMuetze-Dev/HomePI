import type { AuftragZeile } from "./api";

/**
 * Was ein beendeter Auftrag gebracht hat — in seinen eigenen Worten.
 *
 * „0 geprüft, 0 Befunde" unter einer Initialisierung ist keine Auskunft,
 * sondern eine Verwechslung: die holt Mannschaften und prüft nichts. Und ein
 * Lauf, der nichts tun konnte, soll den Grund nennen und nicht eine Null.
 */
export function ergebnisSatz(z: AuftragZeile): string {
  if (z.meldung) return z.meldung;
  if (z.zustand === "angefordert") return "Wartet auf den Prüfdienst";
  if (z.art === "initialisierung") return "Mannschaften geholt";
  if (z.gepruefte === 0) return "Keine Spielberichte im Prüfzeitraum";
  return `${z.gepruefte} geprüft, ${z.befunde} Befunde`;
}
