import { Abschnitt, Etikett } from "../../ui";
import type { Phase, Spiel } from "./api";
import stil from "./KinderzimmerSeite.module.css";

interface Props {
  phasen: readonly Phase[];
  spiele: readonly Spiel[];
}

/**
 * Alle Spiele, nach Entwicklungsphase - auch die, die das Gerät noch nicht
 * kann.
 *
 * Die geplanten stehen mit Absicht hier: Wer sieht, was in einem Jahr kommt,
 * versteht besser, warum das Gerät jetzt nur leuchtet und klingt. Und die
 * Begründung steht bei jedem Spiel offen da, nicht hinter einem Klick: Sie
 * ist der Grund, warum es diese Seite gibt.
 */
export function SpieleTafel({ phasen, spiele }: Props) {
  return (
    <>
      {phasen.map((phase) => (
        <Abschnitt
          key={phase.nummer}
          titel={`Phase ${phase.nummer} · ${phase.titel}`}
          beiwort={phase.alter}
          regel
        >
          <div className={stil.phase}>
            {spiele
              .filter((s) => s.phase === phase.nummer)
              .map((spiel) => (
                <SpielText key={spiel.id} spiel={spiel} />
              ))}
          </div>
        </Abschnitt>
      ))}
    </>
  );
}

function Zustand({ spiel }: { spiel: Spiel }) {
  if (!spiel.bereit) return <Etikett>geplant</Etikett>;
  if (spiel.aktiv) return <Etikett ton="gut">eingeschaltet</Etikett>;
  return <Etikett ton="warnung">ausgeschaltet</Etikett>;
}

function SpielText({ spiel }: { spiel: Spiel }) {
  const kennung = `spiel-${spiel.id}`;
  return (
    <article
      className={[stil.spiel, spiel.bereit ? undefined : stil.geplant]
        .filter(Boolean)
        .join(" ")}
      aria-labelledby={kennung}
    >
      <div className={stil.spielkopf}>
        <h3 id={kennung} className={stil.spieltitel}>
          <span className={stil.spielnummer}>{spiel.nummer}. </span>
          {spiel.titel}
        </h3>
        <Zustand spiel={spiel} />
        <span className={stil.nebensache}>{spiel.alter}</span>
      </div>
      <dl className={stil.spieltexte}>
        <dt>So geht’s</dt>
        <dd>{spiel.ablauf}</dd>
        <dt>Das fördert es</dt>
        <dd>{spiel.foerdert}</dd>
        <dt>Warum das wirkt</dt>
        <dd>{spiel.warum}</dd>
      </dl>
    </article>
  );
}
