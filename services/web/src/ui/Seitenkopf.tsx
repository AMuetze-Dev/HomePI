import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import stil from "./Seitenkopf.module.css";

interface Props {
  titel: string;
  beschreibung?: string | undefined;
  /** Rechts neben dem Titel - etwa ein Zustandsetikett. */
  neben?: ReactNode | undefined;
  zurueck?: { ziel: string; text: string } | undefined;
}

export function Seitenkopf({ titel, beschreibung, neben, zurueck }: Props) {
  return (
    <div className={stil.kopf}>
      {zurueck && (
        <Link to={zurueck.ziel} className={stil.zurueck}>
          <svg
            className={stil.pfeil}
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M10 3 5 8l5 5" />
          </svg>
          {zurueck.text}
        </Link>
      )}

      <div className={stil.zeile}>
        <h1 className={stil.titel}>{titel}</h1>
        {neben}
      </div>

      {beschreibung && <p className={stil.beschreibung}>{beschreibung}</p>}
    </div>
  );
}
