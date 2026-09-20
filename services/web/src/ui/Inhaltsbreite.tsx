import type { ReactNode } from "react";

import type { Breite } from "../module/typen";
import stil from "./Inhaltsbreite.module.css";

interface Props {
  breite?: Breite | undefined;
  children: ReactNode;
}

// string | undefined, weil die Typen fuer CSS-Module genau das liefern -
// eine Klasse, die es in der Datei nicht gibt, ist zur Laufzeit undefined.
const KLASSE: Record<Breite, string | undefined> = {
  text: stil.text,
  normal: stil.normal,
  weit: stil.weit,
  voll: stil.voll,
};

/**
 * Begrenzt, wie breit eine Ansicht werden darf.
 *
 * Steht bewusst um den Inhalt herum und nicht in der Hülle: Die Hülle weiß
 * nicht, was sie anzeigt, und eine einzige Breite für alles war genau der
 * Fehler, den diese Komponente behebt. Eine Geräteliste mit drei Einträgen
 * und eine Spielprüftabelle haben verschiedene Bedürfnisse.
 *
 * Welche Stufe ein Artefakt bekommt, steht in `src/module/register.ts`.
 */
export function Inhaltsbreite({ breite = "normal", children }: Props) {
  return <div className={KLASSE[breite]}>{children}</div>;
}
