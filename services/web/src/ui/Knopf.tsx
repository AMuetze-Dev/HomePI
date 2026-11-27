import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";

import stil from "./Knopf.module.css";

type Auspraegung = "primaer" | "sekundaer" | "leise";
type Groesse = "sm" | "md";

interface Aussehen {
  auspraegung?: Auspraegung;
  groesse?: Groesse;
  children: ReactNode;
}

type Props = Aussehen &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
    /** Warum der Knopf gesperrt ist - erscheint beim Darüberfahren, nur solange er es ist. */
    grund?: string | undefined;
  };

type VerweisProps = Aussehen &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "children"> & { href: string };

function klassen(
  auspraegung: Auspraegung,
  groesse: Groesse,
  className: string | undefined,
): string {
  return [stil.knopf, stil[auspraegung], stil[groesse], className]
    .filter(Boolean)
    .join(" ");
}

/**
 * Es gibt genau drei Ausprägungen, und das ist Absicht: sobald eine vierte
 * dazukommt, hat die Seite eine Hierarchie zu viel und keine ist mehr klar.
 *
 * - primaer:   die eine Handlung, um die es auf dieser Fläche geht
 * - sekundaer: gleichwertige Alternativen daneben
 * - leise:     alles, was nur mitläuft
 */
export function Knopf({
  auspraegung = "sekundaer",
  groesse = "md",
  type = "button",
  className,
  children,
  grund,
  ...rest
}: Props) {
  if (grund === undefined) {
    return (
      <button type={type} className={klassen(auspraegung, groesse, className)} {...rest}>
        {children}
      </button>
    );
  }

  // Mit Grund steht eine Hülle um den Knopf, und zwar immer, nicht nur im
  // gesperrten Zustand: Sonst sprünge das Layout, sobald er frei wird. Den
  // title trägt die Hülle, weil ein gesperrter <button> keine
  // Mausereignisse bekommt und mancher Browser seinen title deshalb nicht
  // zeigt. Die Lage im Layout (className) gehört der Hülle, der Knopf füllt
  // sie aus.
  return (
    <span
      className={[stil.huelle, className].filter(Boolean).join(" ")}
      title={rest.disabled ? grund : undefined}
    >
      <button
        type={type}
        className={klassen(auspraegung, groesse, stil.fuellend)}
        {...rest}
      >
        {children}
      </button>
    </span>
  );
}

/**
 * Ein Verweis, der aussieht wie ein Knopf - etwa für ein PDF, das in den
 * Download-Ordner oder den Viewer des Browsers geht. Beides kann die Seite
 * nicht besser, und ein <a> sagt dem Screenreader ehrlich, dass es dorthin
 * geht statt etwas auszulösen.
 *
 * Vorher baute jedes Artefakt das Aussehen mit eigenen Regeln nach - und
 * eines griff dabei auf drei Größen zurück, die es nicht gab.
 */
export function KnopfVerweis({
  auspraegung = "sekundaer",
  groesse = "md",
  className,
  children,
  ...rest
}: VerweisProps) {
  return (
    <a className={klassen(auspraegung, groesse, className)} {...rest}>
      {children}
    </a>
  );
}
