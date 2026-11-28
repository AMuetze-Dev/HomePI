import type { Platz } from "./api";
import stil from "./Quiz.module.css";

/**
 * Name und Punkte, mehr nicht - genau das, was die Schnittstelle ohne Konto
 * überhaupt herausgibt.
 */
export function Rangliste({
  plaetze,
  hervorheben,
  gross = false,
}: {
  plaetze: Platz[];
  hervorheben?: string | undefined;
  gross?: boolean;
}) {
  if (plaetze.length === 0) {
    return <p className={stil.nebensache}>Noch spielt niemand mit.</p>;
  }
  return (
    <ol className={stil.rangliste} data-gross={gross} aria-label="Rangliste">
      {plaetze.map((platz) => (
        <li
          key={platz.name}
          className={stil.platz}
          aria-current={platz.name === hervorheben ? "true" : undefined}
        >
          <span className={stil.rang}>{platz.rang}.</span>
          <span className={stil.platzname}>{platz.name}</span>
          <span className={stil.platzpunkte}>{platz.punkte}</span>
        </li>
      ))}
    </ol>
  );
}
