/**
 * Die wenigen Symbole der Zeitmessung - die, die man von jedem Abspielgerät
 * kennt, dazu Tafel, Sprechblase und Stoppuhr.
 *
 * Eigene Striche statt einer Symbolbibliothek: Es sind sieben, und eine
 * Bibliothek dafür wöge mehr als dieses ganze Artefakt. Die Farbe kommt über
 * currentColor aus dem Text drumherum, also aus den Tokens.
 */

type Name =
  "praesentation" | "gespraech" | "gesamt" | "start" | "weiter" | "stopp" | "zurueck";

const PFADE: Record<Name, string[]> = {
  // Tafel auf einem Ständer
  praesentation: ["M3 4h18v11H3z", "M12 15v4", "M8 21l4-2 4 2"],
  // Sprechblase
  gespraech: ["M4 5h16v10H9l-5 4z"],
  // Stoppuhr
  gesamt: ["M12 21a8 8 0 1 0 0-16 8 8 0 0 0 0 16z", "M12 9v4l2.5 1.5", "M10 2h4"],
  start: ["M7 4l13 8-13 8z"],
  // Weiter zum Nächsten: Dreieck mit Strich
  weiter: ["M5 4l11 8-11 8z", "M19 4v16"],
  stopp: ["M6 6h12v12H6z"],
  // Kreispfeil gegen den Uhrzeigersinn
  zurueck: ["M4 12a8 8 0 1 0 2.3-5.7", "M4 4v4h4"],
};

export function Sinnbild({ name, gefuellt = false }: { name: Name; gefuellt?: boolean }) {
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
    >
      {PFADE[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
