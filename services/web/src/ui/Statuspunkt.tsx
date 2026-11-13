import stil from "./Statuspunkt.module.css";

/**
 * „akzent" ist kein Signal, sondern eine Auszeichnung: etwas läuft gerade,
 * etwas ist das Gewählte. Die drei Signale daneben sagen, wie es steht -
 * dieser hier sagt nur, dass es gemeint ist.
 */
export type Ton = "gut" | "warnung" | "fehler" | "neutral" | "akzent";

interface Props {
  ton: Ton;
  /** Lässt den Punkt dezent pulsieren, solange etwas unterwegs ist. */
  laedt?: boolean;
}

/**
 * Rein dekorativ: die Bedeutung steht immer im Text daneben. Ein Zustand,
 * der nur über Farbe transportiert wird, ist für einen erheblichen Teil der
 * Nutzer gar kein Zustand.
 */
export function Statuspunkt({ ton, laedt = false }: Props) {
  const klassen = [stil.punkt, stil[ton], laedt ? stil.laedt : undefined]
    .filter(Boolean)
    .join(" ");

  return <span className={klassen} aria-hidden="true" />;
}
