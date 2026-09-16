import type { ModulOberflaeche } from "./typen";

/**
 * Eigene Oberflächen der Artefakte.
 *
 * Hier trägt sich ein Artefakt ein, das mehr will als die generische Ansicht.
 * Die Liste ist zur Build-Zeit fest - das ist der bewusste Unterschied zu
 * Module Federation: ein Bundle, ein Container, keine Laufzeit-Abhängigkeit
 * zwischen Frontend-Teilen. Der Preis ist ein neuer Shell-Build, wenn eine
 * Oberfläche dazukommt; das sind rund zwei Minuten in der CI.
 *
 * Kacheln auf der Startseite brauchen diesen Eintrag NICHT - die kommen aus
 * dem Manifest des Gateways und erscheinen ohne Frontend-Änderung.
 */
export const OBERFLAECHEN: readonly ModulOberflaeche[] = [
  // { id: "geraete", Komponente: GeraeteSeite },
];

export function oberflaecheFuer(id: string): ModulOberflaeche | undefined {
  return OBERFLAECHEN.find((o) => o.id === id);
}
