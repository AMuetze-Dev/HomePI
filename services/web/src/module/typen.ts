import type { ComponentType } from "react";

import type { ModulEintrag } from "../api/client";

/**
 * Wie viel Platz eine Ansicht beansprucht.
 *
 * Vorher entschied das die Hülle für alle gleich. Das ging so lange gut, wie
 * es ein Modul gab. Bei dreien ist es falsch: eine Geräteliste mit drei
 * Einträgen braucht keine 1088 px, eine Spielprüftabelle mit neun Bereichen
 * hätte gern mehr.
 *
 * Deshalb meldet das Modul seinen Bedarf an, und die Hülle richtet sich
 * danach. Vier Stufen, mehr braucht es nicht — eine fünfte wäre schon eine
 * Stufe, bei der niemand mehr sagen könnte, wann man sie nimmt.
 */
export type Breite =
  /** Eine Spalte zum Lesen. Formulare, Text, Einstellungen. */
  | "text"
  /** Voreinstellung. Karten und mittlere Listen. */
  | "normal"
  /** Dichte Listen, mehrspaltige Raster. */
  | "weit"
  /** Keine Begrenzung außer dem Seitenrand. Tabellen, Pläne, Übersichten. */
  | "voll";

/**
 * Ein Bereich innerhalb eines Moduls.
 *
 * Unterseiten sind echte Adressen (`/modul/staffelpilot/spiele`) und nicht
 * bloß ein Zustand im Modul. Der Unterschied ist keine Förmlichkeit:
 *
 *   - Ein Bereich lässt sich verlinken und als Lesezeichen ablegen.
 *   - Der Zurück-Knopf des Browsers führt zum vorigen Bereich statt aus dem
 *     Modul heraus.
 *   - Ein Neuladen landet dort, wo man war, und nicht wieder auf der ersten
 *     von neun Flächen.
 *
 * Der frühere Einwand dagegen lautete, ein Seitenwechsel bedeute einen neuen
 * Ladevorgang und damit die verlorene Stelle in der Liste. Das verwechselt
 * Unterseite mit Neuladen: Das Modul bleibt über allen Bereichen montiert,
 * seine Daten bleiben stehen, der Wechsel kostet keinen Abruf.
 */
export interface Unterseite {
  /** Erscheint in der Adresse. Kleinbuchstaben, keine Umlaute. */
  id: string;
  /** Steht in der Navigation. */
  wort: string;
  /**
   * Abweichende Breite für diesen Bereich. Ohne Angabe gilt die des Moduls.
   *
   * Das ist kein Feinschliff, sondern ein Fehler, den man sofort sieht: Ein
   * Modul mit neun Bereichen hat fast nie überall denselben Bedarf. Bei
   * StaffelPilot braucht die Spielprüfung jeden Millimeter, während das
   * Formular „Staffel anlegen" bei voller Breite Eingabefelder von 1400 px
   * bekommt — quer über den Monitor, mit dem Namensfeld links und der
   * Beschriftung außer Sichtweite.
   */
  breite?: Breite | undefined;
}

export interface ModulProps {
  modul?: ModulEintrag | undefined;
  /** Der aktive Bereich. Nur gesetzt, wenn das Modul Unterseiten anmeldet. */
  unterseite?: string | undefined;
}

/**
 * Der Vertrag zwischen einem Artefakt und der Hülle.
 *
 * Eine eigene Oberfläche ist optional. Ohne sie bekommt das Modul die
 * generische Ansicht, die seine Endpunkte aus dem OpenAPI-Schema liest — ein
 * neues Artefakt ist damit sofort benutzbar, auch bevor jemand ein Frontend
 * dafür geschrieben hat.
 *
 * Breite und Unterseiten sind ebenfalls optional. Ein Modul, das nichts
 * angibt, bekommt eine mittlere Spalte und keine zweite Navigationsebene —
 * und sieht damit aus wie alles andere, nur schlichter. Genau das ist
 * gemeint: derselbe Stil, unterschiedlicher Umfang.
 */
export interface ModulOberflaeche {
  /** Muss der Kennung aus dem Backend-Manifest entsprechen. */
  id: string;
  Komponente: ComponentType<ModulProps>;
  /** Voreinstellung: "normal". */
  breite?: Breite | undefined;
  /** Ohne Angabe hat das Modul keine zweite Navigationsebene. */
  unterseiten?: readonly Unterseite[] | undefined;
}
