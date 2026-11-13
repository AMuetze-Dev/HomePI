import { createContext, useContext, type ReactNode } from "react";

import { Regel } from "./Regel";
import stil from "./Tabelle.module.css";

/** Das Spaltenraster reicht die Tabelle an ihre Reihen durch. Es jedem
 *  Aufruf mitzugeben wäre dieselbe Zeichenkette zehnmal — und beim elften
 *  Mal eine andere. */
const Raster = createContext<string>("1fr");

interface TabelleProps {
  /** Benennt die Liste für Screenreader. */
  beschriftung: string;
  /** `grid-template-columns`, etwa "1.6fr 1fr 1fr .9fr .7fr". */
  raster: string;
  /** Die Spaltenköpfe. Leer lassen, wo die Werte für sich sprechen. */
  spalten?: readonly string[];
  /**
   * Die letzte Spalte steht rechts — wie ihre `<Zelle rechts>`.
   *
   * Ausdrücklich und nicht geraten: Eine Tabelle, deren letzte Spalte links
   * ausgerichtet ist, bekam sonst einen Kopf, der rechts stand. Das sieht
   * nach einer verrutschten Zeile aus, und man sucht den Fehler in den Daten.
   */
  rechtsBuendig?: boolean;
  children: ReactNode;
}

/**
 * Eine dichte Liste in Spalten — ohne Kasten, ohne Zebrastreifen.
 *
 * Das ist die Form, in der diese Oberfläche Mengen zeigt: Spaltenköpfe in
 * gesperrten Kapitälchen, darunter Reihen, die eine ausblendende Linie
 * trennt. Kein Rahmen: Zwanzig Zeilen in zwanzig Kästen sind zwanzigmal
 * dieselbe Kante, und die liest man mit.
 *
 * **Liste und nicht `<table>`.** Eine Reihe hier ist oft aufklappbar, und
 * ein Tabellenfeld, in dem ein ganzer Bericht aufgeht, ist für einen
 * Screenreader eine Zelle, die plötzlich eine Seite enthält. Als Liste mit
 * `aria-expanded` am Kopf ist dieselbe Bedienung erklärbar. Der Preis: Die
 * Spaltennamen werden nicht zu jedem Wert mit angesagt — deshalb muss jede
 * Zelle für sich sprechen („2 offen", nicht „2").
 *
 * Unter 48 rem löst sich das Raster auf: Die erste Zelle wird zur
 * Überschrift der Reihe, die übrigen zu einer Zeile dahinter. Eine Tabelle,
 * die auf einem Telefon waagerecht scrollt, versteckt ausgerechnet die
 * rechte Spalte — also meist den Zustand, wegen dessen man hinsieht.
 */
export function Tabelle({
  beschriftung,
  raster,
  spalten,
  rechtsBuendig = false,
  children,
}: TabelleProps) {
  return (
    <Raster.Provider value={raster}>
      <div className={stil.tabelle}>
        {spalten && spalten.length > 0 && (
          /* aria-hidden: Die Namen stehen hier als Orientierung fuer das
             Auge. Angesagt werden sie nicht, weil die Liste darunter keine
             Tabelle ist - und ein Satz Spaltennamen ohne Tabelle dahinter
             ist fuer einen Screenreader nur eine Zeile aus Woertern. */
          <div
            className={rechtsBuendig ? stil.kopfzeileRechts : stil.kopfzeile}
            style={{ gridTemplateColumns: raster }}
            aria-hidden="true"
          >
            {spalten.map((wort) => (
              <span key={wort}>{wort}</span>
            ))}
          </div>
        )}

        <Regel />

        <ul className={stil.reihen} aria-label={beschriftung}>
          {children}
        </ul>
      </div>
    </Raster.Provider>
  );
}

interface ReiheProps {
  /** Hebt die Reihe hervor: ein Hauch Akzent von links. Für das, was dran ist. */
  betont?: boolean;
  /** Nimmt die Reihe zurück: erledigt, abgelaufen, nicht mehr dran. */
  leise?: boolean;
  /** Macht die Reihe anklickbar. Ohne das ist sie nur Anzeige. */
  onKlick?: () => void;
  /** Nur mit `onKlick`: Sagt an, ob die Ausklappung offen ist. */
  offen?: boolean;
  /** Was unter der Reihe aufgeht, wenn sie offen ist. */
  ausklappung?: ReactNode;
  children: ReactNode;
}

/**
 * Eine Reihe — anklickbar, hervorgehoben oder zurückgenommen.
 *
 * Die Linie steht **unter** jeder Reihe und nicht zwischen ihnen: So trägt
 * auch die letzte eine, und die Liste endet mit einer Kante statt im Nichts.
 */
export function Reihe({
  betont = false,
  leise = false,
  onKlick,
  offen,
  ausklappung,
  children,
}: ReiheProps) {
  const klassen = [
    stil.reihe,
    betont ? stil.betont : undefined,
    leise ? stil.leise : undefined,
  ]
    .filter(Boolean)
    .join(" ");
  const raster = useContext(Raster);

  return (
    <li className={stil.eintrag}>
      {onKlick ? (
        <button
          type="button"
          className={klassen}
          style={{ gridTemplateColumns: raster }}
          onClick={onKlick}
          aria-expanded={ausklappung === undefined ? undefined : !!offen}
        >
          {children}
        </button>
      ) : (
        <div className={klassen} style={{ gridTemplateColumns: raster }}>
          {children}
        </div>
      )}

      {offen && ausklappung}
      <Regel />
    </li>
  );
}

/**
 * Eine Zelle. `rechts` für die letzte Spalte, `leise` für alles, was nur
 * danebensteht — Staffel, Datum, Kennung.
 */
export function Zelle({
  rechts = false,
  leise = false,
  children,
}: {
  rechts?: boolean;
  leise?: boolean;
  children: ReactNode;
}) {
  return (
    <span
      className={[
        stil.zelle,
        rechts ? stil.rechts : undefined,
        leise ? stil.zelleLeise : undefined,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </span>
  );
}
