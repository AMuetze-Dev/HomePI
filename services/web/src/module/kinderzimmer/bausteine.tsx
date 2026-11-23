import { useId, type TextareaHTMLAttributes } from "react";

import stil from "./KinderzimmerSeite.module.css";

/**
 * Drei Eingaben, die `src/ui` nicht hat: Auswahlliste, mehrzeiliger Text,
 * Schieberegler mit Zahl. Sie sehen aus wie `Feld` und sind wie dort über
 * die Beschriftung erreichbar.
 */

export function Auswahl<W extends string>({
  beschriftung,
  wert,
  optionen,
  beiWahl,
  disabled,
}: {
  beschriftung: string;
  wert: W;
  optionen: readonly (readonly [W, string])[];
  beiWahl: (wert: W) => void;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className={stil.auswahl}>
      <label htmlFor={id}>{beschriftung}</label>
      <select
        id={id}
        value={wert}
        disabled={disabled}
        onChange={(e) => beiWahl(e.target.value as W)}
      >
        {optionen.map(([w, wort]) => (
          <option key={w} value={w}>
            {wort}
          </option>
        ))}
      </select>
    </div>
  );
}

export function Textfeld({
  beschriftung,
  ...rest
}: { beschriftung: string } & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id">) {
  const id = useId();
  return (
    <div className={stil.textfeld}>
      <label htmlFor={id}>{beschriftung}</label>
      <textarea id={id} {...rest} />
    </div>
  );
}

export function Regler({
  beschriftung,
  wert,
  min,
  max,
  einheit,
  hinweis,
  beiWechsel,
  disabled,
}: {
  beschriftung: string;
  wert: number;
  min: number;
  max: number;
  einheit: string;
  hinweis?: string;
  beiWechsel: (wert: number) => void;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className={stil.regler}>
      <label htmlFor={id}>{beschriftung}</label>
      <div className={stil.reglerzeile}>
        <input
          id={id}
          type="range"
          min={min}
          max={max}
          value={wert}
          disabled={disabled}
          onChange={(e) => beiWechsel(Number(e.target.value))}
        />
        <output htmlFor={id}>
          {wert} {einheit}
        </output>
      </div>
      {hinweis && <p className={stil.nebensache}>{hinweis}</p>}
    </div>
  );
}
