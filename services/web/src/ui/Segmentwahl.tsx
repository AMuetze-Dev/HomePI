import { useId } from "react";

import stil from "./Segmentwahl.module.css";

export interface Segment<W extends string> {
  wert: W;
  wort: string;
}

interface Props<W extends string> {
  /** Benennt die Gruppe für Screenreader. Sichtbar steht meist schon eine
   *  Zeile daneben - deshalb trägt die Beschriftung hier nur der Rahmen. */
  beschriftung: string;
  optionen: readonly Segment<W>[];
  wert: W;
  beiWahl: (wert: W) => void;
}

/**
 * Zwei bis vier Möglichkeiten nebeneinander, eine davon gewählt.
 *
 * Auf echten Optionsfeldern gebaut und nicht auf Knöpfen: Pfeiltasten,
 * Gruppenansage und die Frage „welche ist gewählt" bringt der Browser von
 * sich aus mit. Ein nachgebautes Element müsste das alles erst wieder
 * lernen, und es lernt es erfahrungsgemäß halb.
 *
 * Die Felder selbst sind unsichtbar - sichtbar ist das Wort dahinter. Nicht
 * `display: none`: damit verschwindet das Feld auch aus der Tastaturfolge
 * und aus dem Screenreader.
 */
export function Segmentwahl<W extends string>({
  beschriftung,
  optionen,
  wert,
  beiWahl,
}: Props<W>) {
  const name = useId();

  return (
    <div className={stil.gruppe} role="radiogroup" aria-label={beschriftung}>
      {optionen.map((option) => (
        <label key={option.wert} className={stil.segment}>
          <input
            type="radio"
            className={stil.feld}
            name={name}
            value={option.wert}
            checked={option.wert === wert}
            onChange={() => beiWahl(option.wert)}
          />
          <span className={stil.wort}>{option.wort}</span>
        </label>
      ))}
    </div>
  );
}
