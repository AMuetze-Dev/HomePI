import type { ButtonHTMLAttributes } from "react";

import stil from "./Quiz.module.css";

/**
 * Die Symbole des Quiz - eigene Striche statt einer Bibliothek, wie in der
 * Zeitmessung von ihk. Farbe über currentColor, also aus den Tokens.
 *
 * Ein Symbol ersetzt Text nur dort, wo es eindeutig ist (Abspielen, Schloss,
 * QR-Code). Jeder Knopf damit trägt seinen Namen trotzdem - für Screenreader
 * als aria-label, für alle anderen als Tooltip.
 */
export type Symbolname =
  | "qr"
  | "tafel"
  | "teams"
  | "schloss"
  | "offen"
  | "auswertung"
  | "schluessel"
  | "mehr"
  | "auge"
  | "verborgen"
  | "weiter"
  | "start"
  | "haken"
  | "kreuz"
  | "plus"
  | "minus"
  | "hochladen"
  | "pokal"
  | "ton"
  | "zurueck"
  | "spieler"
  | "pause"
  | "bild"
  | "liste";

const PFADE: Record<Symbolname, string[]> = {
  qr: [
    "M4 4h6v6H4z",
    "M14 4h6v6h-6z",
    "M4 14h6v6H4z",
    "M14 14h2v2h-2z",
    "M18 14h2",
    "M14 18v2h2",
    "M18 18h2v2",
  ],
  // Bildschirm auf Fuss - die Anzeigetafel
  tafel: ["M3 4h18v12H3z", "M8 20h8", "M12 16v4"],
  teams: [
    "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "M3 20a6 6 0 0 1 12 0",
    "M16 11a3 3 0 1 0 0-6",
    "M18 20a6 6 0 0 0-3-5.2",
  ],
  schloss: ["M5 11h14v10H5z", "M8 11V7a4 4 0 0 1 8 0v4"],
  offen: ["M5 11h14v10H5z", "M8 11V7a4 4 0 0 1 7.5-2"],
  auswertung: ["M4 20V10", "M10 20V4", "M16 20v-7", "M22 20H2"],
  schluessel: ["M15 7a4 4 0 1 1-3.9 4.9L3 20v-3h3v-3h3l2.1-2.1", "M16 6h.01"],
  mehr: ["M5 12h.01", "M12 12h.01", "M19 12h.01"],
  auge: [
    "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z",
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  ],
  verborgen: [
    "M3 3l18 18",
    "M10.6 6.1A10 10 0 0 1 12 6c6 0 10 6 10 6a17 17 0 0 1-3 3.6",
    "M6.6 6.6A17 17 0 0 0 2 12s4 7 10 7a9.7 9.7 0 0 0 5.4-1.6",
  ],
  weiter: ["M5 4l11 8-11 8z", "M19 4v16"],
  start: ["M7 4l13 8-13 8z"],
  haken: ["M4 12l5 5L20 6"],
  kreuz: ["M6 6l12 12", "M18 6L6 18"],
  plus: ["M12 5v14", "M5 12h14"],
  minus: ["M5 12h14"],
  hochladen: ["M12 16V4", "M7 9l5-5 5 5", "M4 20h16"],
  pokal: [
    "M8 4h8v5a4 4 0 0 1-8 0z",
    "M8 6H5a3 3 0 0 0 3 4",
    "M16 6h3a3 3 0 0 1-3 4",
    "M12 13v4",
    "M8 20h8",
  ],
  ton: ["M4 9h4l5-4v14l-5-4H4z", "M17 9a4 4 0 0 1 0 6"],
  zurueck: ["M15 5l-7 7 7 7"],
  spieler: ["M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", "M4 21a8 8 0 0 1 16 0"],
  pause: ["M8 5v14", "M16 5v14"],
  bild: ["M3 5h18v14H3z", "M3 16l5-5 4 4 3-3 6 6", "M15 9h.01"],
  liste: ["M9 6h12", "M9 12h12", "M9 18h12", "M4 6h.01", "M4 12h.01", "M4 18h.01"],
};

export function Symbol({
  name,
  gefuellt = false,
}: {
  name: Symbolname;
  gefuellt?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1.25em"
      height="1.25em"
      fill={gefuellt ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={stil.symbol}
    >
      {PFADE[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

/**
 * Ein Knopf aus einem Symbol. Der Name ist Pflicht: Ohne ihn wäre der Knopf
 * für einen Screenreader stumm und für alle anderen ein Rätsel.
 */
export function SymbolKnopf({
  symbol,
  name,
  aktiv = false,
  className,
  ...rest
}: {
  symbol: Symbolname;
  name: string;
  aktiv?: boolean;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "aria-label">) {
  return (
    <button
      type="button"
      aria-label={name}
      title={name}
      data-aktiv={aktiv || undefined}
      className={[stil.symbolknopf, className].filter(Boolean).join(" ")}
      {...rest}
    >
      <Symbol name={symbol} />
    </button>
  );
}
