import type { ButtonHTMLAttributes, ReactNode } from "react";

import stil from "./Knopf.module.css";

type Auspraegung = "primaer" | "sekundaer" | "leise";
type Groesse = "sm" | "md";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  auspraegung?: Auspraegung;
  groesse?: Groesse;
  children: ReactNode;
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
  const klassen = [stil.knopf, stil[auspraegung], stil[groesse], className]
    .filter(Boolean)
    .join(" ");

  return (
    <button type={type} className={klassen} {...rest}>
      {children}
    </button>
  );
}
