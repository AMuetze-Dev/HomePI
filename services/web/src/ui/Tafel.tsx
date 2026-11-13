import type { ReactNode } from "react";

import { Regel } from "./Regel";
import stil from "./Tafel.module.css";

interface Props {
  titel: string;
  /**
   * Der Satz neben dem Titel: was gerade ansteht, in Zahlen.
   *
   * Nicht darunter und nicht als Kennzahl daneben, sondern in derselben
   * Zeile — er beantwortet die Frage, mit der man die Fläche aufmacht
   * („wie viel ist es"), und soll mit dem Titel zusammen gelesen werden.
   */
  beiwort?: ReactNode;
  /** Rechtsbündig in der Titelzeile: ein bis zwei Handlungen, mehr nicht. */
  aktionen?: ReactNode;
  children: ReactNode;
}

/**
 * Eine Fläche innerhalb eines Artefakts: Titelzeile, Linie, Inhalt.
 *
 * Bis hierher baute jede Tafel ihren Kopf selbst, und entsprechend sah er
 * überall anders aus: einmal `<h2>` allein, einmal Titel mit Knopf daneben,
 * einmal gar keiner. Dass ein Artefakt mit zehn Flächen dabei
 * auseinanderläuft, ist keine Nachlässigkeit, sondern die Folge davon, dass
 * es keinen gemeinsamen Ort gab.
 *
 * Die Linie darunter ist dieselbe wie überall — an beiden Enden
 * ausblendend. Sie trennt, ohne einen Kasten zu zeichnen.
 *
 * Der Titel ist ein `<h1>`: Eine Tafel ist die Überschrift der Ansicht, und
 * wo sie steht, setzt die Modulseite keine zweite darüber
 * (`eigenerTitel` in `src/module/typen.ts`). Abschnitte **innerhalb** einer
 * Tafel bleiben `<h2>` — so stimmt die Gliederung, ohne dass jemand einen
 * Rang von Hand mitgeben muss.
 */
export function Tafel({ titel, beiwort, aktionen, children }: Props) {
  return (
    <section className={stil.tafel}>
      <div className={stil.kopf}>
        <h1 className={stil.titel}>{titel}</h1>
        {beiwort && <p className={stil.beiwort}>{beiwort}</p>}
        {aktionen && <div className={stil.aktionen}>{aktionen}</div>}
      </div>
      <Regel className={stil.regel} />
      {children}
    </section>
  );
}
