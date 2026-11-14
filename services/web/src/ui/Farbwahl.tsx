import { useId } from "react";

import stil from "./Farbwahl.module.css";

export interface Farbe<W extends string> {
  wert: W;
  wort: string;
}

interface Props<W extends string> {
  /** Benennt die Gruppe für Screenreader. */
  beschriftung: string;
  optionen: readonly Farbe<W>[];
  wert: W;
  beiWahl: (wert: W) => void;
}

/**
 * Eine Wahl, bei der man die Farbe sieht und nicht nur ihren Namen.
 *
 * „Glut" und „Moos" sagen einem nichts, bevor man sie einmal gesehen hat —
 * eine Liste aus Wörtern wäre hier ein Ratespiel. Jeder Eintrag zeigt
 * deshalb einen Tupfen in genau der Farbe, die die Oberfläche annehmen
 * wird, und das Wort darunter.
 *
 * **Der Tupfen holt seine Farbe aus derselben Quelle wie die Oberfläche.**
 * Er trägt `data-grund` selbst, und weil die Wähler in `tokens.css` nicht
 * auf `:root` festgenagelt sind, gilt der Satz Werte auch für ihn. Eine
 * zweite Liste von Hexwerten für die Vorschau wäre die erste, die veraltet.
 *
 * Auf echten Optionsfeldern gebaut wie die Segmentwahl: Pfeiltasten,
 * Gruppenansage und die Frage „welche ist gewählt" bringt der Browser mit.
 * Den Namen trägt das Wort, nicht der Tupfen — eine Farbe ist für einen
 * Screenreader nichts.
 */
export function Farbwahl<W extends string>({
  beschriftung,
  optionen,
  wert,
  beiWahl,
}: Props<W>) {
  const name = useId();

  return (
    <div className={stil.gruppe} role="radiogroup" aria-label={beschriftung}>
      {optionen.map((option) => (
        <label key={option.wert} className={stil.farbe}>
          <input
            type="radio"
            className={stil.feld}
            name={name}
            value={option.wert}
            checked={option.wert === wert}
            onChange={() => beiWahl(option.wert)}
          />
          <span className={stil.tupfen} data-grund={option.wert} aria-hidden="true" />
          <span className={stil.wort}>{option.wort}</span>
        </label>
      ))}
    </div>
  );
}
