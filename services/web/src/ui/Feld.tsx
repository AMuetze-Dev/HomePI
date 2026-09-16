import { useId, type InputHTMLAttributes } from "react";

import stil from "./Feld.module.css";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  beschriftung: string;
  hinweis?: string | undefined;
}

/**
 * Beschriftung und Feld gehören zusammen - deshalb vergibt die Komponente
 * die Kennung selbst. Ein Feld ohne verbundenes Label ist für einen
 * Screenreader schlicht namenlos, und genau das passiert, wenn man das
 * Verbinden dem Aufrufer überlässt.
 */
export function Feld({ beschriftung, hinweis, className, ...rest }: Props) {
  const id = useId();
  const hinweisId = hinweis ? `${id}-hinweis` : undefined;

  return (
    <div className={[stil.gruppe, className].filter(Boolean).join(" ")}>
      <label className={stil.beschriftung} htmlFor={id}>
        {beschriftung}
      </label>
      <input id={id} className={stil.eingabe} aria-describedby={hinweisId} {...rest} />
      {hinweis && (
        <span id={hinweisId} className={stil.hinweis}>
          {hinweis}
        </span>
      )}
    </div>
  );
}
