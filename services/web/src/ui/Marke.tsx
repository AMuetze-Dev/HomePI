import stil from "./Marke.module.css";

interface Props {
  /** Alle vier Felder im Akzent - der Zustand "Navigation ist offen". */
  aktiv?: boolean;
  /** Mit gefasstem Rahmen und größer. Für Startseite und Anmeldung. */
  gross?: boolean;
}

/**
 * Das Markenzeichen: vier Felder, eines davon im Akzent.
 *
 * Es ist dasselbe Zeichen wie das für „Übersicht" in der Navigation - und
 * das ist der Punkt. Die Startseite IST die Übersicht; ein zweites Symbol
 * dafür hätte nur bedeutet, dass man zwei lernen muss.
 *
 * Vier Rechtecke und kein Buchstabe: Das vorherige „H" im Kästchen sah auf
 * jeder Plattform anders aus, weil die Systemschrift entschied, wie fett
 * und wie breit. Eine Zeichnung sieht überall gleich aus und erbt die Farbe
 * der Umgebung.
 */
export function Marke({ aktiv = false, gross = false }: Props) {
  return (
    <span
      className={[gross ? stil.gross : stil.marke, aktiv ? stil.aktiv : undefined]
        .filter(Boolean)
        .join(" ")}
      aria-hidden="true"
    >
      <span className={stil.feld} />
      <span className={stil.feld} />
      <span className={stil.feld} />
      <span className={stil.akzentfeld} />
    </span>
  );
}
