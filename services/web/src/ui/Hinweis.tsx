import type { ReactNode } from "react";

import stil from "./Hinweis.module.css";
import { Statuspunkt, type Ton } from "./Statuspunkt";

interface Props {
  children: ReactNode;
  ton?: Extract<Ton, "fehler" | "warnung" | "neutral">;
  /** role="alert" meldet die Nachricht sofort an Screenreader. */
  dringend?: boolean;
}

export function Hinweis({ children, ton = "neutral", dringend = false }: Props) {
  return (
    <div
      className={[stil.hinweis, stil[ton]].join(" ")}
      role={dringend ? "alert" : "status"}
    >
      <span className={stil.punkt}>
        <Statuspunkt ton={ton} />
      </span>
      <span>{children}</span>
    </div>
  );
}
