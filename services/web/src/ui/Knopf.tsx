import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";

import stil from "./Knopf.module.css";

type Auspraegung = "primaer" | "sekundaer" | "leise";
type Groesse = "sm" | "md";

interface Aussehen {
  auspraegung?: Auspraegung;
  groesse?: Groesse;
  children: ReactNode;
}

type Props = Aussehen & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children">;

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
  ...rest
}: Props) {
  return (
    <button type={type} className={klassen(auspraegung, groesse, className)} {...rest}>
      {children}
    </button>
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
