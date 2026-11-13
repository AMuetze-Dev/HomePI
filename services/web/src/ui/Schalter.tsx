import stil from "./Schalter.module.css";

interface Props {
  beschriftung: string;
  an: boolean;
  beiWechsel: (an: boolean) => void;
}

/**
 * Ein Schalter für einen Zustand, der sofort gilt.
 *
 * Auf einem echten Kästchen gebaut: Leertaste, Tabulator und die Ansage
 * „Kontrollkästchen, aktiviert" kommen damit vom Browser. Ein `<button>`
 * mit `aria-pressed` wäre dasselbe in umständlicher - und in der Hälfte der
 * Nachbauten fehlt am Ende das Attribut.
 *
 * Die Beschriftung steht hier nur für Screenreader; sichtbar trägt sie die
 * Zeile links daneben. Ohne sie wäre der Schalter namenlos.
 */
export function Schalter({ beschriftung, an, beiWechsel }: Props) {
  return (
    <label className={stil.schalter}>
      <input
        type="checkbox"
        className={stil.feld}
        checked={an}
        onChange={(e) => beiWechsel(e.target.checked)}
      />
      <span className="nur-vorlesen">{beschriftung}</span>
      <span className={stil.bahn} aria-hidden="true">
        <span className={stil.griff} />
      </span>
    </label>
  );
}
