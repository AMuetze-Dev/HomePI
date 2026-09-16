import stil from "./Platzhalter.module.css";

interface Props {
  breite?: string;
  hoehe?: string;
  className?: string | undefined;
}

/**
 * Füllt den Platz, den der echte Inhalt gleich einnimmt. Das verhindert den
 * Sprung beim Nachladen - der Layoutsprung ist das, was eine Oberfläche
 * unfertig wirken lässt, nicht die Wartezeit selbst.
 */
export function Platzhalter({ breite = "100%", hoehe = "1rem", className }: Props) {
  return (
    <span
      className={[stil.platzhalter, className].filter(Boolean).join(" ")}
      style={{ display: "block", width: breite, height: hoehe }}
      aria-hidden="true"
    />
  );
}
