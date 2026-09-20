import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

import { Benutzerleiste } from "./Benutzerleiste";
import stil from "./Huelle.module.css";
import { Navigation } from "./Navigation";
import { Themenwechsel } from "./Themenwechsel";

interface Props {
  children: ReactNode;
  /** Ohne Navigation und Benutzerleiste. Fuer die Ersteinrichtung: dort gibt
   *  es noch kein Konto und kein Artefakt, und beides daneben waere eine
   *  Einladung ins Leere. */
  schlicht?: boolean;
}

/**
 * Rahmen für alle Ansichten: Navigationsleiste, Kopfzeile, Inhalt.
 *
 * Die Hülle kennt keine Fachlichkeit - und seit dieser Fassung auch nicht
 * mehr die Breite des Inhalts. Die meldet das Modul selbst an
 * (src/module/typen.ts); die Hülle stellt nur den Platz bereit.
 *
 * Die Leiste läuft über die volle Höhe und trägt die Marke oben. Die
 * Alternative wäre eine durchgehende Kopfzeile über der Leiste gewesen; sie
 * kostet 3,5 rem Höhe über die ganze Breite, ohne mehr zu zeigen.
 *
 * Auf schmalen Geräten wird aus der Leiste eine Schublade. Nicht als
 * Notlösung: Auf einem Telefon ist eine dauerhaft sichtbare Navigation
 * schlicht der halbe Bildschirm.
 */
export function Huelle({ children, schlicht = false }: Props) {
  const [schubladeOffen, setSchubladeOffen] = useState(false);
  const { pathname } = useLocation();

  // Nach jedem Wechsel zu. Ohne das bleibt die Schublade auf einem Telefon
  // über dem Ziel stehen, das man gerade angetippt hat.
  useEffect(() => setSchubladeOffen(false), [pathname]);

  // Escape schließt. Wer eine Schublade öffnen kann, muss sie auch ohne
  // Zielsuche wieder loswerden.
  useEffect(() => {
    if (!schubladeOffen) return undefined;
    const beiTaste = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSchubladeOffen(false);
    };
    document.addEventListener("keydown", beiTaste);
    return () => document.removeEventListener("keydown", beiTaste);
  }, [schubladeOffen]);

  return (
    <div className={schlicht ? stil.huelleSchlicht : stil.huelle}>
      <a className={stil.sprung} href="#inhalt">
        Zum Inhalt springen
      </a>

      {!schlicht && (
        <>
          <aside
            id="navigation"
            className={schubladeOffen ? stil.leisteOffen : stil.leiste}
          >
            <div className={stil.leistenkopf}>
              <Marke />
            </div>
            <Navigation beiAuswahl={() => setSchubladeOffen(false)} />

            {/* Steht am Fuß der Leiste statt unter jedem Inhalt. Unter dem
                Inhalt hätte die Zeile bei einer langen Tabelle niemand je
                gesehen - und bei einer kurzen hing sie in der Luft. */}
            <p className={stil.leistenfuss}>
              Selbst gehostet auf einem Raspberry&nbsp;Pi. Alle Daten bleiben im eigenen
              Netz.
            </p>
          </aside>

          {schubladeOffen && (
            <button
              type="button"
              className={stil.schleier}
              aria-label="Navigation schließen"
              onClick={() => setSchubladeOffen(false)}
            />
          )}
        </>
      )}

      <div className={stil.spalte}>
        <header className={stil.kopf}>
          {schlicht ? (
            <Marke />
          ) : (
            <button
              type="button"
              className={stil.schubladenknopf}
              aria-label="Navigation öffnen"
              aria-expanded={schubladeOffen}
              aria-controls="navigation"
              onClick={() => setSchubladeOffen(true)}
            >
              <svg
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <path d="M2.5 4h11M2.5 8h11M2.5 12h11" />
              </svg>
            </button>
          )}

          <div className={stil.werkzeuge}>
            {!schlicht && <Benutzerleiste />}
            <Themenwechsel />
          </div>
        </header>

        <main id="inhalt" className={stil.inhalt}>
          {children}
        </main>
      </div>
    </div>
  );
}

function Marke() {
  return (
    <Link to="/" className={stil.marke}>
      <span className={stil.markenzeichen} aria-hidden="true">
        H
      </span>
      HomePI
    </Link>
  );
}
