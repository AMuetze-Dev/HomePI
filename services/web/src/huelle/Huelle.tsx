import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Benutzerleiste } from "./Benutzerleiste";
import stil from "./Huelle.module.css";
import { Themenwechsel } from "./Themenwechsel";

interface Props {
  children: ReactNode;
  /** Ohne Benutzerleiste. Fuer die Ersteinrichtung: dort gibt es noch
   *  kein Konto, und ein 'Anmelden' daneben waere eine Einladung ins
   *  Leere. */
  schlicht?: boolean;
}

/**
 * Rahmen für alle Ansichten: Kopfzeile, Inhaltsspalte, Fußzeile.
 *
 * Die Hülle kennt keine Fachlichkeit. Sie legt nur fest, wie breit Inhalt
 * werden darf und wo er sitzt - alles Weitere bringen die Ansichten mit.
 */
export function Huelle({ children, schlicht = false }: Props) {
  return (
    <div className={stil.huelle}>
      <a className={stil.sprung} href="#inhalt">
        Zum Inhalt springen
      </a>

      <header className={stil.kopf}>
        <div className={stil.kopfinhalt}>
          <Link to="/" className={stil.marke}>
            <span className={stil.markenzeichen} aria-hidden="true">
              H
            </span>
            HomePI
          </Link>

          <div className={stil.werkzeuge}>
            {!schlicht && <Benutzerleiste />}
            <Themenwechsel />
          </div>
        </div>
      </header>

      <main id="inhalt" className={stil.inhalt}>
        {children}
      </main>

      <footer className={stil.fuss}>
        <div className={stil.fussinhalt}>
          <span>Selbst gehostet auf einem Raspberry Pi.</span>
          <span>Alle Daten bleiben im eigenen Netz.</span>
        </div>
      </footer>
    </div>
  );
}
