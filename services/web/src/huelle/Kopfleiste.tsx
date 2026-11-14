import { Link, useMatch } from "react-router-dom";

import { useModule } from "../module/useModule";
import { Marke } from "../ui";
import { Bereichsleiste } from "./Bereichsleiste";
import { Benutzerleiste } from "./Benutzerleiste";
import stil from "./Kopfleiste.module.css";

interface Props {
  /** Gibt es überhaupt etwas zu navigieren? Abgemeldet nicht. */
  navigierbar: boolean;
  navOffen: boolean;
  beiNavigation: () => void;
}

/**
 * Eine Zeile über allem: Zeichen, Weg, Bereiche, Konto.
 *
 * Sie beantwortet, wo man ist — und lässt einen dort weitergehen. Die
 * Bereiche des geöffneten Artefakts stehen in **dieser** Zeile und nicht in
 * einer zweiten darunter: Eine Leiste, die nur sagt, wo man ist, und eine
 * zweite, mit der man sich bewegt, sind zwei Zeilen für eine Aufgabe. Das
 * letzte Glied der Brotkrume entfällt dafür — welcher Bereich gilt, steht
 * schon an der Markierung in den Bereichen daneben.
 *
 * Die frühere Kopfzeile trug Umschalter und Knöpfe; die stehen jetzt dort,
 * wo sie hingehören, nämlich in den Einstellungen und in der Navigation.
 *
 * Auf der Startseite sieht sie anders aus: Dort gibt es keinen Weg zu
 * zeigen, also steht statt der Brotkrume der Name der Installation und das
 * Datum. Das ist kein zweites Bauteil, sondern dieselbe Zeile mit einer
 * leeren Mitte - sonst wäre bei der nächsten Änderung eine der beiden
 * zurückgeblieben.
 */
export function Kopfleiste({ navigierbar, navOffen, beiNavigation }: Props) {
  const weg = useWeg();

  return (
    <header className={stil.leiste}>
      {navigierbar ? (
        <button
          type="button"
          className={stil.zeichenknopf}
          aria-label="Navigation öffnen"
          aria-expanded={navOffen}
          onClick={beiNavigation}
        >
          <Marke aktiv={navOffen} />
        </button>
      ) : (
        <Link to="/" className={stil.zeichenknopf} aria-label="Zur Übersicht">
          <Marke />
        </Link>
      )}

      {weg.length === 0 ? (
        <span className={stil.wortmarke}>HomePI</span>
      ) : (
        <nav className={stil.weg} aria-label="Pfad">
          {weg.map((glied, i) => (
            <span key={glied} className={stil.glied}>
              {i > 0 && (
                <span className={stil.trenner} aria-hidden="true">
                  /
                </span>
              )}
              {/* Nur das letzte Glied ist die Seite, auf der man steht. Die
                  davor sind Herkunft, nicht Ziel - sie als Verweise
                  anzubieten hieße, einen Zwischenzustand zu versprechen,
                  den es nicht gibt: Ein Artefakt ohne Bereich leitet weiter
                  auf seinen ersten. */}
              <span className={i === weg.length - 1 ? stil.hier : stil.vorher}>
                {glied}
              </span>
            </span>
          ))}
        </nav>
      )}

      <Bereichsleiste />

      <div className={stil.rechts}>
        {weg.length === 0 && <span className={stil.datum}>{heute()}</span>}
        <Benutzerleiste />
      </div>
    </header>
  );
}

/**
 * Der Pfad als Wörter. Leer heißt Startseite.
 *
 * useMatch und nicht useParams: Die Leiste steht in der Hülle und damit
 * AUSSERHALB von <Routes>. Dort liefert useParams immer ein leeres Objekt.
 */
function useWeg(): string[] {
  const zustand = useModule();
  const modulTreffer = useMatch("/modul/:id/*");
  const einstellungen = useMatch("/einstellungen");
  const anmelden = useMatch("/anmelden");

  if (einstellungen) return ["HomePI", "Einstellungen"];
  if (anmelden) return ["HomePI", "Anmelden"];
  if (!modulTreffer) return [];

  const id = modulTreffer.params.id ?? "";
  const modul =
    zustand.phase === "fertig" ? zustand.module.find((m) => m.id === id) : undefined;

  // Nur das Artefakt. Der Bereich steht nicht hier, sondern als markierter
  // Eintrag in der Bereichsleiste daneben -- zweimal dasselbe Wort in einer
  // Zeile ist eines zu viel.
  //
  // Solange das Manifest unterwegs ist, steht die Kennung da und nicht ein
  // Platzhalter, der eine Zeile später durch etwas anderes ersetzt wird.
  return [modul?.titel ?? id];
}

/** „Dienstag, 12. November" - ohne Jahr, weil es niemanden interessiert,
 *  der gerade auf seinen eigenen Pi schaut. */
function heute(): string {
  return new Date().toLocaleDateString("de-DE", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}
