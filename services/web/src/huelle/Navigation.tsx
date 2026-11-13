import { useEffect, useRef } from "react";
import { NavLink, useMatch, useNavigate } from "react-router-dom";

import type { ModulEintrag } from "../api/client";
import { useAnmeldung } from "../anmeldung/kontext";
import { sichtbareUnterseiten } from "../module/register";
import { useModule } from "../module/useModule";
import { Marke, Monogramm, Platzhalter, Regel } from "../ui";
import stil from "./Navigation.module.css";

interface Props {
  beiSchliessen: () => void;
}

/**
 * Die Navigation als Fläche über der Seite - beide Ebenen nebeneinander.
 *
 * Vorher standen Artefakte und ihre Bereiche eingerückt untereinander in
 * einer Leiste am Rand. Das funktionierte, solange ein Artefakt drei
 * Bereiche hatte; bei neun wurde aus der Leiste eine Liste, in der man
 * sucht statt findet - und sie stand dabei dauerhaft im Bild.
 *
 * Hier liegen links die Artefakte und rechts die Bereiche des geöffneten.
 * Beide Ebenen sind gleichzeitig zu sehen, und zwar in Wortgrößen, die man
 * aus zwei Metern liest. Der Preis ist, dass die Fläche gerufen werden
 * muss - mit Escape oder dem Zeichen oben links.
 *
 * Die Seite darunter bleibt schemenhaft sichtbar. Nicht als Effekt: Sie ist
 * die Antwort auf „wohin komme ich zurück, wenn ich das hier wegklicke".
 */
