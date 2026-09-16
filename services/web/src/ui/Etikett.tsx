import type { ReactNode } from "react";

import stil from "./Etikett.module.css";
import type { Ton } from "./Statuspunkt";

interface Props {
  children: ReactNode;
  ton?: Ton;
  /** Monospace - für Versionen, Kennungen, alles Technische. */
  mono?: boolean;
}

export function Etikett({ children, ton = "neutral", mono = false }: Props) {
  const klassen = [stil.etikett, stil[ton], mono ? stil.mono : undefined]
    .filter(Boolean)
    .join(" ");

  return <span className={klassen}>{children}</span>;
}
