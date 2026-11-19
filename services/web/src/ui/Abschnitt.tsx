import type { ReactNode } from "react";

import { Regel } from "./Regel";
import stil from "./Abschnitt.module.css";

interface Props {
  titel: string;
  /** Für `aria-labelledby`, wo ein Bereich darin benannt werden muss. */
  id?: string | undefined;
  /** Der Satz neben der Überschrift - eine Zahl, eine knappe Erklärung. */
  beiwort?: ReactNode;
  /** Eine ausblendende Linie unter der Überschrift. Für lange Flächen, auf
   *  denen mehrere Abschnitte untereinander stehen. */
  regel?: boolean;
  children: ReactNode;
}

/**
 * Ein Abschnitt innerhalb einer Fläche: Überschrift in gesperrten
 * Kapitälchen, darunter der Inhalt.
 *
 * Er fasst beides zu **einem** Kind der Tafel zusammen, und das ist sein
 * eigentlicher Zweck. Die Tafel verteilt 2 rem zwischen ihren Abschnitten;
 * zwischen einer Überschrift und dem, was sie überschreibt, sind 2 rem aber
 * zu viel — dann gehört die Zeile optisch zu nichts mehr. Zusammengefasst
 * gilt nach außen der Abstand der Tafel und nach innen der hier.
 *
 * Kapitälchen und nicht eine größere Schrift: Die Fläche hat schon eine
 * Überschrift, und das hier ordnet nur noch innerhalb. Ein zweiter großer
 * Titel darunter machte eine Ebene auf, die es nicht gibt.
 */
export function Abschnitt({ titel, id, beiwort, regel = false, children }: Props) {
  return (
    <section className={stil.abschnitt} aria-labelledby={id}>
      <div className={stil.kopf}>
        <h2 id={id} className={stil.titel}>
          {titel}
        </h2>
        {beiwort && <p className={stil.beiwort}>{beiwort}</p>}
      </div>
      {regel && <Regel kurz className={stil.regel} />}
      {children}
    </section>
  );
}
