import type { ReactNode } from "react";

import stil from "./Karte.module.css";

interface Props {
  children: ReactNode;
  /** Ohne Innenabstand, wenn der Inhalt selbst einer mitbringt (z.B. Tabellen). */
  blank?: boolean;
  className?: string | undefined;
}

export function Karte({ children, blank = false, className }: Props) {
  const klassen = [stil.karte, blank ? undefined : stil.innen, className]
    .filter(Boolean)
    .join(" ");

  return <div className={klassen}>{children}</div>;
}
