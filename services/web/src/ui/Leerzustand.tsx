import type { ReactNode } from "react";

import stil from "./Leerzustand.module.css";

interface Props {
  titel: string;
  children: ReactNode;
  aktion?: ReactNode | undefined;
}

/**
 * Der Erstzustand ist der erste Eindruck. Eine leere Fläche ohne Erklärung
 * lässt ratlos zurück - hier steht deshalb immer, was als Nächstes zu tun
 * ist.
 */
export function Leerzustand({ titel, children, aktion }: Props) {
  return (
    <div className={stil.leer}>
      <p className={stil.titel}>{titel}</p>
      <p className={stil.text}>{children}</p>
      {aktion && <div className={stil.aktion}>{aktion}</div>}
    </div>
  );
}
