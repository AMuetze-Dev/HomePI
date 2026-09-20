import { GeraeteSeite } from "./geraete/GeraeteSeite";
import type { Breite, ModulOberflaeche, Unterseite } from "./typen";
import { StaffelpilotSeite } from "./staffelpilot/StaffelpilotSeite";
import { VerwaltungSeite } from "./verwaltung/VerwaltungSeite";

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
 *
 * Neben der Komponente steht hier der Platzbedarf und die zweite
 * Navigationsebene. Beides gehört in dieselbe Zeile wie die Komponente und
 * nicht in die jeweilige Ansicht: So steht an einer Stelle, wie sich die
 * Artefakte zueinander verhalten, statt verteilt auf drei Dateien.
 */
export const OBERFLAECHEN: readonly ModulOberflaeche[] = [
  {
    id: "staffelpilot",
    Komponente: StaffelpilotSeite,
    // Grundmaß für die Flächen, die Listen zeigen. Die Bereiche, bei denen
    // das falsch wäre, sagen es unten selbst.
    breite: "voll",
    unterseiten: [
      // Kennzahlen und die Liste des Tages - lebt von der Breite.
      { id: "uebersicht", wort: "Übersicht" },
      // Paarung, Datum, Befunde, Aktionen in einer Zeile. Der Grund, warum
      // dieses Modul überhaupt "voll" bekommt.
      { id: "spiele", wort: "Spielprüfung" },
      { id: "prueflauf", wort: "Prüflauf", breite: "normal" },
      { id: "ergebnisse", wort: "Ergebnisse", breite: "weit" },
      // Formulare. Ein Eingabefeld über die ganze Monitorbreite ist nicht
      // großzügig, sondern unlesbar: Der Blick findet den Anfang der
      // nächsten Zeile nicht mehr.
      { id: "staffeln", wort: "Staffeln", breite: "normal" },
      { id: "vorgaenge", wort: "Vorgänge", breite: "weit" },
      { id: "regeln", wort: "Regeln", breite: "normal" },
      { id: "einstellungen", wort: "Einstellungen", breite: "text" },
      { id: "zugang", wort: "DFBnet-Zugang", breite: "text" },
    ],
  },
  {
    id: "geraete",
    Komponente: GeraeteSeite,
    // Eine Liste, ein Formular. Mehr Breite macht sie nicht besser, nur
    // die Wege zwischen Name und Aktion laenger.
    breite: "normal",
  },
  {
    id: "verwaltung",
    Komponente: VerwaltungSeite,
    breite: "normal",
  },
];

export function oberflaecheFuer(id: string): ModulOberflaeche | undefined {
  return OBERFLAECHEN.find((o) => o.id === id);
}

/** Voreinstellung für Module ohne eigene Oberfläche. */
export const BREITE_VOREINSTELLUNG: Breite = "normal";

/**
 * Die Breite für ein Modul, wahlweise für einen bestimmten Bereich.
 *
 * Drei Stufen, von genau nach grob: Bereich, dann Modul, dann
 * Voreinstellung. Damit muss ein Bereich nur dann etwas sagen, wenn er vom
 * Modul abweicht - und die Liste im Register bleibt lesbar.
 */
export function breiteFuer(id: string, unterseite?: string): Breite {
  const oberflaeche = oberflaecheFuer(id);
  const bereich = unterseite
    ? oberflaeche?.unterseiten?.find((u) => u.id === unterseite)
    : undefined;
  return bereich?.breite ?? oberflaeche?.breite ?? BREITE_VOREINSTELLUNG;
}

export function unterseitenFuer(id: string): readonly Unterseite[] {
  return oberflaecheFuer(id)?.unterseiten ?? [];
}

/**
 * Die erste Unterseite ist die Startfläche des Moduls.
 *
 * Bewusst die erste aus der Liste und keine eigene Angabe: Zwei Stellen, die
 * festlegen, womit ein Modul beginnt, laufen irgendwann auseinander.
 */
export function ersteUnterseite(id: string): string | undefined {
  return unterseitenFuer(id)[0]?.id;
}
