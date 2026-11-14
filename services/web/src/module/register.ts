import { GeraeteSeite } from "./geraete/GeraeteSeite";
import type { Breite, ModulOberflaeche, Unterseite } from "./typen";
import { StaffelpilotSeite } from "./staffelpilot/StaffelpilotSeite";
import { VerwaltungSeite } from "./verwaltung/VerwaltungSeite";
import { HaushaltsbuchSeite } from "./haushaltsbuch/HaushaltsbuchSeite";
import { TischtennisSeite } from "./tischtennis/TischtennisSeite";

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
    id: "haushaltsbuch",
    Komponente: HaushaltsbuchSeite,
    // Je Person eine Bilanzkarte nebeneinander, darunter Tabellen mit
    // Rhythmus und Betrag. Bei "normal" stehen die Karten untereinander und
    // der Vergleich, um den es geht, findet nicht mehr statt.
    breite: "weit",
    unterseiten: [
      { id: "uebersicht", wort: "Monatsplan" },
      // Ein Bild, das ganz von der Breite lebt: jede Spalte ist eine Station,
      // und die Beschriftung steht daneben, nicht darunter.
      { id: "fluss", wort: "Geldfluss", breite: "voll" },
      { id: "posten", wort: "Posten" },
      // Formulare. Ein Eingabefeld über die ganze Monitorbreite ist nicht
      // großzügig, sondern unlesbar.
      { id: "stammdaten", wort: "Konten & Personen", breite: "normal" },
    ],
  },
  {
    id: "staffelpilot",
    Komponente: StaffelpilotSeite,
    // Grundmaß für die Flächen, die Listen zeigen. Die Bereiche, bei denen
    // das falsch wäre, sagen es unten selbst.
    breite: "voll",
    // Jeder Bereich baut seinen Kopf selbst: Neben dem Namen steht hier
    // ueberall etwas, das nur der Bereich kennt - eine Zahl, ein Filter, die
    // eine Handlung dieser Flaeche. Siehe `eigenerTitel` in typen.ts.
    unterseiten: [
      // Kennzahlen und die Liste des Tages - lebt von der Breite.
      { id: "uebersicht", wort: "Übersicht", eigenerTitel: true },
      // Paarung, Datum, Befunde, Aktionen in einer Zeile. Der Grund, warum
      // dieses Modul überhaupt "voll" bekommt.
      { id: "spiele", wort: "Spielprüfung", eigenerTitel: true },
      { id: "prueflauf", wort: "Prüflauf", breite: "normal", eigenerTitel: true },
      { id: "ergebnisse", wort: "Ergebnisse", breite: "weit", eigenerTitel: true },
      // Formulare. Ein Eingabefeld über die ganze Monitorbreite ist nicht
      // großzügig, sondern unlesbar: Der Blick findet den Anfang der
      // nächsten Zeile nicht mehr.
      { id: "staffeln", wort: "Staffeln", breite: "normal", eigenerTitel: true },
      { id: "vorgaenge", wort: "Vorgänge", breite: "weit", eigenerTitel: true },
      { id: "regeln", wort: "Regeln", breite: "normal", eigenerTitel: true },
      // Quelltext. Breiter als ein Formular, denn hier steht Python mit
      // Einrückung -- in einer Textspalte bricht jede zweite Zeile um.
      { id: "regeldateien", wort: "Regeldateien", breite: "normal", eigenerTitel: true },
      { id: "einstellungen", wort: "Einstellungen", breite: "text", eigenerTitel: true },
      { id: "zugang", wort: "DFBnet-Zugang", breite: "text", eigenerTitel: true },
      // Ein Weg, keine Flaeche: einmal durchlaufen, danach nur noch bei
      // Bedarf aus den Einstellungen heraus. Deshalb versteckt -- in der
      // Leiste waere es ein Eintrag, der ab dem zweiten Tag nur stoert.
      {
        id: "einrichten",
        wort: "Einrichtung",
        breite: "text",
        versteckt: true,
        eigenerTitel: true,
      },
    ],
  },
  {
    id: "tischtennis",
    Komponente: TischtennisSeite,
    // Die Dashboard-Ansicht lebt von der Breite: zwei Tische nebeneinander,
    // darunter Gruppen und Raster.
    breite: "weit",
    // Jeder Bereich baut seinen Kopf selbst: Neben dem Namen steht hier
    // ueberall etwas, das nur der Bereich kennt - das Turnier, sein Zustand,
    // seine Zahlen. Siehe `eigenerTitel` in typen.ts.
    unterseiten: [
      // Zuerst, und das mit Absicht: diese Flaeche ist der Grund, warum das
      // Artefakt oeffentlich ist. Wer die Kachel ohne Konto antippt, landet
      // auf der ersten Unterseite - also hier.
      { id: "dashboard", wort: "Dashboard", breite: "voll", eigenerTitel: true },
      // Teilnehmer, Auswuerfeln und Spielplan in einem. Drei Reiter waren
      // richtig, solange ein Ergebnis aus sechs Zahlen bestand; seit es ein
      // Name ist, sind es zwei Handgriffe und einer zu viel.
      { id: "turnier", wort: "Turnier", eigenerTitel: true },
      { id: "einstellungen", wort: "Einstellungen", breite: "text", eigenerTitel: true },
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
 * Dieselbe Liste ohne die versteckten.
 *
 * Die Navigation nimmt diese, alles andere die ganze: eine versteckte
 * Unterseite ist eine echte Adresse und soll sich verlinken, neu laden und
 * mit dem Zurück-Knopf verlassen lassen — sie steht nur in keiner Leiste.
 */
export function sichtbareUnterseiten(id: string): readonly Unterseite[] {
  return unterseitenFuer(id).filter((u) => !u.versteckt);
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