export function Navigation({ beiSchliessen }: Props) {
  const zustand = useModule();
  const { benutzer, abmelden } = useAnmeldung();
  const navigate = useNavigate();
  const treffer = useMatch("/modul/:id/*");
  const offenesModul = treffer?.params.id ?? "";

  const flaeche = useRef<HTMLDivElement>(null);
  const vorherFokussiert = useRef<Element | null>(null);

  // Fokus hinein und am Ende zurück. Ohne das steht der Schreibpunkt
  // weiterhin auf der Seite DAHINTER: Tabulator wandert dann durch Dinge,
  // die gerade niemand sieht.
  useEffect(() => {
    vorherFokussiert.current = document.activeElement;
    flaeche.current?.focus();

    return () => {
      if (vorherFokussiert.current instanceof HTMLElement) {
        vorherFokussiert.current.focus();
      }
    };
  }, []);

  const module = zustand.phase === "fertig" ? zustand.module : [];
  const offen = module.find((m) => m.id === offenesModul);
  const bereiche = offen ? sichtbareUnterseiten(offen.id) : [];

  return (
    <div className={stil.schleier}>
      {/* Der Hintergrund schliesst, ist aber kein Ziel fuer die Tastatur -
          dafuer gibt es Escape und den Knopf. Ein fokussierbarer, leerer
          Bereich waere eine Station auf dem Weg, die nichts sagt. */}
      <div
        className={stil.hinterklick}
        aria-hidden="true"
        onClick={beiSchliessen}
        role="presentation"
      />

      <div
        ref={flaeche}
        className={stil.flaeche}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        tabIndex={-1}
        onKeyDown={(e) => {
          if (e.key === "Tab") halteFokus(e, flaeche.current);
        }}
      >
        <div className={stil.kopf}>
          <Marke aktiv />
          <span className={stil.wortmarke}>Navigation</span>
          {/* Der Name steht im aria-label und nicht im Text: Sichtbar steht
              hier auf einer Tastatur „Esc schließt" und auf einem Telefon
              „Schließen" - zwei Beschriftungen für eine Handlung, weil es
              auf einem Telefon keine Escape-Taste gibt. Für einen
              Screenreader wäre beides zusammen ein Satz ohne Sinn. */}
          <button
            type="button"
            className={stil.schliessen}
            aria-label="Navigation schließen"
            onClick={beiSchliessen}
          >
            <span className={stil.mitTaste} aria-hidden="true">
              <span className={stil.taste}>Esc</span>
              schließt
            </span>
            <span className={stil.ohneTaste} aria-hidden="true">
              Schließen
            </span>
          </button>
        </div>

        <div className={stil.spalten}>
          <div className={stil.artefakte}>
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                isActive ? stil.uebersichtHier : stil.uebersicht
              }
            >
              <span className={stil.uebersichtzeichen} aria-hidden="true">
                <Marke />
              </span>
              Übersicht
            </NavLink>

            <Regel className={stil.regel} />

            <p className={stil.gruppe}>Artefakte</p>

            {zustand.phase === "laedt" && (
              <div className={stil.laden} aria-hidden="true">
                <Platzhalter breite="60%" hoehe="2rem" />
                <Platzhalter breite="45%" hoehe="2rem" />
                <Platzhalter breite="55%" hoehe="2rem" />
              </div>
            )}

            {zustand.phase === "fehler" && (
              <p className={stil.leer} role="alert">
                Das Gateway hat das Verzeichnis nicht geliefert: {zustand.nachricht}
              </p>
            )}

            {zustand.phase === "fertig" && module.length === 0 && (
              <p className={stil.leer}>
                Hier steht nur, wofür du berechtigt bist — und das ist im Moment nichts.
              </p>
            )}

            {/* Die Liste bleibt bewusst OHNE aria-label: Die Startseite
                darunter hat bereits eine namens „Artefakte". Zwei
                gleichnamige Listen sagt ein Screenreader zweimal an, und
                jede Suche nach einem Eintrag trifft doppelt. Den Namen
                trägt hier der Dialog darum herum. */}
            {module.length > 0 && (
              <ul className={stil.liste}>
                {module.map((modul) => (
                  <li key={modul.id}>
                    <Artefakt modul={modul} offen={modul.id === offenesModul} />
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className={stil.bereichsspalte}>
            {offen && bereiche.length > 0 && (
              <>
                <p className={stil.gruppe}>Bereiche in {offen.titel}</p>
                <ul className={stil.bereiche} aria-label={`Bereiche von ${offen.titel}`}>
                  {bereiche.map((bereich) => (
                    <li key={bereich.id}>
                      <NavLink
                        to={`/modul/${offen.id}/${bereich.id}`}
                        className={({ isActive }) =>
                          isActive ? stil.bereichHier : stil.bereich
                        }
                      >
                        {bereich.wort}
                      </NavLink>
                    </li>
                  ))}
                </ul>
                <Regel kurz className={stil.regel} />
              </>
            )}

            <div className={stil.konto}>
              <NavLink
                to="/einstellungen"
                className={({ isActive }) => (isActive ? stil.bereichHier : stil.bereich)}
              >
                Einstellungen
              </NavLink>
              {benutzer && (
                <button
                  type="button"
                  className={stil.bereich}
                  onClick={() => {
                    void abmelden().then(() => navigate("/"));
                  }}
                >
                  Abmelden
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Artefakt({ modul, offen }: { modul: ModulEintrag; offen: boolean }) {
  return (
    <NavLink
      to={`/modul/${modul.id}`}
      className={(offen ? stil.artefaktHier : stil.artefakt) ?? ""}
    >
      <Monogramm name={einWort(modul.titel)} form="feld" betont={offen} />
      <span className={stil.titel}>{modul.titel}</span>
      {/* Der Punkt ist Dekoration, das Wort traegt die Bedeutung. Nur farbig
          markiert kaeme die Stoerung weder bei einem Screenreader noch bei
          Farbenblindheit an. */}
      {modul.status === "fehler" && (
        <>
          <span className={stil.stoerung} aria-hidden="true" />
          <span className="nur-vorlesen">Nicht erreichbar</span>
        </>
      )}
    </NavLink>
  );
}

/**
 * Ein Artefakt bekommt EINEN Buchstaben, auch wenn sein Titel zwei Wörter
 * hat: „Nutzerverwaltung" und „Haushaltsbuch" stehen hier nebeneinander,
 * und zwei Buchstaben machten aus dem Feld ein Etikett.
 */
function einWort(titel: string): string {
  return titel.trim().split(/\s+/)[0] ?? titel;
}

/**
 * Tabulator bleibt in der Fläche.
 *
 * Ohne das wandert der Fokus hinter die Fläche und bedient eine Seite, die
 * niemand sieht - für Tastatur- und Screenreader-Benutzer ist das Overlay
 * dann nur eine Farbe, kein Zustand.
 */
function halteFokus(ereignis: React.KeyboardEvent, flaeche: HTMLElement | null) {
  if (!flaeche) return;

  const ziele = flaeche.querySelectorAll<HTMLElement>(
    'a[href], button:not(:disabled), input:not(:disabled), [tabindex]:not([tabindex="-1"])',
  );
  if (ziele.length === 0) return;

  const erstes = ziele[0];
  const letztes = ziele[ziele.length - 1];
  if (!erstes || !letztes) return;

  const aktiv = document.activeElement;

  if (ereignis.shiftKey && (aktiv === erstes || aktiv === flaeche)) {
    ereignis.preventDefault();
    letztes.focus();
  } else if (!ereignis.shiftKey && aktiv === letztes) {
    ereignis.preventDefault();
    erstes.focus();
  }
}
